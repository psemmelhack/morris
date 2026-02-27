import logging
from datetime import datetime
from telegram import Update, Bot
from telegram.ext import Application, MessageHandler, CommandHandler, filters, ContextTypes
from telegram.constants import ParseMode

from config import settings
from database import get_session, upsert_session, save_event
from crew import find_activities

logger = logging.getLogger(__name__)


# ─── Outbound helpers ────────────────────────────────────────────────────────

async def send_morning_greeting():
    """Called by the scheduler at 6AM."""
    bot = Bot(token=settings.telegram_bot_token)
    today = datetime.now().strftime("%A, %B %d")
    greeting = (
        f"Good morning! It's {today} and I'm already thinking about your day. 🌅\n\n"
        f"You're in *{settings.user_location}*. What would you like to do today? "
        f"Tell me anything — a vibe, an activity, something specific, or just 'surprise me'."
    )
    await bot.send_message(
        chat_id=settings.telegram_chat_id,
        text=greeting,
        parse_mode=ParseMode.MARKDOWN,
    )
    upsert_session(settings.telegram_chat_id, "AWAITING_PREFERENCE")


async def send_reminder_via_telegram(event: dict):
    """Send a 1-hour reminder via Telegram."""
    bot = Bot(token=settings.telegram_bot_token)
    event_time_str = ""
    if event.get("event_time"):
        try:
            dt = datetime.fromisoformat(str(event["event_time"]))
            event_time_str = dt.strftime("%-I:%M %p")
        except Exception:
            event_time_str = str(event["event_time"])

    msg = f"⏰ *Heads up!* Your event starts in about an hour:\n\n*{event['name']}*\n"
    if event.get("venue"):
        msg += f"📍 {event['venue']}\n"
    if event_time_str:
        msg += f"🕐 {event_time_str}\n"
    if event.get("address"):
        msg += f"🗺 {event['address']}\n"
    if event.get("url"):
        msg += f"\n[More info]({event['url']})"

    await bot.send_message(
        chat_id=settings.telegram_chat_id,
        text=msg,
        parse_mode=ParseMode.MARKDOWN,
    )


# ─── Handlers ────────────────────────────────────────────────────────────────

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = str(update.effective_chat.id)
    text = update.message.text.strip()

    if chat_id != settings.telegram_chat_id:
        return

    session = get_session(chat_id)
    state = session["state"] if session else "IDLE"

    if state == "AWAITING_PREFERENCE":
        await handle_preference(update, context, chat_id, text)
    elif state == "AWAITING_SELECTION":
        await handle_selection(update, context, chat_id, text, session)
    else:
        if text.lower() in ["/start", "/morning", "hey morris", "wake up"]:
            today = datetime.now().strftime("%A, %B %d")
            await update.message.reply_text(
                f"Hey! What would you like to do today? It's {today} in {settings.user_location}."
            )
            upsert_session(chat_id, "AWAITING_PREFERENCE")
        else:
            await update.message.reply_text(
                "I'm not sure what you need right now. Say 'hey Morris' to get started, "
                "or wait for my morning message."
            )


async def handle_preference(update: Update, context: ContextTypes.DEFAULT_TYPE, chat_id: str, preference: str):
    await update.message.reply_text("On it. Give me a minute to find the good stuff... 🔍")
    try:
        today = datetime.now().strftime("%A, %B %d, %Y")
        message, events = find_activities(preference, settings.user_location, today)
        upsert_session(chat_id, "AWAITING_SELECTION", suggestions=events)
        await update.message.reply_text(message, parse_mode=ParseMode.MARKDOWN)
    except Exception as e:
        logger.error(f"Crew error: {e}")
        await update.message.reply_text(
            "Hmm, I ran into a snag finding things. Want to try again with a different idea?"
        )
        upsert_session(chat_id, "AWAITING_PREFERENCE")


async def handle_selection(update: Update, context: ContextTypes.DEFAULT_TYPE, chat_id: str, text: str, session: dict):
    suggestions = session.get("suggestions") or []

    dismissals = ["no", "nah", "none", "skip", "nothing", "nevermind", "never mind", "pass"]
    if any(d in text.lower() for d in dismissals):
        await update.message.reply_text("No problem — I'll catch you tomorrow morning. Have a good one! 👋")
        upsert_session(chat_id, "IDLE")
        return

    try:
        idx = int(''.join(filter(str.isdigit, text))) - 1
        if 0 <= idx < len(suggestions):
            event = suggestions[idx]
            save_event(chat_id, event)

            time_note = ""
            if event.get("event_time"):
                try:
                    dt = datetime.fromisoformat(str(event["event_time"]))
                    time_note = f" at {dt.strftime('%-I:%M %p')}"
                except Exception:
                    pass

            await update.message.reply_text(
                f"✅ *Locked in:* {event['name']}{time_note}\nI'll remind you an hour before it starts.",
                parse_mode=ParseMode.MARKDOWN
            )
            upsert_session(chat_id, "IDLE")
        else:
            await update.message.reply_text(
                f"I've got options 1–{len(suggestions)}. Which one? Or say 'none' to skip."
            )
    except (ValueError, TypeError):
        await update.message.reply_text(
            "Just reply with the number of the one you like, or say 'none' if nothing grabbed you."
        )


async def handle_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Hey, I'm Morris 👋 Your personal guide to interesting things happening around you.\n\n"
        "I'll message you every morning with ideas for your day. "
        "Or just say 'hey Morris' anytime to get started."
    )
    upsert_session(str(update.effective_chat.id), "IDLE")


# ─── App builder ─────────────────────────────────────────────────────────────

def build_application() -> Application:
    app = Application.builder().token(settings.telegram_bot_token).build()
    app.add_handler(CommandHandler("start", handle_start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    return app
