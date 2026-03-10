from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, EmailStr, Field


# --- User Schemas ---
class UserCreate(BaseModel):
    username: str = Field(..., min_length=1, max_length=100)
    email: EmailStr
    password: str = Field(..., min_length=6)
    role: str = Field(default="author")


class UserResponse(BaseModel):
    id: int
    username: str
    role: str

    class Config:
        from_attributes = True


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class LoginResponse(BaseModel):
    token: str
    user: UserResponse


# --- Post Schemas ---
class PostCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=500)
    content: str = Field(default="")


class PostUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=1, max_length=500)
    content: Optional[str] = None


class PostResponse(BaseModel):
    id: int
    title: str
    slug: str
    content: str
    status: str
    author_id: int
    scheduled_for: Optional[datetime] = None
    published_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class PostListResponse(BaseModel):
    items: List[PostResponse]
    total: int
    page: int
    page_size: int
    total_pages: int


class PublishedPostResponse(BaseModel):
    id: int
    title: str
    slug: str
    content: str
    author: str
    published_at: Optional[datetime] = None
    created_at: datetime

    class Config:
        from_attributes = True


class PublishedPostListResponse(BaseModel):
    items: List[PublishedPostResponse]
    total: int
    page: int
    page_size: int
    total_pages: int


class ScheduleRequest(BaseModel):
    scheduled_for: datetime


# --- Revision Schemas ---
class RevisionResponse(BaseModel):
    revision_id: int
    post_id: int
    title_snapshot: str
    content_snapshot: str
    revision_author: Optional[str] = None
    revision_timestamp: datetime

    class Config:
        from_attributes = True


# --- Media Schemas ---
class MediaResponse(BaseModel):
    id: int
    filename: str
    original_filename: str
    content_type: str
    file_size: int
    url: str
    uploaded_at: datetime

    class Config:
        from_attributes = True


# --- Search Schemas ---
class SearchResult(BaseModel):
    items: List[PublishedPostResponse]
    total: int
    query: str
    page: int
    page_size: int
