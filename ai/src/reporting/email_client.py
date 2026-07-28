import base64
import logging
import socket
import smtplib
import datetime
import requests
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
from pathlib import Path
from typing import List, Dict, Any
from config import settings
from db import get_daily_digest_recipients
from src.reporting.excel import DOMAIN_REPORT_META

# Render blocks outbound SMTP (confirmed: connections to smtp.gmail.com hang and time out
# with "Network is unreachable" / "Connection timed out" even with correct credentials and
# IPv4 forced). Resend's HTTPS API is the workaround for the on-demand send only — the daily
# digest keeps using SMTP as before since it runs from GitHub Actions, which isn't blocked.
RESEND_API_URL = "https://api.resend.com/emails"
SENDGRID_API_URL = "https://api.sendgrid.com/v3/mail/send"
RESEND_DEFAULT_FROM = "onboarding@resend.dev"

logger = logging.getLogger(__name__)

class IPv4OnlySMTP(smtplib.SMTP):
    """
    Identical to smtplib.SMTP, except it only ever attempts IPv4 connections.

    Some hosts (Render included) resolve smtp.gmail.com to an IPv6 address with no
    outbound IPv6 route, which surfaces as "OSError: [Errno 101] Network is
    unreachable" even though an IPv4 route to the same server works fine. Forcing
    IPv4 here sidesteps that without changing anything about how SMTP itself works.
    """
    def _get_socket(self, host, port, timeout):
        addr_infos = socket.getaddrinfo(host, port, socket.AF_INET, socket.SOCK_STREAM)
        last_err = None
        for family, socktype, proto, _canonname, sockaddr in addr_infos:
            sock = None
            try:
                sock = socket.socket(family, socktype, proto)
                if timeout is not None and timeout is not socket._GLOBAL_DEFAULT_TIMEOUT:
                    sock.settimeout(timeout)
                sock.connect(sockaddr)
                return sock
            except OSError as e:
                last_err = e
                if sock is not None:
                    sock.close()
        raise last_err if last_err is not None else OSError("getaddrinfo returned no IPv4 addresses")

# Domain -> (section heading, emoji), used to build the combined email body
DOMAIN_EMAIL_META = {
    "cyber": {"heading": "Cyber Security", "emoji": "🇺🇸"},
    "data": {"heading": "Data Engineering / Analytics", "emoji": "📊"},
    "java": {"heading": "Java Developer", "emoji": "☕"},
    "dotnet": {"heading": ".NET Developer", "emoji": "🔷"},
}

def build_domain_section_html(domain: str, jobs: List[Dict[str, Any]]) -> str:
    """Builds the HTML block (heading + summary + preview table) for a single domain."""
    meta = DOMAIN_EMAIL_META.get(domain, {"heading": domain.title(), "emoji": "📌"})

    table_rows = ""
    for idx, job in enumerate(jobs[:10], 1):  # Show top 10 previews per domain
        zebra_class = 'class="zebra"' if idx % 2 == 0 else ""
        table_rows += f"""
        <tr {zebra_class}>
            <td style="text-align: center;">{idx}</td>
            <td><strong>{job.get('company')}</strong></td>
            <td>{job.get('title')}</td>
            <td>{job.get('location')}</td>
            <td>{job.get('experience_metadata', 'Not Specified')}</td>
            <td><a href="{job.get('apply_link')}" class="btn">Apply</a></td>
        </tr>
        """

    more_jobs_count = max(0, len(jobs) - 10)
    footer_preview_note = ""
    if more_jobs_count > 0:
        footer_preview_note = f"<p class='note'>...and {more_jobs_count} more job leads in the attached Excel file!</p>"

    return f"""
    <h2 class="domain-heading">{meta['emoji']} {meta['heading']} — {len(jobs)} Leads</h2>
    <table>
        <thead>
            <tr>
                <th style="width: 5%; text-align: center;">#</th>
                <th style="width: 25%;">Company</th>
                <th style="width: 35%;">Job Title</th>
                <th style="width: 15%;">Location</th>
                <th style="width: 10%;">Exp</th>
                <th style="width: 10%;">Link</th>
            </tr>
        </thead>
        <tbody>
            {table_rows}
        </tbody>
    </table>
    {footer_preview_note}
    """

