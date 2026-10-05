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
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
# Railway Volume должен быть подключён к /data.
# Локально (если /data ещё нет) используем папку проекта.
DATA_DIR = os.getenv("DATA_DIR", "/data")
try:
    os.makedirs(DATA_DIR, exist_ok=True)
except OSError:
    DATA_DIR = BASE_DIR
    os.makedirs(DATA_DIR, exist_ok=True)

DB_FILE = os.path.join(DATA_DIR, "workout_stats.db")
LEGACY_STATS_FILES = [
    os.path.join(DATA_DIR, "workout_stats.json"),
    os.path.join(BASE_DIR, "workout_stats.json"),
]

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
# --- 🗄️ SQLITE-СТАТИСТИКА (Railway Volume) ---


def get_db():
    """Открывает SQLite в постоянной папке Railway Volume."""
    conn = sqlite3.connect(DB_FILE, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db():
    """Создаёт таблицы, если их ещё нет."""
    with get_db() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS users (
                telegram_id INTEGER PRIMARY KEY,
                first_name TEXT DEFAULT '',
                username TEXT DEFAULT '',
                total_workouts INTEGER NOT NULL DEFAULT 0,
                total_calories REAL NOT NULL DEFAULT 0,
                total_minutes REAL NOT NULL DEFAULT 0,
                last_workout_at TEXT,
                reminders_sent TEXT NOT NULL DEFAULT '[]',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS workouts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                timestamp TEXT NOT NULL,
                action TEXT DEFAULT 'workout_finished',
                workout_type TEXT DEFAULT '',
                mode TEXT DEFAULT '',
                load TEXT DEFAULT '',
                focus TEXT DEFAULT '',
                duration_seconds INTEGER NOT NULL DEFAULT 0,
                formatted_time TEXT DEFAULT '',
                duration_source TEXT DEFAULT 'unknown',
                calories REAL NOT NULL DEFAULT 0,
                weight TEXT DEFAULT '',
                age TEXT DEFAULT '',
                gender TEXT DEFAULT '',
                height TEXT DEFAULT '',
                rounds_completed INTEGER NOT NULL DEFAULT 0,
                total_rounds INTEGER NOT NULL DEFAULT 0,
                work_time INTEGER NOT NULL DEFAULT 0,
                rest_time INTEGER NOT NULL DEFAULT 0,
                exercises TEXT NOT NULL DEFAULT '[]',
                date TEXT DEFAULT '',
                FOREIGN KEY(user_id) REFERENCES users(telegram_id) ON DELETE CASCADE
            );

            CREATE INDEX IF NOT EXISTS idx_workouts_user_timestamp
                ON workouts(user_id, timestamp);
        """)


def _row_to_user(row):
    reminders = []
    if row["reminders_sent"]:
        try:
            reminders = json.loads(row["reminders_sent"])
        except (TypeError, ValueError):
            reminders = []
    return {
        "total_workouts": int(row["total_workouts"] or 0),
        "total_calories": float(row["total_calories"] or 0),
        "total_minutes": float(row["total_minutes"] or 0),
        "workouts": [],
        "last_workout_at": row["last_workout_at"],
        "reminders_sent": reminders,
        "first_name": row["first_name"] or "",
        "username": row["username"] or "",
    }


def _row_to_workout(row):
    try:
        exercises = json.loads(row["exercises"] or "[]")
    except (TypeError, ValueError):
        exercises = []
    return {
        "id": row["id"],
        "timestamp": row["timestamp"],
        "action": row["action"],
        "workout_type": row["workout_type"],
        "mode": row["mode"],
        "load": row["load"],
        "focus": row["focus"],
        "duration_seconds": int(row["duration_seconds"] or 0),
        "formatted_time": row["formatted_time"],
        "duration_source": row["duration_source"],
        "calories": float(row["calories"] or 0),
        "weight": row["weight"],
        "age": row["age"],
        "gender": row["gender"],
        "height": row["height"],
        "rounds_completed": int(row["rounds_completed"] or 0),
        "total_rounds": int(row["total_rounds"] or 0),
        "work_time": int(row["work_time"] or 0),
        "rest_time": int(row["rest_time"] or 0),
        "exercises": exercises,
        "date": row["date"],
        "minutes": round(int(row["duration_seconds"] or 0) / 60, 2),
    }


def load_stats():
    """Возвращает статистику в прежнем формате, но читает её из SQLite."""
    init_db()
    stats = {}
    with get_db() as conn:
        users = conn.execute("SELECT * FROM users").fetchall()
        workouts = conn.execute(
            "SELECT * FROM workouts ORDER BY timestamp ASC"
        ).fetchall()

    for row in users:
        stats[str(row["telegram_id"])] = _row_to_user(row)
    for row in workouts:
        uid = str(row["user_id"])
        if uid not in stats:
            stats[uid] = {
                "total_workouts": 0, "total_calories": 0.0,
                "total_minutes": 0.0, "workouts": [],
                "last_workout_at": None, "reminders_sent": [],
                "first_name": "", "username": ""
            }
        stats[uid]["workouts"].append(_row_to_workout(row))
    return stats


def save_stats(stats):
    """Совместимость со старым кодом: сохраняет пользователей в SQLite."""
    init_db()
    now = datetime.now().isoformat()
    with get_db() as conn:
        for uid, user in stats.items():
            conn.execute(
                """INSERT INTO users
                   (telegram_id, first_name, username, total_workouts,
                    total_calories, total_minutes, last_workout_at,
                    reminders_sent, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                   ON CONFLICT(telegram_id) DO UPDATE SET
                    first_name=excluded.first_name,
                    username=excluded.username,
                    total_workouts=excluded.total_workouts,
                    total_calories=excluded.total_calories,
                    total_minutes=excluded.total_minutes,
                    last_workout_at=excluded.last_workout_at,
                    reminders_sent=excluded.reminders_sent,
                    updated_at=excluded.updated_at""",
                (
                    int(uid), user.get("first_name", ""), user.get("username", ""),
                    int(user.get("total_workouts", 0)),
                    float(user.get("total_calories", 0)),
                    float(user.get("total_minutes", 0)),
                    user.get("last_workout_at"),
                    json.dumps(user.get("reminders_sent", []), ensure_ascii=False),
                    now, now,
                )
            )


def migrate_legacy_json():
    """Однократно переносит старую JSON-статистику в SQLite, если она есть."""
    init_db()
    with get_db() as conn:
        count = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    if count:
        return

    legacy_file = next((p for p in LEGACY_STATS_FILES if os.path.exists(p)), None)
    if not legacy_file:
        return

    try:
        with open(legacy_file, "r", encoding="utf-8") as f:
            legacy = json.load(f)
    except (OSError, ValueError) as e:
        print(f"⚠️ Не удалось импортировать старую JSON-статистику: {e}")
        return

    for uid, user in legacy.items():
        uid_int = int(uid)
        now = datetime.now().isoformat()
        with get_db() as conn:
            conn.execute(
                """INSERT OR REPLACE INTO users
                   (telegram_id, first_name, username, total_workouts,
                    total_calories, total_minutes, last_workout_at,
                    reminders_sent, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    uid_int, user.get("first_name", ""), user.get("username", ""),
                    int(user.get("total_workouts", 0)),
                    float(user.get("total_calories", 0)),
                    float(user.get("total_minutes", 0)),
                    user.get("last_workout_at"),
                    json.dumps(user.get("reminders_sent", []), ensure_ascii=False),
                    now, now,
                )
            )
            for workout in user.get("workouts", []):
                duration_seconds = int(round(
                    float(workout.get("duration_seconds", 0))
                ))
                if not duration_seconds:
                    duration_seconds = int(round(float(workout.get("minutes", 0)) * 60))
                conn.execute(
                    """INSERT INTO workouts
                       (user_id, timestamp, action, workout_type, mode, load,
                        focus, duration_seconds, formatted_time, duration_source,
                        calories, weight, age, gender, height, rounds_completed,
                        total_rounds, work_time, rest_time, exercises, date)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        uid_int, workout.get("timestamp", now),
                        workout.get("action", "workout_finished"),
                        workout.get("workout_type", workout.get("mode", "Тренировка")),
                        workout.get("mode", ""), workout.get("load", ""),
                        workout.get("focus", ""), duration_seconds,
                        workout.get("formatted_time", ""),
                        workout.get("duration_source", "legacy"),
                        float(workout.get("calories", 0)), workout.get("weight", ""),
                        workout.get("age", ""), workout.get("gender", ""),
                        workout.get("height", ""), int(workout.get("rounds_completed", 0) or 0),
                        int(workout.get("total_rounds", 0) or 0),
                        int(workout.get("work_time", 0) or 0),
                        int(workout.get("rest_time", 0) or 0),
                        json.dumps(workout.get("exercises", []), ensure_ascii=False),
                        workout.get("date", workout.get("timestamp", now)),
                    )
                )
    print(f"✅ Старая статистика импортирована из {legacy_file} в SQLite")


def get_stats_by_period(user_id: str, days: int):
    init_db()
    cutoff_date = datetime.now() - timedelta(days=days)
    with get_db() as conn:
        row = conn.execute(
            """SELECT COUNT(*) AS workouts,
                      COALESCE(SUM(calories), 0) AS calories,
                      COALESCE(SUM(duration_seconds), 0) AS seconds
               FROM workouts
               WHERE user_id = ? AND timestamp >= ?""",
            (int(user_id), cutoff_date.isoformat())
        ).fetchone()
    return {
        "workouts": int(row["workouts"] or 0),
        "calories": float(row["calories"] or 0),
        "minutes": round(float(row["seconds"] or 0) / 60, 2),
    }


def calculate_streak(user_id: str, stats: dict):
    user_id_str = str(user_id)
    if user_id_str not in stats or not stats[user_id_str].get("workouts"):
        return 0, 0

    workouts = sorted(
        stats[user_id_str]["workouts"],
        key=lambda x: x["timestamp"]
    )
    if not workouts:
        return 0, 0

    max_streak = 1
    current_streak = 1

    last_date = datetime.fromisoformat(workouts[0]["timestamp"]).date()
    for i in range(1, len(workouts)):
        current_date = datetime.fromisoformat(workouts[i]["timestamp"]).date()
        diff = (current_date - last_date).days
        if diff == 1:
            current_streak += 1
            max_streak = max(max_streak, current_streak)
        elif diff > 1:
            current_streak = 1
        last_date = current_date

    today = datetime.now().date()
    recent_date = datetime.fromisoformat(workouts[-1]["timestamp"]).date()
    if (today - recent_date).days > 1:
        return 0, max_streak

    streak = 1
    cursor = today
    for item in reversed(workouts):
        item_date = datetime.fromisoformat(item["timestamp"]).date()
        if item_date == cursor:
            streak += 1
            cursor -= timedelta(days=1)
        elif (cursor - item_date).days == 1:
            streak += 1
            cursor = item_date
        else:
            break

    return streak - 1, max_streak

def _number(value, default=0.0):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _duration_seconds(workout_data: dict):
    for key in ("duration_seconds", "elapsed_seconds", "seconds"):
        value = _number(workout_data.get(key), -1)
        if value >= 0:
            return int(round(value)), "actual"

    for key in ("duration_minutes", "elapsed_minutes", "minutes"):
        value = _number(workout_data.get(key), -1)
        if value >= 0:
            return int(round(value * 60)), "actual"

    return 0, "unknown"


def register_user(user: types.User):
    init_db()
    now = datetime.now().isoformat()
    with get_db() as conn:
        existing = conn.execute(
            "SELECT telegram_id FROM users WHERE telegram_id = ?", (user.id,)
        ).fetchone()
        if existing:
            conn.execute(
                """UPDATE users
                   SET first_name = ?, username = ?, updated_at = ?
                   WHERE telegram_id = ?""",
                (user.first_name or "", user.username or "", now, user.id)
            )
        else:
            conn.execute(
                """INSERT INTO users
                   (telegram_id, first_name, username, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?)""",
                (user.id, user.first_name or "", user.username or "", now, now)
            )


def record_workout(user_id: str, workout_data: dict):
    init_db()
    uid = int(user_id)
    now = datetime.now().isoformat()
    calories = _number(workout_data.get("calories"), 0.0)
    duration_seconds, duration_source = _duration_seconds(workout_data)
    minutes = round(duration_seconds / 60, 2)

    with get_db() as conn:
        user = conn.execute(
            "SELECT telegram_id FROM users WHERE telegram_id = ?", (uid,)
        ).fetchone()
        if not user:
            conn.execute(
                """INSERT INTO users (telegram_id, created_at, updated_at)
                   VALUES (?, ?, ?)""", (uid, now, now)
            )

        cursor = conn.execute(
            """INSERT INTO workouts
               (user_id, timestamp, action, workout_type, mode, load, focus,
                duration_seconds, formatted_time, duration_source, calories,
                weight, age, gender, height, rounds_completed, total_rounds,
                work_time, rest_time, exercises, date)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                uid, now,
                workout_data.get("action", "workout_finished"),
                workout_data.get("workout_type", workout_data.get("mode", "Тренировка")),
                workout_data.get("mode", ""), workout_data.get("load", ""),
                workout_data.get("focus", ""), duration_seconds,
                workout_data.get("formatted_time", ""), duration_source,
                calories, workout_data.get("weight", ""),
                workout_data.get("age", ""), workout_data.get("gender", ""),
                workout_data.get("height", ""),
                int(workout_data.get("rounds_completed", 0) or 0),
                int(workout_data.get("total_rounds", 0) or 0),
                int(workout_data.get("work_time", 0) or 0),
                int(workout_data.get("rest_time", 0) or 0),
                json.dumps(workout_data.get("exercises", []), ensure_ascii=False),
                workout_data.get("date", now),
            )
        )
        workout_id = cursor.lastrowid
        conn.execute(
            """UPDATE users
               SET total_workouts = total_workouts + 1,
                   total_calories = total_calories + ?,
                   total_minutes = total_minutes + ?,
                   last_workout_at = ?,
                   reminders_sent = '[]',
                   updated_at = ?
               WHERE telegram_id = ?""",
            (calories, minutes, now, now, uid)
        )
        row = conn.execute(
            "SELECT * FROM workouts WHERE id = ?", (workout_id,)
        ).fetchone()
    return _row_to_workout(row)



