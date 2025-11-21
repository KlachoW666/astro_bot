from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from datetime import datetime
from config import TIMEZONE
from main import bot
from horoscope import generate_horoscope
from db import get_db_connection

# === Ежедневная рассылка гороскопов ===

async def send_daily_horoscope():
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT user_id, sign FROM users WHERE subscription_status = 'active'")
    users = cur.fetchall()
    cur.close()
    conn.close()

    for user_id, sign in users:
        horoscope = generate_horoscope(user_id, sign)
        try:
            await bot.send_message(user_id, horoscope)
        except:
            continue

# === Еженедельные напоминания о подписке ===

async def send_subscription_reminder():
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT user_id FROM users WHERE subscription_status = 'inactive'")
    users = cur.fetchall()
    cur.close()
    conn.close()

    for (user_id,) in users:
        try:
            await bot.send_message(
                user_id,
                "🔔 Напоминание: ваша премиум-подписка не активна. Хотите продлить?"
            )
        except:
            continue

# === Планировщики ===

def scheduler():
    scheduler = AsyncIOScheduler()
    scheduler.add_job(
        send_daily_horoscope,
        CronTrigger(hour=8, minute=0, second=0, timezone=TIMEZONE)
    )
    scheduler.start()

def subscription_reminder_scheduler():
    scheduler = AsyncIOScheduler()
    scheduler.add_job(
        send_subscription_reminder,
        CronTrigger(day_of_week="mon", hour=9, minute=0, timezone=TIMEZONE)
    )
    scheduler.start()
