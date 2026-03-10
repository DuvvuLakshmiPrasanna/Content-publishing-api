"""Tests for media upload functionality."""
import io


class TestMediaUpload:
    def test_upload_image(self, client, auth_headers):
        # Create a fake image file
        file_content = b"\x89PNG\r\n\x1a\n" + b"\x00" * 100
        response = client.post(
            "/media/upload",
            files={"file": ("test_image.png", io.BytesIO(file_content), "image/png")},
            headers=auth_headers,
        )
        assert response.status_code == 201
        data = response.json()
        assert data["original_filename"] == "test_image.png"
        assert data["content_type"] == "image/png"
        assert data["url"].startswith("/uploads/")
        assert data["file_size"] > 0

    def test_upload_requires_auth(self, client):
        file_content = b"\x89PNG\r\n\x1a\n" + b"\x00" * 100
        response = client.post(
            "/media/upload",
            files={"file": ("test.png", io.BytesIO(file_content), "image/png")},
        )
        assert response.status_code == 401

    def test_upload_disallowed_extension(self, client, auth_headers):
        response = client.post(
            "/media/upload",
            files={"file": ("malicious.exe", io.BytesIO(b"bad"), "application/octet-stream")},
            headers=auth_headers,
        )
        assert response.status_code == 400

    def test_upload_public_user_forbidden(self, client, public_headers):
        file_content = b"\x89PNG\r\n\x1a\n" + b"\x00" * 100
        response = client.post(
            "/media/upload",
            files={"file": ("test.png", io.BytesIO(file_content), "image/png")},
            headers=public_headers,
        )
        assert response.status_code == 403
