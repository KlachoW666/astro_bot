import logging
import asyncio
import random
import json
import os
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import LabeledPrice, PreCheckoutQuery, Message, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import ReplyKeyboardBuilder
from config import API_TOKEN, PAYMENT_PROVIDER_TOKEN, TIMEZONE
from db import create_tables, ensure_user, set_user_sign, get_user_sign, update_subscription, get_subscription_status
from horoscope import generate_horoscope
# from tarot import generate_tarot  # Убираем импорт
from jobs import send_daily_horoscope, send_subscription_reminder
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

# Инициализация бота и диспетчера
bot = Bot(token=API_TOKEN)
dp = Dispatcher()

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Проверяем, если база данных и таблицы не созданы — создаём их
create_tables()

# Стили для текстов (для уникальности)
STYLES = [
    "Мудрый наставник", "Шутливый философ", "Драматичный пророк", "Практичный психолог",
    "Мистический поёт", "Энергетический гид", "Дружелюбный ангел", "Тихий голос внутри",
    "Теневой наставник", "Путешественник по мирам", "Хранитель времени", "Певец души"
]

# Уникальные приветственные фразы
WELCOME_MESSAGES = [
    "✨ Привет! Я астробот, который говорит с тобой живым языком.",
    "🌟 Ты в точке, где звёзды начинают шептать. Прислушайся.",
    "🔮 Привет! Ты — герой своей сегодняшней истории. Я помогу её прочитать.",
    "🌙 Светит луна, ветер зовёт — ты готов к внутреннему путешествию?",
    "💫 Ты нашёл бота, где текст — это не просто слова, а отражение твоей души."
]

# Фразы для выбора знака
SIGN_PROMPTS = [
    "Выбери свой знак зодиака — и пусть он станет твоим компасом на день.",
    "Кто ты сегодня? Выбери знак и начни путешествие.",
    "Твои звёзды ждут — укажи, под каким ты родился.",
    "Сила дня — в тебе. Выбери знак, и я расскажу, как её использовать.",
    "Звёзды хотят с тобой поговорить. Под каким ты знаком?"
]

# Карты Таро
TAROT_CARDS = [
    "Шут", "Маг", "Верховная Жрица", "Императрица", "Император", "Иерофант", "Влюбленные", "Колесница", "Сила", "Повешенный", "Смерть", "Умеренность", "Дьявол", "Башня", "Звезда", "Луна", "Солнце", "Суд", "Мир",
    "2 Жезлов", "3 Жезлов", "4 Жезлов", "5 Жезлов", "6 Жезлов", "7 Жезлов", "8 Жезлов", "9 Жезлов", "10 Жезлов", "Валет Жезлов", "Рыцарь Жезлов", "Дама Жезлов", "Король Жезлов",
    "2 Кубков", "3 Кубков", "4 Кубков", "5 Кубков", "6 Кубков", "7 Кубков", "8 Кубков", "9 Кубков", "10 Кубков", "Валет Кубков", "Рыцарь Кубков", "Дама Кубков", "Король Кубков",
    "2 Мечей", "3 Мечей", "4 Мечей", "5 Мечей", "6 Мечей", "7 Мечей", "8 Мечей", "9 Мечей", "10 Мечей", "Валет Мечей", "Рыцарь Мечей", "Дама Мечей", "Король Мечей",
    "2 Пентаклей", "3 Пентаклей", "4 Пентаклей", "5 Пентаклей", "6 Пентаклей", "7 Пентаклей", "8 Пентаклей", "9 Пентаклей", "10 Пентаклей", "Валет Пентаклей", "Рыцарь Пентаклей", "Дама Пентаклей", "Король Пентаклей"
]

# --- НОВЫЙ КОД ДЛЯ ТАРО ---

# Загрузка интерпретаций из JSON-файла
def load_tarot_interpretations():
    """Загружает интерпретации карт Таро из JSON-файла в папке data."""
    json_path = os.path.join('data', 'tarot_interpretations.json')
    try:
        with open(json_path, 'r', encoding='utf-8') as file:
            interpretations = json.load(file)
        print(f"Интерпретации Таро загружены из {json_path}") # Лог для проверки
        return interpretations
    except FileNotFoundError:
        print(f"Файл {json_path} не найден!")
        return {}
    except json.JSONDecodeError:
        print(f"Ошибка при чтении файла {json_path}!")
        return {}

