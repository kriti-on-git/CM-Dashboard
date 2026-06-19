import os
import sys
import asyncio
from datetime import datetime, timezone, timedelta
from unittest.mock import patch

# Add backend directory to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'CM-Dasboard')))

from app.db.session import AsyncSessionLocal
from app.models.user import User, RoleEnum
from app.models.notification import Notification
from app.core import security
from app.core.config import settings

# Test using httpx AsyncClient
from httpx import AsyncClient
from app.main import app
from fastapi import BackgroundTasks
from app.services.notification.service import NotificationService, notification_background_job

async def test_notifications_flow():
    print("Starting Notification Service integration tests...")

    test_email = "test_officer_notification@delhi.gov.in"
    test_email_deleted = "test_deleted_notification@delhi.gov.in"

    # 1. Clean up existing test users and notifications
    async with AsyncSessionLocal() as session:
        from sqlalchemy import select
        res_user = await session.execute(select(User).filter(User.email.in_([test_email, test_email_deleted])))
        users = res_user.scalars().all()
        user_ids = [u.id for u in users]
        
        # Clean up notifications first
        if user_ids:
            res_notifs = await session.execute(select(Notification).filter(Notification.user_id.in_(user_ids)))
            notifs = res_notifs.scalars().all()
            for n in notifs:
                await session.delete(n)
        
        # Delete users
        for u in users:
            await session.delete(u)
            
        await session.commit()
    print(" -> Cleaned up old test data.")

    # 2. Create the test officer and deleted user
    async with AsyncSessionLocal() as session:
        officer = User(
            name="Test Officer Notification",
            email=test_email,
            role=RoleEnum.OFFICER,
            is_deleted=False
        )
        deleted_user = User(
            name="Test Deleted User Notification",
            email=test_email_deleted,
            role=RoleEnum.CITIZEN,
            is_deleted=True
        )
        session.add(officer)
        session.add(deleted_user)
        await session.commit()
        await session.refresh(officer)
        await session.refresh(deleted_user)
        officer_id = officer.id
        deleted_user_id = deleted_user.id
        print(f" -> Created active officer: {test_email} with ID: {officer_id}")
        print(f" -> Created soft-deleted user: {test_email_deleted} with ID: {deleted_user_id}")

    # Generate token for the active officer
    officer_token = security.create_access_token(
        subject=officer_id,
        email=test_email,
        role=RoleEnum.OFFICER.value
    )
    print(" -> Generated access token for officer.")

    import httpx
    transport = httpx.ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        headers = {"Authorization": f"Bearer {officer_token}"}

        # --- Test 1: List notifications when empty ---
        print("\nTest 1: Fetching unread notifications when empty...")
        response = await client.get("/api/v1/notifications/unread", headers=headers)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        assert len(response.json()) == 0, f"Expected 0 unread, got {len(response.json())}"
        print(" -> PASSED: Unread notifications list is empty.")

        # --- Test 2: Trigger Assignment and Status changes and verify ---
        print("\nTest 2: Dispatching events via NotificationService (Assignment & Status Change)...")
        bg_tasks = BackgroundTasks()
        NotificationService.dispatch_assigned_notification(
            user_id=officer_id,
            ticket_id="DL-2026-000099",
            background_tasks=bg_tasks
        )
        NotificationService.dispatch_status_changed_notification(
            user_id=officer_id,
            ticket_id="DL-2026-000099",
            new_status="IN_PROGRESS",
            background_tasks=bg_tasks
        )
        
        # Execute background tasks manually
        print(" -> Executing background tasks...")
        for task in bg_tasks.tasks:
            await task.func(*task.args, **task.kwargs)
            
        # Verify in DB via API
        response = await client.get("/api/v1/notifications/unread", headers=headers)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        unread_notifications = response.json()
        assert len(unread_notifications) == 2, f"Expected 2 unread notifications, got {len(unread_notifications)}"
        
        # Check messages
        messages = [n["message"] for n in unread_notifications]
        assert "Complaint ticket DL-2026-000099 has been assigned to you." in messages
        assert "The status of complaint ticket DL-2026-000099 has changed to IN_PROGRESS." in messages
        print(" -> PASSED: Both notifications registered in DB and retrieved via GET /unread.")

        # --- Test 3: Mark one notification as read ---
        print("\nTest 3: Marking one notification as read...")
        notif_to_read = unread_notifications[0]
        notif_id = notif_to_read["id"]
        
        # Mark read
        response = await client.patch(f"/api/v1/notifications/{notif_id}/read", headers=headers)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        assert response.json()["is_read"] is True
        
        # Retrieve again, count should be 1
        response = await client.get("/api/v1/notifications/unread", headers=headers)
        assert response.status_code == 200
        unread_notifications_after = response.json()
        assert len(unread_notifications_after) == 1, f"Expected 1 unread notification, got {len(unread_notifications_after)}"
        assert unread_notifications_after[0]["id"] != notif_id
        print(" -> PASSED: Marked as read successfully and excluded from GET /unread.")

        # Try to mark someone else's notification as read or non-existent notification
        print(" -> Testing unauthorized / non-existent read access...")
        response = await client.patch("/api/v1/notifications/999999/read", headers=headers)
        assert response.status_code == 404, f"Expected 404, got {response.status_code}"
        print(" -> PASSED: Non-existent notification returns 404.")

        # --- Test 4: Duplicate suppression (same message within 1 minute) ---
        print("\nTest 4: Testing duplicate notification suppression...")
        bg_tasks = BackgroundTasks()
        # Clean up unread notifications to make verification simple
        async with AsyncSessionLocal() as session:
            from sqlalchemy import delete
            await session.execute(delete(Notification).where(Notification.user_id == officer_id))
            await session.commit()
            
        # Dispatch two identical notifications
        message_body = "Duplicate test alert message"
        bg_tasks.add_task(notification_background_job, officer_id, message_body, "Duplicate Test")
        bg_tasks.add_task(notification_background_job, officer_id, message_body, "Duplicate Test")
        
        # Execute tasks
        for task in bg_tasks.tasks:
            await task.func(*task.args, **task.kwargs)
            
        # Retrieve notifications, should be only 1
        async with AsyncSessionLocal() as session:
            res_notifs = await session.execute(select(Notification).filter(Notification.user_id == officer_id))
            notifs = res_notifs.scalars().all()
            assert len(notifs) == 1, f"Expected 1 notification in DB, got {len(notifs)}"
        print(" -> PASSED: Duplicate notification successfully suppressed.")

        # --- Test 5: Storm suppression (max 10 email sends within 1 minute) ---
        print("\nTest 5: Testing notification storm email suppression...")
        # Clear database notifications first
        async with AsyncSessionLocal() as session:
            await session.execute(delete(Notification).where(Notification.user_id == officer_id))
            await session.commit()
            
        bg_tasks = BackgroundTasks()
        
        # Dispatch 12 notifications with different messages to bypass duplicate suppression
        for i in range(12):
            msg = f"Storm test alert {i}"
            bg_tasks.add_task(notification_background_job, officer_id, msg, f"Storm Subject {i}")
            
        # Patch async_send_notification_email to count email dispatches
        email_dispatch_count = 0
        async def mock_send_email(email_to, subject, message):
            nonlocal email_dispatch_count
            email_dispatch_count += 1
            
        with patch('app.services.notification.service.async_send_notification_email', new=mock_send_email):
            for task in bg_tasks.tasks:
                await task.func(*task.args, **task.kwargs)
                
        # Assertions
        async with AsyncSessionLocal() as session:
            res_notifs = await session.execute(select(Notification).filter(Notification.user_id == officer_id))
            notifs = res_notifs.scalars().all()
            # All 12 should be recorded in the DB for the dashboard
            assert len(notifs) == 12, f"Expected all 12 notifications in DB, got {len(notifs)}"
            # Email mock should have been called only 10 times due to storm suppression
            assert email_dispatch_count == 10, f"Expected exactly 10 emails sent, got {email_dispatch_count}"
            
        print(" -> PASSED: Storm suppression allows DB logs but limits emails to 10.")

        # --- Test 6: Deleted user check ---
        print("\nTest 6: Testing notification suppression for soft-deleted / inactive users...")
        bg_tasks = BackgroundTasks()
        bg_tasks.add_task(notification_background_job, deleted_user_id, "Hello Deleted User", "Subject")
        
        for task in bg_tasks.tasks:
            await task.func(*task.args, **task.kwargs)
            
        # Verify in DB that no notification is written
        async with AsyncSessionLocal() as session:
            res_notifs = await session.execute(select(Notification).filter(Notification.user_id == deleted_user_id))
            notifs = res_notifs.scalars().all()
            assert len(notifs) == 0, f"Expected 0 notifications in DB for deleted user, got {len(notifs)}"
        print(" -> PASSED: Notification suppressed for deactivated user.")

        # --- Test 7: SMTP failure resiliency ---
        print("\nTest 7: Testing SMTP failure resiliency...")
        bg_tasks = BackgroundTasks()
        # Clean up database notifications first
        async with AsyncSessionLocal() as session:
            await session.execute(delete(Notification).where(Notification.user_id == officer_id))
            await session.commit()
            
        bg_tasks.add_task(notification_background_job, officer_id, "Resiliency test", "Subject")
        
        # Mock SMTP to raise exception
        async def mock_send_email_raise(email_to, subject, message):
            raise Exception("SMTP Server Connection Timeout")
            
        with patch('app.services.notification.service.async_send_notification_email', new=mock_send_email_raise):
            for task in bg_tasks.tasks:
                await task.func(*task.args, **task.kwargs)
                
        # Assert DB notification is still created
        async with AsyncSessionLocal() as session:
            res_notifs = await session.execute(select(Notification).filter(Notification.user_id == officer_id))
            notifs = res_notifs.scalars().all()
            assert len(notifs) == 1, f"Expected notification in DB despite SMTP failure, got {len(notifs)}"
        print(" -> PASSED: SMTP error caught gracefully, DB notification created successfully.")

    # Cleanup test users
    async with AsyncSessionLocal() as session:
        res_user = await session.execute(select(User).filter(User.email.in_([test_email, test_email_deleted])))
        users = res_user.scalars().all()
        user_ids = [u.id for u in users]
        
        if user_ids:
            res_notifs = await session.execute(select(Notification).filter(Notification.user_id.in_(user_ids)))
            notifs = res_notifs.scalars().all()
            for n in notifs:
                await session.delete(n)
        for u in users:
            await session.delete(u)
        await session.commit()
    print("\nAll notification service integration tests completed successfully!")

if __name__ == "__main__":
    asyncio.run(test_notifications_flow())
