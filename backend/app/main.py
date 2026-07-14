from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .config import settings
from .database import engine, Base
from .api.v1 import wallets, events, nodes, stats, export, health, ws, labels, tax, backup, notifications, balance_history
from .services.scheduler import scheduler
from .utils.log_buffer import install_buffer_handler
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


def _seed_defaults():
    from .database import SessionLocal
    from .models.node import Node
    db = SessionLocal()
    try:
        changed = False
        if not db.query(Node).filter(Node.url == "https://bobnet.qubic.li").first():
            db.add(Node(
                url="https://bobnet.qubic.li",
                node_type="BOB_NODE",
                label="Qubic BOB",
                priority=10,
                is_active=1,
                health_status="ONLINE",
                notes="live sync",
            ))
            changed = True
        if not db.query(Node).filter(Node.url == "https://rpc.qubic.org").first():
            db.add(Node(
                url="https://rpc.qubic.org",
                node_type="RPC",
                label="Qubic RPC",
                priority=99,
                is_active=1,
                health_status="ONLINE",
                notes="history / fallback",
            ))
            changed = True
        if changed:
            db.commit()
    finally:
        db.close()


_seed_defaults()


@asynccontextmanager
async def lifespan(app: FastAPI):
    install_buffer_handler()
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
app.include_router(tax.router, prefix="/api/v1", tags=["tax"])
app.include_router(backup.router, prefix="/api/v1", tags=["backup"])
app.include_router(notifications.router, prefix="/api/v1", tags=["notifications"])
app.include_router(balance_history.router, prefix="/api/v1", tags=["balance-history"])
