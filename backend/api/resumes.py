"""
api/resumes.py — Resume management endpoints.
Supports file upload + manual entry.
"""
import os
from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional, List
import json

from backend.database import get_db
from backend.models import Resume
from backend.modules.resume_manager.manager import (
    save_resume_file, create_resume, get_all_resumes, delete_resume,
    extract_text_from_file,
)
from backend.config import settings

router = APIRouter(prefix="/api/resumes", tags=["resumes"])

VALID_ROLE_TYPES = ["frontend", "backend", "fullstack", "ai", "devops", "freelancer", "other"]


def _resume_to_dict(r: Resume) -> dict:
    return {
        "id": r.id,
        "name": r.name,
        "role_type": r.role_type,
        "skills": r.skills or [],
        "experience_summary": r.experience_summary,
        "file_path": r.file_path,
        "has_file": bool(r.file_path and Path(r.file_path).exists()),
        "tags": r.tags or [],
        "is_active": r.is_active,
        "is_default": r.is_default,
        "created_at": r.created_at.isoformat() if r.created_at else None,
    }


@router.get("")
async def list_resumes(db: AsyncSession = Depends(get_db)):
    """List all active resumes."""
    resumes = await get_all_resumes(db)
    return {"resumes": [_resume_to_dict(r) for r in resumes]}


@router.post("/upload")
async def upload_resume(
    file: UploadFile = File(...),
    name: str = Form(None),
    role_type: str = Form("other"),
    skills: str = Form("[]"),
    experience_summary: str = Form(""),
    tags: str = Form("[]"),
    is_default: bool = Form(False),
    auto_extract: bool = Form(False),
    db: AsyncSession = Depends(get_db),
):
    """Upload a resume file (PDF/DOCX/TXT) and save to DB."""
    # Save file first to extract text if needed
    content = await file.read()
    safe_name = Path(file.filename).name
    file_path = await save_resume_file(safe_name, content)
    
    # Defaults
    final_role = role_type
    final_skills = []
    final_tags = []
    try:
        final_skills = json.loads(skills) if skills else []
        final_tags = json.loads(tags) if tags else []
    except json.JSONDecodeError:
        pass
        
    final_summary = experience_summary
    final_name = name or safe_name

    # AI auto-extraction
    if auto_extract:
        text = extract_text_from_file(file_path)
        if text.strip():
            from backend.modules.ai_engine.resume_parser import parse_resume_content
            ai_data = parse_resume_content(text)
            final_role = ai_data.get("role_type", "other")
            final_skills = ai_data.get("skills", [])
            final_summary = ai_data.get("experience_summary", "")
            if not name:
                final_name = f"{final_role.title()} Resume (Auto-Parsed)"
                
    if final_role not in VALID_ROLE_TYPES:
        final_role = "other"

    resume = await create_resume(
        db=db,
        name=final_name,
        role_type=final_role,
        skills=final_skills,
        experience_summary=final_summary,
        file_path=file_path,
        tags=final_tags,
        is_default=is_default,
    )
    return _resume_to_dict(resume)


@router.post("")
async def create_resume_manual(payload: dict, db: AsyncSession = Depends(get_db)):
    """Create a resume from manual input (no file)."""
    role_type = payload.get("role_type", "other")
    if role_type not in VALID_ROLE_TYPES:
        raise HTTPException(status_code=400, detail=f"Invalid role_type: {role_type}")

    resume = await create_resume(
        db=db,
        name=payload.get("name", "My Resume"),
        role_type=role_type,
        skills=payload.get("skills", []),
        experience_summary=payload.get("experience_summary", ""),
        tags=payload.get("tags", []),
        is_default=payload.get("is_default", False),
        content_text=payload.get("content_text", ""),
    )
    return _resume_to_dict(resume)


@router.put("/{resume_id}")
async def update_resume(
    resume_id: int,
    payload: dict,
    db: AsyncSession = Depends(get_db),
):
    """Update resume metadata."""
    result = await db.execute(select(Resume).where(Resume.id == resume_id))
    resume = result.scalars().first()
    if not resume:
        raise HTTPException(status_code=404, detail="Resume not found")

    for field in ["name", "role_type", "skills", "experience_summary", "tags", "is_default", "is_active"]:
        if field in payload:
            setattr(resume, field, payload[field])

    return _resume_to_dict(resume)


@router.delete("/{resume_id}")
async def remove_resume(resume_id: int, db: AsyncSession = Depends(get_db)):
    """Soft-delete a resume."""
    deleted = await delete_resume(db, resume_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Resume not found")
    return {"deleted": True}
