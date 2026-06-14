"""V1 API router aggregation."""

from fastapi import APIRouter

from app.api.v1.admin import router as admin_router
from app.api.v1.agent import router as agent_router
from app.api.v1.auth import router as auth_router
from app.api.v1.chat import router as chat_router
from app.api.v1.dashboard import router as dashboard_router
from app.api.v1.documents import router as documents_router
from app.api.v1.eval import router as eval_router
from app.api.v1.extraction import router as extraction_router
from app.api.v1.parsing import router as parsing_router
from app.api.v1.qa import router as qa_router
from app.api.v1.reports import router as reports_router
from app.api.v1.risks import router as risks_router
from app.api.v1.search import router as search_router

v1_router = APIRouter(prefix="/api/v1")

v1_router.include_router(auth_router)
v1_router.include_router(admin_router)
v1_router.include_router(chat_router)
v1_router.include_router(dashboard_router)
v1_router.include_router(documents_router)
v1_router.include_router(eval_router)
v1_router.include_router(extraction_router)
v1_router.include_router(parsing_router)
v1_router.include_router(qa_router)
v1_router.include_router(reports_router)
v1_router.include_router(risks_router)
v1_router.include_router(search_router)
v1_router.include_router(agent_router)
