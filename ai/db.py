import os
import bcrypt
import datetime
from typing import Any, Dict, List, Optional
from sqlalchemy import create_engine, Column, Integer, String, DateTime, Date, Text, LargeBinary, Boolean, ForeignKey, UniqueConstraint, inspect, text
from sqlalchemy.orm import declarative_base, sessionmaker, relationship
from dotenv import load_dotenv

# Load environmental variables
load_dotenv()


DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    # Use SQLite fallback if DATABASE_URL is not set, but notify user
    DATABASE_URL = "sqlite:///./cyberjobs.db"

# Neon/PostgreSQL connection strings often use the postgres:// prefix.
# SQLAlchemy requires postgresql:// instead of postgres://, so we replace it if present.
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

# Setup SQLAlchemy engine and session
# For SQLite, we need to allow multithreading, but PostgreSQL doesn't need it
if DATABASE_URL.startswith("sqlite"):
    engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
else:
    # PostgreSQL configuration
    engine = create_engine(DATABASE_URL, pool_pre_ping=True)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# Password hashing helpers using bcrypt
def hash_password(password: str) -> str:
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password.encode('utf-8'), salt).decode('utf-8')

def verify_password(password: str, hashed_password: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode('utf-8'), hashed_password.encode('utf-8'))
    except Exception:
        return False

# Database Models
class User(Base):
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), unique=True, index=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    role = Column(String(50), nullable=False, default="editor")  # "admin" or "editor"
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)
    
    logs = relationship("ActivityLog", back_populates="user", cascade="all, delete-orphan")

class Company(Base):
    __tablename__ = "companies"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), unique=True, index=True, nullable=False)
    ats = Column(String(50), nullable=False)  # "greenhouse", "lever", "ashby", "playwright"
    token = Column(String(255), index=True, nullable=True)
    careers_url = Column(Text, nullable=True, default="")
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)

class Job(Base):
    __tablename__ = "jobs"
    
    id = Column(Integer, primary_key=True, index=True)
    company = Column(String(255), index=True, nullable=False)
    title = Column(String(255), nullable=False)
    location = Column(String(255), nullable=True)
    experience_metadata = Column(Text, nullable=True)
    apply_link = Column(Text, unique=True, index=True, nullable=False)
    date_posted = Column(String(50), nullable=True)  # Format: "YYYY-MM-DD"
    scraped_at = Column(DateTime, default=datetime.datetime.utcnow)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

class ActivityLog(Base):
    __tablename__ = "activity_logs"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    action = Column(String(255), nullable=False)  # e.g., "LOGIN", "COMPANY_ADD", "SCRAPE_RUN"
    details = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    
    user = relationship("User", back_populates="logs")

class Setting(Base):
    __tablename__ = "settings"

    key = Column(String(255), primary_key=True, index=True)
    value = Column(Text, nullable=True)

class DomainReport(Base):
    """One row per domain (cyber/data_analyst/data_engineer/java/dotnet) per day, holding
    that day's generated Excel report so the dashboard can resend the latest one for a
    domain on demand."""
    __tablename__ = "domain_reports"

    id = Column(Integer, primary_key=True, index=True)
    domain = Column(String(20), index=True, nullable=False)  # "cyber", "data_analyst", "data_engineer", "java", "dotnet"
    report_date = Column(Date, nullable=False)
    filename = Column(String(255), nullable=False)
    file_data = Column(LargeBinary, nullable=False)
    job_count = Column(Integer, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    __table_args__ = (UniqueConstraint("domain", "report_date", name="uq_domain_report_date"),)

class Recipient(Base):
    """A saved client email address that domain reports can be sent to on demand.

    Kept separate from DailyRecipient (below) so adding an on-demand client never changes
    who receives the automated daily digest, and vice versa.
    """
    __tablename__ = "recipients"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), unique=True, index=True, nullable=False)
    name = Column(String(255), nullable=True)
    # Hidden from non-admin users on the Email page's client list when True. Admins always
    # see every recipient; this only restricts what editors/other roles are shown.
    admin_only = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

