"""Tests for caching behavior."""
from unittest.mock import patch, MagicMock


class TestCaching:
    def test_published_post_is_cached_on_read(self, client, auth_headers):
        resp = client.post("/posts", json={"title": "Cached Post", "content": "Content"}, headers=auth_headers)
        post_id = resp.json()["id"]
        client.post(f"/posts/{post_id}/publish", headers=auth_headers)

        # First read - cache miss, should read from DB
        response1 = client.get(f"/posts/published/{post_id}")
        assert response1.status_code == 200

        # Second read - should return same data (potentially from cache)
        response2 = client.get(f"/posts/published/{post_id}")
        assert response2.status_code == 200
        assert response1.json() == response2.json()

    def test_cache_invalidated_on_update(self, client, auth_headers):
        resp = client.post("/posts", json={"title": "Cache Invalidate", "content": "Original"}, headers=auth_headers)
        post_id = resp.json()["id"]
        client.post(f"/posts/{post_id}/publish", headers=auth_headers)

        # Read to cache
        client.get(f"/posts/published/{post_id}")

        # Update the post
        client.put(f"/posts/{post_id}", json={"content": "Updated content"}, headers=auth_headers)

        # Read again - should get updated content
        response = client.get(f"/posts/published/{post_id}")
        assert response.status_code == 200
        assert response.json()["content"] == "Updated content"

    def test_cache_invalidated_on_delete(self, client, auth_headers):
        resp = client.post("/posts", json={"title": "Delete Cache", "content": "Gone"}, headers=auth_headers)
        post_id = resp.json()["id"]
        client.post(f"/posts/{post_id}/publish", headers=auth_headers)

        # Read to cache
        client.get(f"/posts/published/{post_id}")

        # Delete
        client.delete(f"/posts/{post_id}", headers=auth_headers)

        # Should be 404 now
        response = client.get(f"/posts/published/{post_id}")
        assert response.status_code == 404
