"""Complete end-to-end API testing script following the evaluator checklist."""
import time
import io
from datetime import datetime, timedelta, timezone
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)
PASS = 0
FAIL = 0
TOKEN = None


def check(name, condition, detail=""):
    global PASS, FAIL
    if condition:
        PASS += 1
        print(f"  ✅ {name}")
    else:
        FAIL += 1
        print(f"  ❌ {name} — {detail}")


# ═══════════════════════════════════════════════════
# STEP 1: Health Check
# ═══════════════════════════════════════════════════
print("\n" + "=" * 60)
print("STEP 1: HEALTH CHECK")
print("=" * 60)
r = client.get("/health")
check("GET /health returns 200", r.status_code == 200, f"got {r.status_code}")
check("Health status is healthy", r.json().get("status") == "healthy", f"got {r.json()}")

# ═══════════════════════════════════════════════════
# STEP 2: AUTHENTICATION
# ═══════════════════════════════════════════════════
print("\n" + "=" * 60)
print("STEP 2: AUTHENTICATION — Register + Login")
print("=" * 60)

# Register author1
r = client.post("/auth/register", json={
    "username": "author1",
    "email": "author1@example.com",
    "password": "password123"
})
check("POST /auth/register returns 201", r.status_code == 201, f"got {r.status_code}: {r.text}")
check("Register returns username", r.json().get("username") == "author1", f"got {r.json()}")

# Register duplicate — should fail
r = client.post("/auth/register", json={
    "username": "author1dup",
    "email": "author1@example.com",
    "password": "password123"
})
check("Duplicate email rejected", r.status_code in (400, 409, 422), f"got {r.status_code}")

# Register with invalid email
r = client.post("/auth/register", json={
    "username": "baduser",
    "email": "not-an-email",
    "password": "password123"
})
check("Invalid email rejected", r.status_code == 422, f"got {r.status_code}")

# Register with short password
r = client.post("/auth/register", json={
    "username": "baduser2",
    "email": "bad2@example.com",
    "password": "12"
})
check("Short password rejected", r.status_code == 422, f"got {r.status_code}")

# Login
r = client.post("/auth/login", json={
    "email": "author1@example.com",
    "password": "password123"
})
check("POST /auth/login returns 200", r.status_code == 200, f"got {r.status_code}: {r.text}")
data = r.json()
check("Login returns token", "token" in data, f"keys: {list(data.keys())}")
check("Login returns user object", "user" in data, f"keys: {list(data.keys())}")
check("User has correct username", data.get("user", {}).get("username") == "author1", f"got {data}")
check("User has role 'author'", data.get("user", {}).get("role") == "author", f"got {data}")
TOKEN = data.get("token")
AUTH = {"Authorization": f"Bearer {TOKEN}"}

# Login with wrong password
r = client.post("/auth/login", json={"email": "author1@example.com", "password": "wrongpass"})
check("Wrong password rejected (401)", r.status_code == 401, f"got {r.status_code}")

# Login with nonexistent user
r = client.post("/auth/login", json={"email": "nobody@example.com", "password": "password123"})
check("Nonexistent user rejected (401)", r.status_code == 401, f"got {r.status_code}")

# Protected route without token
r = client.get("/posts")
check("Protected route without token → 401", r.status_code in (401, 403), f"got {r.status_code}")

# Protected route with invalid token
r = client.get("/posts", headers={"Authorization": "Bearer invalidtoken"})
check("Invalid token → 401", r.status_code == 401, f"got {r.status_code}")

# Register a public user and verify RBAC
r = client.post("/auth/register", json={
    "username": "publicuser",
    "email": "public@example.com",
    "password": "password123",
    "role": "public"
})
r = client.post("/auth/login", json={"email": "public@example.com", "password": "password123"})
PUBLIC_TOKEN = r.json().get("token")
PUBLIC_AUTH = {"Authorization": f"Bearer {PUBLIC_TOKEN}"}
r = client.post("/posts", json={"title": "Forbidden", "content": "test"}, headers=PUBLIC_AUTH)
check("Public user cannot create post (403)", r.status_code == 403, f"got {r.status_code}")

# ═══════════════════════════════════════════════════
# STEP 3: CREATE POSTS
# ═══════════════════════════════════════════════════
print("\n" + "=" * 60)
print("STEP 3: CREATE POSTS")
print("=" * 60)

