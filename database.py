import psycopg2
import psycopg2.extras
from datetime import datetime
from typing import Optional
from config import settings


def get_conn():
    return psycopg2.connect(settings.database_url, cursor_factory=psycopg2.extras.RealDictCursor)


def init_db():
    """Create tables if they don't exist."""
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS sessions (
                    id SERIAL PRIMARY KEY,
                    chat_id TEXT NOT NULL,
                    state TEXT NOT NULL DEFAULT 'IDLE',
                    -- IDLE | AWAITING_PREFERENCE | AWAITING_SELECTION
                    suggestions JSONB,
                    created_at TIMESTAMPTZ DEFAULT NOW(),
                    updated_at TIMESTAMPTZ DEFAULT NOW()
                );

                CREATE TABLE IF NOT EXISTS events (
                    id SERIAL PRIMARY KEY,
                    chat_id TEXT NOT NULL,
                    name TEXT NOT NULL,
                    venue TEXT,
                    address TEXT,
                    event_time TIMESTAMPTZ,
                    description TEXT,
                    url TEXT,
                    reminder_sent BOOLEAN DEFAULT FALSE,
                    created_at TIMESTAMPTZ DEFAULT NOW()
                );

                CREATE INDEX IF NOT EXISTS idx_events_reminder
                    ON events (event_time, reminder_sent)
                    WHERE reminder_sent = FALSE;
            """)
        conn.commit()
    print("Database initialized.")


# ─── Session management ───────────────────────────────────────────────────────

def get_session(chat_id: str) -> Optional[dict]:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT * FROM sessions WHERE chat_id = %s ORDER BY id DESC LIMIT 1",
                (chat_id,)
            )
            return cur.fetchone()


def upsert_session(chat_id: str, state: str, suggestions: Optional[list] = None):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO sessions (chat_id, state, suggestions, updated_at)
                VALUES (%s, %s, %s, NOW())
                ON CONFLICT DO NOTHING
            """, (chat_id, state, psycopg2.extras.Json(suggestions) if suggestions else None))

            # Always update the most recent session
            cur.execute("""
                UPDATE sessions
                SET state = %s,
                    suggestions = COALESCE(%s::jsonb, suggestions),
                    updated_at = NOW()
                WHERE id = (
                    SELECT id FROM sessions WHERE chat_id = %s ORDER BY id DESC LIMIT 1
                )
            """, (
                state,
                psycopg2.extras.Json(suggestions) if suggestions is not None else None,
                chat_id
            ))
        conn.commit()


# ─── Event management ────────────────────────────────────────────────────────

def save_event(chat_id: str, event: dict) -> int:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO events (chat_id, name, venue, address, event_time, description, url)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                RETURNING id
            """, (
                chat_id,
                event.get("name"),
                event.get("venue"),
                event.get("address"),
                event.get("event_time"),  # should be a datetime or None
                event.get("description"),
                event.get("url"),
            ))
            row = cur.fetchone()
        conn.commit()
    return row["id"]


def get_events_needing_reminder() -> list:
    """Return events starting within the next 60–65 minutes that haven't been reminded."""
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT * FROM events
                WHERE reminder_sent = FALSE
                  AND event_time IS NOT NULL
                  AND event_time BETWEEN NOW() + INTERVAL '55 minutes'
                                     AND NOW() + INTERVAL '65 minutes'
            """)
            return cur.fetchall()


def mark_reminder_sent(event_id: int):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE events SET reminder_sent = TRUE WHERE id = %s",
                (event_id,)
            )
        conn.commit()
