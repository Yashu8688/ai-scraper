import logging
import smtplib
import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
from pathlib import Path
from typing import List, Dict, Any
from config import settings

logger = logging.getLogger(__name__)

def build_html_body(jobs: List[Dict[str, Any]]) -> str:
    """Creates a beautiful, styled HTML body for the email report."""
    today_str = datetime.date.today().strftime("%B %d, %Y")
    
    # Generate job list table rows
    table_rows = ""
    for idx, job in enumerate(jobs[:10], 1): # Show top 10 previews in the email body
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
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>🇺🇸 Cyber Security Job Aggregator</h1>
                <p>Daily Digest — {today_str}</p>
            </div>
            <div class="content">
                <div class="summary-box">
                    <p><strong>🎯 Today's Summary:</strong> We identified <strong>{len(jobs)}</strong> fresh, unique Cyber Security roles in the US matching 1-6 years of experience. A beautiful, formatted Excel sheet is attached to this email.</p>
                </div>
                
                <h3>🔥 Top Job Leads Preview:</h3>
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
            </div>
            <div class="footer">
                <p>Sent by Cyber Security Job Aggregator automated pipeline.</p>
                <p>Configure targets, notifications, and AI filters in your settings.</p>
            </div>
        </div>
    </body>
    </html>
    """
    return html

def send_email_with_report(excel_path: str, jobs: List[Dict[str, Any]]) -> bool:
    """
    Sends the generated Excel report to the configured recipient email address.
    """
    # 1. Validation check
    if not settings.SMTP_USER or not settings.SMTP_PASSWORD or not settings.EMAIL_TO:
        logger.warning(
            "SMTP credentials or recipient email address are missing in .env settings. "
            "Email dispatch skipped. (Generate Excel report local only)"
        )
        return False
        
    excel_file = Path(excel_path)
    if not excel_file.exists():
        logger.error(f"Cannot find Excel report attachment at: {excel_path}")
        return False
        
    try:
        today_str = datetime.date.today().strftime("%d/%m/%Y")
        subject = f"🇺🇸 Cyber Security Jobs Digest ({today_str}) - {len(jobs)} Leads"
        
        recipients = [e.strip() for e in settings.EMAIL_TO.split(",") if e.strip()]

        msg = MIMEMultipart()
        msg["From"] = settings.EMAIL_FROM
        msg["To"] = ", ".join(recipients)
        msg["Subject"] = subject

        html_body = build_html_body(jobs)
        msg.attach(MIMEText(html_body, "html"))

        logger.info(f"Attaching Excel file to email: {excel_file.name}")
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
