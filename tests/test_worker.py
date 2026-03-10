"""Tests for the scheduled publishing background worker."""
from datetime import datetime, timedelta
from unittest.mock import patch
from app.models import Post, PostStatus


class TestScheduledWorker:
    def test_worker_publishes_due_posts(self, client, auth_headers, db_session):
        # Create and schedule a post
        create_resp = client.post("/posts", json={"title": "Scheduled Post", "content": "Content"}, headers=auth_headers)
        post_id = create_resp.json()["id"]

        # Manually set scheduled_for to past (simulating time passing)
        post = db_session.query(Post).filter(Post.id == post_id).first()
        post.status = PostStatus.scheduled
        post.scheduled_for = datetime.utcnow() - timedelta(minutes=5)
        db_session.commit()

        # Run the worker task directly
        from app.worker import publish_scheduled_posts
        result = publish_scheduled_posts()
        assert result["published"] == 1

        # Verify the post is now published
        db_session.expire_all()
        post = db_session.query(Post).filter(Post.id == post_id).first()
        assert post.status == PostStatus.published
        assert post.published_at is not None

    def test_worker_is_idempotent(self, client, auth_headers, db_session):
        create_resp = client.post("/posts", json={"title": "Idempotent", "content": "Content"}, headers=auth_headers)
        post_id = create_resp.json()["id"]

        post = db_session.query(Post).filter(Post.id == post_id).first()
        post.status = PostStatus.scheduled
        post.scheduled_for = datetime.utcnow() - timedelta(minutes=5)
        db_session.commit()

        from app.worker import publish_scheduled_posts

        # Run twice
        result1 = publish_scheduled_posts()
        result2 = publish_scheduled_posts()

        assert result1["published"] == 1
        assert result2["published"] == 0  # already published, nothing to do

    def test_worker_does_not_publish_future_posts(self, client, auth_headers, db_session):
        create_resp = client.post("/posts", json={"title": "Future Post", "content": "Content"}, headers=auth_headers)
        post_id = create_resp.json()["id"]

        post = db_session.query(Post).filter(Post.id == post_id).first()
        post.status = PostStatus.scheduled
        post.scheduled_for = datetime.utcnow() + timedelta(hours=2)
        db_session.commit()

        from app.worker import publish_scheduled_posts
        result = publish_scheduled_posts()
        assert result["published"] == 0

        db_session.expire_all()
        post = db_session.query(Post).filter(Post.id == post_id).first()
        assert post.status == PostStatus.scheduled
