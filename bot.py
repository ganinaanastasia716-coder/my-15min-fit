import asyncio
import json
import os
import random
import sqlite3
import urllib.parse
from datetime import datetime, timedelta

from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import Command, CommandStart
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
WEB_APP_BASE_URL = os.getenv("WEB_APP_BASE_URL", "").strip()

if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN must be set")

if not WEB_APP_BASE_URL:
    raise ValueError("WEB_APP_BASE_URL must be set to the HTTPS URL of index.html")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# ---------------------------------------------------------------------------
# DATABASE
# ---------------------------------------------------------------------------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
LOCAL_STATS_FILE = os.path.join(BASE_DIR, "workout_stats.json")
DB_FILE = os.getenv("STATS_DB_FILE", "").strip() or (
    "/data/workout_stats.db" if os.path.isdir("/data")
    else os.path.join(BASE_DIR, "workout_stats.db")
)

def db():
    os.makedirs(os.path.dirname(DB_FILE) or ".", exist_ok=True)
    conn = sqlite3.connect(DB_FILE, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=30000")
    return conn

def init_db():
    with db() as conn:
        conn.execute("CREATE TABLE IF NOT EXISTS stats (user_id TEXT PRIMARY KEY, data TEXT NOT NULL)")
        conn.commit()

def import_old_json():
    init_db()
    with db() as conn:
        if conn.execute("SELECT COUNT(*) FROM stats").fetchone()[0]:
            return
    if not os.path.exists(LOCAL_STATS_FILE):
        return
    try:
        old = json.loads(open(LOCAL_STATS_FILE, encoding="utf-8").read())
        if not isinstance(old, dict):
            return
        with db() as conn:
            for uid, data in old.items():
                conn.execute(
                    "INSERT OR REPLACE INTO stats(user_id,data) VALUES(?,?)",
                    (str(uid), json.dumps(data, ensure_ascii=False))
                )
            conn.commit()
        print("✅ Старый workout_stats.json импортирован в SQLite")
    except Exception as e:
        print("⚠️ Ошибка импорта JSON:", e)

init_db()
import_old_json()
print("🗄️ SQLite:", DB_FILE)

def load_stats():
    init_db()
    result = {}
    with db() as conn:
        for row in conn.execute("SELECT user_id,data FROM stats"):
            try:
                result[str(row["user_id"])] = json.loads(row["data"])
            except Exception:
                result[str(row["user_id"])] = {}
    return result

def save_stats(stats):
    with db() as conn:
        for uid, data in stats.items():
            conn.execute(
                """INSERT INTO stats(user_id,data) VALUES(?,?)
                   ON CONFLICT(user_id) DO UPDATE SET data=excluded.data""",
                (str(uid), json.dumps(data, ensure_ascii=False))
            )
        conn.commit()

def register_user(user):
    stats = load_stats()
    uid = str(user.id)
    stats.setdefault(uid, {
        "profile": {},
        "total_workouts": 0,
        "total_calories": 0,
        "total_minutes": 0,
        "workouts": [],
        "last_workout_at": None,
        "reminders_sent": []
    })
    stats[uid]["telegram_name"] = user.first_name or ""
    save_stats(stats)

def record_workout(user_id, payload):
    stats = load_stats()
    uid = str(user_id)
    user = stats.setdefault(uid, {
        "profile": {}, "total_workouts": 0, "total_calories": 0,
        "total_minutes": 0, "workouts": [], "last_workout_at": None,
        "reminders_sent": []
    })

    duration = max(0, int(float(payload.get("duration_seconds", 0) or 0)))
    calories = max(0.0, float(payload.get("calories", 0) or 0))
    now = datetime.now().isoformat()

    profile = payload.get("profile") or {}
    if profile:
        user["profile"] = profile

    item = {
        "timestamp": now,
        "workout_type": payload.get("workout_type", "Тренировка"),
        "mode": payload.get("mode", ""),
        "focus": payload.get("focus", ""),
        "intensity": payload.get("intensity", ""),
        "duration_seconds": duration,
        "minutes": round(duration / 60, 2),
        "calories": calories,
        "weight": payload.get("weight", profile.get("weight", "")),
        "rounds_completed": payload.get("rounds_completed", 0),
        "total_rounds": payload.get("total_rounds", 0),
        "round_times": payload.get("round_times", []),
        "exercises": payload.get("exercises", []),
        "details": payload.get("details", "")
    }

    user["workouts"].append(item)
    user["total_workouts"] = int(user.get("total_workouts", 0)) + 1
    user["total_calories"] = float(user.get("total_calories", 0)) + calories
    user["total_minutes"] = float(user.get("total_minutes", 0)) + duration / 60
    user["last_workout_at"] = now
    user["reminders_sent"] = []

    save_stats(stats)
    return item

def streaks(user_id):
    data = load_stats().get(str(user_id), {})
    dates = set()
    for w in data.get("workouts", []):
        try:
            dates.add(datetime.fromisoformat(w["timestamp"]).date())
        except Exception:
            pass
    if not dates:
        return 0, 0
    ordered = sorted(dates)
    best = cur = 1
    for i in range(1, len(ordered)):
        if (ordered[i] - ordered[i-1]).days == 1:
            cur += 1
            best = max(best, cur)
        else:
            cur = 1
    today = datetime.now().date()
    current = 0
    cursor = today
    while cursor in dates:
        current += 1
        cursor -= timedelta(days=1)
    if current == 0 and today - ordered[-1] == timedelta(days=1):
        current = 1
    return current, best

# ---------------------------------------------------------------------------
# WORKOUT LIBRARY
# ---------------------------------------------------------------------------
FOCUS = {
    "legs": "Ноги",
    "glutes": "Ягодицы",
    "back": "Спина",
    "chest": "Грудь",
    "shoulders": "Плечи",
    "arms": "Руки",
    "all": "Всё тело",
}

NORMAL_EXERCISES = {
    "Силовая": {
        "legs": ["Приседания", "Выпады назад", "Болгарские сплит-приседания", "Приседания сумо"],
        "glutes": ["Ягодичный мостик", "Болгарские сплит-приседания", "Выпады назад", "Мостик с разведением колен"],
        "back": ["Лодочка", "Тяга полотенца", "Супермен", "Планка с тягой локтя"],
        "chest": ["Отжимания", "Отжимания с широкой постановкой", "Отжимания с колен", "Планка"],
        "shoulders": ["Pike push-up", "Планка с касанием плеч", "Т-планка", "Отжимания в пайке"],
        "arms": ["Отжимания узким хватом", "Обратные отжимания", "Планка на локтях", "Отжимания с колен"],
        "all": ["Приседания", "Отжимания", "Выпады", "Планка", "Ягодичный мостик"]
    },
    "Кардио": {
        "legs": ["Бег с высоким подниманием коленей", "Jumping Jacks", "Выпады с прыжком", "Прыжки конькобежца"],
        "glutes": ["Приседания с выпрыгиванием", "Прыжки конькобежца", "Выпады с прыжком", "Бег на месте"],
        "back": ["Mountain climbers", "Бёрпи", "Jumping Jacks", "Бег на месте"],
        "chest": ["Бёрпи", "Планка с прыжком", "Mountain climbers", "Взрывные отжимания"],
        "shoulders": ["Боксёрские удары", "Планка с прыжком", "Mountain climbers", "Jumping Jacks"],
        "arms": ["Боксёрские удары", "Бёрпи", "Планка", "Mountain climbers"],
        "all": ["Бёрпи", "Jumping Jacks", "Mountain climbers", "Бег на месте", "Прыжки конькобежца"]
    },
    "Растяжка": {
        "legs": ["Растяжка квадрицепса", "Наклон к ногам", "Поза голубя", "Бабочка"],
        "glutes": ["Поза голубя", "Бабочка", "Наклон к ногам", "Скрутка лёжа"],
        "back": ["Кошка-корова", "Поза ребёнка", "Сфинкс", "Собака мордой вниз"],
        "chest": ["Растяжка груди у стены", "Кобра", "Замок за спиной", "Скрутка"],
        "shoulders": ["Растяжка плеча", "Растяжка трицепса", "Замок за спиной", "Круги плечами"],
        "arms": ["Растяжка трицепса", "Растяжка предплечий", "Плечо поперёк груди", "Замок за спиной"],
        "all": ["Поза ребёнка", "Собака мордой вниз", "Бабочка", "Кобра", "Кошка-корова"]
    },
    "Микс": {}
}
for z in FOCUS:
    NORMAL_EXERCISES["Микс"][z] = (
        NORMAL_EXERCISES["Силовая"][z] + NORMAL_EXERCISES["Кардио"][z]
    )

INTENSITY = {
    "light": ("🟢 Лёгкая", 3.5, 10, 6),
    "medium": ("🟡 Средняя", 6.0, 15, 8),
    "high": ("🔴 Высокая", 8.5, 20, 10),
}

CF_EXERCISES = [
    ("Thruster", [8, 12, 15], "Штанга / гантели"),
    ("Burpee", [6, 10, 14], "Вес тела"),
    ("Box Step-up / Box Jump", [8, 10, 12], "Бокс"),
    ("Kettlebell Swing", [10, 15, 20], "Гиря"),
    ("Push-up", [8, 12, 16], "Вес тела"),
    ("Double-under / Single-under", [30, 40, 50], "Скакалка"),
    ("Dumbbell Snatch", [8, 12, 16], "Гантель"),
    ("Goblet Squat", [10, 15, 20], "Гиря / гантель"),
    ("Pull-up / Scaled Pull-up", [5, 8, 12], "Турник"),
    ("Wall Ball", [8, 12, 15], "Медбол"),
    ("Row", [200, 250, 300], "Гребля"),
    ("Run", [200, 300, 400], "Бег"),
]

def webapp_url(params):
    sep = "&" if "?" in WEB_APP_BASE_URL else "?"
    return WEB_APP_BASE_URL + sep + urllib.parse.urlencode(params)

# ---------------------------------------------------------------------------
# TELEGRAM MENUS
# ---------------------------------------------------------------------------
def main_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💪 Силовая", callback_data="workout_Силовая")],
        [InlineKeyboardButton(text="🔥 Кардио", callback_data="workout_Кардио")],
        [InlineKeyboardButton(text="🧘 Растяжка", callback_data="workout_Растяжка")],
        [InlineKeyboardButton(text="🎲 Микс дня", callback_data="workout_Микс")],
        [InlineKeyboardButton(text="🏋️ CrossFit", callback_data="crossfit_menu")],
        [InlineKeyboardButton(text="📊 Моя статистика", callback_data="stats_show")],
    ])

