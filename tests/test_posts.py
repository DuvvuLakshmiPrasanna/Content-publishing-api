"""Tests for post CRUD and lifecycle operations."""
from datetime import datetime, timedelta


class TestCreatePost:
    def test_create_post(self, client, auth_headers):
        response = client.post("/posts", json={
            "title": "My First Post",
            "content": "Hello world!",
        }, headers=auth_headers)
        assert response.status_code == 201
        data = response.json()
        assert data["title"] == "My First Post"
        assert data["slug"] == "my-first-post"
        assert data["content"] == "Hello world!"
        assert data["status"] == "draft"

    def test_create_post_generates_unique_slug(self, client, auth_headers):
        client.post("/posts", json={"title": "Duplicate Title", "content": "First"}, headers=auth_headers)
        response = client.post("/posts", json={"title": "Duplicate Title", "content": "Second"}, headers=auth_headers)
        assert response.status_code == 201
        data = response.json()
        assert data["slug"] != "duplicate-title"  # should have been made unique
        assert data["slug"].startswith("duplicate-title")

    def test_create_post_empty_content(self, client, auth_headers):
        response = client.post("/posts", json={"title": "Title Only"}, headers=auth_headers)
        assert response.status_code == 201
        assert response.json()["content"] == ""


class TestListPosts:
    def test_list_own_posts(self, client, auth_headers):
        client.post("/posts", json={"title": "Post 1", "content": "Content 1"}, headers=auth_headers)
        client.post("/posts", json={"title": "Post 2", "content": "Content 2"}, headers=auth_headers)
        response = client.get("/posts", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 2
        assert len(data["items"]) == 2
        assert data["page"] == 1

    def test_list_posts_pagination(self, client, auth_headers):
        for i in range(15):
            client.post("/posts", json={"title": f"Post {i}", "content": f"Content {i}"}, headers=auth_headers)
        response = client.get("/posts?page=2&page_size=10", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 15
        assert data["page"] == 2
        assert len(data["items"]) == 5

    def test_author_cannot_see_other_authors_posts(self, client, auth_headers, auth_headers2):
        client.post("/posts", json={"title": "Author1 Post", "content": "Content"}, headers=auth_headers)
        response = client.get("/posts", headers=auth_headers2)
        assert response.status_code == 200
        assert response.json()["total"] == 0


class TestGetPost:
    def test_get_own_post(self, client, auth_headers):
        create_resp = client.post("/posts", json={"title": "Get Me", "content": "Here"}, headers=auth_headers)
        post_id = create_resp.json()["id"]
        response = client.get(f"/posts/{post_id}", headers=auth_headers)
        assert response.status_code == 200
        assert response.json()["title"] == "Get Me"

    def test_get_nonexistent_post(self, client, auth_headers):
        response = client.get("/posts/99999", headers=auth_headers)
        assert response.status_code == 404

    def test_cannot_get_other_authors_post(self, client, auth_headers, auth_headers2):
        create_resp = client.post("/posts", json={"title": "Private", "content": "Secret"}, headers=auth_headers)
        post_id = create_resp.json()["id"]
        response = client.get(f"/posts/{post_id}", headers=auth_headers2)
        assert response.status_code == 404


class TestUpdatePost:
    def test_update_post_title_and_content(self, client, auth_headers):
        create_resp = client.post("/posts", json={"title": "Original", "content": "Original content"}, headers=auth_headers)
        post_id = create_resp.json()["id"]
        response = client.put(f"/posts/{post_id}", json={
            "title": "Updated Title",
            "content": "Updated content",
        }, headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["title"] == "Updated Title"
        assert data["content"] == "Updated content"

    def test_update_creates_revision(self, client, auth_headers):
        create_resp = client.post("/posts", json={"title": "Version 1", "content": "Content v1"}, headers=auth_headers)
        post_id = create_resp.json()["id"]
        client.put(f"/posts/{post_id}", json={"title": "Version 2", "content": "Content v2"}, headers=auth_headers)
        revisions_resp = client.get(f"/posts/{post_id}/revisions", headers=auth_headers)
        assert revisions_resp.status_code == 200
        revisions = revisions_resp.json()
        assert len(revisions) == 1
        assert revisions[0]["title_snapshot"] == "Version 1"
        assert revisions[0]["content_snapshot"] == "Content v1"

    def test_cannot_update_other_authors_post(self, client, auth_headers, auth_headers2):
        create_resp = client.post("/posts", json={"title": "Mine", "content": "Content"}, headers=auth_headers)
        post_id = create_resp.json()["id"]
        response = client.put(f"/posts/{post_id}", json={"title": "Stolen"}, headers=auth_headers2)
        assert response.status_code == 404


class TestDeletePost:
    def test_delete_post(self, client, auth_headers):
        create_resp = client.post("/posts", json={"title": "Delete Me", "content": "Bye"}, headers=auth_headers)
        post_id = create_resp.json()["id"]
        response = client.delete(f"/posts/{post_id}", headers=auth_headers)
        assert response.status_code == 204
        get_resp = client.get(f"/posts/{post_id}", headers=auth_headers)
        assert get_resp.status_code == 404

    def test_cannot_delete_other_authors_post(self, client, auth_headers, auth_headers2):
        create_resp = client.post("/posts", json={"title": "Keep Me", "content": "Stay"}, headers=auth_headers)
        post_id = create_resp.json()["id"]
        response = client.delete(f"/posts/{post_id}", headers=auth_headers2)
        assert response.status_code == 404


class TestPublishPost:
    def test_publish_draft(self, client, auth_headers):
        create_resp = client.post("/posts", json={"title": "Publish Me", "content": "Content"}, headers=auth_headers)
        post_id = create_resp.json()["id"]
        response = client.post(f"/posts/{post_id}/publish", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "published"
        assert data["published_at"] is not None

    def test_publish_already_published(self, client, auth_headers):
        create_resp = client.post("/posts", json={"title": "Pub", "content": "Content"}, headers=auth_headers)
        post_id = create_resp.json()["id"]
        client.post(f"/posts/{post_id}/publish", headers=auth_headers)
        response = client.post(f"/posts/{post_id}/publish", headers=auth_headers)
        assert response.status_code == 400


class TestSchedulePost:
    def test_schedule_draft(self, client, auth_headers):
        create_resp = client.post("/posts", json={"title": "Schedule Me", "content": "Content"}, headers=auth_headers)
        post_id = create_resp.json()["id"]
        future = (datetime.utcnow() + timedelta(hours=1)).isoformat()
        response = client.post(f"/posts/{post_id}/schedule", json={"scheduled_for": future}, headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "scheduled"
        assert data["scheduled_for"] is not None

    def test_schedule_with_past_time(self, client, auth_headers):
        create_resp = client.post("/posts", json={"title": "Past", "content": "Content"}, headers=auth_headers)
        post_id = create_resp.json()["id"]
        past = (datetime.utcnow() - timedelta(hours=1)).isoformat()
        response = client.post(f"/posts/{post_id}/schedule", json={"scheduled_for": past}, headers=auth_headers)
        assert response.status_code == 400

    def test_cannot_schedule_published_post(self, client, auth_headers):
        create_resp = client.post("/posts", json={"title": "Published", "content": "Content"}, headers=auth_headers)
        post_id = create_resp.json()["id"]
        client.post(f"/posts/{post_id}/publish", headers=auth_headers)
        future = (datetime.utcnow() + timedelta(hours=1)).isoformat()
        response = client.post(f"/posts/{post_id}/schedule", json={"scheduled_for": future}, headers=auth_headers)
        assert response.status_code == 400
