from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
import io
from ...database import get_db
from ...services.export_service import export_cointracking, export_steuerberater

router = APIRouter()


@router.get("/export/cointracking")
def export_ct(year: int | None = Query(None), db: Session = Depends(get_db)):
    csv_data = export_cointracking(db, year)
    filename = f"cointracking_private_{year or 'all'}.csv"
    return StreamingResponse(
        io.BytesIO(csv_data.encode("utf-8-sig")),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@router.get("/export/steuerberater")
def export_sb(year: int | None = Query(None), db: Session = Depends(get_db)):
    csv_data = export_steuerberater(db, year)
    filename = f"steuerberater_business_{year or 'all'}.csv"
    return StreamingResponse(
        io.BytesIO(csv_data.encode("utf-8-sig")),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )
