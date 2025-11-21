import random
from db import get_db_connection, get_tarot_history, save_tarot_history

TAROT_STYLES = [
    "мистический",
    "практичный",
    "юмористический",
    "поэтичный",
    "терапевтический",
]

POSITIONS = ["Прошлое", "Настоящее", "Будущее"]


def load_tarot_deck() -> list[tuple]:
    """
    Загружаем колоду Таро из таблицы tarot_cards.
    Ожидаемые поля: card_id, name, meaning (минимум).
    """
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT card_id, name, meaning FROM tarot_cards")
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return rows


def _build_card_interpretation(
    card_name: str,
    meaning: str,
    position: str,
    topic: str,
    style: str,
    sign: str | None,
) -> str:
    """
    Генерация интерпретации карты без жёстких шаблонов.
    """
    base = f"{position}: {card_name}."

    bridges = {
        "мистический": "Эта карта звучит как шёпот между мирами:",
        "практичный": "Если говорить совсем по-деловому:",
        "юмористический": "Если смотреть с лёгкой самоиронией:",
        "поэтичный": "Если облечь всё это в образ:",
        "терапевтический": "Если относиться к этому как к мягкой сессии с самим собой:",
    }

    topic_line = f"Тема расклада — {topic.lower()}."
    sign_line = f"Ты сейчас как {sign}, который учится видеть глубже привычного." if sign else ""
    bridge = bridges.get(style, "Суть в том, что:")
    meaning_part = f"{bridge} {meaning}"

    return "\n".join([base, topic_line, sign_line, meaning_part]).strip()


def generate_tarot(user_id: int, topic: str, sign: str | None = None) -> str:
    """
    Генерация расклада из 3 карт:
    - без повторения недавно использованных карт (по имени)
    - с разными стилями интерпретации
    """
    deck = load_tarot_deck()
    if not deck:
        return "Колоде сегодня не до работы — в базе пока нет карт Таро. 🃏"

    history = set(get_tarot_history(user_id))

    # выбираем карты, которые не встречались недавно, если возможно
    fresh_cards = [c for c in deck if c[1] not in history]
    source = fresh_cards if len(fresh_cards) >= 3 else deck

    selected = random.sample(source, 3)
    styles_cycle = random.sample(TAROT_STYLES, k=3)

    parts = []
    for (card, pos, style) in zip(selected, POSITIONS, styles_cycle):
        card_id, name, meaning = card
        text = _build_card_interpretation(
            card_name=name,
            meaning=meaning,
            position=pos,
            topic=topic,
            style=style,
            sign=sign,
        )
        parts.append(text)

    # сохраняем названия карт в историю
    save_tarot_history(user_id, [c[1] for c in selected])

    return "\n\n".join(parts)
