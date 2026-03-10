# Architecture

## System Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                          Docker Compose Network                             │
│                                                                             │
│  ┌──────────────────────┐         ┌──────────────────────┐                  │
│  │                      │         │                      │                  │
│  │   FastAPI Server     │────────▶│   PostgreSQL 15      │                  │
│  │   (API Service)      │         │   (Primary DB)       │                  │
│  │                      │         │                      │                  │
│  │  ┌────────────────┐  │         │  ┌────────────────┐  │                  │
│  │  │ Auth Middleware │  │         │  │ users          │  │                  │
│  │  │ (JWT/RBAC)     │  │         │  │ posts          │  │                  │
│  │  ├────────────────┤  │         │  │ post_revisions │  │                  │
│  │  │ Route Handlers │  │         │  │ media          │  │                  │
│  │  │ - /auth/*      │  │         │  ├────────────────┤  │                  │
│  │  │ - /posts/*     │  │         │  │ GIN Index      │  │                  │
│  │  │ - /search      │  │         │  │ (Full-Text     │  │                  │
│  │  │ - /media/*     │  │         │  │  Search)       │  │                  │
│  │  │ - /posts/pub.* │  │         │  └────────────────┘  │                  │
│  │  └────────────────┘  │         └──────────────────────┘                  │
│  │          │           │                                                   │
│  │          ▼           │                                                   │
│  │  ┌────────────────┐  │         ┌──────────────────────┐                  │
│  │  │ Cache Layer    │──│────────▶│   Redis 7            │                  │
│  │  │ (Cache-Aside)  │  │         │   (Cache + Broker)   │                  │
│  │  └────────────────┘  │         │                      │                  │
│  │                      │         │  ┌────────────────┐  │                  │
│  │  Port: 8000          │         │  │ Cache Store    │  │                  │
│  └──────────────────────┘         │  │ (published     │  │                  │
│                                   │  │  posts, search │  │                  │
│                                   │  │  results)      │  │                  │
│  ┌──────────────────────┐         │  ├────────────────┤  │                  │
│  │                      │         │  │ Message Broker │  │                  │
│  │   Celery Worker      │────────▶│  │ (Celery tasks) │  │                  │
│  │   (Background Jobs)  │         │  └────────────────┘  │                  │
│  │                      │         │                      │                  │
│  │  ┌────────────────┐  │         │  Port: 6379          │                  │
│  │  │ Celery Beat    │  │         └──────────────────────┘                  │
│  │  │ (Scheduler)    │  │                                                   │
│  │  │ Every 60s      │  │                                                   │
│  │  ├────────────────┤  │                                                   │
│  │  │ Task:          │  │                                                   │
│  │  │ publish_       │──│─────────▶ PostgreSQL                              │
│  │  │ scheduled_     │  │           (Update status to 'published')          │
│  │  │ posts          │  │                                                   │
│  │  └────────────────┘  │                                                   │
│  │                      │                                                   │
│  └──────────────────────┘                                                   │
│                                                                             │
│  ┌──────────────────────┐                                                   │
│  │   Shared Volume      │                                                   │
│  │   /app/uploads       │                                                   │
│  │   (Media Storage)    │                                                   │
│  └──────────────────────┘                                                   │
└─────────────────────────────────────────────────────────────────────────────┘

                        External Clients
                    ┌───────────────────────┐
                    │  HTTP Requests         │
                    │  (Port 8000)           │
                    │                       │
                    │  Authors:             │
                    │  POST /auth/login     │
                    │  POST /posts          │
                    │  PUT  /posts/{id}     │
                    │  POST /posts/{id}/    │
                    │       publish         │
                    │  POST /media/upload   │
                    │                       │
                    │  Public:              │
                    │  GET /posts/published │
                    │  GET /search?q=...   │
                    └───────────────────────┘
```

## Component Descriptions

### 1. FastAPI Server (API Service)

The main application server built with FastAPI. It handles all HTTP requests and is the only service exposed to external clients (port 8000).

**Responsibilities:**

- JWT-based authentication and role-based authorization
- Content CRUD operations with transactional integrity
- Content versioning (creating revisions on updates)
- Content lifecycle management (draft → scheduled → published)
- Media file upload and serving
- Full-text search via PostgreSQL
- Cache management (read-through with invalidation)

**Key Design Choices:**

- Stateless design: All request context comes from the JWT token
- Dependency injection for database sessions and authentication
- Automatic slug generation with uniqueness guarantees

### 2. PostgreSQL 15 (Primary Database)

The relational database storing all persistent data.

**Tables:**

- `users` — User accounts with hashed passwords and roles
- `posts` — Content with status, slugs, and search vectors
- `post_revisions` — Historical snapshots of post content changes
- `media` — Metadata for uploaded media files

**Key Features:**

- Full-text search using `tsvector` column with GIN index
- Automatic search vector updates via database trigger
- Strategic indexes on status, scheduled_for, author_id, and foreign keys
- Enum types for user roles and post statuses

### 3. Redis 7 (Cache + Message Broker)

Serves dual purpose as both a caching layer and Celery message broker.

**Caching (Cache-Aside Strategy):**

- Published post data is cached on first read (5-minute TTL)
- Individual post cache: `published:post:{id}`
- List cache: `published:list:{page}:{page_size}`
- Search cache: `search:{query}:{page}:{page_size}`
- Cache invalidation occurs on: post update, post deletion, status change

**Message Broker:**

- Routes Celery task messages between the API and worker
- Stores task results and beat schedule state

### 4. Celery Worker (Background Jobs)

A separate containerized process that runs periodic and on-demand tasks.

**Scheduled Task: `publish_scheduled_posts`**

- Runs every 60 seconds via Celery Beat
- Queries for posts with `status = 'scheduled'` AND `scheduled_for <= NOW()`
- Transactionally updates each post to `status = 'published'` with `published_at` timestamp
- Invalidates relevant cache entries after publishing

**Idempotency:**

- Only processes posts still in `scheduled` status
- Running the task multiple times for the same post is safe
- Automatic retry on failure (max 3 retries with 10s backoff)

### 5. Shared Volume (Media Storage)

A Docker volume mounted at `/app/uploads` shared between the API and worker containers.

**Media Handling:**

- Files are validated for extension (whitelist) and size (max 10MB)
- Stored with UUID-based filenames to prevent collisions
- Served as static files by FastAPI's StaticFiles middleware

## Data Flow

### Content Creation & Update Flow

```
Client → POST /posts → Auth Middleware → Create Post → DB (insert) → Response
Client → PUT /posts/{id} → Auth Middleware → Begin Transaction
    → Save current state as revision (post_revisions)
    → Update post with new data
    → Commit Transaction
    → Invalidate Cache (if published)
    → Response
```

### Scheduled Publishing Flow

```
Celery Beat (every 60s) → Trigger publish_scheduled_posts task
    → Query: SELECT * FROM posts WHERE status='scheduled' AND scheduled_for <= NOW()
    → For each post: UPDATE status='published', published_at=NOW()
    → Commit Transaction
    → Invalidate published posts cache
```

### Search Flow

```
Client → GET /search?q=python
    → Check Redis cache
    → Cache HIT: Return cached results
    → Cache MISS:
        → PostgreSQL: to_tsvector('english', title || content) @@ plainto_tsquery('english', 'python')
        → Rank results by ts_rank
        → Cache results in Redis (5 min TTL)
        → Return results
```

### Caching Flow (Cache-Aside)

```
Read Path:
    Client → GET /posts/published/{id}
        → Check Redis (published:post:{id})
        → HIT: Return cached data
        → MISS: Query DB → Store in Redis → Return data

Write Path (Invalidation):
    Client → PUT /posts/{id}
        → Update DB
        → DELETE Redis key (published:post:{id})
        → DELETE Redis keys (published:list:*, search:*)
```

## Security Architecture

1. **Authentication**: JWT tokens with configurable expiration, signed with HS256
2. **Authorization**: Role-based (author/public) enforced at the route level via FastAPI dependencies
3. **Data Isolation**: Authors can only access/modify their own posts
4. **Password Security**: bcrypt hashing with automatic salt
5. **Input Validation**: Pydantic schemas validate all inputs; SQLAlchemy provides parameterized queries
6. **File Upload Security**: Extension whitelist, size limits, UUID filenames
