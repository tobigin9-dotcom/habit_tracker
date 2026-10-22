# Habit Tracker — Telegram + FastAPI

Telegram habit tracker built with Python 3.11, pyTelegramBotAPI, FastAPI, PostgreSQL,
SQLAlchemy 2, Alembic, JWT, Argon2 password hashing, APScheduler and Docker Compose.

## Features

- Telegram registration and login; bot messages are the user-facing interface.
- JWT-protected REST API and a separate internal bot-to-API bearer token.
- Per-user habit CRUD, daily completion status, completion statistics.
- Per-habit reminders; background reminder service polls the API.
- Daily carry-forward: unfinished active habits remain available on later days until
  the target completion count (default 21) is reached.
- PostgreSQL persistence and Alembic migrations.

## Quick start

1. Install Docker Desktop / Docker Engine and Docker Compose.
2. Copy `.env.example` to `.env`.
3. Generate secrets and update `.env`:
   ```bash
   python -c "import secrets; print(secrets.token_urlsafe(48))"
   ```
   Use a different generated value for `JWT_SECRET_KEY` and `BOT_API_TOKEN`.
4. Create a Telegram bot with `@BotFather`; set `BOT_TOKEN` in `.env`.
5. Run:
   ```bash
   docker compose up --build
   ```
   The database migration runs before the API starts. API docs: http://localhost:8000/docs.
6. In Telegram, open your bot and send `/start`.

## Telegram commands

- `/start` — register a Telegram account.
- `/help` — command list.
- `/add_habit` — add a habit (name, description, target, reminder time).
- `/habits` — show today's habits and inline completion buttons.
- `/edit_habit` — edit a habit.
- `/delete_habit` — delete a habit.
- `/track_habit` — show completion buttons for today's habits.
- `/habit_stats` — completion statistics.
- `/set_reminder` — change a habit's reminder time.

Use reminder times in 24-hour `HH:MM` format. The configured `TIMEZONE` is used by the
reminder worker. A reminder is sent at most once per user/habit/local day.

## API overview

- `POST /auth/register` — register a Telegram ID and password hash.
- `POST /auth/token` — exchange Telegram ID + password for a JWT.
- `GET /users/me`
- `GET/POST /habits`
- `GET/PATCH/DELETE /habits/{habit_id}`
- `POST /habits/{habit_id}/completion`
- `GET /habits/{habit_id}/stats`
- `GET /internal/reminders/due` — internal bot-token protected.
- `POST /internal/reminders/{habit_id}/sent` — record a reminder send.
- `GET /health`

## Security notes

- Never commit `.env` or share the bot token.
- The bot deletes the password message where Telegram permits it. Telegram IDs are
  verified from the incoming update, and the bot keeps API JWTs in memory only.
- Passwords are Argon2-hashed; JWTs are signed and expire.
- API endpoints require JWT ownership checks. Internal reminder endpoints use a
  separate service token.
- For production, terminate TLS at a reverse proxy, restrict API exposure, rotate secrets,
  configure backups, monitoring, rate limiting and privacy/retention policy.
- The API is published on port 8000 for local evaluation. Restrict or remove this port
  in production and place it behind TLS.

## Development

```bash
poetry install
poetry run ruff check .
poetry run pytest
```

For local development outside Docker, set `DATABASE_URL` to a reachable PostgreSQL URL.
