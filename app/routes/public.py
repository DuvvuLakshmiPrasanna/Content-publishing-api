import json
import math
from fastapi import APIRouter, Depends, Query, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import func, text
from app.database import get_db
from app.models import Post, PostStatus, User
from app.schemas import PublishedPostResponse, PublishedPostListResponse, SearchResult
from app.cache import get_cache, set_cache

router = APIRouter(tags=["Public"])


def _post_to_published_response(post: Post) -> dict:
    return {
        "id": post.id,
        "title": post.title,
        "slug": post.slug,
        "content": post.content,
        "author": post.author.username if post.author else "Unknown",
        "published_at": post.published_at.isoformat() if post.published_at else None,
        "created_at": post.created_at.isoformat(),
    }


@router.get("/posts/published", response_model=PublishedPostListResponse)
def list_published_posts(
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    db: Session = Depends(get_db),
):
    cache_key = f"published:list:{page}:{page_size}"
    cached = get_cache(cache_key)
    if cached:
        return json.loads(cached)

    query = db.query(Post).filter(Post.status == PostStatus.published)
    total = query.count()
    total_pages = max(1, math.ceil(total / page_size))
    posts = (
        query.order_by(Post.published_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    items = [_post_to_published_response(p) for p in posts]
    response = {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": total_pages,
    }
    set_cache(cache_key, json.dumps(response))
    return response


@router.get("/posts/published/{post_id}", response_model=PublishedPostResponse)
def get_published_post(post_id: int, db: Session = Depends(get_db)):
    cache_key = f"published:post:{post_id}"
    cached = get_cache(cache_key)
    if cached:
        return json.loads(cached)

    post = db.query(Post).filter(Post.id == post_id, Post.status == PostStatus.published).first()
    if not post:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Published post not found")
    response = _post_to_published_response(post)
    set_cache(cache_key, json.dumps(response))
    return response


@router.get("/search", response_model=SearchResult)
def search_posts(
    q: str = Query(..., min_length=1, max_length=200),
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    db: Session = Depends(get_db),
):
    cache_key = f"search:{q}:{page}:{page_size}"
    cached = get_cache(cache_key)
    if cached:
        return json.loads(cached)

    ts_query = func.plainto_tsquery("english", q)
    query = (
        db.query(Post)
        .filter(Post.status == PostStatus.published)
        .filter(Post.search_vector.op("@@")(ts_query))
    )
    total = query.count()
    posts = (
        query.order_by(
            func.ts_rank(Post.search_vector, ts_query).desc()
        )
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    items = [_post_to_published_response(p) for p in posts]
    response = {
        "items": items,
        "total": total,
        "query": q,
        "page": page,
        "page_size": page_size,
    }
    set_cache(cache_key, json.dumps(response))
    return response
