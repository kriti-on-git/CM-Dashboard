import os
import sys
import asyncio
from datetime import datetime, timedelta, timezone

# Add backend directory to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'CM-Dasboard')))

from app.db.session import AsyncSessionLocal
from app.models.user import User, RoleEnum
from app.models.complaint import Complaint, PriorityEnum, ComplaintStatus
from app.models.complaint_update import ComplaintUpdate
from app.models.comment import Comment
from app.models.attachment import Attachment
from app.models.notification import Notification
from app.models.otp import OTP
from app.models.feedback import Feedback
from app.models.escalation import Escalation

async def main():
    print("Starting database models integration verification...")
    async with AsyncSessionLocal() as session:
        # 1. Create Citizen User
        citizen = User(
            name="Delhi Citizen",
            email="citizen@delhi.gov.in",
            phone="9999999999",
            role=RoleEnum.CITIZEN
        )
        session.add(citizen)
        
        # 2. Create Officer User
        officer = User(
            name="Water Officer",
            email="officer.water@delhi.gov.in",
            phone="8888888888",
            role=RoleEnum.OFFICER,
            department="Jal Board"
        )
        session.add(officer)
        
        await session.commit()
        await session.refresh(citizen)
        await session.refresh(officer)
        print(f"Created Users -> Citizen ID: {citizen.id}, Officer ID: {officer.id}")
        
        # 3. Create Complaint
        complaint = Complaint(
            ticket_id="DL-2026-0001",
            citizen_name=citizen.name,
            citizen_email=citizen.email,
            citizen_phone=citizen.phone,
            title="Burst Pipeline in Saket",
            description="Massive water wastage due to a cracked pipe near Metro Station gate 2.",
            category="WATER_SUPPLY",
            department="Jal Board",
            district="South Delhi",
            lat=28.5276,
            lon=77.2065,
            priority=PriorityEnum.HIGH,
            status=ComplaintStatus.OPEN,
            assigned_to=officer.id
        )
        session.add(complaint)
        await session.commit()
        await session.refresh(complaint)
        print(f"Created Complaint -> Ticket ID: {complaint.ticket_id}, Assigned To Officer ID: {complaint.assigned_to}")
        
        # 4. Add Complaint Update Timeline entry
        update_log = ComplaintUpdate(
            complaint_id=complaint.id,
            status=ComplaintStatus.IN_PROGRESS,
            updated_by=officer.id,
            note="Team dispatched to the site with welding equipment."
        )
        session.add(update_log)
        
        # 5. Add Comment
        comment = Comment(
            complaint_id=complaint.id,
            user_id=citizen.id,
            message="Please hurry, water is flooding the street."
        )
        session.add(comment)
        
        # 6. Add Attachment
        attachment = Attachment(
            complaint_id=complaint.id,
            file_url="https://storage.delhigov.in/grievances/water_leakage_saket.jpg"
        )
        session.add(attachment)
        
        # 7. Add Notification
        notification = Notification(
            user_id=officer.id,
            message="New complaint assigned: DL-2026-0001"
        )
        session.add(notification)
        
        # 8. Add OTP
        otp_record = OTP(
            email="citizen@delhi.gov.in",
            otp_hash="hashed_otp_code_1234",
            expiry=datetime.now(timezone.utc) + timedelta(minutes=4)
        )
        session.add(otp_record)
        
        # 9. Add Feedback
        feedback = Feedback(
            complaint_id=complaint.id,
            citizen_id=citizen.id,
            rating=5,
            note="Quick resolution. Thanks CMO!"
        )
        session.add(feedback)
        
        # 10. Add Escalation log
        escalation = Escalation(
            complaint_id=complaint.id,
            escalated_by=None,
            escalated_to=officer.id,
            reason="Deadline breached on pipeline repair."
        )
        session.add(escalation)
        
        await session.commit()
        print("Successfully saved all updates, comments, attachments, notifications, OTP, feedback, and escalations.")
        
        # 11. Verify Relationships (eager load check via database select)
        from sqlalchemy import select
        from sqlalchemy.orm import selectinload
        
        q = (
            select(Complaint)
            .filter(Complaint.id == complaint.id)
            .options(
                selectinload(Complaint.updates),
                selectinload(Complaint.comments),
                selectinload(Complaint.attachments)
            )
        )
        res = await session.execute(q)
        fetched_complaint = res.scalars().one()
        
        print(f"Verified Relationships:")
        print(f" - Updates count: {len(fetched_complaint.updates)}")
        print(f" - Comments count: {len(fetched_complaint.comments)}")
        print(f" - Attachments count: {len(fetched_complaint.attachments)}")
        
        # 12. Test Cascade Deletion on Complaint
        print("Testing Cascade Deletion of Complaint...")
        await session.delete(fetched_complaint)
        await session.commit()
        
        # Verify cascaded deletions
        q_updates = select(ComplaintUpdate).filter(ComplaintUpdate.complaint_id == complaint.id)
        res_updates = await session.execute(q_updates)
        updates_left = res_updates.scalars().all()
        assert len(updates_left) == 0, "Updates should be cascade deleted!"
        
        q_comments = select(Comment).filter(Comment.complaint_id == complaint.id)
        res_comments = await session.execute(q_comments)
        comments_left = res_comments.scalars().all()
        assert len(comments_left) == 0, "Comments should be cascade deleted!"
        
        print("Cascade deletion successfully verified!")
        
        # 13. Test Soft Delete flag
        print("Testing soft delete flag capability...")
        citizen.is_deleted = True
        session.add(citizen)
        await session.commit()
        
        # 14. Clean up remaining records to keep database clean
        await session.delete(citizen)
        await session.delete(officer)
        
        q_otp = select(OTP).filter(OTP.email == "citizen@delhi.gov.in")
        res_otp = await session.execute(q_otp)
        otp_left = res_otp.scalars().first()
        if otp_left:
            await session.delete(otp_left)
            
        await session.commit()
        print("Verification completed successfully with no failures!")

if __name__ == "__main__":
    asyncio.run(main())
