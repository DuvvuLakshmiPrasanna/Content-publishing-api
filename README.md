# Content Publishing API

A robust backend API for a content management system (CMS) that handles complex content lifecycles, including drafting, scheduling, and publishing. Features content versioning, scheduled publishing via background jobs, full-text search, and Redis caching.

## Tech Stack

| Component            | Technology                                                  |
| -------------------- | ----------------------------------------------------------- |
| **API Framework**    | FastAPI (Python 3.11)                                       |
| **Database**         | PostgreSQL 15 with full-text search (GIN indexes, tsvector) |
| **Cache**            | Redis 7                                                     |
| **Background Jobs**  | Celery with Redis broker + Celery Beat scheduler            |
| **ORM**              | SQLAlchemy 2.0                                              |
| **Migrations**       | Alembic                                                     |
| **Auth**             | JWT (python-jose + passlib/bcrypt)                          |
| **Containerization** | Docker + Docker Compose                                     |

## Architecture

See [ARCHITECTURE.md](ARCHITECTURE.md) for a detailed diagram and component descriptions.

## Quick Start

### Prerequisites

- Docker and Docker Compose installed on your machine.

### Running the Application

```bash
# Clone the repository
git clone <repository-url>
cd content-publishing-api

# Start all services (API, Worker, PostgreSQL, Redis)
docker-compose up --build
```

That's it! The application will:

1. Start PostgreSQL and Redis containers
2. Run database migrations automatically
3. Seed the database with initial test users
4. Start the FastAPI application on port 8000
5. Start the Celery background worker for scheduled publishing

### Access the API

- **API Base URL**: http://localhost:8000
- **Swagger UI (Interactive Docs)**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc
- **Health Check**: http://localhost:8000/health

### Default Users (Seeded)

| Username   | Email               | Password    | Role   |
| ---------- | ------------------- | ----------- | ------ |
| author1    | author1@example.com | password123 | author |
| author2    | author2@example.com | password123 | author |
| publicuser | public@example.com  | password123 | public |

## Running Tests

```bash
# Run tests inside Docker
docker-compose exec api pytest tests/ -v --tb=short

# Or run with coverage
docker-compose exec api pytest tests/ -v --cov=app --cov-report=term-missing
```

## API Documentation

### Authentication

#### Register a New User

```
POST /auth/register
```

**Request Body:**

```json
{
  "username": "newauthor",
  "email": "newauthor@example.com",
  "password": "securepassword"
}
```

**Response (201):**

```json
{
  "id": 4,
  "username": "newauthor",
  "role": "author"
}
```

#### Login

```
POST /auth/login
```

**Request Body:**

```json
{
  "email": "author1@example.com",
  "password": "password123"
}
```

**Response (200):**

```json
{
  "token": "eyJhbGciOiJIUzI1Ni...",
  "user": {
    "id": 1,
    "username": "author1",
    "role": "author"
  }
}
```

### Posts (Author Only - Requires JWT)

All author endpoints require the `Authorization: Bearer <token>` header.

#### Create Post

```
POST /posts
```

**Request Body:**

```json
{
  "title": "My First Blog Post",
  "content": "This is the content of my first blog post."
}
```

**Response (201):** Returns the created post with auto-generated slug and `draft` status.

#### List My Posts

```
GET /posts?page=1&page_size=10
```

Returns paginated list of the authenticated author's posts (all statuses).

#### Get Post

```
GET /posts/{id}
```

#### Update Post

```
PUT /posts/{id}
```

**Request Body:**

```json
{
  "title": "Updated Title",
  "content": "Updated content"
}
```

Automatically creates a revision of the previous state when title or content changes.

#### Delete Post

```
DELETE /posts/{id}
```

Returns `204 No Content`.

#### Publish Post

```
POST /posts/{id}/publish
```

Changes status from `draft`/`scheduled` to `published`. Sets `published_at` timestamp.

#### Schedule Post

```
POST /posts/{id}/schedule
```

**Request Body:**

```json
{
  "scheduled_for": "2026-03-15T10:00:00"
}
```

Changes status to `scheduled`. The background worker will automatically publish it at the scheduled time.

#### Get Post Revisions (Version History)

