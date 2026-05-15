from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings
from app.core.database import Base, engine
from app.api.v1 import api_router

# Create all tables on startup
import app.models  # noqa: F401 – registers all models with Base
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="CRM for Sales Department — clients, deals, contacts, tasks, pipeline",
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router)


@app.get("/", tags=["Root"])
def root():
    return {"app": settings.APP_NAME, "version": settings.APP_VERSION, "docs": "/docs"}


@app.get("/health", tags=["Root"])
def health():
    return {"status": "ok"}