REMINDER_DAYS = (3, 7, 14, 30)
REMINDER_INTERVAL = 60 * 60

def _last_workout(user_data):
    if user_data.get("last_workout_at"):
        return user_data["last_workout_at"]
    workouts = user_data.get("workouts", [])
    dates = [w.get("timestamp") for w in workouts if w.get("timestamp")]
    return max(dates) if dates else None


def _reminder_text(days, first_name):
    name = f", {first_name}" if first_name else ""
    texts = {
        3: f"👋 {name} уже 3 дня без тренировки.\n\nСамое время вернуться к плану 💪 Сделаем тренировку сегодня?",
        7: f"📅 {name} уже неделя без тренировки.\n\nНе теряем ритм — даже короткая тренировка лучше паузы. 🔥",
        14: f"⚠️ {name} уже 14 дней без тренировки.\n\nДавай мягко вернёмся в режим. Я могу составить тренировку прямо сейчас.",
        30: f"⏰ {name} уже 30 дней без тренировки.\n\nПора возвращаться! Начнём с подходящей нагрузки и без перегруза. 💪"
    }
    return texts[days]


def update_reminders_sent(user_id, reminders):
    init_db()
    with get_db() as conn:
        conn.execute(
            """UPDATE users SET reminders_sent = ?, updated_at = ?
               WHERE telegram_id = ?""",
            (json.dumps(sorted(set(reminders))), datetime.now().isoformat(), int(user_id))
        )


