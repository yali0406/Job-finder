"""Email a digest of new well-scoring jobs through Gmail SMTP (an app password, not the account password)."""
import html
import os
import smtplib
from email.message import EmailMessage

from .common import log

MIN_SCORE = 60


def send_digest(jobs: list[dict], site_url: str = ""):
    user, password = os.environ.get("GMAIL_USER"), os.environ.get("GMAIL_APP_PASSWORD")
    to = os.environ.get("NOTIFY_EMAIL") or user
    good = sorted((j for j in jobs if (j.get("score") or 0) >= MIN_SCORE), key=lambda j: -(j.get("score") or 0))
    if not good:
        return
    if not (user and password):
        log.info("%d new jobs scored %d+, but GMAIL_USER / GMAIL_APP_PASSWORD are not set", len(good), MIN_SCORE)
        return

    e = html.escape
    rows = "".join(
        f'<tr><td style="padding:10px 0;border-bottom:1px solid #e4e7ec">'
        f'<b style="font-size:18px;color:#16a34a">{j.get("score")}</b>&nbsp; '
        f'<a href="{e(j.get("url") or "")}" style="font-weight:600;color:#1c2430">{e(j["title"])}</a><br>'
        f'<span style="color:#667085">{e(j.get("company") or "")} · {e(j.get("location") or "")}'
        f'{" · 🐣" if j.get("broad") == "early-stage startup" else ""}</span>'
        f'<div style="margin-top:4px">{e(j.get("reason") or "")}</div></td></tr>'
        for j in good
    )
    link = f'<p><a href="{e(site_url)}">לכל המשרות באתר</a></p>' if site_url else ""
    msg = EmailMessage()
    msg["Subject"] = f"{len(good)} משרות חדשות עם ציון {MIN_SCORE}+" if len(good) > 1 else f"משרה חדשה: {good[0]['title']} ({good[0].get('score')})"
    msg["From"] = f"Job Finder <{user}>"
    msg["To"] = to
    msg.set_content("\n\n".join(f"{j.get('score')} · {j['title']} · {j.get('company')}\n{j.get('url')}" for j in good))
    msg.add_alternative(
        f'<div dir="rtl" style="font-family:Arial,sans-serif;font-size:15px;color:#1c2430;max-width:640px">'
        f'<table style="width:100%;border-collapse:collapse">{rows}</table>{link}</div>',
        subtype="html",
    )
    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=30) as s:
            s.login(user, password)
            s.send_message(msg)
        log.info("Emailed %d new jobs to %s", len(good), to)
    except (smtplib.SMTPException, OSError) as ex:
        log.warning("Email failed: %s", ex)
