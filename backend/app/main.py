from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .config import settings
from .database import engine, Base
from .api.v1 import wallets, events, nodes, stats, export, health, ws, labels
from .services.scheduler import scheduler
import os
from pathlib import Path


def _init_db():
    from alembic.config import Config
    from alembic import command
    from sqlalchemy import inspect
    import logging

    try:
        alembic_cfg = Config(str(Path(__file__).parent.parent / "alembic.ini"))
        alembic_cfg.set_main_option("sqlalchemy.url", settings.database_url)

        # Ensure data directory exists
        url = settings.database_url
        if "sqlite" in url:
            db_path = url.split("sqlite:///")[-1].lstrip("/")
            Path(db_path).parent.mkdir(parents=True, exist_ok=True)

        is_fresh = inspect(engine).get_table_names() == []

        if is_fresh:
            Base.metadata.create_all(bind=engine)
            command.stamp(alembic_cfg, "head")
        else:
            command.upgrade(alembic_cfg, "head")

    except Exception as e:
        logging.warning(f"DB init via alembic failed ({e}), falling back to create_all")
        Base.metadata.create_all(bind=engine)


_init_db()


@asynccontextmanager
async def lifespan(app: FastAPI):
    scheduler.start()
    yield
    scheduler.shutdown()


app = FastAPI(title="QubicFlow API", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router, prefix="/api/v1", tags=["health"])
app.include_router(wallets.router, prefix="/api/v1", tags=["wallets"])
app.include_router(events.router, prefix="/api/v1", tags=["events"])
app.include_router(nodes.router, prefix="/api/v1", tags=["nodes"])
app.include_router(stats.router, prefix="/api/v1", tags=["stats"])
app.include_router(export.router, prefix="/api/v1", tags=["export"])
app.include_router(ws.router, prefix="/api/v1", tags=["ws"])
app.include_router(labels.router, prefix="/api/v1", tags=["labels"])
