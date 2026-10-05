import asyncio
import json
import os
import urllib.parse
import random
import sqlite3
from datetime import datetime, timedelta

from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import Command, CommandStart
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
WEB_APP_BASE_URL = os.getenv(
    "WEB_APP_BASE_URL", 
    "https://github.io"
)
STATS_FILE = "workout_stats.json"

if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN must be set in .env")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# --- 📚 НАДЁЖНАЯ БАЗА УПРАЖНЕНИЙ ---
EXERCISES_DATABASE = {
    "Силовая": {
        "верх": [
            {"name": "💪 Отжимания классические"},
            {"name": "💪 Алмазные отжимания"},
            {"name": "💪 Отжимания с широкой постановкой"},
            {"name": "💪 Обратные отжимания от стула"},
            {"name": "🤸 Планка с касанием плеч"},
            {"name": "🤸 Динамическая планка"},
            {"name": "💪 Лодочка (статика на спину)"},
            {"name": "💪 Эксцентрические медленные отжимания"},
            {"name": "💪 Отжимания в пайке"},
            {"name": "💪 Индийские отжимания (Хинду)"},
            {"name": "💪 Отжимания с колен"},
            {"name": "🤸 Планка на локтях с выносом руки"},
            {"name": "💪 Круговые отжимания"},
            {"name": "🤸 Т-планка с разворотом корпуса"},
            {"name": "💪 Лодочка статика"},
            {"name": "🤸 Планка «Сфинкс» на трицепс"},
            {"name": "💪 Отжимания лучника"},
            {"name": "💪 Имитация подтягиваний лежа"}
        ],
        "ноги": [
            {"name": "🦵 Приседания с паузой 3 сек"},
            {"name": "🦵 Выпады назад (поочередно)"},
            {"name": "🦵 Боковые выпады"},
            {"name": "⚡ Болгарские сплит-приседания"},
            {"name": "🔥 Ягодичный мостик на одной ноге"},
            {"name": "🦵 Приседания сумо"},
            {"name": "🔥 Подъемы на носки (на икры)"},
            {"name": "🦵 Стульчик у стены (статика)"},
            {"name": "🦵 Приседания пистолетиком у опоры"},
            {"name": "🦵 Выпады вперед"},
            {"name": "🔥 Классический ягодичный мостик"},
            {"name": "🦵 Диагональные выпады (реверанс)"},
            {"name": "🦵 Приседания с узкой постановкой ног"},
            {"name": "🔥 Подъемы ноги назад на четвереньках"},
            {"name": "🔥 Махи ногой в сторону лежа"},
            {"name": "🦵 Прыжки в полуприседе (статодинамика)"},
            {"name": "🔥 Ягодичный мост с разведением колен"}
        ],
        "пресс": [
            {"name": "🔥 Классические скручивания"},
            {"name": "🔥 Скручивания «Велосипед»"},
            {"name": "💥 Обратные скручивания"},
            {"name": "🤸 Классическая планка на локтях"},
            {"name": "🔥 Упражнение «Книжка» (складка)"},
            {"name": "🤸 Боковая планка"},
            {"name": "💥 Подъемы ног лежа"},
            {"name": "🔥 Русский твист"},
            {"name": "🔥 Скручивания «Ножницы»"},
            {"name": "🤸 Планка «Паук» (колено к локтю)"},
            {"name": "🔥 Касание лодыжек лежа"},
            {"name": "🔥 Поза лодки (статика пресс)"},
            {"name": "💥 Опускание ног поочередно"},
            {"name": "🔥 Косые скручивания лежа"},
            {"name": "🤸 Вакуум живота"},
            {"name": "💥 Вертикальные ножницы ногами"},
            {"name": "🔥 Двойные скручивания"}
        ],
        "все": [
            {"name": "💪 Классические отжимания"},
            {"name": "🦵 Глубокие приседания"},
            {"name": "🔥 Скручивания на пресс"},
            {"name": "🤸 Планка на ладонях"},
            {"name": "💥 Ягодичный мостик двух ног"},
            {"name": "💪 Отжимания в пайке"},
            {"name": "🦵 Диагональные выпады"},
            {"name": "🔥 Русский твист"},
            {"name": "💪 Супермен"},
            {"name": "🦵 Приседания сумо"}
        ]
    },
    "Кардио": {
        "верх": [
            {"name": "💥 Боксерские удары перед собой"},
            {"name": "🤸 Планка с прыжком (Plank Jacks)"},
            {"name": "💥 Бег в планке на руках"},
            {"name": "💪 Взрывные отжимания"},
            {"name": "🤸 Переходы в планке вправо-влево"},
            {"name": "💥 Быстрые удары «апперкот»"},
            {"name": "🤸 Планка с хлопком по груди"},
            {"name": "💥 Имитация прыжков на скакалке руками"},
            {"name": "💪 Отжимания с выпрыгиванием руками"},
            {"name": "🤸 Планка-лягушка"},
            {"name": "💥 Шаги руками вперед-назад из стойки"}
        ],
        "ноги": [
            {"name": "⚡ Выпады с прыжком"},
            {"name": "⚡ Приседания с выпрыгиванием"},
            {"name": "🏃 Бег с высоким подниманием коленей"},
            {"name": "🏃 Захлест голени назад"},
            {"name": "⚡ Прыжки конькобежца"},
            {"name": "🏃 Бег на месте на носочках"},
            {"name": "⚡ Прыжки в приседе вперед-назад"},
            {"name": "⚡ Взрывные выпрыгивания из глубокого седа"},
            {"name": "🏃 Боковые шаги с подпрыжкой"},
            {"name": "⚡ Выпады в стороны в динамике"},
            {"name": "⚡ Прыжки «звездочка»"}
        ],
        "пресс": [
            {"name": "🤸 Быстрый «Горный альпинист»"},
            {"name": "🔥 Динамический русский твист"},
            {"name": "🤸 Боковая планка со скручиванием"},
            {"name": "💥 Подъем коленей к груди в прыжке"},
            {"name": "🔥 Велосипед в быстром темпе"},
            {"name": "🤸 Альпинист по диагонали"},
            {"name": "🔥 Скручивания с хлопком под ногой"},
            {"name": "🤸 Планка с прыжками ногами в стороны"},
            {"name": "💥 Махи «ножницы» на скорость"}
        ],
        "все": [
            {"name": "⚡ Взрывные Бёрпи"},
            {"name": "🏃 Прыжки Джампинг Джек"},
            {"name": "🤸 Горный альпинист быстрый"},
            {"name": "⚡ Прыжки со сменой ног в выпаде"},
            {"name": "🏃 Бег на месте с ускорением"},
            {"name": "⚡ Бёрпи без отжиманий"},
            {"name": "🏃 Прыжки «Лягушка» во все стороны"},
            {"name": "⚡ Прыжки конькобежца широкие"},
            {"name": "🤸 Планка с выпрыгиванием в упор"}
        ]
    },
    "Растяжка": {
        "верх": [
            {"name": "🧘 Растяжка плеч поперек груди"},
            {"name": "🧘 Растяжка трицепса за головой"},
            {"name": "🧘 Замок из рук за спиной"},
            {"name": "🧘 Наклоны шеи в стороны"},
            {"name": "🧘 Растяжка грудных мышц у стены"},
            {"name": "🧘 Поза замка (руки вверх)"},
            {"name": "🧘 Растяжка предплечий и кистей"},
            {"name": "🧘 Округление спины стоя"}
        ],
        "ноги": [
            {"name": "🧘 Наклоны к стопам sitting (складка)"},
            {"name": "🧘 Глубокий выпад (растяжка квадрицепса)"},
            {"name": "🧘 Растяжка «Бабочка»"},
            {"name": "🧘 Наклоны к ногам стоя"},
            {"name": "🧘 Растяжка задней поверхности бедра лежа"},
            {"name": "🧘 Поза голубя (растяжка ягодиц)"},
            {"name": "🧘 Поза полушпагата"},
            {"name": "🧘 Растяжка квадрицепса стоя на одной ноге"}
        ],
        "пресс": [
            {"name": "🧘 Поза кобры (вытяжение живота)"},
            {"name": "🧘 Поза кошки-коровы"},
            {"name": "🧘 Боковое вытягивание корпуса стоя"},
            {"name": "🧘 Скручивание позвоночника лежа"},
            {"name": "🧘 Поза ребенка (расслабление спины)"},
            {"name": "🧘 Поза сфинкса"},
            {"name": "🧘 Боковые наклоны сидя на коленях"},
            {"name": "🧘 Поза моста статическая"}
        ],
        "все": [
            {"name": "🧘 Поза ребенка длительная"},
            {"name": "🧘 Складка сидя к двум ногам"},
            {"name": "🧘 Поза собаки мордой вниз"},
            {"name": "🧘 Растяжка бабочка с наклоном вперед"},
            {"name": "🧘 Поза кобры с поворотом головы"},
            {"name": "🧘 Поза голубя на обе ноги"}
        ]
    },
    "Микс": {
        "верх": [], 
        "ноги": [], 
        "пресс": [], 
        "все": []
    }
}

