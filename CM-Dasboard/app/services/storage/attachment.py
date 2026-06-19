import os
import io
import uuid
import hashlib
import logging
import mimetypes
import asyncio
from datetime import datetime, timezone
from typing import Optional, Set
from PIL import Image

import boto3
from botocore.exceptions import ClientError
from fastapi import UploadFile, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.core.config import settings
from app.models.attachment import Attachment

logger = logging.getLogger(__name__)

# Constants
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'pdf'}
REJECTED_EXTENSIONS = {'exe', 'js', 'zip'}
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB
EICAR_SIGNATURE = b"X5O!P%@AP[4\\PZX54(P^)7CC)7}$EICAR-STANDARD-ANTIVIRUS-TEST-FILE!$H+H*"
LOCAL_UPLOAD_DIR = os.path.join("app", "static", "uploads")

class AttachmentService:
    """
    Handles file verification, metadata gathering, S3 upload logic with local fallbacks, 
    and orphan cleanup jobs.
    """

    @staticmethod
    async def validate_and_upload(
        file: UploadFile,
        complaint_id: int,
        db: AsyncSession
    ) -> Attachment:
        """
        Validates the file, computes checksum/mime metadata, uploads to S3 (with local fallback),
        and persists the Attachment record.
        """
        # 1. Extract and validate extension
        filename = file.filename
        if not filename:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Filename cannot be empty."
            )

        ext = filename.split('.')[-1].lower() if '.' in filename else ''
        if ext in REJECTED_EXTENSIONS or ext not in ALLOWED_EXTENSIONS:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"File extension '.{ext}' is not allowed. Supported formats: png, jpg, jpeg, pdf."
            )

        # 2. Read content in memory for validation & metadata
        try:
            content = await file.read()
        except Exception as read_err:
            logger.error(f"Failed to read upload file {filename}: {read_err}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Upload interrupted or failed during read."
            )

        # Size check
        file_size = len(content)
        if file_size > MAX_FILE_SIZE:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"File {filename} size ({file_size / 1024 / 1024:.2f} MB) exceeds the 10 MB limit."
            )

        # 3. Virus scanning (EICAR)
        if EICAR_SIGNATURE in content:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Malicious payload check failed. Virus signature detected in {filename}."
            )

        # 4. MIME type detection
        mime_type, _ = mimetypes.guess_type(filename)
        if not mime_type:
            mime_type = file.content_type or "application/octet-stream"

        # 5. PIL image verification (corrupted image check)
        if mime_type.startswith("image/"):
            try:
                img = Image.open(io.BytesIO(content))
                img.verify()
            except Exception as img_err:
                logger.error(f"Image verification failed for {filename}: {img_err}")
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Uploaded image '{filename}' is corrupted or invalid."
                )

        # 6. PDF magic bytes validation (malicious payload check)
        if ext == "pdf" and not content.startswith(b"%PDF"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Uploaded PDF '{filename}' is invalid or contains an invalid header payload."
            )

        # 7. Checksum calculation
        checksum = hashlib.sha256(content).hexdigest()

        # 8. Unique UUID Filename
        unique_filename = f"{uuid.uuid4().hex}.{ext}"

        # 9. Upload execution (S3 compatible with local fallback)
        file_url = None
        s3_success = False

        if settings.S3_ACCESS_KEY and settings.S3_SECRET_KEY and settings.S3_BUCKET:
            try:
                # Attempt S3 Upload in a separate thread
                await asyncio.to_thread(
                    AttachmentService._upload_to_s3,
                    content,
                    unique_filename,
                    mime_type
                )
                
                # Format URL
                if settings.S3_ENDPOINT_URL:
                    file_url = f"{settings.S3_ENDPOINT_URL.rstrip('/')}/{settings.S3_BUCKET}/{unique_filename}"
                else:
                    file_url = f"https://{settings.S3_BUCKET}.s3.{settings.S3_REGION}.amazonaws.com/{unique_filename}"
                s3_success = True
                logger.info(f"Successfully uploaded {filename} to S3 as key: {unique_filename}")
            except Exception as s3_err:
                logger.warning(
                    f"AWS S3 compatible storage is unavailable or configuration failed: {s3_err}. "
                    f"Falling back to local storage for file: {filename}"
                )

        if not s3_success:
            # Fallback to Local Storage
            try:
                os.makedirs(LOCAL_UPLOAD_DIR, exist_ok=True)
                local_path = os.path.join(LOCAL_UPLOAD_DIR, unique_filename)
                
                await asyncio.to_thread(
                    AttachmentService._write_local,
                    local_path,
                    content
                )
                file_url = f"/static/uploads/{unique_filename}"
                logger.info(f"Successfully saved {filename} to local fallback storage: {local_path}")
            except Exception as disk_err:
                logger.error(f"Local storage fallback failed: {disk_err}", exc_info=True)
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Failed to save attachment due to complete storage unavailability."
                )

        # 10. Persist Attachment db model
        db_attachment = Attachment(
            complaint_id=complaint_id,
            file_url=file_url,
            mime_type=mime_type,
            checksum=checksum
        )
        db.add(db_attachment)
        return db_attachment

    @staticmethod
    def _upload_to_s3(content: bytes, key: str, content_type: str) -> None:
        """Helper to invoke synchronous boto3 uploads in a thread pool."""
        s3 = boto3.client(
            "s3",
            aws_access_key_id=settings.S3_ACCESS_KEY,
            aws_secret_access_key=settings.S3_SECRET_KEY,
            endpoint_url=settings.S3_ENDPOINT_URL or None,
            region_name=settings.S3_REGION
        )
        s3.put_object(
            Bucket=settings.S3_BUCKET,
            Key=key,
            Body=content,
            ContentType=content_type
        )

    @staticmethod
    def _write_local(dest_path: str, content: bytes) -> None:
        """Helper to write local files."""
        with open(dest_path, "wb") as f:
            f.write(content)

    @staticmethod
    async def delete_orphan_files(db: AsyncSession) -> None:
        """
        Finds all orphan files in local storage and S3 bucket (unlinked from attachments database)
        and deletes them.
        """
        logger.info("Starting orphan file cleanup task...")
        
        # Retrieve all file urls from DB
        result = await db.execute(select(Attachment.file_url))
        urls = result.scalars().all()
        db_filenames: Set[str] = {os.path.basename(u) for u in urls if u}

        # 1. Clean local orphans
        if os.path.exists(LOCAL_UPLOAD_DIR):
            for fn in os.listdir(LOCAL_UPLOAD_DIR):
                if fn.startswith('.'):
                    continue
                if fn not in db_filenames:
                    local_path = os.path.join(LOCAL_UPLOAD_DIR, fn)
                    try:
                        os.remove(local_path)
                        logger.info(f"Deleted local orphan file: {fn}")
                    except Exception as e:
                        logger.error(f"Failed to delete local orphan {fn}: {e}")

        # 2. Clean S3 orphans
        if settings.S3_ACCESS_KEY and settings.S3_SECRET_KEY and settings.S3_BUCKET:
            try:
                s3_keys = await asyncio.to_thread(AttachmentService._list_s3_keys)
                orphan_keys = [k for k in s3_keys if k not in db_filenames]
                
                if orphan_keys:
                    await asyncio.to_thread(AttachmentService._delete_s3_keys, orphan_keys)
                    logger.info(f"Deleted {len(orphan_keys)} orphan files from S3 bucket.")
            except Exception as s3_err:
                logger.error(f"Failed to delete orphan files from S3 storage: {s3_err}")

    @staticmethod
    def _list_s3_keys() -> list[str]:
        """Lists all keys in the S3 bucket."""
        s3 = boto3.client(
            "s3",
            aws_access_key_id=settings.S3_ACCESS_KEY,
            aws_secret_access_key=settings.S3_SECRET_KEY,
            endpoint_url=settings.S3_ENDPOINT_URL or None,
            region_name=settings.S3_REGION
        )
        keys = []
        paginator = s3.get_paginator('list_objects_v2')
        for page in paginator.paginate(Bucket=settings.S3_BUCKET):
            for content in page.get('Contents', []):
                keys.append(content['Key'])
        return keys

    @staticmethod
    def _delete_s3_keys(keys: list[str]) -> None:
        """Deletes multiple keys from the S3 bucket."""
        s3 = boto3.client(
            "s3",
            aws_access_key_id=settings.S3_ACCESS_KEY,
            aws_secret_access_key=settings.S3_SECRET_KEY,
            endpoint_url=settings.S3_ENDPOINT_URL or None,
            region_name=settings.S3_REGION
        )
        # Format object lists
        delete_list = {'Objects': [{'Key': k} for k in keys]}
        s3.delete_objects(Bucket=settings.S3_BUCKET, Delete=delete_list)
