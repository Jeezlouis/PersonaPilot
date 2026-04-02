"""
manager.py — Resume Manager.
Handles file upload, text extraction (PDF/DOCX), and CRUD.
"""
import logging
import os
from pathlib import Path
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.config import settings
from backend.models import Resume

logger = logging.getLogger(__name__)


def _extract_pdf_text(file_path: str) -> str:
    """Extract plain text from a PDF file."""
    try:
        import PyPDF2
        text_parts = []
        with open(file_path, "rb") as f:
            reader = PyPDF2.PdfReader(f)
            for page in reader.pages:
                text_parts.append(page.extract_text() or "")
        return "\n".join(text_parts)
    except Exception as e:
        logger.warning(f"PDF extraction failed ({file_path}): {e}")
        return ""


def _extract_docx_text(file_path: str) -> str:
    """Extract plain text from a DOCX file."""
    try:
        from docx import Document
        doc = Document(file_path)
        return "\n".join([para.text for para in doc.paragraphs])
    except Exception as e:
        logger.warning(f"DOCX extraction failed ({file_path}): {e}")
        return ""


def extract_text_from_file(file_path: str) -> str:
    """Auto-detect format and extract text."""
    ext = Path(file_path).suffix.lower()
    if ext == ".pdf":
        return _extract_pdf_text(file_path)
    elif ext in [".docx", ".doc"]:
        return _extract_docx_text(file_path)
    elif ext in [".txt", ".md"]:
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            return f.read()
    return ""


async def save_resume_file(filename: str, content: bytes) -> str:
    """Save uploaded resume file. Returns relative path."""
    resume_dir = Path(settings.resume_dir)
    resume_dir.mkdir(parents=True, exist_ok=True)
    dest = resume_dir / filename
    with open(dest, "wb") as f:
        f.write(content)
    return str(dest)


async def create_resume(
    db: AsyncSession,
    name: str,
    role_type: str,
    skills: list,
    experience_summary: str,
    file_path: Optional[str] = None,
    tags: Optional[list] = None,
    is_default: bool = False,
    content_text: Optional[str] = None,
) -> Resume:
    """Create a new resume record."""
    # Extract text from file if not provided
    if file_path and not content_text:
        content_text = extract_text_from_file(file_path)

    # If this is default, unset others
    if is_default:
        existing = await db.execute(select(Resume).where(Resume.is_default == True))
        for r in existing.scalars().all():
            r.is_default = False

    resume = Resume(
        name=name,
        role_type=role_type,
        skills=skills,
        experience_summary=experience_summary,
        file_path=file_path,
        content_text=content_text,
        tags=tags or [],
        is_default=is_default,
        is_active=True,
    )
    db.add(resume)
    await db.flush()
    logger.info(f"Resume created: {name} ({role_type}) id={resume.id}")
    return resume


async def get_all_resumes(db: AsyncSession) -> list:
    result = await db.execute(
        select(Resume).where(Resume.is_active == True).order_by(Resume.created_at.desc())
    )
    return result.scalars().all()


async def delete_resume(db: AsyncSession, resume_id: int) -> bool:
    result = await db.execute(select(Resume).where(Resume.id == resume_id))
    resume = result.scalars().first()
    if not resume:
        return False
    resume.is_active = False  # Soft delete
    await db.flush()
    logger.info(f"Resume soft-deleted: id={resume_id}")
    return True
