import asyncio
import os

import structlog

from finrag.chunker.financial import FinancialChunker
from finrag.core.config import settings
from finrag.db.chunk_repository import ChunkRepository
from finrag.db.document_repository import DocumentRepository
from finrag.db.session import async_session_factory
from finrag.db.vector.client import BaseVectorClient, MockVectorClient
from finrag.indexer.embeddings import get_embedding_provider
from finrag.indexer.loader import VectorLoader
from finrag.parser.pdf_layout import PDFLayoutParser
from finrag.tasks.celery_app import celery_app
from finrag.utils.storage import get_storage_client

logger = structlog.get_logger(__name__)


def _get_vector_client() -> BaseVectorClient:
    """Get the configured vector database client with graceful fallback."""
    try:
        from finrag.db.vector.client import QdrantVectorClient

        client = QdrantVectorClient()
        client.ensure_collection()
        return client
    except Exception as e:
        logger.warning(
            "Could not connect to Qdrant. Falling back to MockVectorClient.",
            error=str(e),
        )
        return MockVectorClient(vector_dimension=settings.EMBEDDING_DIMENSION)


async def process_document_async(document_id: str) -> None:
    """Async handler to download, parse layout, chunk, embed, index, and update status of a document."""
    logger.info("Starting background processing of document", document_id=document_id)

    async with async_session_factory() as session:
        repo = DocumentRepository(session)
        chunk_repo = ChunkRepository(session)
        doc = await repo.get_by_id(document_id)
        if not doc:
            logger.error("Document not found in database", document_id=document_id)
            return

        # Update status to PROCESSING
        doc.status = "PROCESSING"
        await repo.save(doc)
        await session.commit()

        storage_uri = doc.storage_uri
        ticker = doc.ticker
        period = doc.period
        year = doc.year

        # Download the file bytes from storage
        storage_client = get_storage_client()
        temp_file_path = None
        try:
            file_bytes = await storage_client.download_file(storage_uri)

            # Save to a temporary file locally so layout parser can open it
            temp_dir = os.path.join(os.getcwd(), "temp")
            os.makedirs(temp_dir, exist_ok=True)
            temp_file_path = os.path.join(temp_dir, f"{document_id}.pdf")
            with open(temp_file_path, "wb") as f:
                f.write(file_bytes)

            # ---- Stage 1: Parse layout chunks ----
            parser = PDFLayoutParser()
            parsed_doc = parser.parse(
                file_path=temp_file_path,
                document_id=document_id,
                ticker=ticker,
                period=period,
                year=year,
            )

            logger.info(
                "PDF parsing completed, starting chunking",
                document_id=document_id,
                num_items=len(parsed_doc.items),
            )

            # ---- Stage 2: Semantic chunking ----
            doc.status = "CHUNKING"
            await repo.save(doc)
            await session.commit()

            chunker = FinancialChunker(
                max_chunk_tokens=settings.CHUNK_MAX_TOKENS,
                overlap_tokens=settings.CHUNK_OVERLAP_TOKENS,
            )
            chunks = chunker.chunk(parsed_doc)

            logger.info(
                "Chunking completed, starting indexing",
                document_id=document_id,
                num_chunks=len(chunks),
            )

            # ---- Stage 3: Embedding generation & vector indexing ----
            doc.status = "INDEXING"
            await repo.save(doc)
            await session.commit()

            embedding_provider = get_embedding_provider(use_mock=True)  # Use mock by default for now
            vector_client = _get_vector_client()
            loader = VectorLoader(
                embedding_provider=embedding_provider,
                vector_client=vector_client,
                chunk_repo=chunk_repo,
                batch_size=settings.EMBEDDING_BATCH_SIZE,
            )
            indexed_count = await loader.load_chunks(chunks)

            logger.info(
                "Successfully processed document through full pipeline",
                document_id=document_id,
                parsed_items=len(parsed_doc.items),
                chunks_created=len(chunks),
                vectors_indexed=indexed_count,
            )

            doc.status = "COMPLETED"
            await repo.save(doc)
            await session.commit()

        except Exception as e:
            logger.exception(
                "Failed to process document in background task",
                document_id=document_id,
                error=str(e),
            )
            doc.status = "FAILED"
            await repo.save(doc)
            await session.commit()
        finally:
            if temp_file_path and os.path.exists(temp_file_path):
                try:
                    os.remove(temp_file_path)
                except Exception as ex:
                    logger.warning(
                        "Failed to remove temporary file",
                        path=temp_file_path,
                        error=str(ex),
                    )


@celery_app.task(name="finrag.tasks.process_document")
def process_document_task(document_id: str) -> None:
    """Celery task entry point to process document in event loop."""
    asyncio.run(process_document_async(document_id))