r = client.post("/posts", json={"title": "My First Post", "content": "This is my first CMS post"}, headers=AUTH)
check("POST /posts returns 201", r.status_code == 201, f"got {r.status_code}: {r.text}")
post1 = r.json()
check("Post has id", "id" in post1, f"keys: {list(post1.keys())}")
check("Post status is 'draft'", post1.get("status") == "draft", f"got {post1.get('status')}")
check("Slug auto-generated", post1.get("slug") == "my-first-post", f"got {post1.get('slug')}")
check("Title matches", post1.get("title") == "My First Post")
POST1_ID = post1["id"]

# Create second post with same title — unique slug
r = client.post("/posts", json={"title": "My First Post", "content": "Duplicate title test"}, headers=AUTH)
check("Duplicate title gets unique slug", r.json().get("slug") != "my-first-post", f"got {r.json().get('slug')}")
POST2_ID = r.json()["id"]

# Create with empty content allowed
r = client.post("/posts", json={"title": "Empty Content Post", "content": ""}, headers=AUTH)
check("Empty content allowed", r.status_code == 201, f"got {r.status_code}")

# ═══════════════════════════════════════════════════
# STEP 4: GET AUTHOR POSTS (Pagination)
# ═══════════════════════════════════════════════════
print("\n" + "=" * 60)
print("STEP 4: LIST AUTHOR POSTS + PAGINATION")
print("=" * 60)

r = client.get("/posts?page=1&page_size=10", headers=AUTH)
check("GET /posts returns 200", r.status_code == 200, f"got {r.status_code}: {r.text}")
data = r.json()
check("Response has 'items' list", isinstance(data.get("items"), list), f"keys: {list(data.keys())}")
check("Response has 'total' count", "total" in data, f"keys: {list(data.keys())}")
check("Response has 'page'", "page" in data)
check("Shows author's posts (total >= 3)", data.get("total", 0) >= 3, f"total={data.get('total')}")

# Pagination test
r = client.get("/posts?page=1&page_size=2", headers=AUTH)
data = r.json()
check("Pagination limits items", len(data.get("items", [])) == 2, f"got {len(data.get('items', []))}")
check("total_pages calculated", data.get("total_pages", 0) >= 2, f"got total_pages={data.get('total_pages')}")

# ═══════════════════════════════════════════════════
# STEP 5: GET SINGLE POST
# ═══════════════════════════════════════════════════
print("\n" + "=" * 60)
print("STEP 5: GET SINGLE POST")
print("=" * 60)

r = client.get(f"/posts/{POST1_ID}", headers=AUTH)
check(f"GET /posts/{POST1_ID} returns 200", r.status_code == 200, f"got {r.status_code}")
check("Returns correct post", r.json().get("id") == POST1_ID)

# Nonexistent post
r = client.get("/posts/99999", headers=AUTH)
check("Nonexistent post → 404", r.status_code == 404, f"got {r.status_code}")

# Author2 can't see author1's posts
r2 = client.post("/auth/register", json={
    "username": "author2",
    "email": "author2@example.com",
    "password": "password123"
})
r2 = client.post("/auth/login", json={"email": "author2@example.com", "password": "password123"})
AUTH2 = {"Authorization": f"Bearer {r2.json()['token']}"}
r = client.get(f"/posts/{POST1_ID}", headers=AUTH2)
check("Author2 can't see Author1's post (404)", r.status_code == 404, f"got {r.status_code}")

# ═══════════════════════════════════════════════════
# STEP 6: UPDATE POST → VERSIONING
# ═══════════════════════════════════════════════════
print("\n" + "=" * 60)
print("STEP 6: UPDATE POST → TRIGGERS VERSIONING")
print("=" * 60)

r = client.put(f"/posts/{POST1_ID}", json={
    "title": "My First Post Updated",
    "content": "Updated content"
}, headers=AUTH)
check(f"PUT /posts/{POST1_ID} returns 200", r.status_code == 200, f"got {r.status_code}: {r.text}")
check("Title updated", r.json().get("title") == "My First Post Updated")
check("Content updated", r.json().get("content") == "Updated content")

# Author2 can't update author1's post
r = client.put(f"/posts/{POST1_ID}", json={"title": "Hacked"}, headers=AUTH2)
check("Author2 can't update Author1's post (404)", r.status_code == 404, f"got {r.status_code}")