@dp.message(CommandStart())
async def start(message: types.Message):
    register_user(message.from_user)
    await message.answer(
        f"Привет, {message.from_user.first_name or ''}! 👋\n\nВыбери тренировку:",
        reply_markup=main_keyboard()
    )

@dp.message(Command("stats"))
async def stats_cmd(message: types.Message):
    await show_stats(message.from_user.id, message)

async def show_stats(user_id, target):
    data = load_stats().get(str(user_id), {})
    total = int(data.get("total_workouts", 0))
    cal = float(data.get("total_calories", 0))
    minutes = float(data.get("total_minutes", 0))
    current, best = streaks(user_id)

    text = (
        "📊 **МОЯ СТАТИСТИКА**\n\n"
        f"💪 Тренировок: **{total}**\n"
        f"🔥 Калории: **{cal:.0f} ккал**\n"
        f"⏱ Время: **{minutes:.0f} мин**\n"
        f"🔥 Серия: **{current} дней**\n"
        f"🏆 Рекорд: **{best} дней**"
    )
    if isinstance(target, types.CallbackQuery):
        await target.message.answer(text, reply_markup=main_keyboard())
    else:
        await target.answer(text, reply_markup=main_keyboard())

@dp.callback_query(F.data == "stats_show")
async def stats_callback(callback: types.CallbackQuery):
    await show_stats(callback.from_user.id, callback)
    await callback.answer()

