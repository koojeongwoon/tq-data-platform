from sqlalchemy import JSON, Column, DateTime, Integer, String
from sqlalchemy.sql import func

from .database import Base


class RawData(Base):
    __tablename__ = "raw_data"

    id = Column(Integer, primary_key=True, index=True)
    source = Column(String, index=True)
    data = Column(JSON)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
