from fastapi import APIRouter

router = APIRouter()


@router.get("/stats/current")
def current_stats():
    return {}


@router.get("/stats/snapshots")
def snapshots():
    return []
