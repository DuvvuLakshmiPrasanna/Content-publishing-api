from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
import os
from app.config import get_settings
from app.routes import auth, posts, public, media

settings = get_settings()

app = FastAPI(
    title="Content Publishing API",
    description="A robust CMS API with scheduled publishing, content versioning, and full-text search.",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount uploads directory for serving media files
upload_dir = settings.MEDIA_UPLOAD_DIR
os.makedirs(upload_dir, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=upload_dir), name="uploads")

# Include routers (public before posts so /posts/published matches before /posts/{id})
app.include_router(auth.router)
app.include_router(public.router)
app.include_router(posts.router)
app.include_router(media.router)


@app.get("/health", tags=["Health"])
def health_check():
    return {"status": "healthy"}
