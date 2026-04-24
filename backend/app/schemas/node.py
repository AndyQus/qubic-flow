from pydantic import BaseModel
from typing import Optional


class NodeCreate(BaseModel):
    url: str
    node_type: str
    label: Optional[str] = None
    priority: int = 1


class NodeOut(BaseModel):
    id: int
    url: str
    node_type: str
    label: Optional[str]
    priority: int
    tick: Optional[int]
    response_time_ms: Optional[int]
    health_status: str
    is_active: int
    fail_count: Optional[int]
    last_checked: Optional[str]
    last_error: Optional[str]
    is_sync_active: bool = False

    class Config:
        from_attributes = True
