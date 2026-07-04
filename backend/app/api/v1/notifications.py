from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ...database import get_db
from ...services.notification_service import (
    get_notify_settings,
    save_notify_settings,
    send_test_notification,
)

router = APIRouter()


@router.get("/notifications/settings")
def read_settings(db: Session = Depends(get_db)):
    return get_notify_settings(db)


@router.put("/notifications/settings")
def update_settings(payload: dict[str, Any], db: Session = Depends(get_db)):
    return save_notify_settings(db, payload)


@router.post("/notifications/test")
async def test_notification(db: Session = Depends(get_db)):
    ok = await send_test_notification(db)
    return {"ok": ok}
