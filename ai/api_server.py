import os
import sys
import io
import datetime
import pandas as pd
from pathlib import Path
from typing import Optional, List, Dict, Any
from fastapi import FastAPI, APIRouter, Depends, HTTPException, status, Query, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordBearer
from pydantic import BaseModel, EmailStr
from sqlalchemy.orm import Session
from sqlalchemy import func
import jwt

# Add current dir to path to resolve local imports
current_dir = Path(__file__).resolve().parent
sys.path.append(str(current_dir))

from db import SessionLocal, User, Company, Job, ActivityLog, Setting, Recipient, DailyRecipient, get_db, hash_password, verify_password, init_db, get_latest_domain_report, get_daily_digest_recipients, get_domain_report_dates, get_domain_report_by_date
from scrape_trigger import scrape_single_company
from config import settings
from src.scrapers import GreenhouseScraper, LeverScraper, AshbyScraper
from src.orchestrator import scrape_try_all, DOMAINS
from src.reporting import send_domain_report_email
from src.reporting.excel import DOMAIN_REPORT_META

# Load environmental variables
JWT_SECRET = os.getenv("JWT_SECRET", "supersecretjwtkey123!@#")
JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("JWT_EXPIRE_MINUTES", "60"))

# OAuth2 settings
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")

app = FastAPI(title="Cyber Security Job Aggregator API", version="1.0.0")

# Enable CORS for Next.js frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Adjust for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Startup DB setup
@app.on_event("startup")
def on_startup():
    init_db()

# --- Pydantic Schemas ---
class LoginRequest(BaseModel):
    email: str
    password: str

class TokenResponse(BaseModel):
    access_token: str
    token_type: str
    role: str
    email: str

class UserCreate(BaseModel):
    email: str
    password: str
    role: str = "editor"  # "admin" or "editor"

class UserResponse(BaseModel):
    id: int
    email: str
    role: str
    created_at: datetime.datetime

    class Config:
        orm_mode = True

class CompanyCreate(BaseModel):
    name: str
    ats: str  # "greenhouse", "lever", "ashby", "playwright"
    token: Optional[str] = None
    careers_url: Optional[str] = ""

class CompanyResponse(BaseModel):
    id: int
    name: str
    ats: str
    token: Optional[str]
    careers_url: Optional[str]
    created_at: datetime.datetime

    class Config:
        orm_mode = True

class JobResponse(BaseModel):
    id: int
    company: str
    title: str
    location: Optional[str]
    experience_metadata: Optional[str]
    apply_link: str
    date_posted: Optional[str]
    scraped_at: datetime.datetime

    class Config:
        orm_mode = True

class ActivityLogResponse(BaseModel):
    id: int
    user_id: Optional[int]
    action: str
    details: Optional[str]
    created_at: datetime.datetime

    class Config:
        orm_mode = True

class SettingsUpdate(BaseModel):
    min_experience: int
    max_experience: int
    company_cooldown_days: Optional[int] = 14
    use_ai_filter: bool
    smtp_host: str
    smtp_port: int
    smtp_user: str
    smtp_password: str
    email_to: str
    email_from: str
    gemini_api_key: Optional[str] = ""
    claude_api_key: Optional[str] = ""
    resend_api_key: Optional[str] = ""
    sendgrid_api_key: Optional[str] = ""

class DomainReportSendRequest(BaseModel):
    domain: str  # "cyber", "data", "java", or "dotnet"
    # Recipient ids picked on the dashboard. Empty/omitted falls back to the daily
    # digest's EMAIL_TO list, preserving the previous behaviour.
    recipient_ids: Optional[List[int]] = None

class RecipientCreate(BaseModel):
    # Plain str + a regex check: pydantic's EmailStr needs the optional email-validator
    # package, which is not in requirements.txt and would break the API on deploy.
    email: str
    name: Optional[str] = None
    admin_only: bool = False

class RecipientResponse(BaseModel):
    id: int
    email: str
    name: Optional[str]
    admin_only: bool
    created_at: datetime.datetime

    class Config:
        orm_mode = True

class DailyRecipientCreate(BaseModel):
    email: str
    name: Optional[str] = None

