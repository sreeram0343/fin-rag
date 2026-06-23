from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession
from finrag.db.session import get_db_session
from finrag.db.document_repository import DocumentRepository
from finrag.utils.storage import get_storage_client, BaseStorageClient
from finrag.core.security import decode_access_token

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/token")

async def get_document_repository(db: AsyncSession = Depends(get_db_session)) -> DocumentRepository:
    """Dependency yielding a DocumentRepository database wrapper."""
    return DocumentRepository(db)

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
