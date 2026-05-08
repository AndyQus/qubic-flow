from pydantic import BaseModel, field_validator, Field
from typing import Optional, Literal
from urllib.parse import urlparse


class NodeCreate(BaseModel):
    url: str
    node_type: Literal["RPC", "BOB_NODE"]
    label: Optional[str] = None
    priority: int = 1
    notes: Optional[str] = Field(None, max_length=2000)

    @field_validator("url")
    @classmethod
    def validate_url(cls, v: str) -> str:
        parsed = urlparse(v)
        if parsed.scheme not in ("http", "https"):
            raise ValueError("URL must use http or https")
        hostname = (parsed.hostname or "").lower()
        _blocked = ("localhost", "127.0.0.1", "0.0.0.0", "::1", "[::]")
        if hostname in _blocked:
            raise ValueError("localhost URLs are not allowed")
        # Block private/cloud-metadata IP ranges
        _private_prefixes = ("10.", "192.168.", "169.254.", "172.")
        if any(hostname.startswith(p) for p in _private_prefixes):
            raise ValueError("Private or link-local IP ranges are not allowed")
        return v


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
    notes: Optional[str]
    is_sync_active: bool = False

    class Config:
        from_attributes = True
