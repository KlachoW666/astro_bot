import sqlite3
import json
from config import DATABASE_URL


def get_db_connection():
    """
    Возвращаем подключение к SQLite базе данных.
    Если база не существует, она будет создана.
    """
    conn = sqlite3.connect("astro_bot.db")  # SQLite база данных
    conn.row_factory = sqlite3.Row  # Для удобства работы с результатами запросов (как с dict)
    return conn


def create_tables():
    """
    Функция для создания таблиц, если они ещё не существуют.
    """
    conn = get_db_connection()
    cur = conn.cursor()

    # Создание таблицы пользователей
    cur.execute("""
    CREATE TABLE IF NOT EXISTS users (
        user_id BIGINT PRIMARY KEY,
        sign TEXT,
        birth_data DATE,
        subscription_status TEXT DEFAULT 'free',
        last_gen_date TIMESTAMP,
        used_phrases TEXT DEFAULT '[]',  -- JSON-строка
        tarot_history TEXT DEFAULT '[]'  -- JSON-строка
    );
    """)

    # Создание таблицы цитат (для гороскопов)
    cur.execute("""
    CREATE TABLE IF NOT EXISTS quotes (
        quote_id INTEGER PRIMARY KEY AUTOINCREMENT,
        text TEXT NOT NULL,
        last_used TIMESTAMP
    );
    """)

    # Создание таблицы карт Таро
    cur.execute("""
    CREATE TABLE IF NOT EXISTS tarot_cards (
        card_id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        meaning TEXT NOT NULL
    );
    """)

    # Создание таблицы истории цитат пользователя
    cur.execute("""
    CREATE TABLE IF NOT EXISTS user_quote_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        quote TEXT,
        used_at DATETIME DEFAULT CURRENT_TIMESTAMP
    );
    """)

    conn.commit()
    cur.close()
    conn.close()

    print("Таблицы созданы или уже существуют.")


def ensure_user(user_id: int):
    """
    Создаём запись пользователя, если её ещё нет.
    """
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(
        """
        INSERT OR IGNORE INTO users (user_id, subscription_status, used_phrases, tarot_history)
        VALUES (?, 'free', '[]', '[]')
        """,
        (user_id,),
    )
    conn.commit()
    cur.close()
    conn.close()


def set_user_sign(user_id: int, sign: str):
    """
    Устанавливаем знак зодиака для пользователя.
    """
    ensure_user(user_id)
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(
        """
        UPDATE users
        SET sign = ?
        WHERE user_id = ?
        """,
        (sign, user_id),
    )
    conn.commit()
    cur.close()
    conn.close()


def get_user_sign(user_id: int) -> str | None:
    """
    Получаем знак зодиака пользователя.
    """
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT sign FROM users WHERE user_id = ?", (user_id,))
    row = cur.fetchone()
    cur.close()
    conn.close()
    if row:
        return row["sign"]
    return None


def update_subscription(user_id: int, status: str):
    """
    Обновляем статус подписки пользователя.
    """
    ensure_user(user_id)
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(
        "UPDATE users SET subscription_status = ? WHERE user_id = ?",
        (status, user_id),
    )
    conn.commit()
    cur.close()
    conn.close()


def get_subscription_status(user_id: int) -> str | None:
    """
    Получаем статус подписки пользователя.
    """
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(
        "SELECT subscription_status FROM users WHERE user_id = ?",
        (user_id,),
    )
    row = cur.fetchone()
    cur.close()
    conn.close()
    if row:
        return row["subscription_status"]
    return None


# --- Фразы для контроля уникальности ---


def get_used_phrases(user_id: int) -> list[str]:
    """
    Получаем использованные фразы пользователя для уникальности.
    """
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT used_phrases FROM users WHERE user_id = ?", (user_id,))
    row = cur.fetchone()
    cur.close()
    conn.close()
    if not row or row["used_phrases"] is None:
        return []
    try:
        return json.loads(row["used_phrases"])
    except (json.JSONDecodeError, TypeError):
        return []


def save_user_phrase(user_id: int, phrase_key: str):
    """
    phrase_key — любая строка, по которой мы будем отслеживать повторы (например, theme|style|hash).
    """
    ensure_user(user_id)
    phrases = get_used_phrases(user_id)
    if phrase_key not in phrases:
        phrases.append(phrase_key)
    json_phrases = json.dumps(phrases)

    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(
        "UPDATE users SET used_phrases = ? WHERE user_id = ?",
        (json_phrases, user_id),
    )
    conn.commit()
    cur.close()
    conn.close()


# --- Таро-история ---


def get_tarot_history(user_id: int) -> list[str]:
    """
    Получаем историю раскладов Таро для пользователя.
    """
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT tarot_history FROM users WHERE user_id = ?", (user_id,))
    row = cur.fetchone()
    cur.close()
    conn.close()
    if not row or row["tarot_history"] is None:
        return []
    try:
        return json.loads(row["tarot_history"])
    except (json.JSONDecodeError, TypeError):
        return []


def save_tarot_history(user_id: int, card_names: list[str]):
    """
    card_names — список имён карт (строки).
    """
    ensure_user(user_id)
    history = get_tarot_history(user_id)
    history.append(card_names)
    json_history = json.dumps(history)

    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(
        "UPDATE users SET tarot_history = ? WHERE user_id = ?",
        (json_history, user_id),
    )
    conn.commit()
    cur.close()
    conn.close()


# --- История цитат ---


def _get_unique_quote_for_user(user_id: int) -> str:
    """
    Возвращает уникальную цитату, которую пользователь не видел за последние 2 дня.
    """
    conn = get_db_connection()
    cur = conn.cursor()

    # Получаем цитаты, которые пользователь **не видел за последние 2 дня**
    cur.execute("""
        SELECT quote FROM quotes 
        WHERE quote NOT IN (
            SELECT quote FROM user_quote_history 
            WHERE user_id = ? AND used_at > datetime('now', '-2 days')
        )
        ORDER BY RANDOM() LIMIT 1
    """, (user_id,))

    result = cur.fetchone()
    if result:
        quote = result["quote"]
        # Записываем, что пользователь получил эту цитату
        cur.execute(
            "INSERT INTO user_quote_history (user_id, quote, used_at) VALUES (?, ?, datetime('now'))",
            (user_id, quote)
        )
        conn.commit()
    else:
        # Если все цитаты были — сбросим историю
        cur.execute("DELETE FROM user_quote_history WHERE user_id = ?", (user_id,))
        conn.commit()
        # И снова получим случайную
        cur.execute("SELECT quote FROM quotes ORDER BY RANDOM() LIMIT 1")
        result = cur.fetchone()
        quote = result["quote"] if result else "Вселенная молчит... Но слушай внимательно."
        cur.execute(
            "INSERT INTO user_quote_history (user_id, quote, used_at) VALUES (?, ?, datetime('now'))",
            (user_id, quote)
        )
        conn.commit()

    cur.close()
    conn.close()
    return quote
