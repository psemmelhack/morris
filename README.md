# Morris 🎩
### Your personal guide to interesting things happening around you.

Morris wakes up every morning at 6am, asks what you feel like doing, searches for real local
options using Claude + Tavily, and reminds you via Telegram and email when something you picked
is about to start.

---

## Setup

### 1. Prerequisites
- Python 3.11+
- PostgreSQL running locally (or a remote instance)
- A Telegram bot (create via [@BotFather](https://t.me/botfather))
- Your Telegram chat ID (message [@userinfobot](https://t.me/userinfobot))
- A [Tavily](https://tavily.com) API key
- A [Resend](https://resend.com) account with a verified domain

### 2. Clone and install

```bash
cd morris
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 3. Configure

```bash
cp .env.example .env
# Edit .env with your actual keys
```

### 4. Create the database

```bash
createdb morris
# Tables are created automatically on first run
```

---

## Running

### Local development (polling mode — no webhook needed)

```bash
python main.py --poll
```

Morris will connect to Telegram via long-polling. No public URL required.
Type "hey Morris" or `/start` in your Telegram chat to test.

### Production (webhook mode)

You need a public HTTPS URL (Railway, Fly.io, Render, etc.)

```bash
uvicorn main:app --host 0.0.0.0 --port 8000
```

Set `WEBHOOK_BASE_URL` in your `.env` to your public URL.

---

## How it works

```
6:00 AM PT
    ↓
Scheduler fires → Telegram: "Good morning! What would you like to do today?"
    ↓
You reply: "something outdoorsy, maybe a hike or a farmers market"
    ↓
CrewAI runs:
  Scout Agent  → searches Tavily for real local events matching your request
  Curator Agent → picks the best 3-5, writes them up with Morris's personality
    ↓
Telegram: numbered list of options with times, venues, links
    ↓
You reply: "3"
    ↓
Event saved to DB → Scheduler watches for T-60min
    ↓
1 hour before: Telegram + email reminder sent
```

---

## Conversation states

| State | Meaning |
|---|---|
| `IDLE` | Waiting for morning trigger or manual wake |
| `AWAITING_PREFERENCE` | Waiting for what you want to do |
| `AWAITING_SELECTION` | Presented options, waiting for number |

---

## Manual triggers

Send any of these to your bot to start a session outside of 6am:
- `/start`
- `/morning`
- `hey morris`
- `wake up`
