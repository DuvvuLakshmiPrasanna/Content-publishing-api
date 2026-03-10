"""Tests for content versioning."""


class TestVersioning:
    def test_multiple_updates_create_revisions(self, client, auth_headers):
        create_resp = client.post("/posts", json={"title": "V1", "content": "C1"}, headers=auth_headers)
        post_id = create_resp.json()["id"]

        client.put(f"/posts/{post_id}", json={"title": "V2", "content": "C2"}, headers=auth_headers)
        client.put(f"/posts/{post_id}", json={"title": "V3", "content": "C3"}, headers=auth_headers)
        client.put(f"/posts/{post_id}", json={"title": "V4", "content": "C4"}, headers=auth_headers)

        response = client.get(f"/posts/{post_id}/revisions", headers=auth_headers)
        assert response.status_code == 200
        revisions = response.json()
        assert len(revisions) == 3

        # Revisions should be in ascending order of timestamp
        assert revisions[0]["title_snapshot"] == "V1"
        assert revisions[0]["content_snapshot"] == "C1"
        assert revisions[1]["title_snapshot"] == "V2"
        assert revisions[1]["content_snapshot"] == "C2"
        assert revisions[2]["title_snapshot"] == "V3"
        assert revisions[2]["content_snapshot"] == "C3"

    def test_no_revision_on_identical_update(self, client, auth_headers):
        create_resp = client.post("/posts", json={"title": "Same", "content": "Same"}, headers=auth_headers)
        post_id = create_resp.json()["id"]

        # Sending same data should not create a revision
        client.put(f"/posts/{post_id}", json={"title": "Same", "content": "Same"}, headers=auth_headers)

        response = client.get(f"/posts/{post_id}/revisions", headers=auth_headers)
        assert response.status_code == 200
        assert len(response.json()) == 0

    def test_revision_includes_author(self, client, auth_headers):
        create_resp = client.post("/posts", json={"title": "Auth", "content": "Content"}, headers=auth_headers)
        post_id = create_resp.json()["id"]
        client.put(f"/posts/{post_id}", json={"title": "Updated", "content": "New"}, headers=auth_headers)

        response = client.get(f"/posts/{post_id}/revisions", headers=auth_headers)
        revisions = response.json()
        assert len(revisions) == 1
        assert revisions[0]["revision_author"] == "testauthor"
        assert revisions[0]["revision_timestamp"] is not None

    def test_cannot_view_other_authors_revisions(self, client, auth_headers, auth_headers2):
        create_resp = client.post("/posts", json={"title": "Private", "content": "Content"}, headers=auth_headers)
        post_id = create_resp.json()["id"]
        client.put(f"/posts/{post_id}", json={"title": "Updated"}, headers=auth_headers)

        response = client.get(f"/posts/{post_id}/revisions", headers=auth_headers2)
        assert response.status_code == 404
