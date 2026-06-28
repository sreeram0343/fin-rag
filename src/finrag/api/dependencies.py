from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession

from finrag.core.config import settings
from finrag.core.security import decode_access_token
from finrag.db.session import get_db_session
from finrag.db.document_repository import DocumentRepository
from finrag.db.chunk_repository import ChunkRepository
from finrag.utils.storage import get_storage_client, BaseStorageClient
from finrag.db.vector.client import BaseVectorClient, MockVectorClient
from finrag.indexer.embeddings import BaseEmbeddingProvider, get_embedding_provider
from finrag.retriever.base import BaseRetriever
from finrag.retriever.hybrid import HybridRetriever
from finrag.retriever.reranker import BaseReranker, CrossEncoderReranker
from finrag.agent.base import BaseLLM
from finrag.agent.openai_client import OpenAIProvider
from finrag.agent.anthropic_client import AnthropicProvider
from finrag.agent.orchestrator import AgentOrchestrator

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/token")

async def get_document_repository(db: AsyncSession = Depends(get_db_session)) -> DocumentRepository:
    """Dependency yielding a DocumentRepository database wrapper."""
    return DocumentRepository(db)

async def get_chunk_repository(db: AsyncSession = Depends(get_db_session)) -> ChunkRepository:
    """Dependency yielding a ChunkRepository database wrapper."""
    return ChunkRepository(db)

def get_storage() -> BaseStorageClient:
    """Dependency yielding the active StorageClient instance."""
    return get_storage_client()

def verify_token(token: str = Depends(oauth2_scheme)) -> dict:
    """Dependency verifying JWT token authentication."""
    payload = decode_access_token(token)
    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return payload

def get_vector_client() -> BaseVectorClient:
    """Dependency yielding the configured vector client."""
    try:
        from finrag.db.vector.client import QdrantVectorClient
        client = QdrantVectorClient()
        client.ensure_collection()
        return client
    except Exception:
        return MockVectorClient(vector_dimension=settings.EMBEDDING_DIMENSION)

def get_embedding_provider_dep() -> BaseEmbeddingProvider:
    """Dependency yielding the active embedding provider. Uses mock in development/tests."""
    # Use mock by default for now unless specified
    return get_embedding_provider(use_mock=True)

def get_reranker() -> BaseReranker:
    """Dependency yielding the active reranker."""
    return CrossEncoderReranker()

def get_llm_provider() -> BaseLLM:
    """Dependency yielding the active LLM provider based on settings environment."""
    if settings.ENV == "production":
        return AnthropicProvider(api_key=settings.ANTHROPIC_API_KEY)
    return OpenAIProvider(api_key=settings.OPENAI_API_KEY)

def get_retriever(
    vector_client: BaseVectorClient = Depends(get_vector_client),
    embedder: BaseEmbeddingProvider = Depends(get_embedding_provider_dep),
    doc_repo: DocumentRepository = Depends(get_document_repository),
    chunk_repo: ChunkRepository = Depends(get_chunk_repository),
    reranker: BaseReranker = Depends(get_reranker),
) -> BaseRetriever:
    """Dependency yielding the active HybridRetriever."""
    return HybridRetriever(
        vector_client=vector_client,
        embedding_provider=embedder,
        doc_repo=doc_repo,
        chunk_repo=chunk_repo,
        reranker=reranker,
    )

def get_orchestrator(
    llm: BaseLLM = Depends(get_llm_provider),
    retriever: BaseRetriever = Depends(get_retriever),
) -> AgentOrchestrator:
    """Dependency yielding the active AgentOrchestrator."""
    return AgentOrchestrator(llm=llm, retriever=retriever)

