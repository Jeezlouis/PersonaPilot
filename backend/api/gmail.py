from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi.responses import HTMLResponse, RedirectResponse
import logging

from backend.database import get_db
from backend.models import Job, EmailOutreach, Resume
from backend.modules.mailer.gmail_auth import generate_auth_url, handle_callback, get_auth_status
from backend.modules.mailer.gmail_sender import send_cold_email

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/gmail", tags=["gmail"])

@router.get("/auth")
async def gmail_auth():
    url, state = generate_auth_url()
    if not url:
        raise HTTPException(status_code=400, detail=state)
    return RedirectResponse(url)

@router.get("/oauth2callback")
async def gmail_oauth2callback(code: str = Query(None), state: str = Query(None), error: str = Query(None)):
    if error:
        return HTMLResponse(f"<h1>Error</h1><p>{error}</p>")
    if not code:
        return HTMLResponse("<h1>Error</h1><p>No code provided</p>")
    
    # Needs full URL that google redirected back to to fetch token
    import urllib.parse
    # since we just need the code, we reconstruct url
    original_url = f"http://localhost:8000/api/gmail/oauth2callback?code={urllib.parse.quote(code)}&state={urllib.parse.quote(state)}"
    
    success = handle_callback(code, state, original_url)
    if success:
        return HTMLResponse("<h1>Authentication Successful!</h1><p>You can close this tab and return to the Job Automater.</p>")
    else:
        return HTMLResponse("<h1>Authentication Failed</h1><p>Could not save credentials.</p>")

@router.get("/status")
async def gmail_status():
    return get_auth_status()
