import random
import json
from datetime import datetime, timedelta
from db import get_db_connection, get_used_phrases, save_user_phrase


# Загрузка данных из JSON-файлов
def load_data(filename):
    with open(f"data/{filename}", "r", encoding="utf-8") as f:
        return json.load(f)


# Загрузка всех данных
INTROS = load_data("horoscope_intros.json")
THEMES = list(load_data("horoscope_themes.json").keys())
THEME_LINES = load_data("horoscope_themes.json")
STYLES = list(load_data("horoscope_styles.json").keys())
STYLE_LINES = load_data("horoscope_styles.json")
SYMBOLS = load_data("horoscope_symbols.json")
ENDINGS = load_data("horoscope_endings.json")
QUOTES = load_data("quotes.json")


def _get_unique_quote_for_user(user_id: int) -> str:
    """
    Берём случайную цитату, которая не использовалась последние 2 дня.
    Если нет — возвращаем случайную.
    """
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT quote_id, text
        FROM quotes
        WHERE last_used IS NULL
           OR last_used < datetime('now', '-2 days')
        ORDER BY RANDOM()
        LIMIT 1
        """
    )
    row = cur.fetchone()
    if not row:
        cur.close()
        conn.close()
        return random.choice(QUOTES)

    quote_id, text = row
    # обновляем last_used
    cur.execute(
        "UPDATE quotes SET last_used = datetime('now') WHERE quote_id = ?",
        (quote_id,)
    )
    conn.commit()
    cur.close()
    conn.close()
    return text


def can_generate_horoscope(user_id: int) -> bool:
    """
    Проверяем, прошёл ли 1 день с последнего запроса.
    """
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(
        "SELECT last_gen_date FROM users WHERE user_id = ?",
        (user_id,)
    )
    row = cur.fetchone()
    cur.close()
    conn.close()

    if not row or not row["last_gen_date"]:
        return True  # Первый запрос — разрешён

    last_gen = datetime.fromisoformat(row["last_gen_date"])
    now = datetime.now()
    if now - last_gen >= timedelta(days=1):
        return True
    return False


def update_last_gen_date(user_id: int):
    """
    Обновляем дату последнего запроса.
    """
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(
        "UPDATE users SET last_gen_date = datetime('now') WHERE user_id = ?",
        (user_id,)
    )
    conn.commit()
    cur.close()
    conn.close()


def generate_horoscope(user_id: int, sign: str) -> str:
    """
    Генерация уникального гороскопа с рандомизацией:
    - интро
    - тема
    - стиль
    - символ дня
    - цитата
    - финал
    """
    if not can_generate_horoscope(user_id):
        return "🌙 Ты уже получил сегодняшний гороскоп. Приходи завтра — звёзды подготовят новый."

    used = set(get_used_phrases(user_id))

    # Пытаемся найти комбинацию, которой ещё не было
    attempts = 0
    max_attempts = 10
    theme = None
    style = None

    while attempts < max_attempts:
        candidate_theme = random.choice(THEMES)
        candidate_style = random.choice(STYLES)
        key = f"{candidate_theme}|{candidate_style}"
        if key not in used:
            theme = candidate_theme
            style = candidate_style
            save_user_phrase(user_id, key)
            break
        attempts += 1

    # если всё уже использовали — всё равно выбираем что-то, но без сохранения
    if theme is None or style is None:
        theme = random.choice(THEMES)
        style = random.choice(STYLES)

    # Собираем текст
    intro = random.choice(INTROS).format(sign=sign)
    theme_line = random.choice(THEME_LINES[theme])
    style_line = random.choice(STYLE_LINES[style])
    symbol = random.choice(SYMBOLS)
    quote = _get_unique_quote_for_user(user_id)
    ending = random.choice(ENDINGS)

    text = "\n".join([
        intro,
        theme_line,
        style_line,
        "",
        f"Символ дня: {symbol}.",
        f"Мысль дня: «{quote}»",
        "",
        ending
    ])

    # Обновляем дату последнего запроса
    update_last_gen_date(user_id)

    return text