for zone in ["верх", "ноги", "пресс", "все"]:
    EXERCISES_DATABASE["Микс"][zone] = (
        EXERCISES_DATABASE["Силовая"][zone] + 
        EXERCISES_DATABASE["Кардио"][zone]
    )
# --- 📁 СТАТИСТИКА: SQLite + Railway Volume ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
LOCAL_STATS_FILE = os.path.join(BASE_DIR, "workout_stats.json")
if os.path.isdir("/data"):
    DB_FILE = "/data/workout_stats.db"
else:
    DB_FILE = os.path.join(BASE_DIR, "workout_stats.db")


def _db_connect():
    os.makedirs(os.path.dirname(DB_FILE), exist_ok=True)
    conn = sqlite3.connect(DB_FILE, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=30000")
    return conn


def _init_db():
    with _db_connect() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS stats (
                user_id TEXT PRIMARY KEY,
                data TEXT NOT NULL
            )
        """)
        conn.commit()


def _import_json_if_needed():
    # Импортируем старую JSON-статистику только если SQLite пока пустая.
    _init_db()
    with _db_connect() as conn:
        count = conn.execute("SELECT COUNT(*) FROM stats").fetchone()[0]
        if count:
            return

    if not os.path.exists(LOCAL_STATS_FILE):
        return

    try:
        with open(LOCAL_STATS_FILE, "r", encoding="utf-8") as f:
            old_stats = json.load(f)
        if not isinstance(old_stats, dict) or not old_stats:
            return

        with _db_connect() as conn:
            for user_id, user_data in old_stats.items():
                conn.execute(
                    "INSERT OR REPLACE INTO stats (user_id, data) VALUES (?, ?)",
                    (str(user_id), json.dumps(user_data, ensure_ascii=False))
                )
            conn.commit()
        print(f"✅ Старая статистика импортирована из {LOCAL_STATS_FILE} в SQLite")
    except Exception as e:
        print(f"⚠️ Не удалось импортировать старую статистику: {e}")


_init_db()
_import_json_if_needed()
print(f"🗄️ SQLite база: {DB_FILE}")


def load_stats():
    _init_db()
    with _db_connect() as conn:
        rows = conn.execute("SELECT user_id, data FROM stats").fetchall()
    result = {}
    for row in rows:
        try:
            result[str(row["user_id"])] = json.loads(row["data"])
        except (TypeError, json.JSONDecodeError):
            result[str(row["user_id"])] = {}
    return result


def save_stats(stats):
    _init_db()
    with _db_connect() as conn:
        conn.execute("DELETE FROM stats")
        conn.executemany(
            "INSERT INTO stats (user_id, data) VALUES (?, ?)",
            [
                (str(user_id), json.dumps(user_data, ensure_ascii=False))
                for user_id, user_data in stats.items()
            ]
        )
        conn.commit()


def get_stats_by_period(user_id: str, days: int):
    stats = load_stats()
    user_id_str = str(user_id)
    if user_id_str not in stats:
        return {"workouts": 0, "calories": 0.0, "minutes": 0}

    cutoff_date = datetime.now() - timedelta(days=days)
    workouts = stats[user_id_str].get("workouts", [])
    filtered = []
    for w in workouts:
        try:
            if datetime.fromisoformat(w["timestamp"]) >= cutoff_date:
                filtered.append(w)
        except (KeyError, ValueError, TypeError):
            continue

    return {
        "workouts": len(filtered),
        "calories": sum(float(w.get("calories", 0)) for w in filtered),
        "minutes": sum(float(w.get("minutes", 0)) for w in filtered)
    }


def calculate_streak(user_id: str, stats: dict):
    user_id_str = str(user_id)
    if user_id_str not in stats or not stats[user_id_str].get("workouts"):
        return 0, 0

    workouts = sorted(
        stats[user_id_str]["workouts"],
        key=lambda x: x.get("timestamp", "")
    )
    if not workouts:
        return 0, 0

    dates = []
    for workout in workouts:
        try:
            dates.append(datetime.fromisoformat(workout["timestamp"]).date())
        except (KeyError, ValueError, TypeError):
            continue
    dates = sorted(set(dates))
    if not dates:
        return 0, 0

    max_streak = 1
    run = 1
    for i in range(1, len(dates)):
        diff = (dates[i] - dates[i - 1]).days
        if diff == 1:
            run += 1
            max_streak = max(max_streak, run)
        else:
            run = 1

    today = datetime.now().date()
    if (today - dates[-1]).days > 1:
        return 0, max_streak

    current_streak = 1
    cursor = dates[-1]
    for date_value in reversed(dates[:-1]):
        if (cursor - date_value).days == 1:
            current_streak += 1
            cursor = date_value
        else:
            break

    return current_streak, max_streak


def _to_float(value, default=0.0):
    try:
        if value is None or value == "":
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _get_duration(workout_data: dict):
    """Берём фактическое время из WebApp, если оно передано."""
    for key in ("duration_seconds", "seconds", "elapsed_seconds"):
        value = _to_float(workout_data.get(key), -1)
        if value >= 0:
            return int(round(value)), "actual"

    for key in ("duration_minutes", "minutes", "elapsed_minutes"):
        value = _to_float(workout_data.get(key), -1)
        if value >= 0:
            return int(round(value * 60)), "actual"

    details = str(workout_data.get("details", "") or "")
    if "Схема " in details and "Раунды:" in details:
        try:
            scheme = details.split("Схема ", 1)[1].split(" •", 1)[0]
            work, rest = map(int, scheme.split("/"))
            rounds = int(details.split("Раунды: ", 1)[1].split("/", 1)[0])
            return max(0, rounds * (work + rest)), "planned"
        except (ValueError, IndexError):
            pass

    return 0, "unknown"


def record_workout(user_id: str, workout_data: dict):
    stats = load_stats()
    user_id_str = str(user_id)
    now = datetime.now().isoformat()

    if user_id_str not in stats:
        stats[user_id_str] = {
            "total_workouts": 0,
            "total_calories": 0.0,
            "total_minutes": 0,
            "workouts": [],
            "last_workout_at": None,
            "reminders_sent": []
        }

    user_stats = stats[user_id_str]
    user_stats.setdefault("total_workouts", 0)
    user_stats.setdefault("total_calories", 0.0)
    user_stats.setdefault("total_minutes", 0)
    user_stats.setdefault("workouts", [])
    user_stats.setdefault("last_workout_at", None)
    user_stats.setdefault("reminders_sent", [])

    calories = _to_float(workout_data.get("calories"), 0.0)
    duration_seconds, duration_source = _get_duration(workout_data)
    minutes = round(duration_seconds / 60, 2)

    workout_type = (
        workout_data.get("workout_type")
        or workout_data.get("mode")
        or workout_data.get("type")
        or "Тренировка"
    )

    workout_record = {
        "timestamp": now,
        "workout_type": workout_type,
        "mode": workout_data.get("mode", workout_type),
        "load": workout_data.get("load", ""),
        "focus": workout_data.get("focus", ""),
        "details": workout_data.get("details", ""),
        "exercises": workout_data.get("exercises", []),
        "calories": calories,
        "duration_seconds": duration_seconds,
        "minutes": minutes,
        "duration_source": duration_source,
        "weight": workout_data.get("weight", ""),
        "rounds_completed": workout_data.get("rounds_completed", 0),
        "total_rounds": workout_data.get("total_rounds", 0),
        "work_time": workout_data.get("work_time", 0),
        "rest_time": workout_data.get("rest_time", 0)
    }

    user_stats["total_workouts"] += 1
    user_stats["total_calories"] += calories
    user_stats["total_minutes"] += minutes
    user_stats["last_workout_at"] = now
    user_stats["reminders_sent"] = []
    user_stats["workouts"].append(workout_record)

    save_stats(stats)
    return workout_record

# --- 👤 ПОЛЬЗОВАТЕЛИ И НАПОМИНАНИЯ ---

REMINDER_DAYS = (3, 7, 14, 30)
REMINDER_CHECK_INTERVAL = 60 * 60  # проверяем раз в час


def register_user(user: types.User):
    """Создаёт профиль пользователя, даже если тренировка ещё не была выполнена."""
    stats = load_stats()
    user_id = str(user.id)

    if user_id not in stats:
        stats[user_id] = {
            "total_workouts": 0,
            "total_calories": 0.0,
            "total_minutes": 0,
            "workouts": [],
            "last_workout_at": None,
            "reminders_sent": [],
            "first_name": user.first_name or "",
            "username": user.username or ""
        }
    else:
        stats[user_id].setdefault("first_name", user.first_name or "")
        stats[user_id].setdefault("username", user.username or "")
        stats[user_id].setdefault("last_workout_at", None)
        stats[user_id].setdefault("reminders_sent", [])

    save_stats(stats)


def _get_last_workout(stats: dict, user_id: str):
    user = stats.get(str(user_id))
    if not user:
        return None

    if user.get("last_workout_at"):
        return user["last_workout_at"]

    workouts = user.get("workouts", [])
    if not workouts:
        return None

    return max(w.get("timestamp") for w in workouts if w.get("timestamp"))


def _reminder_text(days: int, first_name: str):
    name = f", {first_name}" if first_name else ""
    if days == 3:
        return (
            f"👋 {name} уже 3 дня без тренировки.\n\n"
            "Самое время вернуться к плану 💪 Сделаем тренировку сегодня?"
        )
    if days == 7:
        return (
            f"📅 {name} прошла уже неделя без тренировки.\n\n"
            "Не теряем ритм — даже короткая тренировка лучше паузы. 🔥"
        )
    if days == 14:
        return (
            f"⚠️ {name} уже 14 дней без тренировки.\n\n"
            "Давай мягко вернёмся в режим. Я могу составить тренировку прямо сейчас."
        )
    return (
        f"⏰ {name} уже 30 дней без тренировки.\n\n"
        "Пора возвращаться! Начнём с подходящей нагрузки и без перегруза. 💪"
    )


async def reminder_loop():
    """Автоматические напоминания на 3/7/14/30 день после последней тренировки."""
    while True:
        try:
            stats = load_stats()
            changed = False
            now = datetime.now()

            for user_id, user_data in stats.items():
                last_workout = _get_last_workout(stats, user_id)
                if not last_workout:
                    continue

                try:
                    last_dt = datetime.fromisoformat(last_workout)
                except (TypeError, ValueError):
                    continue

                days_without_workout = (now - last_dt).days
                sent = set(user_data.get("reminders_sent", []))

                # Если бот был выключен, отправляем только самое актуальное
                # достигнутое напоминание, а не четыре сообщения сразу.
                reached = [d for d in REMINDER_DAYS if days_without_workout >= d and d not in sent]
                if not reached:
                    continue

                reminder_day = max(reached)
                try:
                    await bot.send_message(
                        chat_id=int(user_id),
                        text=_reminder_text(
                            reminder_day,
                            user_data.get("first_name", "")
                        ),
                        reply_markup=get_main_keyboard()
                    )
                    user_data.setdefault("reminders_sent", []).extend(reached)
                    changed = True
                except Exception as e:
                    print(f"Не удалось отправить reminder пользователю {user_id}: {e}")

            if changed:
                save_stats(stats)

        except Exception as e:
            print(f"Ошибка reminder_loop: {e}")

        await asyncio.sleep(REMINDER_CHECK_INTERVAL)


# --- ⚙️ НАСТРОЙКИ КЛАВИАТУР И КОНФИГУРАЦИИ ---

WORKOUT_GOALS = {
    "Силовая": {"ru": "Силовая"},
    "Кардио": {"ru": "Кардио / Жиросжигание"},
    "Растяжка": {"ru": "Растяжка"},
    "Микс": {"ru": "Микс дня (Ganina AI)"}
}

FOCUS_ZONES = {
    "верх": {"emoji": "💪", "name": "Верх тела"},
    "ноги": {"emoji": "🦵", "name": "Ноги и ягодицы"},
    "пресс": {"emoji": "🔥", "name": "Пресс и кор"},
    "все": {"emoji": "🧘", "name": "Все тело"}
}

LOAD_LEVELS = {
    "🟢 Лёгкая": {"met": 3.5, "work_time": 20, "rest_time": 10, "rounds": 6},
    "🟡 Средняя": {"met": 6.0, "work_time": 20, "rest_time": 10, "rounds": 8},
    "🔴 Интенсивная": {"met": 8.5, "work_time": 30, "rest_time": 10, "rounds": 10}
}

def get_main_keyboard():
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🏋️ Силовая", callback_data="workout_Силовая")],
            [InlineKeyboardButton(text="🏃 Кардио / Жиросжигание", callback_data="workout_Кардио")],
            [InlineKeyboardButton(text="🧘 Растяжка", callback_data="workout_Растяжка")],
            [InlineKeyboardButton(text="🎲 Микс дня (Ganina AI)", callback_data="workout_Микс")],
            [InlineKeyboardButton(text="📊 Моя статистика", callback_data="stats_show")]
        ]
    )
    return keyboard

# --- 🚀 ОСНОВНЫЕ ХЕНДЛЕРЫ БОТА ---

@dp.message(CommandStart())
async def start_cmd(message: types.Message):
    register_user(message.from_user)
    await message.answer(
        f"Привет, {message.from_user.first_name}! 👋\n\n"
        f"Какую тренировку должна составить Ganina сегодня?", 
        reply_markup=get_main_keyboard()
    )

@dp.message(Command("stats"))
async def stats_cmd(message: types.Message):
    await show_user_stats(message.from_user.id, message)

async def show_user_stats(user_id: int, message_context):
    # load_stats() читает SQLite, поэтому статистика не зависит от локального JSON.
    stats = load_stats()
    user_id_str = str(user_id)
    user_stats = stats.get(user_id_str, {})

    if user_stats.get("total_workouts", 0) == 0:
        text = "📊 **У вас еще нет завершенных тренировок.**\n\nСоздайте первую тренировку прямо сейчас! 💪"
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="🏋️ Создать тренировку", callback_data="workout_Микс")]
            ]
        )
    else:
        total_workouts = int(user_stats.get("total_workouts", 0))
        total_calories = user_stats["total_calories"]
        total_minutes = user_stats.get("total_minutes", 0)

        week_stats = get_stats_by_period(user_id, 7)
        month_stats = get_stats_by_period(user_id, 30)
        current_streak, max_streak = calculate_streak(user_id, stats)
        streak_emoji = "🔥" if current_streak > 0 else "❄️"

        text = (
            f"📊 **ПОЛНАЯ СТАТИСТИКА**\n\n"
            f"📈 **ВСЕГО:**\n"
            f"   💪 Тренировок: {total_workouts}\n"
            f"   🔥 Сожжено ккал: {total_calories:.0f}\n"
            f"   ⏱️  Время тренировок: {total_minutes:.0f} мин\n"
            f"   📉 Средне за тренировку: {total_calories/total_workouts:.0f} ккал\n\n"
            f"📅 **ЗА НЕДЕЛЮ (7 дней):**\n"
            f"   💪 {week_stats['workouts']} зан. | 🔥 {week_stats['calories']:.0f} ккал | ⏱️ {week_stats['minutes']:.0f} мин\n\n"
            f"📆 **ЗА МЕСЯЦ (30 дней):**\n"
            f"   💪 {month_stats['workouts']} зан. | 🔥 {month_stats['calories']:.0f} ккал | ⏱️ {month_stats['minutes']:.0f} мин\n\n"
            f"{streak_emoji} **STREAK (Дни подряд):**\n"
            f"   🔥 Текущая серия: {current_streak} дней\n"
            f"   ⭐ Лучший рекорд: {max_streak} дней"
        )
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="🔄 Обновить", callback_data="stats_show")],
                [InlineKeyboardButton(text="🏋️ Новая тренировка", callback_data="workout_Микс")]
            ]
        )

    if isinstance(message_context, types.CallbackQuery):
        await message_context.message.answer(text, reply_markup=keyboard)
    else:
        await message_context.answer(text, reply_markup=keyboard)

@dp.callback_query(F.data == "stats_show")
async def stats_callback(callback: types.CallbackQuery):
    await show_user_stats(callback.from_user.id, callback)
    await callback.answer()
@dp.callback_query(F.data.startswith("workout_"))
async def select_workout_type(callback: types.CallbackQuery):
    goal = callback.data.split("_", 1)[1]
    focus_keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="💪 Верх тела", callback_data=f"focus_{goal}_верх")],
            [InlineKeyboardButton(text="🦵 Ноги и ягодицы", callback_data=f"focus_{goal}_ноги")],
            [InlineKeyboardButton(text="🔥 Пресс и кор", callback_data=f"focus_{goal}_пресс")],
            [InlineKeyboardButton(text="🧘 Все тело", callback_data=f"focus_{goal}_все")],
            [InlineKeyboardButton(text="← Назад", callback_data="back_to_workout_menu")]
        ]
    )
    goal_name = WORKOUT_GOALS.get(goal, {}).get("ru", goal)
    await callback.message.edit_text(
        f"✨ Вы выбрали: **{goal_name}**\n\n"
        f"На какую зону сосредоточиться?", 
        reply_markup=focus_keyboard
    )
    await callback.answer()

@dp.callback_query(F.data.startswith("focus_"))
async def select_focus_zone(callback: types.CallbackQuery):
    parts = callback.data.split("_", 2)
    goal = parts[1]        
    focus_zone = parts[2]  
    
    intensity_keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🟢 Лёгкая", callback_data=f"intensity_{goal}_{focus_zone}_🟢 Лёгкая")],
            [InlineKeyboardButton(text="🟡 Средняя", callback_data=f"intensity_{goal}_{focus_zone}_🟡 Средняя")],
            [InlineKeyboardButton(text="🔴 Интенсивная", callback_data=f"intensity_{goal}_{focus_zone}_🔴 Интенсивная")],
            [InlineKeyboardButton(text="← Назад", callback_data=f"back_to_focus_{goal}")]
        ]
    )
    focus_name = FOCUS_ZONES.get(focus_zone, {}).get("name", focus_zone)
    await callback.message.edit_text(
        f"🎯 Фокус: **{focus_name}**\n\n"
        f"Выберите уровень интенсивности:", 
        reply_markup=intensity_keyboard
    )
    await callback.answer()

@dp.callback_query(F.data.startswith("intensity_"))
async def select_intensity(callback: types.CallbackQuery):
    parts = callback.data.split("_")
    goal = parts[1]        
    focus_zone = parts[2]  
    load_level = "_".join(parts[3:])
    
    await callback.message.edit_text(
        f"⏳ Сборка персонального плана тренировки..."
    )
    
    pool = EXERCISES_DATABASE.get(goal, EXERCISES_DATABASE["Микс"]).get(
        focus_zone, 
        EXERCISES_DATABASE["Микс"]["все"]
    )
    exercises = random.sample(pool, k=min(5, len(pool)))
    
    encoded_exercises = urllib.parse.quote(
        json.dumps(exercises, ensure_ascii=False)
    )
    load_info = LOAD_LEVELS.get(load_level, LOAD_LEVELS["🟡 Средняя"])
    
    params = {
        "workout": encoded_exercises,
        "load": load_level,
        "focus": focus_zone,
        "work_time": load_info["work_time"],
        "rest_time": load_info["rest_time"],
        "rounds": load_info["rounds"],
        "met": load_info["met"]
    }
    
    web_app_url = f"{WEB_APP_BASE_URL}?{urllib.parse.urlencode(params)}"
    
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🚀 Начать тренировку", web_app=WebAppInfo(url=web_app_url))],
            [InlineKeyboardButton(text="📊 Моя статистика", callback_data="stats_show")],
            [InlineKeyboardButton(text="← Назад", callback_data=f"back_to_intensity_{goal}_{focus_zone}")]
        ]
    )
    
    workout_text = "\n".join(
        [f"{i+1}. {ex['name']}" for i, ex in enumerate(exercises)]
    )
    goal_name = WORKOUT_GOALS.get(goal, {}).get("ru", goal)
    focus_name = FOCUS_ZONES.get(focus_zone, {}).get("name", focus_zone)
    
    await callback.message.answer(
        f"📋 **Ваш случайный план:**\n\n"
        f"**Тип:** {goal_name} • {focus_name}\n"
        f"**Интенсивность:** {load_level}\n\n"
        f"**Упражнения:**\n{workout_text}\n\n"
        f"Нажмите кнопку ниже, чтобы открыть таймер!",
        reply_markup=keyboard
    )
    await callback.answer()

@dp.message(F.web_app_data)
async def handle_web_app_data(message: types.Message):
    try:
        data = json.loads(message.web_app_data.data)

        # Важно: WebApp должен прислать sendData() с фактическими результатами.
        record = record_workout(message.from_user.id, data)

        current_streak, max_streak = calculate_streak(
            message.from_user.id,
            load_stats()
        )

        duration_seconds = int(record.get("duration_seconds", 0))
        duration_minutes = duration_seconds // 60
        duration_remainder = duration_seconds % 60

        if duration_minutes:
            duration_text = f"{duration_minutes} мин"
            if duration_remainder:
                duration_text += f" {duration_remainder} сек"
        else:
            duration_text = f"{duration_remainder} сек"

        workout_type = record.get("workout_type", "Тренировка")
        calories = float(record.get("calories", 0))

        await message.answer(
            f"🎉 **Отличная работа! Тренировка завершена!**\n\n"
            f"🏋️ **Тип:** {workout_type}\n"
            f"💪 **Уровень:** {record.get('load', '—')}\n"
            f"🎯 **Фокус:** {record.get('focus', '—')}\n"
            f"⏱️ **Время:** {duration_text}\n"
            f"🔥 **Сожжено:** {calories:.0f} ккал\n\n"
            f"🔥 **Серия:** {current_streak} дней подряд! "
            f"(Рекорд: {max_streak} дней) 🏆\n\n"
            f"📈 Все показатели сохранены в статистику!",
            reply_markup=get_main_keyboard()
        )
    except Exception as e:
        print(f"Ошибка сохранения: {e}")
        await message.answer(
            "❌ Не удалось сохранить результаты тренировки. "
            "Проверьте, что WebApp отправляет корректный JSON.",
            reply_markup=get_main_keyboard()
        )

# --- 🔄 НАВИГАЦИЯ НАЗАД ---

@dp.callback_query(F.data == "back_to_workout_menu")
async def back_menu(callback: types.CallbackQuery):
    await callback.message.edit_text(
        "Какую тренировку должна составить Ganina сегодня?", 
        reply_markup=get_main_keyboard()
    )
    await callback.answer()

@dp.callback_query(F.data.startswith("back_to_focus_"))
async def back_focus(callback: types.CallbackQuery):
    goal = callback.data.split("_")[-1]
    focus_keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="💪 Верх", callback_data=f"focus_{goal}_верх")],
            [InlineKeyboardButton(text="🦵 Ноги", callback_data=f"focus_{goal}_ноги")],
            [InlineKeyboardButton(text="🔥 Пресс", callback_data=f"focus_{goal}_пресс")],
            [InlineKeyboardButton(text="🧘 Все тело", callback_data=f"focus_{goal}_все")],
            [InlineKeyboardButton(text="← Назад", callback_data="back_to_workout_menu")]
        ]
    )
    await callback.message.edit_text(
        "На какую зону сосредоточиться?", 
        reply_markup=focus_keyboard
    )
    await callback.answer()

@dp.callback_query(F.data.startswith("back_to_intensity_"))
async def back_intensity(callback: types.CallbackQuery):
    parts = callback.data.split("_")
    goal = parts[3]
    focus_zone = parts[4]
    intensity_keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🟢 Лёгкая", callback_data=f"intensity_{goal}_{focus_zone}_🟢 Лёгкая")],
            [InlineKeyboardButton(text="🟡 Средняя", callback_data=f"intensity_{goal}_{focus_zone}_🟡 Средняя")],
            [InlineKeyboardButton(text="🔴 Интенсивная", callback_data=f"intensity_{goal}_{focus_zone}_🔴 Интенсивная")],
            [InlineKeyboardButton(text="← Назад", callback_data=f"back_to_focus_{goal}")]
        ]
    )
    await callback.message.edit_text(
        "Выберите уровень интенсивности:", 
        reply_markup=intensity_keyboard
    )
    await callback.answer()

# --- 🚩 ТОЧКА ВХОДА ЗАПУСКА ---

async def main():
    print("🤖 Бот запущен...")
    reminder_task = asyncio.create_task(reminder_loop())

    try:
        await dp.start_polling(bot)
    finally:
        reminder_task.cancel()
        try:
            await reminder_task
        except asyncio.CancelledError:
            pass
        await bot.session.close()

if __name__ == "__main__":
    asyncio.run(main())