```
GET /posts/{id}/revisions
```

**Response (200):**

```json
[
  {
    "revision_id": 1,
    "post_id": 1,
    "title_snapshot": "Original Title",
    "content_snapshot": "Original content",
    "revision_author": "author1",
    "revision_timestamp": "2026-03-10T10:00:00"
  }
]
```

### Media (Author Only)

#### Upload Media

```
POST /media/upload
```

**Content-Type:** `multipart/form-data`
**Field:** `file` - Image file (jpg, jpeg, png, gif, webp, svg, bmp; max 10MB)

**Response (201):**

```json
{
  "id": 1,
  "filename": "abc123.png",
  "original_filename": "photo.png",
  "content_type": "image/png",
  "file_size": 12345,
  "url": "/uploads/abc123.png",
  "uploaded_at": "2026-03-10T10:00:00"
}
```

### Public Endpoints (No Auth Required)

#### List Published Posts

```
GET /posts/published?page=1&page_size=10
```

#### Get Published Post

```
GET /posts/published/{id}
```

#### Search Published Posts

```
GET /search?q=python&page=1&page_size=10
```

Full-text search on title and content of published posts using PostgreSQL's built-in text search capabilities with GIN indexes.

## Design Decisions

### Content Versioning

Every update to a post's title or content creates a snapshot (revision) of the previous state before applying changes. This is done within the same database transaction to ensure consistency.

### Scheduled Publishing

Celery Beat runs a periodic task every 60 seconds that queries for all posts with `status=scheduled` and `scheduled_for <= now()`. Each qualifying post is transactionally updated to `published` status. The worker is idempotent — re-running it on already published posts has no effect.

### Caching Strategy

A cache-aside (lazy-loading) strategy is used with Redis:

- Published posts are cached on first read with a 5-minute TTL
- Cache entries are invalidated when posts are updated, deleted, or status changes
- List and search caches are invalidated on any publish/unpublish operation

### Full-Text Search

PostgreSQL's native full-text search is used with:

- `tsvector` column on the posts table for pre-computed search vectors
- GIN index for fast lookups
- Automatic trigger to update search vectors on insert/update
- `plainto_tsquery` for natural language query parsing
- `ts_rank` for relevance-based ordering

### Security

- Passwords are hashed with bcrypt
- JWT tokens with configurable expiration
- Role-based access (author vs public)
- Authors can only manage their own posts
- File upload validation (extension whitelist, size limits)
- All database queries use parameterized queries via SQLAlchemy ORM (SQL injection prevention)
- All multi-table operations wrapped in transactions

## Project Structure

```
content-publishing-api/
├── app/
│   ├── __init__.py
│   ├── main.py              # FastAPI application entry point
│   ├── config.py             # Settings / environment configuration
│   ├── database.py           # SQLAlchemy engine and session
│   ├── models.py             # Database models (User, Post, PostRevision, Media)
│   ├── schemas.py            # Pydantic request/response schemas
│   ├── auth.py               # JWT authentication & authorization
│   ├── cache.py              # Redis caching layer
│   ├── worker.py             # Celery background worker for scheduled publishing
│   ├── seed.py               # Database seeding script
│   └── routes/
│       ├── __init__.py
│       ├── auth.py           # /auth/register, /auth/login
│       ├── posts.py          # /posts CRUD, publish, schedule, revisions
│       ├── public.py         # /posts/published, /search
│       └── media.py          # /media/upload
├── alembic/
│   ├── env.py
│   ├── script.py.mako
│   └── versions/
│       └── 001_initial_schema.py
├── tests/
│   ├── conftest.py           # Test fixtures and configuration
│   ├── test_auth.py          # Authentication & authorization tests
│   ├── test_posts.py         # Post CRUD & lifecycle tests
│   ├── test_versioning.py    # Content versioning tests
│   ├── test_worker.py        # Background worker tests
│   ├── test_public.py        # Public endpoints & search tests
│   ├── test_media.py         # Media upload tests
│   └── test_cache.py         # Caching behavior tests
├── docker-compose.yml
├── Dockerfile
├── requirements.txt
├── alembic.ini
├── submission.yml
├── ARCHITECTURE.md
└── README.md
```