# ---------------------------------------------------------------------------
# NORMAL WORKOUT FLOW:
# direction -> intensity -> body part -> EMOM/AMRAP -> plan -> Mini App
# ---------------------------------------------------------------------------
@dp.callback_query(F.data.startswith("workout_"))
async def choose_intensity(callback: types.CallbackQuery):
    goal = callback.data.split("_", 1)[1]
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🟢 Лёгкая", callback_data=f"intensity_{goal}_light")],
        [InlineKeyboardButton(text="🟡 Средняя", callback_data=f"intensity_{goal}_medium")],
        [InlineKeyboardButton(text="🔴 Высокая", callback_data=f"intensity_{goal}_high")],
        [InlineKeyboardButton(text="← Назад", callback_data="back_main")]
    ])
    await callback.message.edit_text(
        f"✨ **{goal}**\n\nСначала выбери интенсивность:",
        reply_markup=kb
    )
    await callback.answer()

@dp.callback_query(F.data.startswith("intensity_"))
async def choose_focus(callback: types.CallbackQuery):
    _, goal, level = callback.data.split("_", 2)
    rows = [
        ("🦵 Ноги", "legs"), ("🍑 Ягодицы", "glutes"),
        ("💪 Спина", "back"), ("❤️ Грудь", "chest"),
        ("🏋️ Плечи", "shoulders"), ("💪 Руки", "arms"),
        ("🧘 Всё тело", "all")
    ]
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=t, callback_data=f"focus_{goal}_{level}_{k}")]
        for t, k in rows
    ] + [[InlineKeyboardButton(text="← Назад", callback_data=f"workout_{goal}")]])
    await callback.message.edit_text(
        f"🎯 **{goal}**\n🔥 {INTENSITY[level][0]}\n\nТеперь выбери часть тела:",
        reply_markup=kb
    )
    await callback.answer()

