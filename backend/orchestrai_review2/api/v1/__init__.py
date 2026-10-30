from fastapi import APIRouter

from .auth_routes import router as auth_router
from .routes import router as retrieval_router

router = APIRouter()
router.include_router(auth_router)
router.include_router(retrieval_router)

__all__ = ["router"]