class DailyRecipientResponse(BaseModel):
    id: int
    email: str
    name: Optional[str]
    created_at: datetime.datetime

    class Config:
        orm_mode = True


# --- Security / JWT Helpers ---
def create_access_token(data: dict, expires_delta: Optional[datetime.timedelta] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.datetime.utcnow() + expires_delta
    else:
        expire = datetime.datetime.utcnow() + datetime.timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, JWT_SECRET, algorithm=JWT_ALGORITHM)
    return encoded_jwt

def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)) -> User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        email: str = payload.get("sub")
        if email is None:
            raise credentials_exception
    except jwt.PyJWTError:
        raise credentials_exception
        
    user = db.query(User).filter(User.email == email).first()
    if user is None:
        raise credentials_exception
    return user

def get_current_admin(current_user: User = Depends(get_current_user)) -> User:
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin permissions required"
        )
    return current_user


# --- ROUTERS ---
router = APIRouter()

# 1. Auth Endpoints
@router.post("/auth/login", response_model=TokenResponse)
def login(req: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == req.email).first()
    if not user or not verify_password(req.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Generate token
    token = create_access_token(data={"sub": user.email, "role": user.role})
    
    # Log login activity
    log = ActivityLog(user_id=user.id, action="LOGIN", details=f"User {user.email} successfully logged in.")
    db.add(log)
    db.commit()
    
    return {
        "access_token": token,
        "token_type": "bearer",
        "role": user.role,
        "email": user.email
    }

@router.get("/auth/me")
def get_me(current_user: User = Depends(get_current_user)):
    return {
        "id": current_user.id,
        "email": current_user.email,
        "role": current_user.role,
        "created_at": current_user.created_at
    }


# 2. Dashboard Endpoints
@router.get("/dashboard/stats")
def get_dashboard_stats(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    total_companies = db.query(Company).count()
    total_jobs = db.query(Job).count()
    
    # Jobs scraped today (UTC)
    today_start = datetime.datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    jobs_today = db.query(Job).filter(Job.scraped_at >= today_start).count()
    
    # Active ATS scrapers count
    ats_breakdown = db.query(Company.ats, func.count(Company.id)).group_by(Company.ats).all()
    ats_stats = {ats: count for ats, count in ats_breakdown}
    
    # Recent activity logs (limit 6)
    recent_logs = db.query(ActivityLog).order_by(ActivityLog.created_at.desc()).limit(6).all()
    logs_data = [
        {
            "id": l.id,
            "action": l.action,
            "details": l.details,
            "created_at": l.created_at,
            "user_email": db.query(User.email).filter(User.id == l.user_id).scalar() if l.user_id else "System"
        }
        for l in recent_logs
    ]
    
    # Scraped jobs trends (last 7 days)
    trends = []
    for i in range(6, -1, -1):
        day = datetime.datetime.utcnow().date() - datetime.timedelta(days=i)
        day_start = datetime.datetime.combine(day, datetime.time.min)
        day_end = datetime.datetime.combine(day, datetime.time.max)
        count = db.query(Job).filter(Job.scraped_at >= day_start, Job.scraped_at <= day_end).count()
        trends.append({
            "date": day.strftime("%b %d"),
            "jobs": count
        })
        
    return {
        "total_companies": total_companies,
        "total_jobs": total_jobs,
        "jobs_today": jobs_today,
        "ats_stats": ats_stats,
        "recent_activity": logs_data,
        "trends": trends
    }


# 3. Company Management Endpoints
@router.get("/companies")
def get_companies(
    page: int = Query(1, ge=1),
    limit: int = Query(15, ge=1, le=100),
    search: Optional[str] = Query(None),
    ats: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    query = db.query(Company)
    if search:
        query = query.filter(Company.name.ilike(f"%{search}%") | Company.token.ilike(f"%{search}%"))
    if ats:
        query = query.filter(Company.ats == ats.lower())
        
    total = query.count()
    companies = query.order_by(Company.name.asc()).offset((page - 1) * limit).limit(limit).all()
    
    return {
        "total": total,
        "page": page,
        "limit": limit,
        "data": companies
    }

def validate_and_detect_ats(ats: str, token: Optional[str], careers_url: Optional[str], company_name: str) -> str:
    """
    Validates that the provided token or careers_url actually resolves to a real live board.
    For 'all', tries to auto-detect and returns the name of the successful scraper.
    """
    import requests
    import urllib.parse
    
    ats = ats.strip().lower()
    token_str = token.strip().lower() if token else ""
    url_str = careers_url.strip() if careers_url else ""
    
    # 1. Greenhouse
    if ats == "greenhouse":
        if not token_str:
            raise HTTPException(status_code=400, detail="ATS token slug is required for Greenhouse.")
        try:
            scraper = GreenhouseScraper(company_name, token_str, url_str)
            jobs = scraper.scrape()
            if not jobs:
                raise ValueError("No jobs returned")
        except HTTPException:
            raise
        except Exception:
            raise HTTPException(
                status_code=400,
                detail="Could not find a job board for this company — check the token/URL and ATS type."
            )
        return "greenhouse"

    # 2. Lever
    elif ats == "lever":
        if not token_str:
            raise HTTPException(status_code=400, detail="ATS token slug is required for Lever.")
        try:
            scraper = LeverScraper(company_name, token_str, url_str)
            jobs = scraper.scrape()
            if not jobs:
                raise ValueError("No jobs returned")
        except HTTPException:
            raise
        except Exception:
            raise HTTPException(
                status_code=400,
                detail="Could not find a job board for this company — check the token/URL and ATS type."
            )
        return "lever"

    # 3. Ashby
    elif ats == "ashby":
        if not token_str:
            raise HTTPException(status_code=400, detail="ATS token slug is required for Ashby.")
        try:
            scraper = AshbyScraper(company_name, token_str, url_str)
            jobs = scraper.scrape()
            if not jobs:
                raise ValueError("No jobs returned")
        except HTTPException:
            raise
        except Exception:
            raise HTTPException(
                status_code=400,
                detail="Could not find a job board for this company — check the token/URL and ATS type."
            )
        return "ashby"

    # 4. Playwright Custom Crawler
    elif ats == "playwright":
        if not url_str:
            raise HTTPException(status_code=400, detail="Careers Page URL is required for Playwright Custom Crawler.")
        
        # Verify URL is valid
        parsed = urllib.parse.urlparse(url_str)
        if not parsed.scheme or not parsed.netloc:
            raise HTTPException(status_code=400, detail="Invalid Careers Page URL.")
            
        # Verify reachability via HTTP 200
        try:
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            }
            resp = requests.get(url_str, headers=headers, timeout=15, allow_redirects=True)
            if resp.status_code != 200:
                raise ValueError(f"Status code {resp.status_code}")
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(
                status_code=400,
                detail=f"Careers URL is unreachable or returned non-200 status code: {str(e)}"
            )
        return "playwright"

    # 5. "All" (Try to auto-detect)
    elif ats == "all":
        # Make sure at least token or careers_url is provided
        if not token_str and not url_str:
            raise HTTPException(status_code=400, detail="Either ATS Token Slug or Careers Page URL is required for 'All' detection.")
        
        detected_ats, jobs = scrape_try_all(company_name, token_str, url_str)
        if not detected_ats:
            raise HTTPException(
                status_code=400,
                detail="Could not verify this company against any supported ATS provider."
            )
        return detected_ats

    else:
        raise HTTPException(status_code=400, detail=f"Unsupported ATS type: {ats}")

@router.post("/companies", response_model=CompanyResponse)
def create_company(req: CompanyCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    # Duplicate checks
    existing_name = db.query(Company).filter(Company.name.ilike(req.name)).first()
    if existing_name:
        raise HTTPException(status_code=400, detail="Company with this name already exists.")
        
    if req.token:
        existing_token = db.query(Company).filter(Company.token == req.token.lower()).first()
        if existing_token:
            raise HTTPException(status_code=400, detail="Company with this ATS token already exists.")
            
    # Validate and detect correct ATS
    detected_ats = validate_and_detect_ats(
        ats=req.ats,
        token=req.token,
        careers_url=req.careers_url,
        company_name=req.name
    )

    company = Company(
        name=req.name.strip(),
        ats=detected_ats,
        token=req.token.strip().lower() if req.token else None,
        careers_url=req.careers_url.strip() if req.careers_url else ""
    )
    
    db.add(company)
    db.commit()
    db.refresh(company)
    
    # Log addition
    log = ActivityLog(
        user_id=current_user.id,
        action="COMPANY_ADD",
        details=f"Added company {company.name} ({company.ats})"
    )
    db.add(log)
    db.commit()
    
    return company

@router.put("/companies/{id}", response_model=CompanyResponse)
def update_company(id: int, req: CompanyCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    company = db.query(Company).filter(Company.id == id).first()
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")
        
    # Duplicate checks excluding self
    existing_name = db.query(Company).filter(Company.name.ilike(req.name), Company.id != id).first()
    if existing_name:
        raise HTTPException(status_code=400, detail="Company with this name already exists.")
        
    if req.token:
        existing_token = db.query(Company).filter(Company.token == req.token.lower(), Company.id != id).first()
        if existing_token:
            raise HTTPException(status_code=400, detail="Company with this ATS token already exists.")
            
    # Validate and detect correct ATS
    detected_ats = validate_and_detect_ats(
        ats=req.ats,
        token=req.token,
        careers_url=req.careers_url,
        company_name=req.name
    )

    old_details = f"{company.name} ({company.ats})"
    company.name = req.name.strip()
    company.ats = detected_ats
    company.token = req.token.strip().lower() if req.token else None
    company.careers_url = req.careers_url.strip() if req.careers_url else ""
    
    db.commit()
    db.refresh(company)
    
    # Log edit
    log = ActivityLog(
        user_id=current_user.id,
        action="COMPANY_EDIT",
        details=f"Edited company ID {id}: changed {old_details} to {company.name} ({company.ats})"
    )
    db.add(log)
    db.commit()
    
    return company

@router.delete("/companies/{id}")
def delete_company(id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    company = db.query(Company).filter(Company.id == id).first()
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")
        
    company_name = company.name
    db.delete(company)
    db.commit()
    
    # Log deletion
    log = ActivityLog(
        user_id=current_user.id,
        action="COMPANY_DELETE",
        details=f"Deleted company {company_name}"
    )
    db.add(log)
    db.commit()
    
    return {"success": True, "message": f"Successfully deleted company {company_name}"}

@router.post("/companies/{id}/scrape")
def trigger_scrape(id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    result = scrape_single_company(id, user_id=current_user.id)
    if not result.get("success"):
        raise HTTPException(status_code=500, detail=result.get("error", "Failed to scrape company"))
    return result


# 4. Jobs Board Endpoints
@router.get("/jobs")
def get_jobs(
    page: int = Query(1, ge=1),
    limit: int = Query(15, ge=1, le=100),
    search: Optional[str] = Query(None),
    company: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    query = db.query(Job)
    if search:
        query = query.filter(Job.title.ilike(f"%{search}%") | Job.location.ilike(f"%{search}%") | Job.company.ilike(f"%{search}%"))
    if company:
        query = query.filter(Job.company == company)
        
    total = query.count()
    jobs = query.order_by(Job.date_posted.desc(), Job.scraped_at.desc()).offset((page - 1) * limit).limit(limit).all()
    
    return {
        "total": total,
        "page": page,
        "limit": limit,
        "data": jobs
    }


# 5. Users Administration Endpoints (Admin Only)
@router.get("/users", response_model=List[UserResponse])
def get_users(db: Session = Depends(get_db), current_user: User = Depends(get_current_admin)):
    return db.query(User).order_by(User.email.asc()).all()

@router.post("/users", response_model=UserResponse)
def create_user(req: UserCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_admin)):
    existing = db.query(User).filter(User.email == req.email).first()
    if existing:
        raise HTTPException(status_code=400, detail="User already exists")
        
    user = User(
        email=req.email.strip(),
        password_hash=hash_password(req.password),
        role=req.role
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    
    # Log addition
    log = ActivityLog(
        user_id=current_user.id,
        action="USER_CREATE",
        details=f"Created user account: {user.email} (Role: {user.role})"
    )
    db.add(log)
    db.commit()
    
    return user

@router.delete("/users/{id}")
def delete_user(id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_admin)):
    user = db.query(User).filter(User.id == id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
        
    if user.id == current_user.id:
        raise HTTPException(status_code=400, detail="Cannot delete your own account")
        
    user_email = user.email
    db.delete(user)
    db.commit()
    
    # Log deletion
    log = ActivityLog(
        user_id=current_user.id,
        action="USER_DELETE",
        details=f"Deleted user account: {user_email}"
    )
    db.add(log)
    db.commit()
    
    return {"success": True, "message": f"Successfully deleted user {user_email}"}


# 6. Activity Logs Endpoints
@router.get("/activity")
def get_activity_logs(
    page: int = Query(1, ge=1),
    limit: int = Query(25, ge=1, le=100),
    action: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin)
):
    query = db.query(ActivityLog)
    if action:
        query = query.filter(ActivityLog.action == action)
        
    total = query.count()
    logs = query.order_by(ActivityLog.created_at.desc()).offset((page - 1) * limit).limit(limit).all()
    
    logs_data = [
        {
            "id": l.id,
            "action": l.action,
            "details": l.details,
            "created_at": l.created_at,
            "user_email": db.query(User.email).filter(User.id == l.user_id).scalar() if l.user_id else "System"
        }
        for l in logs
    ]
    
    return {
        "total": total,
        "page": page,
        "limit": limit,
        "data": logs_data
    }


# 7. System Settings Endpoints
@router.get("/settings")
def get_sys_settings(current_user: User = Depends(get_current_admin)):
    return {
        "min_experience": settings.EXPERIENCE_MIN_YEARS,
        "max_experience": settings.EXPERIENCE_MAX_YEARS,
        "company_cooldown_days": settings.COMPANY_COOLDOWN_DAYS,
        "use_ai_filter": settings.USE_AI_FILTER,
        "smtp_host": settings.SMTP_HOST,
        "smtp_port": settings.SMTP_PORT,
        "smtp_user": settings.SMTP_USER,
        "smtp_password": settings.SMTP_PASSWORD,
        "email_to": settings.EMAIL_TO,
        "email_from": settings.EMAIL_FROM,
        "claude_api_key": settings.CLAUDE_API_KEY,
        "resend_api_key": settings.RESEND_API_KEY,
        "sendgrid_api_key": settings.SENDGRID_API_KEY
    }

@router.post("/settings")
def update_sys_settings(req: SettingsUpdate, db: Session = Depends(get_db), current_user: User = Depends(get_current_admin)):
    cooldown = req.company_cooldown_days if req.company_cooldown_days is not None else 14
    # 1. Write settings to database
    db_keys = {
        "min_experience": str(req.min_experience),
        "max_experience": str(req.max_experience),
        "company_cooldown_days": str(cooldown),
        "use_ai_filter": "true" if req.use_ai_filter else "false",
        "smtp_host": req.smtp_host,
        "smtp_port": str(req.smtp_port),
        "smtp_user": req.smtp_user,
        "smtp_password": req.smtp_password,
        "email_to": req.email_to,
        "email_from": req.email_from,
    }
    if req.claude_api_key:
        db_keys["claude_api_key"] = req.claude_api_key
    if req.resend_api_key:
        db_keys["resend_api_key"] = req.resend_api_key
    if req.sendgrid_api_key:
        db_keys["sendgrid_api_key"] = req.sendgrid_api_key

    try:
        for k, v in db_keys.items():
            setting_obj = db.query(Setting).filter(Setting.key == k).first()
            if setting_obj:
                setting_obj.value = v
            else:
                setting_obj = Setting(key=k, value=v)
                db.add(setting_obj)
        db.commit()
    except Exception as db_err:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to save settings to database: {str(db_err)}")

    # 2. Write settings back to .env file
    env_path = current_dir.parent / ".env"
    
    env_lines = []
    updated_keys = {
        "MIN_EXPERIENCE": str(req.min_experience),
        "MAX_EXPERIENCE": str(req.max_experience),
        "COMPANY_COOLDOWN_DAYS": str(cooldown),
        "USE_AI_FILTER": "true" if req.use_ai_filter else "false",
        "SMTP_HOST": req.smtp_host,
        "SMTP_PORT": str(req.smtp_port),
        "SMTP_USER": req.smtp_user,
        "SMTP_PASSWORD": req.smtp_password,
        "EMAIL_TO": req.email_to,
        "EMAIL_FROM": req.email_from,
    }
    
    if req.claude_api_key:
        updated_keys["CLAUDE_API_KEY"] = req.claude_api_key
        
    # Read existing settings from .env file
    existing_content = {}
    if env_path.exists():
        with open(env_path, "r", encoding="utf-8") as f:
            for line in f:
                line_stripped = line.strip()
                if not line_stripped or line_stripped.startswith("#"):
                    continue
                if "=" in line_stripped:
                    key, val = line_stripped.split("=", 1)
                    existing_content[key.strip()] = val.strip()

    # Merge keys
    existing_content.update(updated_keys)
    
    # Write config back
    try:
        with open(env_path, "w", encoding="utf-8") as f:
            for key, val in existing_content.items():
                f.write(f"{key}={val}\n")
                
        # Re-set OS environment variables
        for key, val in updated_keys.items():
            os.environ[key] = val
            
        # Update setting constants dynamically in settings.py module wrapper if needed
        settings.EXPERIENCE_MIN_YEARS = req.min_experience
        settings.EXPERIENCE_MAX_YEARS = req.max_experience
        settings.USE_AI_FILTER = req.use_ai_filter
        
        # Log setting change
        log = ActivityLog(
            user_id=current_user.id,
            action="SETTINGS_CHANGE",
            details=f"Updated scraper criteria: Exp range [{req.min_experience} - {req.max_experience} yrs], AI Filter={req.use_ai_filter}"
        )
        db.add(log)
        db.commit()
        
        return {"success": True, "message": "Settings updated successfully."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to save settings: {str(e)}")


# 8. Domain Jobs Endpoints — resend the latest stored per-domain report on demand
@router.get("/domain-reports/latest")
def get_domain_report_status(
    domain: str = Query(...),
    current_user: User = Depends(get_current_user)
):
    domain = domain.strip().lower()
    if domain not in DOMAINS:
        raise HTTPException(status_code=400, detail=f"Unsupported domain: {domain}. Must be one of {DOMAINS}.")

    report = get_latest_domain_report(domain)
    meta = DOMAIN_REPORT_META.get(domain, DOMAIN_REPORT_META["cyber"])

    if not report:
        return {"found": False, "domain": domain, "label": meta["sheet"]}

    return {
        "found": True,
        "domain": domain,
        "label": meta["sheet"],
        "report_date": report["report_date"],
        "filename": report["filename"],
        "job_count": report["job_count"],
    }

@router.get("/domain-reports/dates")
def get_domain_report_dates_endpoint(domain: str = Query(...), current_user: User = Depends(get_current_user)):
    """Every date a report was stored for a domain, newest first -- powers the Job Leads date picker."""
    domain = domain.strip().lower()
    if domain not in DOMAINS:
        raise HTTPException(status_code=400, detail=f"Unsupported domain: {domain}. Must be one of {DOMAINS}.")
    return {"domain": domain, "dates": get_domain_report_dates(domain)}

@router.get("/domain-reports/by-date")
def get_domain_report_rows(
    domain: str = Query(...),
    date: str = Query(...),
    current_user: User = Depends(get_current_user)
):
    """
    Parses the Excel stored for an exact domain + date and returns its rows as JSON, for the
    Job Leads page. Field names match the /jobs endpoint's JobResponse shape so the same card
    UI can render either source.
    """
    domain = domain.strip().lower()
    if domain not in DOMAINS:
        raise HTTPException(status_code=400, detail=f"Unsupported domain: {domain}. Must be one of {DOMAINS}.")
    try:
        parsed_date = datetime.date.fromisoformat(date)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format, expected YYYY-MM-DD.")

    meta = DOMAIN_REPORT_META.get(domain, DOMAIN_REPORT_META["cyber"])
    report = get_domain_report_by_date(domain, parsed_date)
    if not report:
        return {"found": False, "domain": domain, "label": meta["sheet"], "date": date, "jobs": []}

    # Same layout generate_styled_excel writes: a 3-row title block, headers on row 4.
    df = pd.read_excel(io.BytesIO(report["file_data"]), engine="openpyxl", header=3)
    df.columns = [str(c).strip() for c in df.columns]

    def cell(row, col: str) -> str:
        val = row.get(col, "")
        return "" if pd.isna(val) else str(val)

    jobs = [
        {
            "company": cell(row, "Company"),
            "title": cell(row, "Job Title"),
            "location": cell(row, "Location"),
            "experience_metadata": cell(row, "Experience Required"),
            "date_posted": cell(row, "Date Added"),
            "apply_link": cell(row, "Apply Link"),
        }
        for _, row in df.iterrows()
    ]

    return {
        "found": True,
        "domain": domain,
        "label": meta["sheet"],
        "date": date,
        "job_count": report.get("job_count"),
        "jobs": jobs,
    }

@router.get("/recipients", response_model=List[RecipientResponse])
def list_recipients(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Saved client addresses that domain reports can be sent to. Non-admins never see
    recipients marked admin_only."""
    query = db.query(Recipient)
    if current_user.role != "admin":
        query = query.filter(Recipient.admin_only.is_(False))
    return query.order_by(Recipient.name.asc(), Recipient.email.asc()).all()

@router.post("/recipients", response_model=RecipientResponse)
def create_recipient(
    req: RecipientCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    import re
    email = req.email.strip().lower()
    if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[a-z]{2,}", email):
        raise HTTPException(status_code=400, detail="Please enter a valid email address.")
    if db.query(Recipient).filter(Recipient.email == email).first():
        raise HTTPException(status_code=400, detail="This email address is already saved.")

    # Only admins can actually mark a recipient admin_only -- a non-admin's request for it
    # is silently ignored rather than hiding their own addition from themselves.
    admin_only = req.admin_only if current_user.role == "admin" else False

    recipient = Recipient(email=email, name=(req.name or "").strip() or None, admin_only=admin_only)
    db.add(recipient)
    db.commit()
    db.refresh(recipient)

    db.add(ActivityLog(
        user_id=current_user.id,
        action="RECIPIENT_ADD",
        details=f"Added report recipient {recipient.email}."
    ))
    db.commit()
    return recipient

@router.delete("/recipients/{id}")
def delete_recipient(id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    recipient = db.query(Recipient).filter(Recipient.id == id).first()
    if not recipient or (recipient.admin_only and current_user.role != "admin"):
        raise HTTPException(status_code=404, detail="Recipient not found.")

    email = recipient.email
    db.delete(recipient)
    db.commit()

    db.add(ActivityLog(
        user_id=current_user.id,
        action="RECIPIENT_DELETE",
        details=f"Removed report recipient {email}."
    ))
    db.commit()
    return {"success": True, "message": f"{email} removed."}


# --- Daily Digest Recipients: who receives the automated nightly email (separate from
# the on-demand "recipients" list above, which never affects the scheduled run) ---
@router.get("/daily-recipients", response_model=List[DailyRecipientResponse])
def list_daily_recipients(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return db.query(DailyRecipient).order_by(DailyRecipient.name.asc(), DailyRecipient.email.asc()).all()

@router.post("/daily-recipients", response_model=DailyRecipientResponse)
def create_daily_recipient(
    req: DailyRecipientCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    import re
    email = req.email.strip().lower()
    if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[a-z]{2,}", email):
        raise HTTPException(status_code=400, detail="Please enter a valid email address.")
    if db.query(DailyRecipient).filter(DailyRecipient.email == email).first():
        raise HTTPException(status_code=400, detail="This email address is already saved.")

    recipient = DailyRecipient(email=email, name=(req.name or "").strip() or None)
    db.add(recipient)
    db.commit()
    db.refresh(recipient)

    db.add(ActivityLog(
        user_id=current_user.id,
        action="DAILY_RECIPIENT_ADD",
        details=f"Added daily digest recipient {recipient.email}."
    ))
    db.commit()
    return recipient

@router.delete("/daily-recipients/{id}")
def delete_daily_recipient(id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    recipient = db.query(DailyRecipient).filter(DailyRecipient.id == id).first()
    if not recipient:
        raise HTTPException(status_code=404, detail="Daily recipient not found.")

    email = recipient.email
    db.delete(recipient)
    db.commit()

    db.add(ActivityLog(
        user_id=current_user.id,
        action="DAILY_RECIPIENT_DELETE",
        details=f"Removed daily digest recipient {email}."
    ))
    db.commit()
    return {"success": True, "message": f"{email} removed."}


@router.post("/domain-reports/send")
def send_domain_report(
    req: DomainReportSendRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    domain = req.domain.strip().lower()
    if domain != "all" and domain not in DOMAINS:
        raise HTTPException(status_code=400, detail=f"Unsupported domain: {domain}. Must be 'all' or one of {DOMAINS}.")

    # Resolve the clients picked on the dashboard once, shared by every domain below. With
    # none selected, falls back to the daily digest's recipient list (unchanged behaviour).
    recipient_emails: List[str] = []
    if req.recipient_ids:
        rows_query = db.query(Recipient).filter(Recipient.id.in_(req.recipient_ids))
        if current_user.role != "admin":
            rows_query = rows_query.filter(Recipient.admin_only.is_(False))
        rows = rows_query.all()
        found_ids = {r.id for r in rows}
        missing = [i for i in req.recipient_ids if i not in found_ids]
        if missing:
            raise HTTPException(status_code=400, detail=f"Unknown recipient id(s): {missing}")
        recipient_emails = [r.email for r in rows]
    target = ", ".join(recipient_emails) if recipient_emails else "the default digest recipients"

    if domain == "all":
        sent_labels, skipped_labels, failed_labels = [], [], []
        for d in DOMAINS:
            meta = DOMAIN_REPORT_META.get(d, DOMAIN_REPORT_META["cyber"])
            report = get_latest_domain_report(d)
            if not report:
                skipped_labels.append(meta["sheet"])
                continue
            if send_domain_report_email(d, report["file_data"], recipients=recipient_emails or None):
                sent_labels.append(meta["sheet"])
                db.add(ActivityLog(
                    user_id=current_user.id,
                    action="DOMAIN_REPORT_SEND",
                    details=f"Sent latest {meta['sheet']} report (dated {report['report_date']}) to {target} (bulk 'All' send)."
                ))
            else:
                failed_labels.append(meta["sheet"])
        db.commit()

        if not sent_labels and not failed_labels:
            return {"success": False, "message": "No excel found for any domain."}

        parts = []
        if sent_labels:
            parts.append(f"Sent: {', '.join(sent_labels)}")
        if skipped_labels:
            parts.append(f"No report stored: {', '.join(skipped_labels)}")
        if failed_labels:
            parts.append(f"Failed: {', '.join(failed_labels)}")
        return {
            "success": len(sent_labels) > 0,
            "message": " | ".join(parts),
            "sent": sent_labels,
            "skipped": skipped_labels,
            "failed": failed_labels,
        }

    meta = DOMAIN_REPORT_META.get(domain, DOMAIN_REPORT_META["cyber"])
    report = get_latest_domain_report(domain)
    if not report:
        return {"success": False, "message": "No excel found"}

    sent = send_domain_report_email(domain, report["file_data"], recipients=recipient_emails or None)
    if not sent:
        raise HTTPException(
            status_code=500,
            detail="Failed to send email. Check SendGrid/Resend/SMTP settings under System Settings, and check the server logs for the exact provider error."
        )

    log = ActivityLog(
        user_id=current_user.id,
        action="DOMAIN_REPORT_SEND",
        details=f"Sent latest {meta['sheet']} report (dated {report['report_date']}) to {target}."
    )
    db.add(log)
    db.commit()

    return {
        "success": True,
        "message": f"{meta['sheet']} report sent to {len(recipient_emails) or 'default'} recipient(s)."
                   if recipient_emails else f"{meta['sheet']} report sent successfully.",
        "recipients": recipient_emails,
    }


# Mount Router
app.include_router(router, prefix="/api")
