import pytest
import pytest_asyncio
import csv
import io
from datetime import datetime, timezone, timedelta
from unittest.mock import patch, MagicMock
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import RoleEnum
from app.models.complaint import Complaint, ComplaintStatus, PriorityEnum
from app.models.analytics_snapshot import AnalyticsSnapshot
from app.api.routes.analytics import _in_memory_cache

@pytest_asyncio.fixture(autouse=True)
async def clean_db_reports(db_session: AsyncSession):
    # Clear tables before each test
    await db_session.execute(Complaint.__table__.delete())
    await db_session.commit()

@pytest.mark.asyncio
async def test_pdf_report_generation_success(async_client: AsyncClient, db_session: AsyncSession, create_test_user):
    # Create test complaints
    officer = await create_test_user(
        email="officer_pdf@example.com",
        role=RoleEnum.OFFICER,
        name="Officer Rajesh"
    )
    
    c1 = Complaint(
        ticket_id="DL-2026-PDF1",
        citizen_name="Aman",
        title="Water leak",
        category="WATER",
        department="DJB",
        district="South Delhi",
        priority=PriorityEnum.HIGH,
        status=ComplaintStatus.RESOLVED,
        assigned_to=officer.id,
        created_at=datetime.now(timezone.utc) - timedelta(hours=5),
        updated_at=datetime.now(timezone.utc)
    )
    db_session.add(c1)
    await db_session.commit()

    # Query root-level PDF endpoint
    response = await async_client.get("/reports/pdf?type=monthly")
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"
    
    # Check PDF magic bytes at start of stream
    content = response.read()
    assert content.startswith(b"%PDF")

@pytest.mark.asyncio
async def test_pdf_report_filters_and_empty_state(async_client: AsyncClient, db_session: AsyncSession):
    # Test Empty State PDF generation
    response = await async_client.get("/reports/pdf?type=monthly&month=2026-06")
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"
    content = response.read()
    assert content.startswith(b"%PDF")

    # Test Department scope validation error
    response_dep = await async_client.get("/reports/pdf?type=department")
    assert response_dep.status_code == 400
    
    # Test District scope validation error
    response_dist = await async_client.get("/reports/pdf?type=district")
    assert response_dist.status_code == 400

    # Test invalid month format
    response_month = await async_client.get("/reports/pdf?type=monthly&month=invalid")
    assert response_month.status_code == 400

    # Test invalid week format
    response_week = await async_client.get("/reports/pdf?type=weekly&week=invalid")
    assert response_week.status_code == 400

@pytest.mark.asyncio
async def test_csv_export_streaming_success(async_client: AsyncClient, db_session: AsyncSession, create_test_user):
    # Setup test complaints
    officer = await create_test_user(
        email="officer_csv@example.com",
        role=RoleEnum.OFFICER,
        name="Officer Rajesh"
    )
    c1 = Complaint(
        ticket_id="DL-2026-CSV1",
        citizen_name="Rahul",
        title="Pothole in road",
        category="ROAD",
        department="PWD",
        district="West Delhi",
        priority=PriorityEnum.CRITICAL,
        status=ComplaintStatus.RESOLVED,
        assigned_to=officer.id,
        created_at=datetime.now(timezone.utc) - timedelta(hours=2),
        updated_at=datetime.now(timezone.utc)
    )
    db_session.add(c1)
    await db_session.commit()

    # Query CSV endpoint
    response = await async_client.get("/reports/csv?department=PWD")
    assert response.status_code == 200
    assert response.headers["content-type"] == "text/csv; charset=utf-8"
    
    # Parse CSV content
    content = response.read().decode("utf-8")
    lines = list(csv.reader(io.StringIO(content)))
    
    # Verify Header
    assert lines[0] == ["Ticket", "Category", "Department", "Officer", "Priority", "Status", "Created", "Resolved"]
    
    # Verify Data Row
    assert len(lines) == 2
    assert lines[1][0] == "DL-2026-CSV1"
    assert lines[1][1] == "ROAD"
    assert lines[1][2] == "PWD"
    assert lines[1][3] == "Officer Rajesh"
    assert lines[1][4] == "CRITICAL"
    assert lines[1][5] == "RESOLVED"

@pytest.mark.asyncio
async def test_csv_export_date_filters_and_invalid_formats(async_client: AsyncClient):
    # Test invalid date formats
    response = await async_client.get("/reports/csv?start_date=invalid")
    assert response.status_code == 400
    
    response = await async_client.get("/reports/csv?end_date=invalid")
    assert response.status_code == 400

@pytest.mark.asyncio
async def test_csv_export_large_dataset_mock(async_client: AsyncClient, db_session: AsyncSession):
    # To test large dataset chunking resilience (O(1) memory),
    # we mock CSVExportService.stream_complaints_csv to stream 5000 dummy rows
    async def mock_generator(*args, **kwargs):
        yield "Ticket,Category,Department,Officer,Priority,Status,Created,Resolved\n"
        for i in range(5000):
            yield f"DL-2026-{i:06d},ROAD,PWD,Officer {i},MEDIUM,SUBMITTED,2026-06-20T22:00:00,\n"

    with patch("app.services.reports.csv_generator.CSVExportService.stream_complaints_csv", side_effect=mock_generator):
        response = await async_client.get("/reports/csv")
        assert response.status_code == 200
        
        # Read stream line by line
        lines = []
        async for line in response.aiter_lines():
            lines.append(line)
            
        assert len(lines) == 5001
        assert lines[0] == "Ticket,Category,Department,Officer,Priority,Status,Created,Resolved"
        assert lines[1].startswith("DL-2026-000000")
        assert lines[5000].startswith("DL-2026-004999")
