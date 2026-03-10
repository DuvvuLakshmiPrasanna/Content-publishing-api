import math
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from slugify import slugify
import secrets
from app.database import get_db
from app.models import Post, PostRevision, PostStatus, User
from app.schemas import (
    PostCreate, PostUpdate, PostResponse, PostListResponse,
    ScheduleRequest, RevisionResponse,
)
from app.auth import require_author
from app.cache import invalidate_post_cache, invalidate_published_cache

router = APIRouter(prefix="/posts", tags=["Posts"])


def generate_unique_slug(db: Session, title: str, exclude_id: int = None) -> str:
    base_slug = slugify(title, max_length=500)
    slug = base_slug
    counter = 1
    while True:
        query = db.query(Post).filter(Post.slug == slug)
        if exclude_id:
            query = query.filter(Post.id != exclude_id)
        if not query.first():
            return slug
        slug = f"{base_slug}-{secrets.token_hex(3)}"
        counter += 1
        if counter > 20:
            slug = f"{base_slug}-{secrets.token_hex(8)}"
            return slug


# --- Author-only CRUD ---

@router.post("", response_model=PostResponse, status_code=status.HTTP_201_CREATED)
def create_post(
    payload: PostCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_author),
):
    slug = generate_unique_slug(db, payload.title)
    post = Post(
        title=payload.title,
        slug=slug,
        content=payload.content,
        status=PostStatus.draft,
        author_id=current_user.id,
    )
    db.add(post)
    db.commit()
    db.refresh(post)
    return post


@router.get("", response_model=PostListResponse)
def list_posts(
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_author),
):
    query = db.query(Post).filter(Post.author_id == current_user.id)
    total = query.count()
    total_pages = max(1, math.ceil(total / page_size))
    items = query.order_by(Post.created_at.desc()).offset((page - 1) * page_size).limit(page_size).all()
    return PostListResponse(items=items, total=total, page=page, page_size=page_size, total_pages=total_pages)


@router.get("/{post_id}", response_model=PostResponse)
def get_post(
    post_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_author),
):
    post = db.query(Post).filter(Post.id == post_id, Post.author_id == current_user.id).first()
    if not post:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Post not found")
    return post


@router.put("/{post_id}", response_model=PostResponse)
def update_post(
    post_id: int,
    payload: PostUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_author),
):
    post = db.query(Post).filter(Post.id == post_id, Post.author_id == current_user.id).first()
    if not post:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Post not found")

    # Check if there's a meaningful change to version
    title_changed = payload.title is not None and payload.title != post.title
    content_changed = payload.content is not None and payload.content != post.content

    if title_changed or content_changed:
        # Save current state as a revision (within the same transaction)
        revision = PostRevision(
            post_id=post.id,
            title_snapshot=post.title,
            content_snapshot=post.content,
            revision_author_id=current_user.id,
            revision_timestamp=datetime.utcnow(),
        )
        db.add(revision)

    # Apply updates
    if payload.title is not None:
        post.title = payload.title
        post.slug = generate_unique_slug(db, payload.title, exclude_id=post.id)
    if payload.content is not None:
        post.content = payload.content
    post.updated_at = datetime.utcnow()

    db.commit()
    db.refresh(post)

    # Invalidate cache if the post was published
    if post.status == PostStatus.published:
        invalidate_post_cache(post.id)

    return post


@router.delete("/{post_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_post(
    post_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_author),
):
    post = db.query(Post).filter(Post.id == post_id, Post.author_id == current_user.id).first()
    if not post:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Post not found")
    was_published = post.status == PostStatus.published
    db.delete(post)
    db.commit()
    if was_published:
        invalidate_post_cache(post_id)


# --- Lifecycle ---

@router.post("/{post_id}/publish", response_model=PostResponse)
def publish_post(
    post_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_author),
):
    post = db.query(Post).filter(Post.id == post_id, Post.author_id == current_user.id).first()
    if not post:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Post not found")
    if post.status == PostStatus.published:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Post is already published")
    post.status = PostStatus.published
    post.published_at = datetime.utcnow()
    post.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(post)
    invalidate_published_cache()
    return post


@router.post("/{post_id}/schedule", response_model=PostResponse)
def schedule_post(
    post_id: int,
    payload: ScheduleRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_author),
):
    post = db.query(Post).filter(Post.id == post_id, Post.author_id == current_user.id).first()
    if not post:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Post not found")
    if post.status == PostStatus.published:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot schedule an already published post")
    now = datetime.now(timezone.utc)
    scheduled = payload.scheduled_for if payload.scheduled_for.tzinfo else payload.scheduled_for.replace(tzinfo=timezone.utc)
    if scheduled <= now:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Scheduled time must be in the future")
    post.status = PostStatus.scheduled
    post.scheduled_for = payload.scheduled_for
    post.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(post)
    return post


# --- Versioning ---

@router.get("/{post_id}/revisions", response_model=list[RevisionResponse])
def get_revisions(
    post_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_author),
):
    post = db.query(Post).filter(Post.id == post_id, Post.author_id == current_user.id).first()
    if not post:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Post not found")
    revisions = (
        db.query(PostRevision)
        .filter(PostRevision.post_id == post_id)
        .order_by(PostRevision.revision_timestamp.asc())
        .all()
    )
    result = []
    for rev in revisions:
        author_name = None
        if rev.revision_author:
            author_name = rev.revision_author.username
        result.append(
            RevisionResponse(
                revision_id=rev.id,
                post_id=rev.post_id,
                title_snapshot=rev.title_snapshot,
                content_snapshot=rev.content_snapshot,
                revision_author=author_name,
                revision_timestamp=rev.revision_timestamp,
            )
        )
    return result
