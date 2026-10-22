import logging
from zoneinfo import ZoneInfo

import httpx
import telebot
from apscheduler.schedulers.blocking import BlockingScheduler

from app.config import settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
scheduler = BlockingScheduler(timezone=ZoneInfo(settings.timezone))
telegram_bot = (
    telebot.TeleBot(settings.bot_token) if settings.bot_token else None
)


def send_due_reminders() -> None:
    """Poll the API and send due habit reminders."""
    if telegram_bot is None:
        logger.error(
            "BOT_TOKEN is missing; reminder worker cannot send messages"
        )
        return
    try:
        response = httpx.get(
            f"{settings.api_base_url}/internal/reminders/due",
            headers={"X-Internal-Token": settings.bot_api_token},
            timeout=15,
        )
        response.raise_for_status()
        for reminder in response.json():
            if reminder.get("is_completed_today"):
                continue
            message = (
                "⏰ Напоминание о привычке: "
                f"{reminder['name']}\n"
                f"{reminder['description']}\n\n"
                "Отметьте выполнение командой "
                "/habits."
            )
            try:
                telegram_bot.send_message(reminder["telegram_id"], message)
                sent_response = httpx.post(
                    f"{settings.api_base_url}/internal/reminders/"
                    f"{reminder['habit_id']}/sent",
                    headers={"X-Internal-Token": settings.bot_api_token},
                    timeout=10,
                )
                sent_response.raise_for_status()
            except Exception:
                logger.exception(
                    "Failed to send reminder for habit %s",
                    reminder["habit_id"],
                )
    except Exception:
        logger.exception("Reminder polling failed")


if __name__ == "__main__":
    scheduler.add_job(
        send_due_reminders, "interval", minutes=1, max_instances=1
    )
    logger.info("Reminder worker started in timezone %s", settings.timezone)
    scheduler.start()
