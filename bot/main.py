import logging
from datetime import time as datetime_time

import telebot
from telebot import types

from app.config import settings
from bot.api_client import HabitApiClient

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

if not settings.bot_token:
    raise RuntimeError("BOT_TOKEN is required. Set it in .env.")

bot = telebot.TeleBot(settings.bot_token, parse_mode="HTML")
api = HabitApiClient()
pending_actions: dict[int, dict] = {}
authenticated_users: set[int] = set()
user_passwords: dict[int, str] = {}


def escape(value: object) -> str:
    """Escape user-controlled content before using Telegram HTML mode."""
    from html import escape as html_escape

    return html_escape(str(value))


def get_telegram_id(message) -> int:
    return int(message.from_user.id)


def is_authenticated(telegram_id: int) -> bool:
    return telegram_id in authenticated_users and telegram_id in api.tokens


def ensure_authentication(message) -> bool:
    """Ask the user to authenticate if the bot has no in-memory session."""
    telegram_id = get_telegram_id(message)
    if not is_authenticated(telegram_id):
        bot.reply_to(
            message,
            "Сначала выполните /start и "
            "зарегистрируйтесь или войдите.",
        )
        return False
    return True


def send_api_error(message, error: Exception) -> None:
    logger.warning("API operation failed: %s", error)
    bot.reply_to(
        message, f"Не удалось выполнить запрос: {escape(error)}"
    )


def make_habits_keyboard(habits: list[dict]) -> types.InlineKeyboardMarkup:
    keyboard = types.InlineKeyboardMarkup(row_width=2)
    for habit in habits:
        keyboard.row(
            types.InlineKeyboardButton(
                f"✅ {habit['name'][:30]}",
                callback_data=f"done:{habit['id']}",
            ),
            types.InlineKeyboardButton(
                f"↩️ {habit['name'][:25]}",
                callback_data=f"undone:{habit['id']}",
            ),
        )
    return keyboard


@bot.message_handler(commands=["start"])
def start_bot(message):
    telegram_id = get_telegram_id(message)
    display_name = message.from_user.first_name or "Telegram user"
    bot.send_message(
        message.chat.id,
        "Привет! Я помогу отслеживать "
        "привычки.\n"
        "Для регистрации отправьте пароль длиной "
        "от 10 символов.\n"
        "Если аккаунт уже создан, "
        "используйте /login.\n"
        "Пароль хранится только в виде хеша "
        "на сервере.",
    )
    pending_actions[telegram_id] = {
        "action": "register",
        "display_name": display_name,
    }


@bot.message_handler(commands=["login"])
def begin_login(message):
    telegram_id = get_telegram_id(message)
    pending_actions[telegram_id] = {"action": "login"}
    bot.reply_to(
        message,
        "Введите пароль от вашего аккаунта. "
        "Сообщение будет удалено, если "
        "Telegram это позволит.",
    )


@bot.message_handler(commands=["help"])
def show_help(message):
    bot.reply_to(
        message,
        "<b>Команды</b>\n"
        "/start — регистрация\n/login — вход\n"
        "/add_habit — добавить привычку\n"
        "/habits — список и отметки\n"
        "/edit_habit — изменить привычку\n"
        "/delete_habit — удалить привычку\n"
        "/track_habit — отметить выполнение\n"
        "/habit_stats — статистика\n"
        "/set_reminder — изменить время напоминания\n"
        "/cancel — отменить текущий диалог",
    )


@bot.message_handler(commands=["cancel"])
def cancel_action(message):
    pending_actions.pop(get_telegram_id(message), None)
    bot.reply_to(message, "Текущее действие отменено.")


@bot.message_handler(commands=["add_habit"])
def begin_add_habit(message):
    if not ensure_authentication(message):
        return
    pending_actions[get_telegram_id(message)] = {
        "action": "add",
        "step": "name",
    }
    bot.reply_to(message, "Введите название привычки:")


@bot.message_handler(commands=["habits", "track_habit"])
def list_user_habits(message):
    if not ensure_authentication(message):
        return
    try:
        habits = api.list_habits(get_telegram_id(message))
        if not habits:
            bot.reply_to(
                message,
                "Активных привычек пока нет. "
                "Добавьте первую: /add_habit",
            )
            return
        lines = ["<b>Ваши привычки на сегодня</b>"]
        for habit in habits:
            lines.append(
                f"\n<b>#{habit['id']} {escape(habit['name'])}</b>\n"
                f"{escape(habit['description'] or 'Без описания')}"
                "\n"
                f"Выполнено: {habit['completion_count']}/"
                f"{habit['target_completions']} "
                f"· напоминание {habit['reminder_time'][:5]}"
            )
        bot.send_message(
            message.chat.id,
            "\n".join(lines),
            reply_markup=make_habits_keyboard(habits),
        )
    except Exception as error:
        send_api_error(message, error)