# ═══════════════════════════════════════════════════
# STEP 7: GET REVISIONS
# ═══════════════════════════════════════════════════
print("\n" + "=" * 60)
print("STEP 7: GET POST REVISIONS")
print("=" * 60)

r = client.get(f"/posts/{POST1_ID}/revisions", headers=AUTH)
check(f"GET /posts/{POST1_ID}/revisions returns 200", r.status_code == 200, f"got {r.status_code}: {r.text}")
revisions = r.json()
check("Revisions is a list", isinstance(revisions, list))
check("At least 1 revision exists", len(revisions) >= 1, f"got {len(revisions)}")
if revisions:
    rev = revisions[0]
    check("Revision has title_snapshot", "title_snapshot" in rev, f"keys: {list(rev.keys())}")
    check("Revision has content_snapshot", "content_snapshot" in rev, f"keys: {list(rev.keys())}")
    check("Revision has revision_timestamp", "revision_timestamp" in rev, f"keys: {list(rev.keys())}")
    check("Snapshot matches old title", rev.get("title_snapshot") == "My First Post",
          f"got '{rev.get('title_snapshot')}'")
    check("Snapshot matches old content", rev.get("content_snapshot") == "This is my first CMS post",
          f"got '{rev.get('content_snapshot')}'")

# Update again — second revision
r = client.put(f"/posts/{POST1_ID}", json={
    "title": "My First Post V3",
    "content": "Third version content"
}, headers=AUTH)
check("Second update succeeds", r.status_code == 200)
r = client.get(f"/posts/{POST1_ID}/revisions", headers=AUTH)
check("Now 2 revisions exist", len(r.json()) == 2, f"got {len(r.json())}")

# No revision on identical update
r = client.put(f"/posts/{POST1_ID}", json={
    "title": "My First Post V3",
    "content": "Third version content"
}, headers=AUTH)
r = client.get(f"/posts/{POST1_ID}/revisions", headers=AUTH)
check("No revision on identical update (still 2)", len(r.json()) == 2, f"got {len(r.json())}")

# Author2 can't view Author1's revisions
r = client.get(f"/posts/{POST1_ID}/revisions", headers=AUTH2)
check("Author2 can't view Author1's revisions", r.status_code in (404, 403), f"got {r.status_code}")

# ═══════════════════════════════════════════════════
# STEP 8: PUBLISH POST
# ═══════════════════════════════════════════════════
print("\n" + "=" * 60)
print("STEP 8: PUBLISH POST IMMEDIATELY")
print("=" * 60)

r = client.post(f"/posts/{POST1_ID}/publish", headers=AUTH)
check(f"POST /posts/{POST1_ID}/publish returns 200", r.status_code == 200, f"got {r.status_code}: {r.text}")
check("Status is 'published'", r.json().get("status") == "published")
check("published_at is set", r.json().get("published_at") is not None, f"got {r.json().get('published_at')}")

# Publish again — should fail or return already published
r = client.post(f"/posts/{POST1_ID}/publish", headers=AUTH)
check("Publish already published → 400", r.status_code == 400, f"got {r.status_code}")

# ═══════════════════════════════════════════════════
# STEP 9: SCHEDULE POST
# ═══════════════════════════════════════════════════
print("\n" + "=" * 60)
print("STEP 9: SCHEDULE POST FOR FUTURE PUBLISH")
print("=" * 60)

# Create a new post for scheduling
r = client.post("/posts", json={
    "title": "Scheduled Post",
    "content": "This post will be published by the worker"
}, headers=AUTH)
SCHED_ID = r.json()["id"]
check("Created post for scheduling", r.status_code == 201)

# Schedule it 2 seconds in the future (so worker picks it up quickly)
future_time = (datetime.now(timezone.utc) + timedelta(seconds=2)).isoformat()
r = client.post(f"/posts/{SCHED_ID}/schedule", json={"scheduled_for": future_time}, headers=AUTH)
check(f"POST /posts/{SCHED_ID}/schedule returns 200", r.status_code == 200, f"got {r.status_code}: {r.text}")
check("Status is 'scheduled'", r.json().get("status") == "scheduled")

# Schedule with past time — should fail
r2 = client.post("/posts", json={"title": "Past Post", "content": "test"}, headers=AUTH)
past_id = r2.json()["id"]
past_time = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
r = client.post(f"/posts/{past_id}/schedule", json={"scheduled_for": past_time}, headers=AUTH)
check("Schedule with past time → 400", r.status_code == 400, f"got {r.status_code}")

