"""Tests for authentication and authorization."""


class TestRegistration:
    def test_register_new_user(self, client):
        response = client.post("/auth/register", json={
            "username": "newuser",
            "email": "newuser@example.com",
            "password": "password123",
        })
        assert response.status_code == 201
        data = response.json()
        assert data["username"] == "newuser"
        assert data["role"] == "author"
        assert "id" in data

    def test_register_duplicate_email(self, client, author_user):
        response = client.post("/auth/register", json={
            "username": "another",
            "email": "testauthor@example.com",
            "password": "password123",
        })
        assert response.status_code == 409

    def test_register_invalid_email(self, client):
        response = client.post("/auth/register", json={
            "username": "another",
            "email": "not-an-email",
            "password": "password123",
        })
        assert response.status_code == 422

    def test_register_short_password(self, client):
        response = client.post("/auth/register", json={
            "username": "another",
            "email": "another@example.com",
            "password": "12345",
        })
        assert response.status_code == 422


class TestLogin:
    def test_login_success(self, client, author_user):
        response = client.post("/auth/login", json={
            "email": "testauthor@example.com",
            "password": "password123",
        })
        assert response.status_code == 200
        data = response.json()
        assert "token" in data
        assert data["user"]["username"] == "testauthor"
        assert data["user"]["role"] == "author"

    def test_login_wrong_password(self, client, author_user):
        response = client.post("/auth/login", json={
            "email": "testauthor@example.com",
            "password": "wrongpassword",
        })
        assert response.status_code == 401

    def test_login_nonexistent_user(self, client):
        response = client.post("/auth/login", json={
            "email": "nobody@example.com",
            "password": "password123",
        })
        assert response.status_code == 401


class TestAuthorization:
    def test_protected_route_without_token(self, client):
        response = client.get("/posts")
        assert response.status_code == 401

    def test_protected_route_with_invalid_token(self, client):
        response = client.get("/posts", headers={"Authorization": "Bearer invalidtoken"})
        assert response.status_code == 401

    def test_public_user_cannot_create_post(self, client, public_headers):
        response = client.post("/posts", json={
            "title": "Test Post",
            "content": "Test content",
        }, headers=public_headers)
        assert response.status_code == 403
