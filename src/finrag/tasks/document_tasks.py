import asyncio
import os
import structlog
from finrag.tasks.celery_app import celery_app
from finrag.db.session import async_session_factory
from finrag.db.document_repository import DocumentRepository
from finrag.parser.pdf_layout import PDFLayoutParser
from finrag.utils.storage import get_storage_client

logger = structlog.get_logger(__name__)

async def process_document_async(document_id: str) -> None:
    """Async handler to download, parse layout, and update status of a document."""
    logger.info("Starting background processing of document", document_id=document_id)

    async with async_session_factory() as session:
        repo = DocumentRepository(session)
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

            # Parse layout chunks
            parser = PDFLayoutParser()
            parsed_doc = parser.parse(
                file_path=temp_file_path,
                document_id=document_id,
                ticker=ticker,
                period=period,
                year=year
            )

            # Chunks will be stored in PostgreSQL in Milestone 3.
            # For now, layout parsing success is verified, update status to COMPLETED.
            logger.info(
                "Successfully parsed document layout in background task",
                document_id=document_id,
                num_items=len(parsed_doc.items)
            )
            doc.status = "COMPLETED"
            await repo.save(doc)
            await session.commit()

        except Exception as e:
            logger.exception("Failed to process document in background task", document_id=document_id, error=str(e))
            doc.status = "FAILED"
            await repo.save(doc)
            await session.commit()
        finally:
            if temp_file_path and os.path.exists(temp_file_path):
                try:
                    os.remove(temp_file_path)
                except Exception as ex:
                    logger.warning("Failed to remove temporary file", path=temp_file_path, error=str(ex))

@celery_app.task(name="finrag.tasks.process_document")
def process_document_task(document_id: str) -> None:
    """Celery task entry point to process document in event loop."""
    asyncio.run(process_document_async(document_id))
