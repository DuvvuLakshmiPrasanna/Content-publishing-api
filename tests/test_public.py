"""Tests for public endpoints and full-text search."""


class TestPublicEndpoints:
    def test_list_published_posts(self, client, auth_headers):
        # Create and publish posts
        for i in range(3):
            resp = client.post("/posts", json={"title": f"Public Post {i}", "content": f"Content {i}"}, headers=auth_headers)
            client.post(f"/posts/{resp.json()['id']}/publish", headers=auth_headers)

        # Also create a draft (should not appear)
        client.post("/posts", json={"title": "Draft Post", "content": "Draft"}, headers=auth_headers)

        response = client.get("/posts/published")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 3
        assert len(data["items"]) == 3

    def test_list_published_pagination(self, client, auth_headers):
        for i in range(15):
            resp = client.post("/posts", json={"title": f"Paginated Post {i}", "content": f"Content {i}"}, headers=auth_headers)
            client.post(f"/posts/{resp.json()['id']}/publish", headers=auth_headers)

        response = client.get("/posts/published?page=2&page_size=10")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 15
        assert data["page"] == 2
        assert len(data["items"]) == 5

    def test_get_published_post(self, client, auth_headers):
        resp = client.post("/posts", json={"title": "Viewable Post", "content": "Interesting content"}, headers=auth_headers)
        post_id = resp.json()["id"]
        client.post(f"/posts/{post_id}/publish", headers=auth_headers)

        response = client.get(f"/posts/published/{post_id}")
        assert response.status_code == 200
        data = response.json()
        assert data["title"] == "Viewable Post"
        assert data["author"] == "testauthor"

    def test_get_draft_post_via_public(self, client, auth_headers):
        resp = client.post("/posts", json={"title": "Draft", "content": "Hidden"}, headers=auth_headers)
        post_id = resp.json()["id"]

        response = client.get(f"/posts/published/{post_id}")
        assert response.status_code == 404

    def test_public_endpoints_no_auth_required(self, client, auth_headers):
        resp = client.post("/posts", json={"title": "No Auth Needed", "content": "Public"}, headers=auth_headers)
        client.post(f"/posts/{resp.json()['id']}/publish", headers=auth_headers)

        # No auth headers
        response = client.get("/posts/published")
        assert response.status_code == 200


class TestSearch:
    def test_search_published_posts(self, client, auth_headers):
        resp = client.post("/posts", json={
            "title": "Python Programming Guide",
            "content": "Learn Python programming from scratch with this comprehensive guide.",
        }, headers=auth_headers)
        client.post(f"/posts/{resp.json()['id']}/publish", headers=auth_headers)

        resp2 = client.post("/posts", json={
            "title": "JavaScript Basics",
            "content": "Introduction to JavaScript for beginners.",
        }, headers=auth_headers)
        client.post(f"/posts/{resp2.json()['id']}/publish", headers=auth_headers)

        response = client.get("/search?q=Python")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] >= 1
        assert data["query"] == "Python"
        # The Python post should be in results
        titles = [item["title"] for item in data["items"]]
        assert "Python Programming Guide" in titles

    def test_search_does_not_return_drafts(self, client, auth_headers):
        client.post("/posts", json={
            "title": "Secret Draft about Unicorns",
            "content": "This is a secret draft about unicorns.",
        }, headers=auth_headers)

        response = client.get("/search?q=Unicorns")
        assert response.status_code == 200
        assert response.json()["total"] == 0

    def test_search_no_results(self, client):
        response = client.get("/search?q=xyznonexistent")
        assert response.status_code == 200
        assert response.json()["total"] == 0

    def test_search_requires_query(self, client):
        response = client.get("/search")
        assert response.status_code == 422