async def reminder_loop():
    while True:
        try:
            stats = load_stats()
            changed = False
            now = datetime.now()
            for uid, user_data in stats.items():
                last = _last_workout(user_data)
                if not last:
                    continue
                try:
                    last_dt = datetime.fromisoformat(last)
                except (TypeError, ValueError):
                    continue
                days = (now - last_dt).days
                sent = set(user_data.get("reminders_sent", []))
                due = [d for d in REMINDER_DAYS if days >= d and d not in sent]
                if not due:
                    continue
                # Отправляем только самое актуальное напоминание, если бот был офлайн.
                day = max(due)
                try:
                    await bot.send_message(int(uid), _reminder_text(day, user_data.get("first_name", "")), reply_markup=get_main_keyboard())
                    user_data.setdefault("reminders_sent", []).extend(due)
                    update_reminders_sent(uid, user_data["reminders_sent"])
                    changed = True
                except Exception as e:
                    print(f"Reminder error for {uid}: {e}")
            # Напоминания уже сохранены в SQLite через update_reminders_sent().
        except Exception as e:
            print(f"Reminder loop error: {e}")
        await asyncio.sleep(REMINDER_INTERVAL)

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

def build_exercises(pool, count):
    """Возвращает ровно count упражнений: одно упражнение на один раунд."""
    if not pool or count <= 0:
        return []
    if len(pool) >= count:
        return random.sample(pool, k=count)
    return [random.choice(pool) for _ in range(count)]


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
    stats = load_stats()
    user_id_str = str(user_id)

    if user_id_str not in stats or stats[user_id_str].get("total_workouts", 0) == 0:
        text = "📊 **У вас еще нет завершенных тренировок.**\n\nСоздайте первую тренировку прямо сейчас! 💪"
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="🏋️ Создать тренировку", callback_data="workout_Микс")]
            ]
        )
    else:
        user_stats = stats[user_id_str]
        total_workouts = user_stats["total_workouts"]
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
            f"   ⏱️  Минут в работе: {total_minutes}\n"
            f"   📉 Средне за тренировку: {total_calories/total_workouts:.0f} ккал\n\n"
            f"📅 **ЗА НЕДЕЛЮ (7 дней):**\n"
            f"   💪 {week_stats['workouts']} зан. | 🔥 {week_stats['calories']:.0f} ккал | ⏱️ {week_stats['minutes']} мин\n\n"
            f"📆 **ЗА МЕСЯЦ (30 дней):**\n"
            f"   💪 {month_stats['workouts']} зан. | 🔥 {month_stats['calories']:.0f} ккал | ⏱️ {month_stats['minutes']} мин\n\n"
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
    load_info = LOAD_LEVELS.get(load_level, LOAD_LEVELS["🟡 Средняя"])
    total_rounds = int(load_info["rounds"])
    exercises = build_exercises(pool, total_rounds)
    
    encoded_exercises = urllib.parse.quote(
        json.dumps(exercises, ensure_ascii=False)
    )
    params = {
        "workout": encoded_exercises,
        "workout_type": goal,
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
        record = record_workout(message.from_user.id, data)
        current_streak, max_streak = calculate_streak(message.from_user.id, load_stats())

        seconds = int(record.get("duration_seconds", 0))
        mins, secs = divmod(seconds, 60)
        duration = f"{mins} мин" + (f" {secs} сек" if secs else "") if mins else f"{secs} сек"

        await message.answer(
            f"🎉 **Тренировка завершена!**\n\n"
            f"🏋️ **Тип:** {record.get('workout_type', 'Тренировка')}\n"
            f"📌 **Режим:** {record.get('mode', '—')}\n"
            f"💪 **Нагрузка:** {record.get('load', '—')}\n"
            f"🎯 **Фокус:** {record.get('focus', '—')}\n"
            f"⏱️ **Время:** {duration}\n"
            f"🔥 **Калории:** {record.get('calories', 0):.1f} ккал\n"
            f"🔄 **Раунды:** {record.get('rounds_completed', '—')} / {record.get('total_rounds', '—')}\n\n"
            f"🔥 **Серия:** {current_streak} дней (рекорд {max_streak}) 🏆\n\n"
            f"📈 **Статистика сохранена.**",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="📊 Открыть статистику", callback_data="stats_show")],
                [InlineKeyboardButton(text="🏋️ Новая тренировка", callback_data="workout_Микс")]
            ])
        )
    except Exception as e:
        print(f"Ошибка сохранения: {e}")
        await message.answer("❌ Ошибка при записи результатов.", reply_markup=get_main_keyboard())

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
    init_db()
    migrate_legacy_json()
    print(f"🤖 Бот запущен... SQLite: {DB_FILE}")
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
