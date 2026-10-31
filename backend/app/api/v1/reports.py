from datetime import date

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.exceptions import BusinessRuleError
from app.core.permissions import require_staff
from app.dependencies import get_db
from app.models import User
from app.schemas.report import DashboardOut
from app.services import report_service

router = APIRouter(prefix="/reports", tags=["reports"])


@router.get("/dashboard", response_model=DashboardOut)
def dashboard(
    period_start: date | None = None,
    period_end: date | None = None,
    as_of: date | None = None,
    db: Session = Depends(get_db),
    _: User = Depends(require_staff),
) -> DashboardOut:
    today = date.today()
    start = period_start or today.replace(day=1)
    end = period_end or today
    if end < start:
        raise BusinessRuleError("period_end must be on or after period_start.", fields={"period_end": "Invalid range"})
    return report_service.dashboard(db, period_start=start, period_end=end, as_of=as_of or today)
