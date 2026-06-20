import uuid
from sqlalchemy import Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column
from .base import BaseModel

class Report(BaseModel):
    __tablename__ = "reports"
    
    incident_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    created_by: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
