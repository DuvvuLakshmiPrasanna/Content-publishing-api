import os
import uuid
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, status
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import Media, User
from app.schemas import MediaResponse
from app.auth import require_author
from app.config import get_settings

settings = get_settings()
router = APIRouter(prefix="/media", tags=["Media"])

ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".svg", ".bmp"}
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB


@router.post("/upload", response_model=MediaResponse, status_code=status.HTTP_201_CREATED)
async def upload_media(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_author),
):
    if not file.filename:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No file provided")

    # Validate extension
    _, ext = os.path.splitext(file.filename)
    ext = ext.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File type not allowed. Allowed: {', '.join(ALLOWED_EXTENSIONS)}",
        )

    # Read file content
    content = await file.read()
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="File too large (max 10MB)")

    # Generate unique filename
    unique_name = f"{uuid.uuid4().hex}{ext}"
    upload_dir = settings.MEDIA_UPLOAD_DIR
    os.makedirs(upload_dir, exist_ok=True)
    file_path = os.path.join(upload_dir, unique_name)

    # Write file
    with open(file_path, "wb") as f:
        f.write(content)

    url = f"/uploads/{unique_name}"

    media = Media(
        filename=unique_name,
        original_filename=file.filename,
        content_type=file.content_type or "application/octet-stream",
        file_size=len(content),
        url=url,
        author_id=current_user.id,
    )
    db.add(media)
    db.commit()
    db.refresh(media)
    return media
