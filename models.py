from sqlalchemy import Column, Integer, String, DateTime, Boolean
from database import Base
from pydantic import BaseModel

class AttendanceRecord(Base):
    __tablename__ = "attendance"

    id = Column(Integer, primary_key=True, index=True)
    student_name = Column(String, default="Guest Student")
    sign_in = Column(DateTime)
    sign_out = Column(DateTime, nullable=True)
    total_hours = Column(String, nullable=True)
    status = Column(String, default="In-Progress")
    notes = Column(String, nullable=True)
    is_regularized = Column(Boolean, default=False)

class ActivitySchema(BaseModel):
    text: str