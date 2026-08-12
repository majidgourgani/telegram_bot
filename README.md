# Financial Scan — Telegram Bot + Admin Dashboard

A Telegram bot that runs a financial self-assessment ("financial scan") quiz,
paired with a web dashboard to configure it, edit its content, browse the
collected responses, and view analytics.

Everything the bot says or checks — texts, questions, answer scores, the
channel gate, the consent step — lives in the database and is editable from the
dashboard **with no code change and no redeploy** (content and toggles apply on
the user's next interaction; changing the bot token needs a bot restart).

## Architecture

```
app/
├── config.py            # env / .env settings (bootstrap + infra only)
├── database.py          # SQLAlchemy engine, session, init_db()
├── models.py            # ORM models (settings, areas, questions, responses, events…)
├── seed.py              # first-run defaults (the original bot's content)
├── services/            # shared logic used by BOTH bot and web
│   ├── content.py       #   read/write settings + editable content
│   ├── catalog.py       #   CRUD for areas / questions / options
│   ├── scoring.py       #   pure scoring helpers
│   └── responses.py     #   persist responses, analytics queries
├── bot/                 # Telegram bot (python-telegram-bot)
│   ├── handlers.py      #   conversation flow (reads all content from DB)
│   ├── keyboards.py  states.py  utils.py  main.py
└── web/                 # FastAPI admin dashboard (server-rendered)
    ├── main.py  security.py  templating.py
    ├── routers/         #   auth, dashboard, responses, questions, settings, analytics
    ├── templates/       #   Jinja2 pages
    └── static/          #   styles.css, analytics.js (charts, no external deps)
run_bot.py   run_web.py   scripts/migrate_csv.py
Dockerfile   docker-compose.yml
```

Both processes share a single **SQLite** database. Swapping to PostgreSQL later
is just a `DATABASE_URL` change.

## Quick start (local)

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env        # then edit .env
```

Fill in `.env`:

- `BOT_TOKEN` — from [@BotFather](https://t.me/BotFather)
- `CHANNEL_ID` / `CHANNEL_LINK` — your private channel
- `ADMIN_USERNAME` / `ADMIN_PASSWORD` — dashboard login
- `SECRET_KEY` — `python -c "import secrets; print(secrets.token_hex(32))"`

Run the two processes in separate terminals:

```bash
python run_web.py     # dashboard at http://localhost:8000
python run_bot.py     # starts polling Telegram
```

The database and default content are created automatically on first run.

> The bot must be an **admin** of the private channel for the membership check
> to work.

## Quick start (Docker)

```bash
cp .env.example .env    # edit it
docker compose up --build
```

- Dashboard: http://localhost:8000
- Bot: runs in the background, polling Telegram
- Data persists in the `app-data` Docker volume

## Dashboard capabilities

| Page | What you can do |
|------|-----------------|
| **Overview** | Key stats and a bot-configuration health check |
| **Responses** | Search, browse, inspect and delete submissions; export **CSV / Excel** |
| **Questions & Content** | Add/edit/reorder questions, manage areas and answer options |
| **Settings** | Bot token, channel, support links, feature toggles, and all bot texts; upload the completion image |
| **Analytics** | Responses over time, average score per area, and a start → consent → complete funnel |

### Feature toggles (Settings → Features)

- **Require channel membership** — gate the test behind joining the channel
- **Require explicit consent** — show the data-use notice before registration
- **Send image on completion** — deliver the uploaded mini-course image

## Importing old data

If you have a legacy `users.csv` from the original single-file bot:

```bash
python -m scripts.migrate_csv users.csv
```

## Security notes

- The bot token is seeded from `.env` on first run, then stored in the DB so it
  is editable from Settings. Keep `.env` out of version control (it is
  git-ignored) and **rotate any token that was ever committed** via @BotFather.
- The dashboard is protected by a single admin login. Put it behind HTTPS / a
  reverse proxy before exposing it to the internet, and use a strong
  `SECRET_KEY` and `ADMIN_PASSWORD`.

## Tech stack

python-telegram-bot · FastAPI · SQLAlchemy · Jinja2 · SQLite · Docker