@dp.callback_query(F.data.startswith("focus_"))
async def choose_normal_mode(callback: types.CallbackQuery):
    _, goal, level, focus = callback.data.split("_", 3)
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⏱ EMOM", callback_data=f"normal_{goal}_{level}_{focus}_emom")],
        [InlineKeyboardButton(text="🔄 AMRAP", callback_data=f"normal_{goal}_{level}_{focus}_amrap")],
        [InlineKeyboardButton(text="← Назад", callback_data=f"intensity_{goal}_{level}")]
    ])
    await callback.message.edit_text(
        f"🎯 {FOCUS[focus]}\n🔥 {INTENSITY[level][0]}\n\nВыбери формат:",
        reply_markup=kb
    )
    await callback.answer()

@dp.callback_query(F.data.startswith("normal_"))
async def build_normal(callback: types.CallbackQuery):
    _, goal, level, focus, mode = callback.data.split("_", 4)
    pool = NORMAL_EXERCISES.get(goal, NORMAL_EXERCISES["Микс"]).get(focus, [])
    selected = random.sample(pool, min(5, len(pool)))
    _, met, duration, rounds = INTENSITY[level]
    reps = {"light": 8, "medium": 12, "high": 16}[level]
    plan = [{"name": x, "reps": reps} for x in selected]
    params = {
        "workout_type": goal, "focus": focus, "intensity": level,
        "mode": mode, "duration": duration, "rounds": rounds, "met": met,
        "workout": json.dumps(plan, ensure_ascii=False)
    }
    url = webapp_url(params)
    text_plan = "\n".join(f"{i+1}. **{x['name']}** — {x['reps']} повторений" for i, x in enumerate(plan))
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🚀 Открыть тренировку", web_app=WebAppInfo(url=url))],
        [InlineKeyboardButton(text="← Назад", callback_data=f"focus_{goal}_{level}_{focus}")]
    ])
    await callback.message.edit_text(
        f"📋 **ТРЕНИРОВКА ГОТОВА**\n\n"
        f"Тип: **{goal}**\n"
        f"Интенсивность: **{INTENSITY[level][0]}**\n"
        f"Часть тела: **{FOCUS[focus]}**\n"
        f"Формат: **{'⏱ EMOM' if mode == 'emom' else '🔄 AMRAP'}**\n\n"
        f"{text_plan}\n\n"
        "Все параметры уже установлены в Mini App.",
        reply_markup=kb
    )
    await callback.answer()

