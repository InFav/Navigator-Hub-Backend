from sqlalchemy import Column, Integer, String, DateTime, ARRAY, Text, text, ForeignKey
from database import Base
from datetime import datetime
from sqlalchemy.sql import func


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


class PersonaInput(Base):
    __tablename__ = "persona_input"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String, nullable=False)  # Firebase UID
    name = Column(String, nullable=False)
    profession = Column(String, nullable=False)
    current_work = Column(String, nullable=False)
    professional_communities = Column(ARRAY(String), nullable=True)
    goal = Column(String, nullable=False)
    journey = Column(Text, nullable=True)
    company_size = Column(String, nullable=True)
    industry_target = Column(String, nullable=False)
    target_type = Column(String, nullable=False)
    favorite_posts = Column(Text, nullable=False)
    best_posts = Column(Text, nullable=False)
    posts_to_create = Column(Integer, nullable=False)
    post_purpose = Column(String, nullable=False)
    timeline = Column(String, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class PersonaInputNew(Base):
    __tablename__ = "persona_input_new"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String, nullable=False)
    profession = Column(String, nullable=False)
    current_work = Column(String, nullable=False)
    goal = Column(String, nullable=False)
    journey = Column(Text, nullable=True)
    company_size = Column(String, nullable=True)
    industry_target = Column(String, nullable=False)
    target_type = Column(String, nullable=False)
    favorite_posts = Column(Text, nullable=False)
    best_posts = Column(Text, nullable=False)
    posts_to_create = Column(Integer, nullable=False)
    post_purpose = Column(String, nullable=False)
    timeline = Column(String, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class PostNew(Base):
    __tablename__ = "posts_new"

    id = Column(Integer, primary_key=True, index=True)
    persona_id = Column(Integer, ForeignKey("persona_input_new.id"), nullable=False)
    post_content = Column(Text, nullable=False)
    post_date = Column(DateTime(timezone=True), nullable=False)
    clicks = Column(Integer, default=0)
    regenerate_clicks = Column(Integer, default=0)

class Post(Base):
    __tablename__ = "posts"

    id = Column(Integer, primary_key=True, index=True)
    persona_id = Column(Integer, nullable=False)
    post_content = Column(Text, nullable=False)
    post_date = Column(DateTime, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    clicks = Column(Integer, default=0)
    regenerate_clicks = Column(Integer, default=0)

class ChatHistory(Base):
    __tablename__ = "chat_history"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String, nullable=False)  # Firebase UID
    message = Column(Text, nullable=False)
    sender = Column(String, nullable=False)  # 'user' or 'bot'
    created_at = Column(DateTime, default=datetime.utcnow)