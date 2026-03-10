import enum
from datetime import datetime
from sqlalchemy import (
    Column, Integer, String, Text, DateTime, Enum, ForeignKey, Index, func
)
from sqlalchemy.dialects.postgresql import TSVECTOR
from sqlalchemy.orm import relationship
from app.database import Base


class UserRole(str, enum.Enum):
    author = "author"
    public = "public"


class PostStatus(str, enum.Enum):
    draft = "draft"
    scheduled = "scheduled"
    published = "published"


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(100), nullable=False)
    email = Column(String(255), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    role = Column(Enum(UserRole), nullable=False, default=UserRole.author)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    posts = relationship("Post", back_populates="author", cascade="all, delete-orphan")


class Post(Base):
    __tablename__ = "posts"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(500), nullable=False)
    slug = Column(String(600), unique=True, nullable=False, index=True)
    content = Column(Text, nullable=False, default="")
    status = Column(Enum(PostStatus), nullable=False, default=PostStatus.draft, index=True)
    author_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    scheduled_for = Column(DateTime, nullable=True)
    published_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    search_vector = Column(TSVECTOR)

    author = relationship("User", back_populates="posts")
    revisions = relationship("PostRevision", back_populates="post", cascade="all, delete-orphan",
                             order_by="PostRevision.revision_timestamp.desc()")

    __table_args__ = (
        Index("ix_posts_scheduled_for", "scheduled_for", postgresql_where=(status == PostStatus.scheduled)),
        Index("ix_posts_published_at", "published_at"),
        Index("ix_posts_search_vector", "search_vector", postgresql_using="gin"),
    )


class PostRevision(Base):
    __tablename__ = "post_revisions"

    id = Column(Integer, primary_key=True, index=True)
    post_id = Column(Integer, ForeignKey("posts.id", ondelete="CASCADE"), nullable=False, index=True)
    title_snapshot = Column(String(500), nullable=False)
    content_snapshot = Column(Text, nullable=False)
    revision_author_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    revision_timestamp = Column(DateTime, default=datetime.utcnow, nullable=False)

    post = relationship("Post", back_populates="revisions")
    revision_author = relationship("User")


class Media(Base):
    __tablename__ = "media"

    id = Column(Integer, primary_key=True, index=True)
    filename = Column(String(500), nullable=False)
    original_filename = Column(String(500), nullable=False)
    content_type = Column(String(100), nullable=False)
    file_size = Column(Integer, nullable=False)
    url = Column(String(1000), nullable=False)
    author_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    uploaded_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    uploader = relationship("User")