class DailyRecipient(Base):
    """A saved email address that receives the automated daily digest.

    Replaces the old single EMAIL_TO text setting with an editable list. EMAIL_TO is kept
    as a fallback (see get_daily_digest_recipients) so a run never silently goes to nobody
    if this table is ever empty.
    """
    __tablename__ = "daily_recipients"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), unique=True, index=True, nullable=False)
    name = Column(String(255), nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

class Resume(Base):
    """An uploaded candidate resume. Each active resume gets its own daily Excel report of
    jobs ranked for fit against it (see src/resume/), sent only to its ResumeRecipients --
    independent of the fixed-domain reports in DomainReport."""
    __tablename__ = "resumes"

    id = Column(Integer, primary_key=True, index=True)
    candidate_name = Column(String(255), nullable=False)
    original_filename = Column(String(255), nullable=False)
    resume_text = Column(Text, nullable=False)
    # JSON-encoded {target_titles, core_skills, min_years, max_years, summary} extracted
    # once by Claude at upload time (see src/resume/parser.py) -- never re-parsed daily.
    profile_json = Column(Text, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

class ResumeRecipient(Base):
    """A saved email address that a specific resume's daily matched-job report is sent to.
    Scoped per-resume so one candidate's recipients never see another's matches."""
    __tablename__ = "resume_recipients"

    id = Column(Integer, primary_key=True, index=True)
    resume_id = Column(Integer, ForeignKey("resumes.id", ondelete="CASCADE"), nullable=False, index=True)
    email = Column(String(255), nullable=False)
    name = Column(String(255), nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    __table_args__ = (UniqueConstraint("resume_id", "email", name="uq_resume_recipient_email"),)

class ResumeReport(Base):
    """One row per resume per day, holding that day's generated Excel report so the
    dashboard can resend the latest one for a resume on demand -- mirrors DomainReport."""
    __tablename__ = "resume_reports"

    id = Column(Integer, primary_key=True, index=True)
    resume_id = Column(Integer, ForeignKey("resumes.id", ondelete="CASCADE"), nullable=False, index=True)
    report_date = Column(Date, nullable=False)
    filename = Column(String(255), nullable=False)
    file_data = Column(LargeBinary, nullable=False)
    job_count = Column(Integer, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    __table_args__ = (UniqueConstraint("resume_id", "report_date", name="uq_resume_report_date"),)

class ResumeSentJob(Base):
    """Tracks which job links have already been sent to a given resume, so the same job
    isn't repeated in tomorrow's report. DB-based (unlike the file-based history dedup used
    for the fixed domains) since resumes are dynamic rows, not a fixed list."""
    __tablename__ = "resume_sent_jobs"

    id = Column(Integer, primary_key=True, index=True)
    resume_id = Column(Integer, ForeignKey("resumes.id", ondelete="CASCADE"), nullable=False, index=True)
    apply_link = Column(Text, nullable=False)
    sent_date = Column(Date, nullable=False)

# Database dependency
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Initialize database schemas and seed default user
def _run_migrations():
    """
    Base.metadata.create_all() only creates tables that don't exist yet -- it never alters
    a table that's already there. Columns added to a model after its table was first created
    (e.g. Recipient.admin_only) need an explicit ALTER TABLE, done here once and skipped on
    every later startup once the column is confirmed present.
    """
    inspector = inspect(engine)
    if "recipients" in inspector.get_table_names():
        existing_cols = {c["name"] for c in inspector.get_columns("recipients")}
        if "admin_only" not in existing_cols:
            with engine.connect() as conn:
                conn.execute(text(
                    "ALTER TABLE recipients ADD COLUMN admin_only BOOLEAN NOT NULL DEFAULT FALSE"
                ))
                conn.commit()
            print("[DB INIT] Migrated: added recipients.admin_only")

def init_db():
    Base.metadata.create_all(bind=engine)
    _run_migrations()

    # Check if a user table is empty, and seed the default admin
    db = SessionLocal()
    try:
        admin_email = os.getenv("ADMIN_EMAIL", "admin@cyberjobs.com")
        admin_password = os.getenv("ADMIN_PASSWORD", "adminpassword123")
        
        # Verify if any user exists
        exists = db.query(User).filter(User.role == "admin").first()
        if not exists:
            hashed = hash_password(admin_password)
            default_admin = User(
                email=admin_email,
                password_hash=hashed,
                role="admin"
            )
            db.add(default_admin)
            db.commit()
            print(f"[DB INIT] Seeded default admin account: {admin_email}")
    except Exception as e:
        print(f"[DB INIT] Seeding failed/skipped: {e}")
        db.rollback()
    finally:
        db.close()

def save_domain_report(
    domain: str,
    report_date: datetime.date,
    filename: str,
    file_bytes: bytes,
    job_count: Optional[int] = None,
) -> None:
    """Upserts the given domain's report for a single day (one row per domain per day)."""
    db = SessionLocal()
    try:
        existing = db.query(DomainReport).filter(
            DomainReport.domain == domain,
            DomainReport.report_date == report_date,
        ).first()
        if existing:
            existing.filename = filename
            existing.file_data = file_bytes
            existing.job_count = job_count
        else:
            db.add(DomainReport(
                domain=domain,
                report_date=report_date,
                filename=filename,
                file_data=file_bytes,
                job_count=job_count,
            ))
        db.commit()
    finally:
        db.close()

def get_latest_domain_report(domain: str) -> Optional[Dict[str, Any]]:
    """Returns the most recently stored report for a domain, or None if none exists."""
    db = SessionLocal()
    try:
        row = db.query(DomainReport).filter(DomainReport.domain == domain) \
            .order_by(DomainReport.report_date.desc(), DomainReport.id.desc()).first()
        if not row:
            return None
        return {
            "domain": row.domain,
            "report_date": row.report_date,
            "filename": row.filename,
            "file_data": row.file_data,
            "job_count": row.job_count,
        }
    finally:
        db.close()

def get_domain_report_dates(domain: str) -> List[str]:
    """Returns every date (ISO strings, newest first) a report was stored for a domain."""
    db = SessionLocal()
    try:
        rows = db.query(DomainReport.report_date).filter(DomainReport.domain == domain) \
            .order_by(DomainReport.report_date.desc()).all()
        return [r[0].isoformat() for r in rows]
    finally:
        db.close()

def get_domain_report_by_date(domain: str, report_date: datetime.date) -> Optional[Dict[str, Any]]:
    """Returns the stored report for an exact domain + date, or None if none exists."""
    db = SessionLocal()
    try:
        row = db.query(DomainReport).filter(
            DomainReport.domain == domain,
            DomainReport.report_date == report_date,
        ).first()
        if not row:
            return None
        return {
            "domain": row.domain,
            "report_date": row.report_date,
            "filename": row.filename,
            "file_data": row.file_data,
            "job_count": row.job_count,
        }
    finally:
        db.close()

def get_daily_digest_recipients() -> List[str]:
    """
    Returns the email addresses that should receive the automated daily digest: every
    saved DailyRecipient, or -- only if that table is empty -- the legacy EMAIL_TO setting
    split on commas, as a safety net so a run never silently goes to nobody. Queries the
    Setting table directly (not config.settings) to avoid a circular import.
    """
    db = SessionLocal()
    try:
        rows = db.query(DailyRecipient).order_by(DailyRecipient.name.asc(), DailyRecipient.email.asc()).all()
        if rows:
            return [r.email for r in rows]

        setting = db.query(Setting).filter(Setting.key == "email_to").first()
        if setting and setting.value:
            return [e.strip() for e in setting.value.split(",") if e.strip()]
        return []
    finally:
        db.close()

def get_active_resumes() -> List[Dict[str, Any]]:
    """Returns every active Resume with its parsed profile, for the daily matching run."""
    import json
    db = SessionLocal()
    try:
        rows = db.query(Resume).filter(Resume.is_active == True).all()  # noqa: E712
        return [
            {
                "id": r.id,
                "candidate_name": r.candidate_name,
                "profile": json.loads(r.profile_json),
            }
            for r in rows
        ]
    finally:
        db.close()

def get_resume_recipients(resume_id: int) -> List[str]:
    """Returns the email addresses a specific resume's report should be sent to."""
    db = SessionLocal()
    try:
        rows = db.query(ResumeRecipient).filter(ResumeRecipient.resume_id == resume_id).all()
        return [r.email for r in rows]
    finally:
        db.close()

def get_resume_sent_links(resume_id: int) -> set:
    """Returns every job link ever sent to this resume (no time window -- unlike the
    retention-bounded domain-report dedup, a resume's matches must never repeat, so the
    daily matcher excludes every link it has ever sent to this resume, permanently)."""
    db = SessionLocal()
    try:
        rows = db.query(ResumeSentJob.apply_link).filter(ResumeSentJob.resume_id == resume_id).all()
        return {r[0] for r in rows}
    finally:
        db.close()

def record_resume_sent_jobs(resume_id: int, apply_links: List[str]) -> None:
    """Marks the given job links as sent to this resume today, for future dedup."""
    if not apply_links:
        return
    db = SessionLocal()
    try:
        today = datetime.date.today()
        db.bulk_save_objects([
            ResumeSentJob(resume_id=resume_id, apply_link=link, sent_date=today)
            for link in apply_links
        ])
        db.commit()
    finally:
        db.close()

def save_resume_report(
    resume_id: int,
    report_date: datetime.date,
    filename: str,
    file_bytes: bytes,
    job_count: Optional[int] = None,
) -> None:
    """Upserts a resume's report for a single day (one row per resume per day)."""
    db = SessionLocal()
    try:
        existing = db.query(ResumeReport).filter(
            ResumeReport.resume_id == resume_id,
            ResumeReport.report_date == report_date,
        ).first()
        if existing:
            existing.filename = filename
            existing.file_data = file_bytes
            existing.job_count = job_count
        else:
            db.add(ResumeReport(
                resume_id=resume_id,
                report_date=report_date,
                filename=filename,
                file_data=file_bytes,
                job_count=job_count,
            ))
        db.commit()
    finally:
        db.close()

def get_latest_resume_report(resume_id: int) -> Optional[Dict[str, Any]]:
    """Returns the most recently stored report for a resume, or None if none exists."""
    db = SessionLocal()
    try:
        row = db.query(ResumeReport).filter(ResumeReport.resume_id == resume_id) \
            .order_by(ResumeReport.report_date.desc(), ResumeReport.id.desc()).first()
        if not row:
            return None
        return {
            "resume_id": row.resume_id,
            "report_date": row.report_date,
            "filename": row.filename,
            "file_data": row.file_data,
            "job_count": row.job_count,
        }
    finally:
        db.close()

if __name__ == "__main__":
    print("[DB INIT] Setting up database tables...")
    init_db()
    print("[DB INIT] Finished.")