def build_html_body(jobs_by_domain: Dict[str, List[Dict[str, Any]]]) -> str:
    """Creates a beautiful, styled HTML body covering all domains' job reports."""
    today_str = datetime.date.today().strftime("%B %d, %Y")

    total_jobs = sum(len(jobs) for jobs in jobs_by_domain.values())

    domain_sections = ""
    for domain, jobs in jobs_by_domain.items():
        if jobs:
            domain_sections += build_domain_section_html(domain, jobs)

    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <style>
            body {{
                font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                color: #333333;
                background-color: #f4f7f9;
                margin: 0;
                padding: 0;
            }}
            .container {{
                max-width: 650px;
                margin: 30px auto;
                background-color: #ffffff;
                border-radius: 8px;
                box-shadow: 0 4px 10px rgba(0, 0, 0, 0.05);
                overflow: hidden;
                border: 1px solid #e1e8ed;
            }}
            .header {{
                background: linear-gradient(135deg, #1F4E79 0%, #2F4F4F 100%);
                color: #ffffff;
                padding: 30px 20px;
                text-align: center;
            }}
            .header h1 {{
                margin: 0;
                font-size: 24px;
                font-weight: 600;
                letter-spacing: 0.5px;
            }}
            .header p {{
                margin: 5px 0 0 0;
                font-size: 14px;
                opacity: 0.9;
            }}
            .content {{
                padding: 30px 20px;
            }}
            .summary-box {{
                background-color: #EBF3FA;
                border-left: 4px solid #1F4E79;
                padding: 15px;
                margin-bottom: 25px;
                border-radius: 0 4px 4px 0;
            }}
            .summary-box p {{
                margin: 0;
                font-size: 15px;
                color: #1F4E79;
            }}
            table {{
                width: 100%;
                border-collapse: collapse;
                margin-top: 15px;
                font-size: 13px;
            }}
            th {{
                background-color: #1F4E79;
                color: #ffffff;
                text-align: left;
                padding: 10px;
                font-weight: 600;
            }}
            td {{
                padding: 10px;
                border-bottom: 1px solid #e1e8ed;
                vertical-align: middle;
            }}
            tr.zebra {{
                background-color: #F8FAFC;
            }}
            .btn {{
                display: inline-block;
                padding: 6px 12px;
                background-color: #1F4E79;
                color: #ffffff !important;
                text-decoration: none;
                border-radius: 4px;
                font-weight: 600;
                font-size: 11px;
                text-align: center;
            }}
            .btn:hover {{
                background-color: #153553;
            }}
            .note {{
                font-style: italic;
                color: #666666;
                margin-top: 15px;
                text-align: center;
                font-size: 14px;
            }}
            .footer {{
                background-color: #f4f7f9;
                padding: 20px;
                text-align: center;
                font-size: 11px;
                color: #888888;
                border-top: 1px solid #e1e8ed;
            }}
            .domain-heading {{
                margin: 30px 0 5px 0;
                font-size: 17px;
                color: #1F4E79;
                border-bottom: 2px solid #DDEBF7;
                padding-bottom: 6px;
            }}
            .domain-heading:first-of-type {{
                margin-top: 0;
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>💼 Multi-Domain Job Aggregator</h1>
                <p>Daily Digest — {today_str}</p>
            </div>
            <div class="content">
                <div class="summary-box">
                    <p><strong>🎯 Today's Summary:</strong> We identified <strong>{total_jobs}</strong> fresh, unique job leads across Cyber Security, Data, Java, and .NET matching 1-6 years of experience. A separate, formatted Excel sheet per domain is attached to this email.</p>
                </div>

                {domain_sections}
            </div>
            <div class="footer">
                <p>Sent by the Multi-Domain Job Aggregator automated pipeline.</p>
                <p>Configure targets, notifications, and AI filters in your settings.</p>
            </div>
        </div>
    </body>
    </html>
    """
    return html

def send_email_with_report(excel_paths_by_domain: Dict[str, str], jobs_by_domain: Dict[str, List[Dict[str, Any]]]) -> bool:
    """
    Sends one email with all domain Excel reports attached to the configured recipient address.
    """
    # 1. Validation check
    recipients = get_daily_digest_recipients()
    if not settings.SMTP_USER or not settings.SMTP_PASSWORD or not recipients:
        logger.warning(
            "SMTP credentials or recipient email address(es) are missing. "
            "Email dispatch skipped. (Generate Excel report local only)"
        )
        return False

    excel_files = {}
    for domain, excel_path in excel_paths_by_domain.items():
        excel_file = Path(excel_path)
        if not excel_file.exists():
            logger.error(f"[{domain}] Cannot find Excel report attachment at: {excel_path}")
            continue
        excel_files[domain] = excel_file

    if not excel_files:
        logger.error("No Excel report attachments found. Email dispatch skipped.")
        return False

    try:
        today_str = datetime.date.today().strftime("%d/%m/%Y")
        total_jobs = sum(len(jobs) for jobs in jobs_by_domain.values())
        subject = f"💼 Multi-Domain Jobs Digest ({today_str}) - {total_jobs} Leads"

        msg = MIMEMultipart()
        msg["From"] = settings.EMAIL_FROM
        msg["To"] = ", ".join(recipients)
        msg["Subject"] = subject

        html_body = build_html_body(jobs_by_domain)
        msg.attach(MIMEText(html_body, "html"))

        for domain, excel_file in excel_files.items():
            logger.info(f"[{domain}] Attaching Excel file to email: {excel_file.name}")
            with open(excel_file, "rb") as attachment:
                part = MIMEBase("application", "octet-stream")
                part.set_payload(attachment.read())
                encoders.encode_base64(part)
                part.add_header(
                    "Content-Disposition",
                    f"attachment; filename= {excel_file.name}",
                )
                msg.attach(part)

        logger.info(f"Connecting to SMTP server {settings.SMTP_HOST}:{settings.SMTP_PORT} via TLS...")
        server = smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT)
        server.starttls()
        server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)

        server.sendmail(settings.EMAIL_FROM, recipients, msg.as_string())
        server.quit()

        logger.info(f"Email successfully dispatched to {', '.join(recipients)}")
        return True
    except Exception as e:
        logger.error(f"Failed to send email: {str(e)}", exc_info=True)
        return False

def _build_domain_report_html(meta: Dict[str, str]) -> str:
    return f"""
    <!DOCTYPE html>
    <html>
    <head><meta charset="utf-8"></head>
    <body style="font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; color: #333333; background-color: #f4f7f9; margin: 0; padding: 0;">
        <div style="max-width: 600px; margin: 30px auto; background-color: #ffffff; border-radius: 8px; overflow: hidden; border: 1px solid #e1e8ed;">
            <div style="background: linear-gradient(135deg, #1F4E79 0%, #2F4F4F 100%); color: #ffffff; padding: 24px 20px; text-align: center;">
                <h1 style="margin: 0; font-size: 20px; font-weight: 600;">{meta['emoji']} {meta['sheet']}</h1>
                <p style="margin: 5px 0 0 0; font-size: 13px; opacity: 0.9;">Sent on demand from the dashboard</p>
            </div>
            <div style="padding: 24px 20px;">
                <p style="margin: 0; font-size: 14px;">Attached is the most recently generated <strong>{meta['sheet']}</strong> report.</p>
            </div>
            <div style="background-color: #f4f7f9; padding: 16px 20px; text-align: center; font-size: 11px; color: #888888; border-top: 1px solid #e1e8ed;">
                <p style="margin: 0;">Sent by the Multi-Domain Job Aggregator dashboard.</p>
            </div>
        </div>
    </body>
    </html>
    """

def _send_domain_report_via_resend(
    domain: str, meta: Dict[str, str], recipients: List[str], html_body: str,
    file_bytes: bytes, attachment_filename: str,
) -> bool:
    payload = {
        "from": RESEND_DEFAULT_FROM,
        "to": recipients,
        "subject": f"{meta['emoji']} {meta['sheet']} — Latest Report",
        "html": html_body,
        "attachments": [
            {"filename": attachment_filename, "content": base64.b64encode(file_bytes).decode("ascii")}
        ],
    }
    response = requests.post(
        RESEND_API_URL,
        headers={"Authorization": f"Bearer {settings.RESEND_API_KEY}", "Content-Type": "application/json"},
        json=payload,
        timeout=30,
    )
    if response.status_code >= 400:
        logger.error(f"[{domain}] Resend API error {response.status_code}: {response.text[:500]}")
        return False

    logger.info(f"[{domain}] On-demand report emailed via Resend to {', '.join(recipients)} (id={response.json().get('id')})")
    return True

def _send_domain_report_via_sendgrid(
    domain: str, meta: Dict[str, str], recipients: List[str], html_body: str,
    file_bytes: bytes, attachment_filename: str,
) -> bool:
    """
    Sends via SendGrid's HTTPS API using Single Sender Verification (settings.EMAIL_FROM
    must be the verified address) -- unlike Resend's shared sender, this can deliver to any
    recipient once that one address is verified, with no domain/DNS setup required.
    """
    payload = {
        "personalizations": [{"to": [{"email": addr} for addr in recipients]}],
        "from": {"email": settings.EMAIL_FROM},
        "subject": f"{meta['emoji']} {meta['sheet']} — Latest Report",
        "content": [{"type": "text/html", "value": html_body}],
        "attachments": [{
            "filename": attachment_filename,
            "content": base64.b64encode(file_bytes).decode("ascii"),
            "type": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            "disposition": "attachment",
        }],
    }
    response = requests.post(
        SENDGRID_API_URL,
        headers={"Authorization": f"Bearer {settings.SENDGRID_API_KEY}", "Content-Type": "application/json"},
        json=payload,
        timeout=30,
    )
    if response.status_code >= 400:
        logger.error(f"[{domain}] SendGrid API error {response.status_code}: {response.text[:500]}")
        return False

    logger.info(f"[{domain}] On-demand report emailed via SendGrid to {', '.join(recipients)}")
    return True

def _send_domain_report_via_smtp(
    domain: str, meta: Dict[str, str], recipients: List[str], html_body: str,
    file_bytes: bytes, attachment_filename: str,
) -> bool:
    if not settings.SMTP_USER or not settings.SMTP_PASSWORD:
        logger.warning(
            "SMTP credentials are missing in .env settings. On-demand domain report email skipped."
        )
        return False

    msg = MIMEMultipart()
    msg["From"] = settings.EMAIL_FROM
    msg["To"] = ", ".join(recipients)
    msg["Subject"] = f"{meta['emoji']} {meta['sheet']} — Latest Report"
    msg.attach(MIMEText(html_body, "html"))

    part = MIMEBase("application", "octet-stream")
    part.set_payload(file_bytes)
    encoders.encode_base64(part)
    part.add_header("Content-Disposition", f"attachment; filename= {attachment_filename}")
    msg.attach(part)

    logger.info(f"[{domain}] Connecting to SMTP server {settings.SMTP_HOST}:{settings.SMTP_PORT} via TLS (IPv4-only)...")
    server = IPv4OnlySMTP(settings.SMTP_HOST, settings.SMTP_PORT)
    server.starttls()
    server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)

    server.sendmail(settings.EMAIL_FROM, recipients, msg.as_string())
    server.quit()

    logger.info(f"[{domain}] On-demand report emailed via SMTP to {', '.join(recipients)}")
    return True

def send_domain_report_email(domain: str, file_bytes: bytes, recipients: List[str] = None) -> bool:
    """
    Sends a single, already-stored domain report on demand (triggered from the dashboard's
    "Domain Jobs" page). Identified only by role name — the report's original date is
    deliberately not mentioned in the email.

    Tries providers in order: SendGrid (settings.SENDGRID_API_KEY) -> Resend
    (settings.RESEND_API_KEY) -> SMTP. SendGrid is preferred since Single Sender
    Verification lets it deliver to any recipient with no domain/DNS setup; Resend's shared
    sender can only deliver to the account owner's own email without a verified domain.
    Render blocks outbound SMTP, so that fallback will only actually work in environments
    that allow it.

    Args:
        recipients: explicit list of addresses to send to (the clients picked on the
            dashboard). When omitted, falls back to whoever receives the daily digest
            (get_daily_digest_recipients()).
    """
    meta = DOMAIN_REPORT_META.get(domain, DOMAIN_REPORT_META["cyber"])

    if recipients:
        recipients = [e.strip() for e in recipients if e and e.strip()]
    else:
        recipients = get_daily_digest_recipients()

    if not recipients:
        logger.warning(f"[{domain}] No recipients given and no daily digest recipients configured. Email skipped.")
        return False

    html_body = _build_domain_report_html(meta)
    attachment_filename = f"{meta['prefix']}.xlsx"

    try:
        if settings.SENDGRID_API_KEY:
            return _send_domain_report_via_sendgrid(domain, meta, recipients, html_body, file_bytes, attachment_filename)
        if settings.RESEND_API_KEY:
            return _send_domain_report_via_resend(domain, meta, recipients, html_body, file_bytes, attachment_filename)
        return _send_domain_report_via_smtp(domain, meta, recipients, html_body, file_bytes, attachment_filename)
    except Exception as e:
        logger.error(f"[{domain}] Failed to send on-demand report email: {str(e)}", exc_info=True)
        return False
