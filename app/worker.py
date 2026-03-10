from datetime import datetime
from celery import Celery
from celery.schedules import crontab
from app.config import get_settings

settings = get_settings()

celery_app = Celery(
    "cms_worker",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    beat_schedule={
        "publish-scheduled-posts": {
            "task": "app.worker.publish_scheduled_posts",
            "schedule": 60.0,  # every 60 seconds
        },
    },
)


@celery_app.task(name="app.worker.publish_scheduled_posts", bind=True, max_retries=3)
def publish_scheduled_posts(self):
    """
    Background worker that finds all scheduled posts whose scheduled_for
    timestamp is in the past and publishes them transactionally.
    This task is idempotent - re-running won't cause issues.
    """
    from sqlalchemy.orm import Session
    from app.database import SessionLocal
    from app.models import Post, PostStatus
    from app.cache import invalidate_published_cache

    db: Session = SessionLocal()
    published_count = 0
    try:
        now = datetime.utcnow()
        # Find all scheduled posts whose time has come
        posts = (
            db.query(Post)
            .filter(Post.status == PostStatus.scheduled)
            .filter(Post.scheduled_for <= now)
            .all()
        )

        for post in posts:
            # Idempotent check: only publish if still scheduled
            if post.status == PostStatus.scheduled:
                post.status = PostStatus.published
                post.published_at = now
                post.updated_at = now
                published_count += 1

        if published_count > 0:
            db.commit()
            invalidate_published_cache()

        return {"published": published_count, "checked_at": now.isoformat()}
    except Exception as exc:
        db.rollback()
        raise self.retry(exc=exc, countdown=10)
    finally:
        db.close()
