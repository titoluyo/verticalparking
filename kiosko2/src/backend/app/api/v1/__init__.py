"""API v1 routes."""

from fastapi import APIRouter

from .tickets import router as tickets_router
from .cabins import router as cabins_router
from .presence import router as presence_router
from .test import router as test_router
from .health import router as health_router

api_router = APIRouter()

api_router.include_router(health_router, tags=["health"])
api_router.include_router(tickets_router, prefix="/tickets", tags=["tickets"])
api_router.include_router(cabins_router, prefix="/cabins", tags=["cabins"])
api_router.include_router(presence_router, prefix="/presence", tags=["presence"])
api_router.include_router(test_router, prefix="/test", tags=["test"])
