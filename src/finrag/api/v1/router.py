from fastapi import APIRouter
from finrag.api.v1.auth import router as auth_router
from finrag.api.v1.ingest import router as ingest_router
from finrag.api.v1.query import router as query_router
from finrag.api.v1.viewer import router as viewer_router

router = APIRouter()
router.include_router(auth_router)
router.include_router(ingest_router)
router.include_router(query_router)
router.include_router(viewer_router)