@bot.callback_query_handler(
    func=lambda call: call.data.startswith(("done:", "undone:"))
)
def handle_completion(call):
    telegram_id = int(call.from_user.id)
    if not is_authenticated(telegram_id):
        bot.answer_callback_query(
            call.id, "Сессия истекла. Выполните /login."
        )
        return
    action, habit_id_text = call.data.split(":", 1)
    try:
        result = api.complete_habit(
            telegram_id, int(habit_id_text), action == "done"
        )
        status_text = (
            "выполнена"
            if result["is_completed"]
            else "отмечена как невыполненная"
        )
        bot.answer_callback_query(call.id, f"Привычка {status_text}")
        bot.send_message(
            call.message.chat.id,
            f"Прогресс: {result['completion_count']} "
            "выполнений.",
        )
    except Exception as error:
        bot.answer_callback_query(
            call.id, "Не удалось сохранить отметку"
        )
        logger.warning("Completion update failed: %s", error)


@bot.message_handler(commands=["edit_habit"])
def begin_edit_habit(message):
    if not ensure_authentication(message):
        return
    pending_actions[get_telegram_id(message)] = {
        "action": "edit",
        "step": "id",
    }
    bot.reply_to(
        message, "Введите ID привычки. Список: /habits"
    )


@bot.message_handler(commands=["delete_habit"])
def begin_delete_habit(message):
    if not ensure_authentication(message):
        return
    pending_actions[get_telegram_id(message)] = {
        "action": "delete",
        "step": "id",
    }
    bot.reply_to(
        message, "Введите ID привычки, которую нужно удалить:"
    )


@bot.message_handler(commands=["set_reminder"])
def begin_set_reminder(message):
    if not ensure_authentication(message):
        return
    pending_actions[get_telegram_id(message)] = {
        "action": "reminder",
        "step": "id",
    }
    bot.reply_to(message, "Введите ID привычки:")


@bot.message_handler(commands=["habit_stats"])
def begin_stats(message):
    if not ensure_authentication(message):
        return
    pending_actions[get_telegram_id(message)] = {
        "action": "stats",
        "step": "id",
    }
    bot.reply_to(
        message, "Введите ID привычки для просмотра статистики:"
    )


