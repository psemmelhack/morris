import asyncio
import logging
import signal
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, Response
from telegram import Update

from config import settings
from database import init_db
from bot import build_application
from scheduler import create_scheduler

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

# ─── Build components ────────────────────────────────────────────────────────

telegram_app = build_application()
scheduler = create_scheduler()


# ─── FastAPI lifespan ────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("Initializing database...")
    init_db()
    from profile import init_profile_table
    init_profile_table()

    logger.info("Starting scheduler...")
    scheduler.start()

    logger.info("Initializing Telegram app...")
    await telegram_app.initialize()
    await telegram_app.start()

    # Set webhook
    webhook_url = f"{settings.webhook_base_url}/telegram/webhook"
    await telegram_app.bot.set_webhook(webhook_url)
    logger.info(f"Webhook set: {webhook_url}")

    logger.info("Morris is awake. 🟢")
    yield

    # Shutdown
    logger.info("Shutting down...")
    scheduler.shutdown()
    await telegram_app.stop()
    await telegram_app.shutdown()


# ─── FastAPI app ──────────────────────────────────────────────────────────────

app = FastAPI(title="Morris", lifespan=lifespan)


@app.get("/health")
async def health():
    return {"status": "ok", "agent": "Morris"}


@app.post("/telegram/webhook")
async def telegram_webhook(request: Request):
    data = await request.json()
    update = Update.de_json(data, telegram_app.bot)
    await telegram_app.process_update(update)
    return Response(status_code=200)


# ─── Dev runner (polling mode) ───────────────────────────────────────────────

async def run_polling():
    """Use this instead of webhook for local development."""
    init_db()
    scheduler.start()
    await telegram_app.initialize()
    await telegram_app.start()
    logger.info("Morris running in polling mode. 🟢")

    await telegram_app.updater.start_polling(drop_pending_updates=True)
    await asyncio.Event().wait()  # run forever


if __name__ == "__main__":
    import uvicorn
    import sys

    if "--poll" in sys.argv:
        # Local dev: python main.py --poll
        asyncio.run(run_polling())
    else:
        # Production: uvicorn main:app
        uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=False)
