from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship
from .base import BaseModel

class Attachment(BaseModel):
    __tablename__ = "attachments"

    complaint_id: Mapped[int] = mapped_column(ForeignKey("complaints.id", ondelete="CASCADE"), nullable=False)
    file_url: Mapped[str] = mapped_column(String, nullable=False)

    # Relationships
    complaint: Mapped["Complaint"] = relationship("Complaint", back_populates="attachments")
