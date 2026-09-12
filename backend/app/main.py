"""Точка входа FastAPI: роутеры, CORS, healthcheck."""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.core.scheduler import start_scheduler, stop_scheduler
from app.routers import audit, auth, dashboard, guards, mobile, objects, patrols, reports, routes, schedules, shifts

settings = get_settings()

app = FastAPI(
    title="Patrol API",
    version="0.1.0",
    docs_url="/api/docs",
    openapi_url="/api/openapi.json",
)


@app.on_event("startup")
def _start() -> None:
    start_scheduler(app)


@app.on_event("shutdown")
def _stop() -> None:
    stop_scheduler()

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

PREFIX = settings.api_prefix

app.include_router(auth.router, prefix=PREFIX, tags=["auth"])
app.include_router(objects.router, prefix=PREFIX, tags=["objects"])
app.include_router(routes.router, prefix=PREFIX, tags=["routes"])
app.include_router(schedules.router, prefix=PREFIX, tags=["schedules"])
app.include_router(shifts.router, prefix=PREFIX, tags=["shifts"])
app.include_router(guards.router, prefix=PREFIX, tags=["guards"])
app.include_router(patrols.router, prefix=PREFIX, tags=["patrols"])
app.include_router(dashboard.router, prefix=PREFIX, tags=["dashboard"])
app.include_router(reports.router, prefix=PREFIX, tags=["reports"])
app.include_router(audit.router, prefix=PREFIX, tags=["audit"])
app.include_router(mobile.router, prefix=PREFIX, tags=["mobile"])


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok"}
