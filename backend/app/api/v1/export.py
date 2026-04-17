from fastapi import APIRouter

router = APIRouter()


@router.post("/export")
def trigger_export():
    return {"job_id": "not_implemented"}
