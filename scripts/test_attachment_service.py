import os
import sys
import asyncio
import hashlib
from unittest.mock import patch, MagicMock

# Add backend directory to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'CM-Dasboard')))

from app.db.session import AsyncSessionLocal
from app.models.complaint import Complaint
from app.models.attachment import Attachment
from app.core.config import settings
from app.services.storage.attachment import AttachmentService
from botocore.exceptions import ClientError

from httpx import AsyncClient
from app.main import app

async def test_attachment_service_flow():
    print("Starting Attachment Service integration tests...")

    test_email = "attachment_test_citizen@delhi.gov.in"
    local_upload_dir = os.path.join("app", "static", "uploads")

    # Clean up any existing records from this test email
    async with AsyncSessionLocal() as session:
        from sqlalchemy import select
        res_comp = await session.execute(select(Complaint).filter(Complaint.citizen_email == test_email))
        complaints = res_comp.scalars().all()
        for comp in complaints:
            await session.delete(comp)
        await session.commit()
        print(" -> Cleaned up old test complaints.")

    # Reset S3 settings for local fallback test
    settings.S3_ACCESS_KEY = ""
    settings.S3_SECRET_KEY = ""
    settings.S3_BUCKET = ""

    import httpx
    transport = httpx.ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:

        # --- Test 1: Verify database schema contains new metadata columns ---
        print("\nTest 1: Validating database schema updates...")
        async with AsyncSessionLocal() as db_session:
            from sqlalchemy import text
            try:
                await db_session.execute(text("SELECT mime_type, checksum FROM attachments LIMIT 1"))
                print(" -> PASSED: Database schema updated. Columns detected.")
            except Exception as e:
                assert False, f"Column validation failed: {e}"

        # --- Test 2: Local Fallback (S3 unconfigured) & Checksum/MIME Metadata ---
        print("\nTest 2: Testing local fallback storage when S3 is not configured...")
        pdf_content = b"%PDF-1.4\n%dummy pdf content data"
        pdf_sha = hashlib.sha256(pdf_content).hexdigest()
        
        files = [
            ("attachments", ("doc.pdf", pdf_content, "application/pdf"))
        ]
        payload = {
            "citizen_name": "Arvind Kejriwal",
            "citizen_email": test_email,
            "citizen_phone": "+919999999999",
            "title": "Road Repair Request",
            "description": "Please repair the road near block C Saket.",
            "district": "South Delhi"
        }

        response = await client.post("/api/v1/complaints/", data=payload, files=files)
        assert response.status_code == 201, f"Expected 201, got {response.status_code}: {response.text}"
        ticket_id = response.json()["ticket_id"]
        print(f" -> PASSED: Submitted complaint successfully. Ticket ID: {ticket_id}")

        # Query and verify DB metadata
        async with AsyncSessionLocal() as session:
            res_comp = await session.execute(select(Complaint).filter(Complaint.ticket_id == ticket_id))
            comp_rec = res_comp.scalars().first()
            assert comp_rec is not None
            
            res_attach = await session.execute(select(Attachment).filter(Attachment.complaint_id == comp_rec.id))
            db_attachment = res_attach.scalars().first()
            
            assert db_attachment is not None
            assert db_attachment.mime_type == "application/pdf"
            assert db_attachment.checksum == pdf_sha
            assert db_attachment.file_url.startswith("/static/uploads/")
            
            # Verify file exists on local fallback disk
            local_path = os.path.join("app", db_attachment.file_url.lstrip("/"))
            assert os.path.exists(local_path), f"File {local_path} does not exist on disk!"
            print(f" -> PASSED: Metadata verified. Checksum='{db_attachment.checksum}', MimeType='{db_attachment.mime_type}'")
            print(f" -> Verified local fallback file written successfully to: {local_path}")

        # --- Test 3: Pillow Image verification (Corrupted image validation) ---
        print("\nTest 3: Testing Pillow corrupted image detection...")
        corrupt_img = [
            ("attachments", ("photo.png", b"corrupted junk png header", "image/png"))
        ]
        new_payload = payload.copy()
        new_payload["title"] = "Streetlight repair"
        new_payload["description"] = "Corrupted upload streetlight."
        
        response = await client.post("/api/v1/complaints/", data=new_payload, files=corrupt_img)
        assert response.status_code == 400, f"Expected 400, got {response.status_code}: {response.text}"
        assert "is corrupted or invalid" in response.json()["detail"]
        print(" -> PASSED: Correctly identified and rejected corrupted image upload.")

        # --- Test 4: Mocked AWS S3 Compatible Upload ---
        print("\nTest 4: Testing successful S3 storage upload...")
        # Temp configure S3 settings
        settings.S3_ACCESS_KEY = "test_key"
        settings.S3_SECRET_KEY = "test_secret"
        settings.S3_BUCKET = "delhi-grievances"
        settings.S3_ENDPOINT_URL = "https://s3.delhi.gov.in"

        # Generate a valid PNG dynamically to prevent backslash escape issues
        from PIL import Image as PILImage
        import io as io_lib
        img_temp = PILImage.new("RGB", (10, 10), color="blue")
        png_io = io_lib.BytesIO()
        img_temp.save(png_io, format="PNG")
        valid_png_bytes = png_io.getvalue()

        # Mock boto3 s3 client upload
        mock_s3_client = MagicMock()
        mock_s3_client.put_object.return_value = {"ResponseMetadata": {"HTTPStatusCode": 200}}
        
        files_s3 = [
            ("attachments", ("chart.png", valid_png_bytes, "image/png"))
        ]
        s3_payload = payload.copy()
        s3_payload["title"] = "Garbage piling up"
        s3_payload["description"] = "Garbage near block A6 Saket."
        
        with patch("boto3.client", return_value=mock_s3_client):
            response = await client.post("/api/v1/complaints/", data=s3_payload, files=files_s3)
            assert response.status_code == 201, f"Expected 201, got {response.status_code}: {response.text}"
            ticket_id_s3 = response.json()["ticket_id"]
            
            # Check S3 URL persistence
            async with AsyncSessionLocal() as session:
                res_comp = await session.execute(select(Complaint).filter(Complaint.ticket_id == ticket_id_s3))
                comp_rec = res_comp.scalars().first()
                res_attach = await session.execute(select(Attachment).filter(Attachment.complaint_id == comp_rec.id))
                db_attachment = res_attach.scalars().first()
                assert db_attachment is not None
                assert db_attachment.file_url.startswith("https://s3.delhi.gov.in/delhi-grievances/")
                print(f" -> PASSED: Uploaded to S3 successfully. S3 file URL: {db_attachment.file_url}")
                mock_s3_client.put_object.assert_called_once()

        # --- Test 5: S3 Down Fallback (S3 raises exception) ---
        print("\nTest 5: Testing local fallback when AWS S3 returns error (storage unavailable)...")
        # Mock s3 client put_object to fail
        mock_s3_fail = MagicMock()
        mock_s3_fail.put_object.side_effect = ClientError({"Error": {"Code": "ConnectionTimeout", "Message": "S3 Down"}}, "put_object")
        
        files_fail = [
            ("attachments", ("map.png", valid_png_bytes, "image/png"))
        ]
        fail_payload = payload.copy()
        fail_payload["title"] = "Water leakage Saket"
        fail_payload["description"] = "Water leak Saket."
        
        with patch("boto3.client", return_value=mock_s3_fail):
            response = await client.post("/api/v1/complaints/", data=fail_payload, files=files_fail)
            assert response.status_code == 201, f"Expected 201, got {response.status_code}: {response.text}"
            ticket_id_fail = response.json()["ticket_id"]
            
            # Check fallback local URL persistence
            async with AsyncSessionLocal() as session:
                res_comp = await session.execute(select(Complaint).filter(Complaint.ticket_id == ticket_id_fail))
                comp_rec = res_comp.scalars().first()
                res_attach = await session.execute(select(Attachment).filter(Attachment.complaint_id == comp_rec.id))
                db_attachment = res_attach.scalars().first()
                assert db_attachment is not None
                assert db_attachment.file_url.startswith("/static/uploads/")
                print(f" -> PASSED: S3 exception caught and fallback to local disk storage succeeded. URL: {db_attachment.file_url}")

        # --- Test 6: Delete Orphan Files Utility ---
        print("\nTest 6: Testing orphan file cleanup utility...")
        # Create an orphan file on disk directly
        os.makedirs(local_upload_dir, exist_ok=True)
        orphan_path = os.path.join(local_upload_dir, "orphan_dummy_test_file.png")
        with open(orphan_path, "wb") as f:
            f.write(b"dummy unlinked png image content")
        
        assert os.path.exists(orphan_path), "Failed to seed orphan file!"
        print(f" -> Seeded local orphan file at: {orphan_path}")

        # Execute orphan file cleanup
        async with AsyncSessionLocal() as session:
            await AttachmentService.delete_orphan_files(db=session)

        # Assert the orphan file was deleted
        assert not os.path.exists(orphan_path), "Orphan cleanup failed! Orphan file still exists on disk!"
        print(" -> PASSED: Orphan file cleanup successfully deleted untracked file.")

    # Cleanup DB records
    async with AsyncSessionLocal() as session:
        res_comp = await session.execute(select(Complaint).filter(Complaint.citizen_email == test_email))
        complaints = res_comp.scalars().all()
        for comp in complaints:
            await session.delete(comp)
        await session.commit()
        print("\n -> Cleaned up database test complaints.")

    # Cleanup uploads folder test artifacts
    if os.path.exists(local_upload_dir):
        for fn in os.listdir(local_upload_dir):
            if len(fn) > 32:
                try:
                    os.remove(os.path.join(local_upload_dir, fn))
                except Exception:
                    pass
        print(" -> Cleaned up local files from test script.")

    print("\nAll attachment service integration tests completed successfully!")

if __name__ == "__main__":
    asyncio.run(test_attachment_service_flow())