TAROT_INTERPRETATIONS = load_tarot_interpretations()

def get_tarot_card():
    """Выбирает случайную карту из списка."""
    if not TAROT_CARDS:
        return None
    return random.choice(TAROT_CARDS)

def get_tarot_interpretation(card_name, topic):
    """
    Формирует текст интерпретации для одной карты, привязывая к теме.
    """
    if not TAROT_INTERPRETATIONS or not card_name or card_name not in TAROT_INTERPRETATIONS:
        return f"Интерпретация для карты '{card_name}' недоступна."

    card_data = TAROT_INTERPRETATIONS[card_name]
    # Простой пример: выбираем светлое или теневое значение
    aspect = random.choice(["light", "shadow"])
    interpretation_text = card_data.get(aspect, "Интерпретация отсутствует.")

    # Формируем общий текст с привязкой к теме
    prompt_templates = [
        f"Твоя карта по теме '{topic}': **{card_name}**.\n\nЗначение: {interpretation_text}",
        f"Для вопроса '{topic}' выпала карта: **{card_name}**.\n\nЕё толкование: {interpretation_text}",
        f"Карта Таро: **{card_name}**.\n\nВ контексте '{topic}': {interpretation_text}",
    ]

    return random.choice(prompt_templates)

def generate_tarot(user_id, topic, sign=None):
    """
    Генерирует ответ с раскладом Таро по заданной теме.
    """
    if not topic:
        topic = "Вопрос без границ"

    # Выбираем 1 карту
    drawn_card = get_tarot_card()
    if not drawn_card:
        return "Ошибка при выборе карты."

    interpretation = get_tarot_interpretation(drawn_card, topic)

    # Пример добавления общей вводной
    introduction = random.choice([
        "Шепот звёзд складывается в образ...",
        "Карты раскрывают тайну твоего вопроса о...",
        "Смотри, что говорят Арканы о...",
        "Вот что видят карты по теме..."
    ])

    full_text = f"{introduction} '{topic}':\n\n{interpretation}"
    return full_text

# --- КОНЕЦ НОВОГО КОДА ДЛЯ ТАРО ---

# Функция для генерации уникального приветствия
def get_welcome_message():
    style = random.choice(STYLES)
    welcome = random.choice(WELCOME_MESSAGES)
    prompt = random.choice(SIGN_PROMPTS)
    return f"{welcome}\n\n{prompt}"

# Функция для генерации клавиатуры с знаками зодиака
def build_zodiac_keyboard():
    kb = ReplyKeyboardBuilder()
    zodiac_signs = [
        "♈ Овен", "♉ Телец", "♊ Близнецы", "♋ Рак", "♌ Лев", "♍ Дева",
        "♎ Весы", "♏ Скорпион", "♐ Стрелец", "♑ Козерог", "♒ Водолей", "♓ Рыбы"
    ]
    for sign in zodiac_signs:
        kb.button(text=sign)
    kb.adjust(3, 3, 3, 3)
    return kb.as_markup(resize_keyboard=True, one_time_keyboard=True)

# Главное меню
def build_main_menu():
    kb = ReplyKeyboardBuilder()
    kb.button(text="🔮 Гороскоп на сегодня")
    kb.button(text="🃏 Расклад Таро")
    kb.button(text="⭐ Подписка")
    kb.button(text="👤 Профиль")
    kb.adjust(2, 2)
    return kb.as_markup(resize_keyboard=True)

# Хэндлер для команды /start
@dp.message(Command("start"))
async def cmd_start(message: Message):
    user_id = message.from_user.id
    # Создаём запись пользователя в базе данных, если ещё нет
    ensure_user(user_id)

    await message.answer(
        get_welcome_message(),
        reply_markup=build_zodiac_keyboard(),
    )

# Хэндлер для выбора знака зодиака
@dp.message(lambda m: m.text in ["♈ Овен", "♉ Телец", "♊ Близнецы", "♋ Рак", "♌ Лев", "♍ Дева",
                                "♎ Весы", "♏ Скорпион", "♐ Стрелец", "♑ Козерог", "♒ Водолей", "♓ Рыбы"])
