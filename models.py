from sqlalchemy import Column, Integer, String, DateTime, text
from database import Base
from datetime import datetime

class User(Base):
    __tablename__ = "firebase_users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True)
    uid = Column(String, unique=True, index=True)
    name = Column(String, nullable=True)
    picture = Column(String, nullable=True)
    provider = Column(String(50), nullable=True)  # Add this line
    created_at = Column(DateTime, server_default=text('CURRENT_TIMESTAMP'), nullable=False)
    updated_at = Column(DateTime, server_default=text('CURRENT_TIMESTAMP'), onupdate=datetime.utcnow, nullable=False)