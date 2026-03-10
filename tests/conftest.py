import os
import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from fastapi.testclient import TestClient

# Use test database URL
TEST_DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL",
    os.environ.get("DATABASE_URL", "postgresql://cms_user:cms_password@db:5432/cms_db"),
)

# Override before importing app modules
os.environ["DATABASE_URL"] = TEST_DATABASE_URL

from app.database import Base, get_db
from app.main import app
from app.models import User, UserRole
from app.auth import hash_password
from app.cache import redis_client

engine = create_engine(TEST_DATABASE_URL, pool_pre_ping=True)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db


@pytest.fixture(scope="session", autouse=True)
def setup_database():
    """Create all tables and the search trigger once per test session."""
    Base.metadata.create_all(bind=engine)
    # Create the search vector trigger if it doesn't exist
    with engine.connect() as conn:
        conn.execute(text("""
            CREATE OR REPLACE FUNCTION posts_search_vector_update() RETURNS trigger AS $$
            BEGIN
                NEW.search_vector := to_tsvector('english', COALESCE(NEW.title, '') || ' ' || COALESCE(NEW.content, ''));
                RETURN NEW;
            END;
            $$ LANGUAGE plpgsql;
        """))
        conn.execute(text("""
            DROP TRIGGER IF EXISTS posts_search_vector_trigger ON posts;
        """))
        conn.execute(text("""
            CREATE TRIGGER posts_search_vector_trigger
            BEFORE INSERT OR UPDATE OF title, content ON posts
            FOR EACH ROW EXECUTE FUNCTION posts_search_vector_update();
        """))
        conn.commit()
    yield


@pytest.fixture(autouse=True)
def clean_tables():
    """Clean all tables and Redis cache before each test, resetting sequences."""
    with engine.connect() as conn:
        conn.execute(text("TRUNCATE TABLE post_revisions, media, posts, users RESTART IDENTITY CASCADE"))
        conn.commit()
    try:
        redis_client.flushdb()
    except Exception:
        pass
    yield


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def db_session():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture
def author_user(db_session):
    user = User(
        username="testauthor",
        email="testauthor@example.com",
        password_hash=hash_password("password123"),
        role=UserRole.author,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def author2_user(db_session):
    user = User(
        username="testauthor2",
        email="testauthor2@example.com",
        password_hash=hash_password("password123"),
        role=UserRole.author,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def public_user(db_session):
    user = User(
        username="publicuser",
        email="publicuser@example.com",
        password_hash=hash_password("password123"),
        role=UserRole.public,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def auth_headers(client, author_user):
    response = client.post("/auth/login", json={
        "email": "testauthor@example.com",
        "password": "password123",
    })
    token = response.json()["token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def auth_headers2(client, author2_user):
    response = client.post("/auth/login", json={
        "email": "testauthor2@example.com",
        "password": "password123",
    })
    token = response.json()["token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def public_headers(client, public_user):
    response = client.post("/auth/login", json={
        "email": "publicuser@example.com",
        "password": "password123",
    })
    token = response.json()["token"]
    return {"Authorization": f"Bearer {token}"}