@bot.message_handler(
    func=lambda message: bool(
        message.from_user and int(message.from_user.id) in pending_actions
    ),
    content_types=["text"],
)
def process_pending_action(message):
    telegram_id = get_telegram_id(message)
    action_data = pending_actions.get(telegram_id)
    if action_data is None:
        return
    action = action_data["action"]
    message_text = (message.text or "").strip()

    if action in {"register", "login"}:
        try:
            bot.delete_message(message.chat.id, message.message_id)
        except Exception:
            logger.info("Telegram did not allow password message deletion")
        if len(message_text) < 10 and action == "register":
            bot.send_message(
                message.chat.id,
                "Пароль должен содержать не менее "
                "10 символов. Повторите ввод или /cancel.",
            )
            return
        try:
            if action == "register":
                api.register(
                    telegram_id, action_data["display_name"], message_text
                )
                bot.send_message(
                    message.chat.id,
                    "Регистрация завершена. "
                    "Теперь добавьте привычку: /add_habit",
                )
            else:
                api.login(telegram_id, message_text)
                bot.send_message(
                    message.chat.id, "Вход выполнен. Используйте /habits."
                )
            authenticated_users.add(telegram_id)
            pending_actions.pop(telegram_id, None)
        except Exception as error:
            bot.send_message(
                message.chat.id,
                "Не удалось выполнить вход/регистрацию: "
                f"{escape(error)}",
            )
        return

    if not is_authenticated(telegram_id):
        pending_actions.pop(telegram_id, None)
        bot.send_message(
            message.chat.id,
            "Сессия отсутствует. Выполните /start или /login.",
        )
        return

    try:
        if action == "add":
            step = action_data["step"]
            if step == "name":
                action_data.update(name=message_text, step="description")
                bot.reply_to(message, "Введите описание (или -):")
            elif step == "description":
                action_data.update(
                    description="" if message_text == "-" else message_text,
                    step="goal",
                )
                bot.reply_to(message, "Введите цель (или -):")
            elif step == "goal":
                action_data.update(
                    goal="" if message_text == "-" else message_text,
                    step="target",
                )
                bot.reply_to(
                    message,
                    "Сколько выполнений нужно для завершения? "
                    f"Введите число или {settings.habit_target_completions}:",
                )
            elif step == "target":
                target = int(message_text or settings.habit_target_completions)
                if target < 1 or target > 3650:
                    raise ValueError("Укажите число от 1 до 3650")
                action_data.update(target_completions=target, step="reminder")
                bot.reply_to(
                    message,
                    f"Время напоминания HH:MM "
                    f"(например, {settings.default_reminder_time}):",
                )
            elif step == "reminder":
                datetime_time.fromisoformat(message_text)
                habit = api.create_habit(
                    telegram_id,
                    {
                        "name": action_data["name"],
                        "description": action_data["description"],
                        "goal": action_data["goal"],
                        "target_completions": action_data[
                            "target_completions"
                        ],
                        "reminder_time": message_text,
                    },
                )
                pending_actions.pop(telegram_id, None)
                bot.reply_to(
                    message,
                    f"Привычка «{escape(habit['name'])}» "
                    "создана. /habits",
                )
        elif action in {"edit", "delete", "reminder", "stats"}:
            if action_data["step"] == "id":
                habit_id = int(message_text)
                if action == "delete":
                    api.delete_habit(telegram_id, habit_id)
                    pending_actions.pop(telegram_id, None)
                    bot.reply_to(message, "Привычка удалена.")
                    return
                if action == "stats":
                    stats = api.get_stats(telegram_id, habit_id)
                    pending_actions.pop(telegram_id, None)
                    bot.reply_to(
                        message,
                        f"<b>{escape(stats['name'])}</b>\n"
                        f"Выполнено: {stats['completion_count']}/"
                        f"{stats['target_completions']}\n"
                        f"Осталось: {stats['remaining_completions']}\n"
                        "Записанных дней: "
                        f"{stats['total_recorded_days']}\n"
                        "Дней с выполнением: "
                        f"{stats['completed_days']}\n"
                        "Успешность: "
                        f"{stats['completion_rate_percent']}%",
                    )
                    return
                action_data.update(habit_id=habit_id, step="value")
                if action == "edit":
                    bot.reply_to(
                        message,
                        "Что изменить? Введите name, description, "
                        "goal, target или reminder:",
                    )
                else:
                    bot.reply_to(
                        message, "Введите новое время напоминания HH:MM:"
                    )
            elif action_data["step"] == "value":
                habit_id = action_data["habit_id"]
                if action == "reminder":
                    datetime_time.fromisoformat(message_text)
                    api.update_habit(
                        telegram_id, habit_id, {"reminder_time": message_text}
                    )
                else:
                    field_name = message_text.lower()
                    if field_name not in {
                        "name",
                        "description",
                        "goal",
                        "target",
                        "reminder",
                    }:
                        raise ValueError(
                            "Допустимые поля:"
                            "name, description, goal, target, reminder"
                        )
                    action_data.update(field_name=field_name, step="new_value")
                    bot.reply_to(message, "Введите новое значение:")
                    return
                pending_actions.pop(telegram_id, None)
                bot.reply_to(message, "Изменения сохранены.")
            elif action_data["step"] == "new_value":
                field_name = action_data["field_name"]
                field_map = {
                    "target": "target_completions",
                    "reminder": "reminder_time",
                }
                field_name = field_map.get(field_name, field_name)
                value = message_text
                if field_name == "target_completions":
                    value = int(value)
                elif field_name == "reminder_time":
                    datetime_time.fromisoformat(value)
                api.update_habit(
                    telegram_id, action_data["habit_id"], {field_name: value}
                )
                pending_actions.pop(telegram_id, None)
                bot.reply_to(message, "Изменения сохранены.")
    except (ValueError, TypeError) as error:
        bot.reply_to(
            message, f"Проверьте ввод: {escape(error)}. "
            "Повторите или /cancel.",
        )
    except Exception as error:
        pending_actions.pop(telegram_id, None)
        send_api_error(message, error)


def run_bot() -> None:
    """Start Telegram long polling."""
    logger.info("Starting habit tracker Telegram bot")
    bot.infinity_polling(
        skip_pending=True,
        timeout=30,
        long_polling_timeout=30,
    )


if __name__ == "__main__":
    run_bot()