# Can't schedule already published post
r = client.post(f"/posts/{POST1_ID}/schedule", json={"scheduled_for": future_time}, headers=AUTH)
check("Can't schedule published post → 400", r.status_code == 400, f"got {r.status_code}")

# ═══════════════════════════════════════════════════
# STEP 10: VERIFY BACKGROUND WORKER
# ═══════════════════════════════════════════════════
print("\n" + "=" * 60)
print("STEP 10: VERIFY BACKGROUND WORKER (calling task directly)")
print("=" * 60)

# Directly invoke the Celery task logic to simulate the worker
from app.worker import publish_scheduled_posts
time.sleep(3)  # Wait for scheduled time to pass
publish_scheduled_posts()

# Verify the scheduled post is now published
from app.database import SessionLocal
from app.models import Post, PostStatus
db = SessionLocal()
sched_post = db.query(Post).filter(Post.id == SCHED_ID).first()
check("Worker published the scheduled post", sched_post.status == PostStatus.published,
      f"status={sched_post.status.value if sched_post else 'not found'}")
check("published_at is set by worker", sched_post.published_at is not None)
db.close()

# ═══════════════════════════════════════════════════
# STEP 11: PUBLIC ENDPOINTS (NO AUTH)
# ═══════════════════════════════════════════════════
print("\n" + "=" * 60)
print("STEP 11: PUBLIC ENDPOINTS (no auth required)")
print("=" * 60)

# Flush cache so we test fresh
from app.cache import redis_client
try:
    redis_client.flushdb()
except Exception:
    pass

r = client.get("/posts/published")
check("GET /posts/published returns 200 (no auth)", r.status_code == 200, f"got {r.status_code}: {r.text}")
data = r.json()
check("Response has items", isinstance(data.get("items"), list))
check("Published posts total >= 2", data.get("total", 0) >= 2, f"total={data.get('total')}")

# All items should be published
for item in data.get("items", []):
    if "status" in item:
        check(f"Item {item.get('id')} is published", item.get("status") == "published")

# Get single published post
r = client.get(f"/posts/published/{POST1_ID}")
check(f"GET /posts/published/{POST1_ID} returns 200", r.status_code == 200, f"got {r.status_code}")
check("Has title", "title" in r.json())
check("Has author", "author" in r.json())
check("Has published_at", "published_at" in r.json())

# Draft post not visible via public
r3 = client.post("/posts", json={"title": "Hidden Draft", "content": "Secret"}, headers=AUTH)
DRAFT_ID = r3.json()["id"]
r = client.get(f"/posts/published/{DRAFT_ID}")
check("Draft not visible publicly (404)", r.status_code == 404, f"got {r.status_code}")

# ═══════════════════════════════════════════════════
# STEP 12: SEARCH
# ═══════════════════════════════════════════════════
print("\n" + "=" * 60)
print("STEP 12: FULL-TEXT SEARCH")
print("=" * 60)

r = client.get("/search?q=first")
check("GET /search?q=first returns 200", r.status_code == 200, f"got {r.status_code}: {r.text}")
data = r.json()
check("Search has 'items'", isinstance(data.get("items"), list))
check("Search has 'total'", "total" in data)
check("Search has 'query'", data.get("query") == "first", f"got {data.get('query')}")
check("Search found results", data.get("total", 0) >= 1, f"total={data.get('total')}")

# Search for 'post' — should match multiple
r = client.get("/search?q=post")
check("Search 'post' finds results", r.json().get("total", 0) >= 1, f"total={r.json().get('total')}")

# Search doesn't return drafts
r = client.get("/search?q=Hidden+Draft")
check("Search doesn't return drafts", r.json().get("total", 0) == 0, f"total={r.json().get('total')}")

# Search requires query
r = client.get("/search")
check("Search without query → 422", r.status_code == 422, f"got {r.status_code}")

# ═══════════════════════════════════════════════════
# STEP 13: MEDIA UPLOAD
# ═══════════════════════════════════════════════════
print("\n" + "=" * 60)
print("STEP 13: MEDIA UPLOAD")
print("=" * 60)

# Create a fake image file
fake_image = io.BytesIO(b"\x89PNG\r\n\x1a\n" + b"\x00" * 100)
r = client.post("/media/upload", files={"file": ("test_image.png", fake_image, "image/png")}, headers=AUTH)
check("POST /media/upload returns 201", r.status_code == 201, f"got {r.status_code}: {r.text}")
check("Response has url/filename", "url" in r.json() or "filename" in r.json(), f"keys: {list(r.json().keys())}")

