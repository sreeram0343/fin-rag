from fastapi import APIRouter, Form, HTTPException, status
from finrag.core.security import create_access_token
import datetime

router = APIRouter(prefix="/auth", tags=["Authentication"])

@router.post("/token")
async def login_for_access_token(
    grant_type: str = Form(...),
    client_id: str = Form(...),
    client_secret: str = Form(...)
) -> dict:
    """Authenticate client credentials and issue JWT bearer token."""
    if grant_type not in ["password", "client_credentials"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Unsupported grant type. Must be 'password' or 'client_credentials'."
        )

    # In development, accept any non-empty credentials
    if not client_id or not client_secret:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid client credentials."
        )

    access_token = create_access_token(
        data={"sub": client_id, "scopes": ["read:documents", "write:documents", "read:queries"]}
    )

    return {
        "access_token": access_token,
        "token_type": "bearer",
        "expires_in": 3600,
        "scope": "read:documents write:documents read:queries"
    }
