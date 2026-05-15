from fastapi import APIRouter
from app.api.v1 import auth, clients, contacts, deals, tasks, analytics, admin

api_router = APIRouter(prefix="/api/v1")

api_router.include_router(auth.router)
api_router.include_router(clients.router)
api_router.include_router(contacts.router)
api_router.include_router(deals.router)
api_router.include_router(tasks.router)
api_router.include_router(analytics.router)
api_router.include_router(admin.router)
