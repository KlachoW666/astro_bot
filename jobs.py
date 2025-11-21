from aiogram import Bot
from config import TIMEZONE
from db import get_db_connection
from horoscope import generate_horoscope


async def send_daily_horoscope(bot: Bot):
    """
    Ежедневная рассылка гороскопов всем пользователям, у которых выбран знак.
    """
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT user_id, sign FROM users WHERE sign IS NOT NULL")
    rows = cur.fetchall()
    cur.close()
    conn.close()

    for user_id, sign in rows:
        text = generate_horoscope(user_id, sign)
        try:
            await bot.send_message(chat_id=user_id, text=text)
        except Exception:
            # Например, пользователь заблокировал бота — просто пропускаем
            continue


async def send_subscription_reminder(bot: Bot):
    """
    Пример напоминаний неактивным пользователям.
    Можно расширить логикой по датам.
    """
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(
        "SELECT user_id FROM users WHERE subscription_status = 'inactive'"
    )
    rows = cur.fetchall()
    cur.close()
    conn.close()

    for (user_id,) in rows:
        try:
            await bot.send_message(
                chat_id=user_id,
                text="🔔 Напоминание: твоя премиум-подписка сейчас не активна. "
                     "Хочешь вернуться к уникальным раскладам и расширенным гороскопам?",
            )
        except Exception:
            continue