# ---------------------------------------------------------------------------
# CROSSFIT FLOW:
# CrossFit -> intensity -> EMOM/AMRAP/RFT -> plan -> same Mini App
# ---------------------------------------------------------------------------
@dp.callback_query(F.data == "crossfit_menu")
async def crossfit_menu(callback: types.CallbackQuery):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🟢 Лёгкая", callback_data="cf_level_light")],
        [InlineKeyboardButton(text="🟡 Средняя", callback_data="cf_level_medium")],
        [InlineKeyboardButton(text="🔴 Высокая", callback_data="cf_level_high")],
        [InlineKeyboardButton(text="← Назад", callback_data="back_main")]
    ])
    await callback.message.edit_text("🏋️ **CROSSFIT**\n\nВыбери интенсивность:", reply_markup=kb)
    await callback.answer()

@dp.callback_query(F.data.startswith("cf_level_"))
async def cf_mode(callback: types.CallbackQuery):
    level = callback.data.split("_")[-1]
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⏱ EMOM", callback_data=f"cf_{level}_emom")],
        [InlineKeyboardButton(text="🔄 AMRAP", callback_data=f"cf_{level}_amrap")],
        [InlineKeyboardButton(text="🏁 RFT / Раунды", callback_data=f"cf_{level}_rft")],
        [InlineKeyboardButton(text="← Назад", callback_data="crossfit_menu")]
    ])
    await callback.message.edit_text(
        f"🏋️ **CROSSFIT**\n\nИнтенсивность: **{INTENSITY[level][0]}**\n\nВыбери формат:",
        reply_markup=kb
    )
    await callback.answer()

@dp.callback_query(F.data.regexp(r"^cf_(light|medium|high)_(emom|amrap|rft)$"))
async def build_crossfit(callback: types.CallbackQuery):
    _, level, mode = callback.data.split("_")
    idx = {"light": 0, "medium": 1, "high": 2}[level]
    items = CF_EXERCISES[:]
    random.shuffle(items)
    plan = [{"name": x[0], "reps": x[1][idx], "gear": x[2]} for x in items[:4]]

    duration = {"light": 10, "medium": 12, "high": 15}[level]
    rounds = {"light": 3, "medium": 5, "high": 7}[level]
    met = {"light": 6.0, "medium": 8.0, "high": 10.0}[level]

    params = {
        "workout_type": "CrossFit", "focus": "CrossFit", "intensity": level,
        "mode": mode, "duration": duration, "rounds": rounds, "met": met,
        "workout": json.dumps(plan, ensure_ascii=False)
    }
    url = webapp_url(params)
    text_plan = "\n".join(
        f"{i+1}. **{x['name']}** — {x['reps']} · {x['gear']}"
        for i, x in enumerate(plan)
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🚀 Открыть тренировку", web_app=WebAppInfo(url=url))],
        [InlineKeyboardButton(text="← Назад", callback_data=f"cf_level_{level}")]
    ])
    await callback.message.edit_text(
        f"📋 **CROSSFIT WOD ГОТОВ**\n\n"
        f"🔥 Интенсивность: **{INTENSITY[level][0]}**\n"
        f"📐 Формат: **{'⏱ EMOM' if mode == 'emom' else '🔄 AMRAP' if mode == 'amrap' else '🏁 RFT'}**\n\n"
        f"{text_plan}\n\n"
        "Открой тренировку — выбранный режим уже будет установлен.",
        reply_markup=kb
    )
    await callback.answer()

