import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

class SettingsModule:
    def __init__(self, original_module):
        self.original_module = original_module
        
        # Base directories
        self.BASE_DIR = Path(__file__).resolve().parent.parent
        self.DATA_DIR = self.BASE_DIR / "data"
        self.HISTORY_DIR = self.DATA_DIR / "history"
        
        # Ensure directories exist
        self.DATA_DIR.mkdir(exist_ok=True)
        self.HISTORY_DIR.mkdir(exist_ok=True)
        
        # Configuration Files
        self.COMPANIES_JSON_PATH = self.BASE_DIR / "config" / "companies.json"

    def _get_db_value(self, db_key: str):
        try:
            # Import dynamically to avoid circular dependencies
            import sys
            from pathlib import Path
            ai_dir = str(Path(__file__).resolve().parent.parent)
            if ai_dir not in sys.path:
                sys.path.append(ai_dir)
            from db import SessionLocal, Setting
            
            db = SessionLocal()
            try:
                setting_obj = db.query(Setting).filter(Setting.key == db_key).first()
                if setting_obj is not None and setting_obj.value is not None:
                    return setting_obj.value
            finally:
                db.close()
        except Exception:
            # Fallback if DB table is not created yet or connection fails
            pass
        return None

    @property
    def SMTP_HOST(self) -> str:
        val = self._get_db_value("smtp_host")
        if val is not None:
            return val
        return os.getenv("SMTP_HOST") or "smtp.gmail.com"

    @property
    def SMTP_PORT(self) -> int:
        val = self._get_db_value("smtp_port")
        if val is not None:
            try:
                return int(val)
            except ValueError:
                pass
        return int(os.getenv("SMTP_PORT", "587"))

    @property
    def SMTP_USER(self) -> str:
        val = self._get_db_value("smtp_user")
        if val is not None:
            return val
        return os.getenv("SMTP_USER", "")

    @property
    def SMTP_PASSWORD(self) -> str:
        val = self._get_db_value("smtp_password")
        if val is not None:
            return val
        return os.getenv("SMTP_PASSWORD", "")

    @property
    def EMAIL_TO(self) -> str:
        val = self._get_db_value("email_to")
        if val is not None:
            return val
        return os.getenv("EMAIL_TO", "")

    @property
    def EMAIL_FROM(self) -> str:
        val = self._get_db_value("email_from")
        if val is not None:
            return val
        return os.getenv("EMAIL_FROM", os.getenv("SMTP_USER", ""))

    @property
    def EXPERIENCE_MIN_YEARS(self) -> int:
        val = self._get_db_value("min_experience")
        if val is not None:
            try:
                return int(val)
            except ValueError:
                pass
        return int(os.getenv("MIN_EXPERIENCE", "1"))

    @property
    def EXPERIENCE_MAX_YEARS(self) -> int:
        val = self._get_db_value("max_experience")
        if val is not None:
            try:
                return int(val)
            except ValueError:
                pass
        return int(os.getenv("MAX_EXPERIENCE", "6"))

    @property
    def COMPANY_COOLDOWN_DAYS(self) -> int:
        val = self._get_db_value("company_cooldown_days")
        if val is not None:
            try:
                return int(val)
            except ValueError:
                pass
        return int(os.getenv("COMPANY_COOLDOWN_DAYS", "14"))

    @property
    def HISTORY_RETENTION_DAYS(self) -> int:
        """
        How long a sent job stays in history. Report files older than this are deleted before
        each run, which also makes those links/companies eligible to appear again.
        Must be >= COMPANY_COOLDOWN_DAYS, otherwise the cooldown could never see its full
        window; the pipeline clamps it at startup.
        """
        val = self._get_db_value("history_retention_days")
        if val is not None:
            try:
                return int(val)
            except ValueError:
                pass
        return int(os.getenv("HISTORY_RETENTION_DAYS", "14"))

    @property
    def CLAUDE_API_KEY(self) -> str:
        val = self._get_db_value("claude_api_key")
        if val is not None:
            return val
        return os.getenv("CLAUDE_API_KEY", "")

    @property
    def RESEND_API_KEY(self) -> str:
        """
        Used only by the on-demand Domain Jobs send (email_client.send_domain_report_email).
        Render blocks outbound SMTP, so that path sends via Resend's HTTPS API instead. The
        daily digest (send_email_with_report) is unaffected and keeps using SMTP as before.
        Resend's shared sender can only deliver to the account owner's own email without a
        verified domain -- SendGrid (below) is preferred when configured, since Single Sender
        Verification lets it send to any recipient without owning a domain.
        """
        val = self._get_db_value("resend_api_key")
        if val is not None:
            return val
        return os.getenv("RESEND_API_KEY", "")

    @property
    def SENDGRID_API_KEY(self) -> str:
        """
        Preferred provider for the on-demand Domain Jobs send (checked before RESEND_API_KEY).
        Uses Single Sender Verification (settings.EMAIL_FROM) rather than full domain
        verification, so it can deliver to any recipient once that one address is verified.
        """
        val = self._get_db_value("sendgrid_api_key")
        if val is not None:
            return val
        return os.getenv("SENDGRID_API_KEY", "")

    @property
    def USE_AI_FILTER(self) -> bool:
        val = self._get_db_value("use_ai_filter")
        if val is not None:
            return val.lower() == "true"
        return os.getenv("USE_AI_FILTER", "false").lower() == "true"

    @property
    def GEMINI_API_KEY(self) -> str:
        val = self._get_db_value("gemini_api_key")
        if val is not None:
            return val
        return os.getenv("GEMINI_API_KEY", "")

    def __setattr__(self, name, value):
        # Allow normal setting of attributes on the proxy module wrapper
        if name in ("original_module", "BASE_DIR", "DATA_DIR", "HISTORY_DIR", "COMPANIES_JSON_PATH"):
            super().__setattr__(name, value)
        else:
            self.__dict__[name] = value

    def __getattr__(self, name):
        return getattr(self.original_module, name)

# Self-replace this module in sys.modules with our dynamically resolving proxy
sys.modules[__name__] = SettingsModule(sys.modules[__name__])