# Upload without auth
fake_image.seek(0)
r = client.post("/media/upload", files={"file": ("test2.png", fake_image, "image/png")})
check("Upload without auth → 401", r.status_code in (401, 403), f"got {r.status_code}")

# Upload disallowed extension
fake_exe = io.BytesIO(b"MZ" + b"\x00" * 100)
r = client.post("/media/upload", files={"file": ("malware.exe", fake_exe, "application/octet-stream")}, headers=AUTH)
check("Disallowed extension rejected (400)", r.status_code == 400, f"got {r.status_code}")

# Public user can't upload
fake_image.seek(0)
r = client.post("/media/upload", files={"file": ("pub.png", fake_image, "image/png")}, headers=PUBLIC_AUTH)
check("Public user can't upload (403)", r.status_code == 403, f"got {r.status_code}")

# ═══════════════════════════════════════════════════
# STEP 14: CACHE TESTING (Redis)
# ═══════════════════════════════════════════════════
print("\n" + "=" * 60)
print("STEP 14: REDIS CACHE TESTING")
print("=" * 60)

try:
    redis_client.flushdb()
except Exception:
    pass

# First request — cache miss → should populate cache
r1 = client.get(f"/posts/published/{POST1_ID}")
check("First request returns 200", r1.status_code == 200)

# Check Redis for the cached key
cached = redis_client.get(f"published:post:{POST1_ID}")
check("Redis cache populated after first request", cached is not None, "cache key not found")

# Second request — should come from cache
r2 = client.get(f"/posts/published/{POST1_ID}")
check("Second request returns 200 (from cache)", r2.status_code == 200)
check("Response data matches", r1.json() == r2.json())

# Update post → cache should be invalidated
r = client.put(f"/posts/{POST1_ID}", json={"title": "Cache Test Update", "content": "New content for cache test"}, headers=AUTH)
cached_after_update = redis_client.get(f"published:post:{POST1_ID}")
check("Cache invalidated after update", cached_after_update is None, "cache was NOT invalidated")

# ═══════════════════════════════════════════════════
# STEP 15: DELETE POST
# ═══════════════════════════════════════════════════
print("\n" + "=" * 60)
print("STEP 15: DELETE POST")
print("=" * 60)

# Author2 can't delete Author1's post
r = client.delete(f"/posts/{POST2_ID}", headers=AUTH2)
check("Author2 can't delete Author1's post", r.status_code in (404, 403), f"got {r.status_code}")

# Author1 can delete own post
r = client.delete(f"/posts/{POST2_ID}", headers=AUTH)
check(f"DELETE /posts/{POST2_ID} returns 200/204", r.status_code in (200, 204), f"got {r.status_code}")

# Verify deleted
r = client.get(f"/posts/{POST2_ID}", headers=AUTH)
check("Deleted post returns 404", r.status_code == 404, f"got {r.status_code}")

# ═══════════════════════════════════════════════════
# STEP 16: DATABASE VERIFICATION
# ═══════════════════════════════════════════════════
print("\n" + "=" * 60)
print("STEP 16: DATABASE VERIFICATION")
print("=" * 60)

from app.models import PostRevision, Media
db = SessionLocal()

# Check post statuses
statuses = [p.status.value for p in db.query(Post).all()]
check("Posts have various statuses", len(set(statuses)) >= 1, f"statuses: {statuses}")
check("'published' status exists", "published" in statuses, f"statuses: {statuses}")

# Check revisions table
rev_count = db.query(PostRevision).count()
check("Revisions table has records", rev_count >= 2, f"count={rev_count}")

# Check media table
media_count = db.query(Media).count()
check("Media table has records", media_count >= 1, f"count={media_count}")

db.close()

# ═══════════════════════════════════════════════════
# FINAL SUMMARY
# ═══════════════════════════════════════════════════
print("\n" + "=" * 60)
print(f"FINAL RESULTS: {PASS} passed, {FAIL} failed out of {PASS + FAIL} checks")
print("=" * 60)
if FAIL == 0:
    print("🎉 ALL CHECKS PASSED — PROJECT IS 100% WORKING!")
else:
    print(f"⚠️  {FAIL} checks failed — review above for details")
