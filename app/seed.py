"""Seed script to create initial users for testing."""
from app.database import SessionLocal
from app.models import User, UserRole
from app.auth import hash_password


def seed():
    db = SessionLocal()
    try:
        # Check if users already exist
        if db.query(User).first():
            print("Database already seeded. Skipping.")
            return

        users = [
            User(
                username="author1",
                email="author1@example.com",
                password_hash=hash_password("password123"),
                role=UserRole.author,
            ),
            User(
                username="author2",
                email="author2@example.com",
                password_hash=hash_password("password123"),
                role=UserRole.author,
            ),
            User(
                username="publicuser",
                email="public@example.com",
                password_hash=hash_password("password123"),
                role=UserRole.public,
            ),
        ]
        db.add_all(users)
        db.commit()
        print("Database seeded with initial users.")
    finally:
        db.close()


if __name__ == "__main__":
    seed()