async def cmd_set_sign(message: Message):
    sign = message.text.split(" ", 1)[1]  # Убираем эмодзи
    user_id = message.from_user.id
    set_user_sign(user_id, sign)
    await message.answer(f"✅ Записал: твой знак — {sign}.\n\nТеперь ты можешь получить:\n🔮 Гороскоп командой /horoscope\n🃏 Расклад Таро — /tarot", reply_markup=build_main_menu())

# Хэндлер для команды /horoscope
@dp.message(Command("horoscope"))
@dp.message(lambda m: m.text == "🔮 Гороскоп на сегодня")
async def cmd_horoscope(message: Message):
    user_id = message.from_user.id
    sign = get_user_sign(user_id)
    if not sign:
        await message.answer(
            "Сначала выбери свой знак зодиака, чтобы я мог говорить с тобой точнее:",
            reply_markup=build_zodiac_keyboard(),
        )
        return
    text = generate_horoscope(user_id, sign)
    await message.answer(text)

# Хэндлер для команды /tarot
@dp.message(Command("tarot"))
@dp.message(lambda m: m.text == "🃏 Расклад Таро")
async def cmd_tarot(message: Message):
    user_id = message.from_user.id
    sign = get_user_sign(user_id)
    topic = "Вопрос без границ"  # можно потом сделать выбор через кнопки
    text = generate_tarot(user_id, topic, sign=sign) # Теперь вызывает функцию из main.py
    await message.answer(text or "Сегодня карты молчат. Попробуй чуть позже. 🃏")

# Хэндлер для команды /subscribe
@dp.message(Command("subscribe"))
@dp.message(lambda m: m.text == "⭐ Подписка")
async def cmd_subscribe_info(message: Message):
    await message.answer(
        "🌟 Премиум даёт тебе:\n"
        "• Ежедневные уникальные расклады Таро\n"
        "• Расширенные гороскопы по дате рождения\n"
        "• Еженедельные PDF-отчёты (можно добавить позже)\n\n"
        "Чтобы оформить подписку, используй команду /pay или нажми на кнопку:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="Купить подписку", callback_data="pay_subscription")]
        ])
    )

# Хэндлер для команды /pay
@dp.message(Command("pay"))
async def cmd_pay(message: Message):
    prices = [LabeledPrice(label="Премиум на 1 месяц", amount=300)]  # 300 Stars
    await message.bot.send_invoice(
        chat_id=message.chat.id,
        title="Премиум-подписка",
        description="Уникальные расклады, расширенные гороскопы и больше магии текста ✨",
        payload="premium_subscription",
        provider_token="",  # Пусто для Stars
        currency="XTR",     # Stars
        prices=prices,
    )

# Хэндлер для профиля
@dp.message(lambda m: m.text == "👤 Профиль")
async def cmd_profile(message: Message):
    user_id = message.from_user.id
    sign = get_user_sign(user_id)
    sub_status = get_subscription_status(user_id) or "free"
    await message.answer(
        f"👤 Твой профиль:\n"
        f"• Знак: {sign or 'не выбран'}\n"
        f"• Подписка: {sub_status}\n\n"
        f"Если хочешь изменить знак — просто напиши его снова."
    )

# Хэндлер для pre_checkout_query
@dp.pre_checkout_query()
async def process_pre_checkout(pre_checkout_q: PreCheckoutQuery):
    await bot.answer_pre_checkout_query(pre_checkout_q.id, ok=True)

# Хэндлер для успешной оплаты
@dp.message(lambda message: message.successful_payment is not None)
async def successful_payment_handler(message: Message):
    user_id = message.from_user.id
    update_subscription(user_id, "active")
    await message.answer(
        "✨ Спасибо за доверие!\nТвоя премиум-подписка активирована. Теперь ты — в эпицентре магии и текста."
    )

# Планировщики задач
async def main():
    logging.basicConfig(level=logging.INFO)
    # Планировщик для ежедневных гороскопов
    scheduler = AsyncIOScheduler(timezone=TIMEZONE)
    scheduler.add_job(
        send_daily_horoscope,
        trigger=CronTrigger(hour=8, minute=0, second=0, timezone=TIMEZONE),
        kwargs={"bot": bot},
    )
    scheduler.add_job(
        send_subscription_reminder,
        trigger=CronTrigger(day_of_week="mon", hour=9, minute=0, timezone=TIMEZONE),
        kwargs={"bot": bot},
    )
    scheduler.start()

    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())