@dp.callback_query(F.data == "back_main")
async def back_main(callback: types.CallbackQuery):
    await callback.message.edit_text("Выбери тренировку:", reply_markup=main_keyboard())
    await callback.answer()

# ---------------------------------------------------------------------------
# RESULT FROM MINI APP
# ---------------------------------------------------------------------------
@dp.message(F.web_app_data)
async def webapp_result(message: types.Message):
    try:
        payload = json.loads(message.web_app_data.data)
        record = record_workout(message.from_user.id, payload)
        current, best = streaks(message.from_user.id)

        sec = int(record["duration_seconds"])
        mins, secs = divmod(sec, 60)
        duration = f"{mins} мин {secs} сек" if mins else f"{secs} сек"

        await message.answer(
            "🎉 **ТРЕНИРОВКА ЗАВЕРШЕНА!**\n\n"
            f"🏋️ {record['workout_type']}\n"
            f"📐 {record['mode']}\n"
            f"🔥 {record['intensity']}\n"
            f"⏱ {duration}\n"
            f"🔥 {record['calories']:.0f} ккал\n"
            f"🔁 Раундов: {record['rounds_completed']}"
            + (f" / {record['total_rounds']}" if record["total_rounds"] else "")
            + f"\n\n🔥 Серия: {current} дней\n🏆 Рекорд: {best} дней\n\n"
            "📈 Результат записан в статистику.",
            reply_markup=main_keyboard()
        )
    except Exception as e:
        print("❌ Ошибка WebApp:", e)
        await message.answer("❌ Не удалось сохранить результат. Попробуй ещё раз.", reply_markup=main_keyboard())

# ---------------------------------------------------------------------------
# REMINDERS: 3 / 7 / 14 / 30 DAYS
# ---------------------------------------------------------------------------
async def reminder_loop():
    await asyncio.sleep(30)
    while True:
        try:
            stats = load_stats()
            now = datetime.now()
            for uid, data in stats.items():
                last = data.get("last_workout_at")
                if not last:
                    continue
                try:
                    last_dt = datetime.fromisoformat(last)
                except Exception:
                    continue
                days = (now - last_dt).days
                for target in (3, 7, 14, 30):
                    if days >= target and target not in data.get("reminders_sent", []):
                        messages = {
                            3: "💪 Уже 3 дня без тренировки. Самое время вернуться!",
                            7: "🔥 Неделя прошла. Давай сделаем новую тренировку!",
                            14: "⚡ Две недели без тренировки. Начнём снова с комфортной интенсивности?",
                            30: "🏆 Месяц — отличный момент вернуться в режим. Ganina Fit ждёт!"
                        }
                        try:
                            await bot.send_message(int(uid), messages[target], reply_markup=main_keyboard())
                            data.setdefault("reminders_sent", []).append(target)
                            save_stats(stats)
                        except Exception as e:
                            print("⚠️ Reminder error:", e)
                        break
        except Exception as e:
            print("⚠️ Reminder loop:", e)
        await asyncio.sleep(3600)

async def main():
    print("🤖 Ganina Fit bot started")
    reminder = asyncio.create_task(reminder_loop())
    try:
        await dp.start_polling(bot)
    finally:
        reminder.cancel()
        try:
            await reminder
        except asyncio.CancelledError:
            pass
        await bot.session.close()

if __name__ == "__main__":
    asyncio.run(main())
