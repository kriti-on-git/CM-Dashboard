import logging
from typing import AsyncGenerator, Optional
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload

from app.models.complaint import Complaint, ComplaintStatus, PriorityEnum

logger = logging.getLogger("cm_dashboard.services.csv_generator")

class CSVExportService:
    @classmethod
    async def stream_complaints_csv(
        cls,
        db: AsyncSession,
        department: Optional[str] = None,
        district: Optional[str] = None,
        priority: Optional[PriorityEnum] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> AsyncGenerator[str, None]:
        """
        Queries and streams CSV-formatted complaints to keep memory usage O(1)
        even for very large datasets (up to 100k complaints).
        """
        logger.info("Starting CSV stream query execution...")
        
        # 1. Build Query
        stmt = select(Complaint).filter(Complaint.is_deleted == False)
        
        if department and department.strip():
            stmt = stmt.filter(Complaint.department == department.strip())
        if district and district.strip():
            stmt = stmt.filter(Complaint.district == district.strip())
        if priority:
            stmt = stmt.filter(Complaint.priority == priority)
        if start_date:
            stmt = stmt.filter(Complaint.created_at >= start_date)
        if end_date:
            stmt = stmt.filter(Complaint.created_at <= end_date)
            
        # Optimize query by pre-loading assigned officer to avoid N+1 queries
        stmt = stmt.options(selectinload(Complaint.assigned_officer))
        
        # Stream the results in batches of 1000
        stmt = stmt.execution_options(yield_per=1000)
        
        # 2. Yield Header Row
        yield "Ticket,Category,Department,Officer,Priority,Status,Created,Resolved\n"
        
        # 3. Stream Data Rows
        try:
            result = await db.stream(stmt)
            async for complaint in result.scalars():
                ticket = complaint.ticket_id
                category = complaint.category or ""
                dept = complaint.department or ""
                officer = complaint.assigned_officer.name if complaint.assigned_officer else "Unassigned"
                prio = complaint.priority.value if complaint.priority else ""
                status = complaint.status.value if complaint.status else ""
                created = complaint.created_at.isoformat() if complaint.created_at else ""
                
                # Check resolved timestamp
                resolved = ""
                if complaint.status == ComplaintStatus.RESOLVED and complaint.updated_at:
                    resolved = complaint.updated_at.isoformat()
                
                # Escape fields according to CSV standard RFC 4180
                row = [ticket, category, dept, officer, prio, status, created, resolved]
                escaped_row = []
                for field in row:
                    field_str = str(field)
                    if ',' in field_str or '"' in field_str or '\n' in field_str or '\r' in field_str:
                        # Double quotes are escaped by doubling them
                        field_str = '"' + field_str.replace('"', '""') + '"'
                    escaped_row.append(field_str)
                    
                yield ",".join(escaped_row) + "\n"
                
            logger.info("CSV stream query generation completed successfully.")
        except Exception as e:
            logger.error(f"Error during CSV stream generation: {e}")
            raise e
