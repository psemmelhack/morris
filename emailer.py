import resend
from datetime import datetime
from config import settings

resend.api_key = settings.resend_api_key


def send_reminder_email(event: dict):
    """Send a 1-hour reminder email for an event."""
    event_time_str = ""
    if event.get("event_time"):
        try:
            dt = datetime.fromisoformat(str(event["event_time"]))
            event_time_str = dt.strftime("%I:%M %p")
        except Exception:
            event_time_str = str(event["event_time"])

    html_body = f"""
    <div style="font-family: Georgia, serif; max-width: 500px; margin: 0 auto; padding: 20px; color: #222;">
        <p style="font-size: 14px; color: #888; margin-bottom: 4px;">Morris — Your Personal Guide</p>
        <h2 style="margin-top: 0;">⏰ Starting in about an hour</h2>

        <div style="border-left: 3px solid #333; padding-left: 16px; margin: 20px 0;">
            <h3 style="margin: 0 0 8px 0;">{event.get('name', '')}</h3>
            {"<p style='margin: 4px 0;'>📍 " + event.get('venue', '') + "</p>" if event.get('venue') else ""}
            {"<p style='margin: 4px 0;'>🕐 " + event_time_str + "</p>" if event_time_str else ""}
            {"<p style='margin: 4px 0;'>🗺 " + event.get('address', '') + "</p>" if event.get('address') else ""}
        </div>

        {"<p style='margin-top: 8px;'><a href='" + event.get('url') + "' style='color: #333;'>Event details →</a></p>" if event.get('url') else ""}

        <p style="font-size: 12px; color: #aaa; margin-top: 32px;">
            You asked Morris to remind you about this. Have a great time.
        </p>
    </div>
    """

    resend.Emails.send({
        "from": settings.reminder_email_from,
        "to": settings.reminder_email_to,
        "subject": f"⏰ Starting soon: {event.get('name', 'Your event')}",
        "html": html_body,
    })

    print(f"Reminder email sent for: {event.get('name')}")
