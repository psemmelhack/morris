import asyncio
import logging
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
import pytz

from config import settings
from database import get_events_needing_reminder, mark_reminder_sent
from emailer import send_reminder_email

logger = logging.getLogger(__name__)

tz = pytz.timezone(settings.user_timezone)


async def morning_job():
    """Fire the morning Telegram greeting."""
    from bot import send_morning_greeting  # local import to avoid circular
    try:
        await send_morning_greeting()
        logger.info("Morning greeting sent.")
    except Exception as e:
        logger.error(f"Morning greeting failed: {e}")


async def reminder_check_job():
    """Check every 5 minutes for events starting in ~1 hour."""
    events = get_events_needing_reminder()
    for event in events:
        try:
            # Send Telegram reminder
            from bot import send_reminder_via_telegram
            await send_reminder_via_telegram(event)

            # Send email reminder
            send_reminder_email(event)

            # Mark as done
            mark_reminder_sent(event["id"])
            logger.info(f"Reminder sent for event id={event['id']}: {event['name']}")

        except Exception as e:
            logger.error(f"Reminder failed for event {event.get('id')}: {e}")


def create_scheduler() -> AsyncIOScheduler:
    scheduler = AsyncIOScheduler(timezone=tz)

    # Morning greeting - 6:00 AM PT daily
    scheduler.add_job(
        morning_job,
        CronTrigger(
            hour=settings.morning_hour,
            minute=settings.morning_minute,
            timezone=tz,
        ),
        id="morning_greeting",
        name="Morning greeting",
        replace_existing=True,
    )

    # Reminder check - every 5 minutes
    scheduler.add_job(
        reminder_check_job,
        "interval",
        minutes=5,
        id="reminder_check",
        name="Event reminder check",
        replace_existing=True,
    )

    return scheduler
