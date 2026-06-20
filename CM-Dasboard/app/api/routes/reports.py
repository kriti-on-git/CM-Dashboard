import io
import uuid
import re
from datetime import datetime, timezone, timedelta
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload
from uuid import UUID

from app.db.session import get_db
from app.models.report import Report
from app.models.complaint import Complaint, PriorityEnum
from app.schemas.report import ReportCreate, ReportUpdate, ReportResponse
from app.services.reports.pdf_generator import PDFReportGenerator
from app.services.reports.csv_generator import CSVExportService

router = APIRouter()

@router.get("/pdf")
async def download_pdf_report(
    type: str = "monthly",
    month: Optional[str] = None,
    week: Optional[str] = None,
    department: Optional[str] = None,
    district: Optional[str] = None,
    db: AsyncSession = Depends(get_db)
):
    """
    Generate and stream ReportLab PDF analytics report.
    Supports Monthly, Weekly, Department, and District scopes.
    """
    stmt = select(Complaint).filter(Complaint.is_deleted == False)
    filter_desc = "All active complaints"
    
    # Pre-load assigned officer to avoid N+1 query patterns
    stmt = stmt.options(selectinload(Complaint.assigned_officer))
    
    # 1. Monthly Filter
    if type == "monthly":
        if not month:
            # Default to current month
            now = datetime.now(timezone.utc)
            month = now.strftime("%Y-%m")
        try:
            year_val, month_val = map(int, month.split("-"))
            start_date = datetime(year_val, month_val, 1, tzinfo=timezone.utc)
            # handle month wrapping
            if month_val == 12:
                end_date = datetime(year_val + 1, 1, 1, tzinfo=timezone.utc)
            else:
                end_date = datetime(year_val, month_val + 1, 1, tzinfo=timezone.utc)
            stmt = stmt.filter(Complaint.created_at >= start_date, Complaint.created_at < end_date)
            filter_desc = f"Month: {month}"
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid month format. Expected YYYY-MM.")
            
    # 2. Weekly Filter
    elif type == "weekly":
        if week:
            # Format: YYYY-Www (e.g. 2026-W25)
            try:
                match = re.match(r"^(\d{4})-W(\d{1,2})$", week)
                if not match:
                    raise ValueError()
                year_val, week_val = map(int, match.groups())
                # datetime.fromisocalendar is supported in Python 3.8+
                start_date = datetime.fromisocalendar(year_val, week_val, 1).replace(tzinfo=timezone.utc)
                end_date = datetime.fromisocalendar(year_val, week_val, 7).replace(tzinfo=timezone.utc)
                stmt = stmt.filter(Complaint.created_at >= start_date, Complaint.created_at <= end_date)
                filter_desc = f"ISO Week: {week}"
            except Exception:
                raise HTTPException(status_code=400, detail="Invalid week format. Expected YYYY-Www.")
        else:
            # Default to trailing 7 days
            start_date = datetime.now(timezone.utc) - timedelta(days=7)
            stmt = stmt.filter(Complaint.created_at >= start_date)
            filter_desc = "Weekly: Trailing 7 Days"
            
    # 3. Department Filter
    elif type == "department":
        if not department:
            raise HTTPException(status_code=400, detail="Department parameter is required for department report.")
        stmt = stmt.filter(Complaint.department == department.strip())
        filter_desc = f"Department: {department.strip()}"
        
    # 4. District Filter
    elif type == "district":
        if not district:
            raise HTTPException(status_code=400, detail="District parameter is required for district report.")
        stmt = stmt.filter(Complaint.district == district.strip())
        filter_desc = f"District: {district.strip()}"
        
    else:
        raise HTTPException(status_code=400, detail="Invalid report type. Expected monthly, weekly, department, or district.")

    # Execute aggregation fetch
    result = await db.execute(stmt)
    complaints = result.scalars().all()
    
    # Generate PDF bytes
    pdf_bytes = PDFReportGenerator.generate_report(complaints, type, filter_desc)
    
    # Filename format: report_YYYY_MM.pdf
    now = datetime.now(timezone.utc)
    filename = f"report_{now.strftime('%Y_%m')}.pdf"
    if type == "monthly" and month:
        filename = f"report_{month.replace('-', '_')}.pdf"
        
    return StreamingResponse(
        io.BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename=\"{filename}\""}
    )

@router.get("/csv")
async def download_csv_export(
    department: Optional[str] = None,
    district: Optional[str] = None,
    priority: Optional[PriorityEnum] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    db: AsyncSession = Depends(get_db)
):
    """
    Stream grievance export formatted in CSV.
    Safely yields chunks under O(1) memory for up to 100k complaints.
    """
    start_dt = None
    end_dt = None
    
    if start_date:
        try:
            start_dt = datetime.fromisoformat(start_date)
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid start_date format. Expected ISO-8601.")
            
    if end_date:
        try:
            end_dt = datetime.fromisoformat(end_date)
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid end_date format. Expected ISO-8601.")
            
    now = datetime.now(timezone.utc)
    filename = f"report_export_{now.strftime('%Y%m%d_%H%M%S')}.csv"
    
    generator = CSVExportService.stream_complaints_csv(
        db=db,
        department=department,
        district=district,
        priority=priority,
        start_date=start_dt,
        end_date=end_dt
    )
    
    return StreamingResponse(
        generator,
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=\"{filename}\""}
    )

@router.post("/", response_model=ReportResponse, status_code=status.HTTP_201_CREATED)
async def create_report(report_in: ReportCreate, db: AsyncSession = Depends(get_db)):
    report = Report(**report_in.model_dump())
    db.add(report)
    await db.commit()
    await db.refresh(report)
    return report

@router.get("/{report_id}", response_model=ReportResponse)
async def read_report(report_id: UUID, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Report).filter(Report.id == report_id))
    report = result.scalars().first()
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")
    return report

@router.get("/", response_model=List[ReportResponse])
async def list_reports(skip: int = 0, limit: int = 100, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Report).offset(skip).limit(limit))
    return result.scalars().all()

@router.patch("/{report_id}", response_model=ReportResponse)
async def update_report(report_id: UUID, report_in: ReportUpdate, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Report).filter(Report.id == report_id))
    report = result.scalars().first()
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")
        
    update_data = report_in.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(report, field, value)
        
    await db.commit()
    await db.refresh(report)
    return report

@router.delete("/{report_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_report(report_id: UUID, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Report).filter(Report.id == report_id))
    report = result.scalars().first()
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")
        
    await db.delete(report)
    await db.commit()
