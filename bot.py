import asyncio
import json
import os
import urllib.parse
from datetime import datetime, timedelta

from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import Command, CommandStart
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
from dotenv import load_dotenv
from google import genai

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
WEB_APP_BASE_URL = os.getenv("WEB_APP_BASE_URL", "https://ganinaanastasia716-coder.github.io/my-15min-fit/")
STATS_FILE = "workout_stats.json"

if not BOT_TOKEN or not GEMINI_API_KEY:
    raise ValueError("BOT_TOKEN and GEMINI_API_KEY must be set in .env")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

ai_client = genai.Client(api_key=GEMINI_API_KEY)

WORKOUT_GOALS = {
    "Силовая": {
        "ru": "Силовая",
        "gems_prompt": "силовые упражнения для увеличения мышечной массы"
    },
    "Кардио": {
        "ru": "Кардио / Жиросжигание",
        "gems_prompt": "высокоинтенсивные кардио-упражнения для жиросжигания"
    },
    "Растяжка": {
        "ru": "Растяжка",
        "gems_prompt": "упражнения на растяжку и гибкость"
    },
    "Микс": {
        "ru": "Микс дня (Ganina AI)",
        "gems_prompt": "микс из различных упражнений: силовые, кардио и растяжка"
    }
}

FOCUS_ZONES = {
    "верх": {
        "emoji": "💪",
        "name": "Верх тела",
        "description": "спину, плечи, руки, грудь"
    },
    "ноги": {
        "emoji": "🦵",
        "name": "Ноги и ягодицы",
        "description": "ноги, ягодицы, квадрицепсы, бицепсы бедра"
    },
    "пресс": {
        "emoji": "🔥",
        "name": "Пресс и кор",
        "description": "пресс, кор, абдоминальные мышцы"
    },
    "все": {
        "emoji": "🧘",
        "name": "Все тело",
        "description": "комплексная тренировка на все группы мышц"
    }
}

LOAD_LEVELS = {
    "🟢 Лёгкая": {
        "met": 3.5,
        "work_time": 20,
        "rest_time": 10,
        "rounds": 6
    },
    "🟡 Средняя": {
        "met": 6.0,
        "work_time": 20,
        "rest_time": 10,
        "rounds": 8
    },
    "🔴 Интенсивная": {
        "met": 8.5,
        "work_time": 30,
        "rest_time": 10,
        "rounds": 10
    }
}

def load_stats():
    try:
        with open(STATS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return {}

def save_stats(stats):
    with open(STATS_FILE, "w", encoding="utf-8") as f:
        json.dump(stats, f, ensure_ascii=False, indent=2)

def get_stats_by_period(user_id: str, days: int):
    stats = load_stats()
    user_id_str = str(user_id)

    if user_id_str not in stats:
        return {"workouts": 0, "calories": 0.0, "minutes": 0}

    cutoff_date = datetime.now() - timedelta(days=days)
    workouts = stats[user_id_str].get("workouts", [])

    filtered = [
        w for w in workouts
        if datetime.fromisoformat(w["timestamp"]) >= cutoff_date
    ]

    return {
        "workouts": len(filtered),
        "calories": sum(float(w.get("calories", 0)) for w in filtered),
        "minutes": sum(int(w.get("minutes", 15)) for w in filtered)
    }

def calculate_streak(user_id: str, stats: dict):
    user_id_str = str(user_id)
    if user_id_str not in stats or not stats[user_id_str].get("workouts"):
        return 0, 0

    workouts = sorted(stats[user_id_str]["workouts"], key=lambda x: x["timestamp"])
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

def record_workout(user_id: str, workout_data: dict):
    stats = load_stats()
    user_id_str = str(user_id)

    if user_id_str not in stats:
        stats[user_id_str] = {"total_workouts": 0, "total_calories": 0.0, "total_minutes": 0, "workouts": []}

    stats[user_id_str]["total_workouts"] += 1
    calories = float(workout_data.get("calories", 0))
    stats[user_id_str]["total_calories"] += calories

    details = workout_data.get("details", "")
    minutes = 15

    if "Схема " in details and "Раунды:" in details:
        try:
            scheme = details.split("Схема ")[1].split(" •")[0]
            work, rest = map(int, scheme.split("/"))
            rounds = int(details.split("Раунды: ")[1].split("/")[0])
            minutes = max(15, rounds * (work + rest) // 60)
        except Exception:
            minutes = 15

    stats[user_id_str]["total_minutes"] += minutes

    workout_record = {
        "timestamp": datetime.now().isoformat(),
        "mode": workout_data.get("mode", ""),
        "load": workout_data.get("load", ""),
        "focus": workout_data.get("focus", ""),
        "details": details,
        "calories": calories,
        "minutes": minutes,
        "weight": workout_data.get("weight", "")
    }

    stats[user_id_str]["workouts"].append(workout_record)
    save_stats(stats)

async def generate_workout_with_gemini(goal: str, load_level: str, focus_zone: str) -> list:
    goal_info = WORKOUT_GOALS.get(goal, WORKOUT_GOALS["Микс"])
    focus_info = FOCUS_ZONES.get(focus_zone, FOCUS_ZONES["все"])

    intensity_guidance = ""
    if load_level == "🟢 Лёгкая":
        intensity_guidance = "Выбери лёгкие, простые упражнения для разминки. Минимальная сложность, спокойный темп."
    elif load_level == "🟡 Средняя":
        intensity_guidance = "Выбери упражнения средней сложности с хорошей нагрузкой и умеренным темпом."
    elif load_level == "🔴 Интенсивная":
        intensity_guidance = "Выбери сложные и интенсивные упражнения для максимальной нагрузки."

    import random
    random_seed = random.randint(1000, 9999)

    prompt = f"""
    ГЕНЕРИРУЙ СЛУЧАЙНЫЙ ВАРИАНТ {random_seed}!
    
    Составь НОВУЮ, УНИКАЛЬНУЮ тренировку для фитнес-приложения FIT15.
    БЕЗ СПОРТИВНОГО ИНВЕНТАРЯ (только вес собственного тела).

    Параметры:
    - Тип: {goal_info['gems_prompt']}
    - Фокус: {focus_info['description']}
    - Интенсивность: {intensity_guidance}
    - ВАЖНО: только упражнения с весом тела! НЕТ гантелей, гирь, тренажеров, эспандеров!
    - НИКОГДА не используй: приседания базовые, отжимания стандартные, планку обычную

    Верни ИСКЛЮЧИТЕЛЬНО JSON-массив из 5 РАЗНЫХ упражнений.
    Каждый объект должен содержать ТОЛЬКО поле "name" (название на русском с эмодзи).

    КРИТИЧЕСКИ ВАЖНО: 
    - Каждый раз НОВЫЕ упражнения!
    - Не повторяй приседания, отжимания, планку
    - Используй вариации: плиометрические, на одной ноге, с прыжками, боковые, диагональные
    - Добавляй сложность: скручивания, выпады, мосты, горные альпинисты, бёрпи, джампинг джеки

    Примеры ПРАВИЛЬНЫХ ответов (каждый раз разные):
    Вариант 1:
    [
        {{"name": "💥 Приседания плиометрические"}},
        {{"name": "🤸 Горный альпинист"}},
        {{"name": "💪 Отжимания в пайке"}},
        {{"name": "⚡ Бёрпи"}},
        {{"name": "🔥 Выпады с прыжком"}}
    ]

    Вариант 2:
    [
        {{"name": "🧘 Боковые скручивания"}},
        {{"name": "🦵 Выпады на месте"}},
        {{"name": "💪 Отжимания узким хватом"}},
        {{"name": "⚡ Джампинг Джеки"}},
        {{"name": "🔥 Ягодичный мост одной ногой"}}
    ]

    Ответь ТОЛЬКО JSON, без лишнего текста!
    """

    try:
        response = ai_client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt
        )

        clean_json = response.text.strip()
        if clean_json.startswith("```json"):
            clean_json = clean_json[7:]
        if clean_json.startswith("```"):
            clean_json = clean_json[3:]
        if clean_json.endswith("```"):
            clean_json = clean_json[:-3]
        clean_json = clean_json.strip()

        exercises = json.loads(clean_json)

        if not isinstance(exercises, list) or len(exercises) == 0:
            raise ValueError("Bad response")

        return exercises

    except Exception as e:
        print(f"⚠️ Ошибка Gemini: {e}")
        fallbacks = {
            "верх": [
                {"name": "💪 Отжимания в пайке"},
                {"name": "🤸 Планка с рывком"},
                {"name": "🔥 Отжимания на одной руке (подготовка)"},
                {"name": "💥 Подъем корпуса лёжа"},
                {"name": "🧘 Планка на предплечьях"}
            ],
            "ноги": [
                {"name": "🦵 Приседания плиометрические"},
                {"name": "💪 Выпады назад с прыжком"},
                {"name": "🔥 Подъем коленей в прыжке"},
                {"name": "🤸 Ягодичный мост на одной ноге"},
                {"name": "⚡ Болгарские выпады"}
            ],
            "пресс": [
                {"name": "🔥 Скручивания с поднятием ног"},
                {"name": "💥 Велосипед с ускорением"},
                {"name": "🤸 Горный альпинист быстрый"},
                {"name": "⚡ Поднятие ног в висе"},
                {"name": "🧘 Боковая планка с подъёмом ноги"}
            ],
            "все": [
                {"name": "💪 Бёрпи"},
                {"name": "🦵 Приседания со скручиванием"},
                {"name": "🔥 Джампинг Джеки"},
                {"name": "⚡ Горный альпинист"},
                {"name": "🧘 Выпады в движении"}
            ]
        }
        return fallbacks.get(focus_zone, fallbacks["все"])

@dp.message(CommandStart())
async def start_cmd(message: types.Message):
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🏋️ Силовая", callback_data="workout_Силовая")],
            [InlineKeyboardButton(text="🏃 Кардио / Жиросжигание", callback_data="workout_Кардио")],
            [InlineKeyboardButton(text="🧘 Растяжка", callback_data="workout_Растяжка")],
            [InlineKeyboardButton(text="🎲 Микс дня (Ganina AI)", callback_data="workout_Микс")],
            [InlineKeyboardButton(text="📊 Моя статистика", callback_data="stats_show")]
        ]
    )

    await message.answer(
        f"Привет, {message.from_user.first_name}! 👋\n\n"
        f"Какую тренировку должна составить Ganina сегодня?",
        reply_markup=keyboard
    )

@dp.message(Command("stats"))
async def stats_cmd(message: types.Message):
    user_id = str(message.from_user.id)
    stats = load_stats()

    if user_id not in stats or stats[user_id]["total_workouts"] == 0:
        await message.answer("📊 У вас еще нет завершенных тренировок.\n\nСоздайте первую тренировку уже сейчас! 💪")
        return

    user_stats = stats[user_id]
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
        f"   💪 {week_stats['workouts']} тренировок\n"
        f"   🔥 {week_stats['calories']:.0f} ккал\n"
        f"   ⏱️  {week_stats['minutes']} минут\n\n"
        f"📆 **ЗА МЕСЯЦ (30 дней):**\n"
        f"   💪 {month_stats['workouts']} тренировок\n"
        f"   🔥 {month_stats['calories']:.0f} ккал\n"
        f"   ⏱️  {month_stats['minutes']} минут\n\n"
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

    await message.answer(text, reply_markup=keyboard)

@dp.callback_query(F.data.startswith("workout_"))
async def select_workout_type(callback: types.CallbackQuery):
    goal = callback.data.split("_", 1)[1]

    focus_keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="💪 Верх тела", callback_data=f"focus_{goal}_верх")],
            [InlineKeyboardButton(text="🦵 Ноги и ягодицы", callback_data=f"focus_{goal}_ноги")],
            [InlineKeyboardButton(text="🔥 Пресс и кор", callback_data=f"focus_{goal}_пресс")],
            [InlineKeyboardButton(text="🧘 Все тело", callback_data=f"focus_{goal}_все")],
            [InlineKeyboardButton(text="← Назад к выбору тренировки", callback_data="back_to_workout_menu")]
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

    focus_info = FOCUS_ZONES.get(focus_zone, FOCUS_ZONES["все"])

    intensity_keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🟢 Лёгкая", callback_data=f"intensity_{goal}_{focus_zone}_🟢 Лёгкая")],
            [InlineKeyboardButton(text="🟡 Средняя", callback_data=f"intensity_{goal}_{focus_zone}_🟡 Средняя")],
            [InlineKeyboardButton(text="🔴 Интенсивная", callback_data=f"intensity_{goal}_{focus_zone}_🔴 Интенсивная")],
            [InlineKeyboardButton(text="← Назад к выбору фокуса", callback_data=f"back_to_focus_{goal}")]
        ]
    )

    goal_name = WORKOUT_GOALS.get(goal, {}).get("ru", goal)
    await callback.message.edit_text(
        f"✨ **{goal_name}**\n"
        f"🎯 **Фокус:** {focus_info['name']}\n\n"
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

    goal_name = WORKOUT_GOALS.get(goal, {}).get("ru", goal)
    focus_info = FOCUS_ZONES.get(focus_zone, FOCUS_ZONES["все"])

    await callback.message.edit_text(
        f"🤖 Ganina генерирует план...\n\n"
        f"📋 **{goal_name}** • {focus_info['name']}\n"
        f"💪 **Интенсивность:** {load_level}\n\n"
        f"Пожалуйста, подождите 2–3 секунды ⏳"
    )

    exercises = await generate_workout_with_gemini(goal, load_level, focus_zone)

    encoded_exercises = urllib.parse.quote(json.dumps(exercises, ensure_ascii=False))
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
            [InlineKeyboardButton(text="← Назад к выбору интенсивности", callback_data=f"back_to_intensity_{goal}_{focus_zone}")]
        ]
    )

    workout_text = "\n".join([f"{i+1}. {ex['name']}" for i, ex in enumerate(exercises)])

    await callback.message.answer(
        f"📋 **Ваш персональный план от Ganina**\n\n"
        f"**Тип:** {goal_name}\n"
        f"**Фокус:** {focus_info['name']}\n"
        f"**Интенсивность:** {load_level}\n"
        f"**Упражнения (без инвентаря):**\n{workout_text}\n\n"
        f"Нажмите кнопку ниже, чтобы запустить таймер!",
        reply_markup=keyboard
    )
    await callback.answer()

@dp.callback_query(F.data == "stats_show")
async def stats_show(callback: types.CallbackQuery):
    user_id = str(callback.from_user.id)
    stats = load_stats()

    if user_id not in stats or stats[user_id]["total_workouts"] == 0:
        await callback.message.answer("📊 У вас еще нет завершенных тренировок.\n\nСоздайте первую тренировку уже сейчас! 💪")
        await callback.answer()
        return

    user_stats = stats[user_id]
    total_workouts = user_stats["total_workouts"]
    total_calories = user_stats["total_calories"]
    total_minutes = user_stats.get("total_minutes", 0)
    week_stats = get_stats_by_period(user_id, 7)
    month_stats = get_stats_by_period(user_id, 30)
    current_streak, max_streak = calculate_streak(user_id, stats)

    text = (
        f"📊 **ПОЛНАЯ СТАТИСТИКА**\n\n"
        f"📈 **ВСЕГО:**\n"
        f"   💪 {total_workouts} тренировок\n"
        f"   🔥 {total_calories:.0f} ккал\n"
        f"   ⏱️  {total_minutes} минут\n\n"
        f"📅 **ЗА НЕДЕЛЮ:**\n"
        f"   💪 {week_stats['workouts']} тренировок\n"
        f"   🔥 {week_stats['calories']:.0f} ккал\n"
        f"   ⏱️  {week_stats['minutes']} минут\n\n"
        f"📆 **ЗА МЕСЯЦ:**\n"
        f"   💪 {month_stats['workouts']} тренировок\n"
        f"   🔥 {month_stats['calories']:.0f} ккал\n"
        f"   ⏱️  {month_stats['minutes']} минут\n\n"
        f"🔥 **STREAK:**\n"
        f"   Текущая серия: {current_streak} дней\n"
        f"   Лучший рекорд: {max_streak} дней"
    )

    await callback.message.answer(text)
    await callback.answer()

@dp.message(F.web_app_data)
async def handle_web_app_data(message: types.Message):
    try:
        data = json.loads(message.web_app_data.data)
        mode = data.get("mode", "Тренировка")
        load_level = data.get("load", "🟡 Средняя")
        focus_zone = data.get("focus", "все")
        details = data.get("details", "—")
        calories = float(data.get("calories", 0))
        weight = data.get("weight", "—")

        data["focus"] = focus_zone
        record_workout(message.from_user.id, data)

        current_streak, max_streak = calculate_streak(message.from_user.id, load_stats())

        await message.answer(
            f"🎉 **Отличная работа! Тренировка завершена!**\n\n"
            f"📌 **Режим:** {mode}\n"
            f"💪 **Уровень:** {load_level}\n"
            f"🎯 **Фокус:** {focus_zone}\n"
            f"📊 **Параметры:** {details}\n"
            f"🔥 **Сожжено калорий:** {calories:.0f} ккал *(для веса {weight} кг)*\n\n"
            f"🔥 **Streak:** {current_streak} дней подряд (Рекорд: {max_streak})\n\n"
            f"Результат записан в вашу статистику! 📈\n"
            f"Восстановитесь и выпейте воды 💧"
        )

    except Exception as e:
        print(f"Ошибка обработки результатов: {e}")
        await message.answer("❌ Ошибка при сохранении результатов. Попробуйте позже.")
@dp.callback_query(F.data == "back_to_workout_menu")
async def back_to_workout_menu(callback: types.CallbackQuery):
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🏋️ Силовая", callback_data="workout_Силовая")],
            [InlineKeyboardButton(text="🏃 Кардио / Жиросжигание", callback_data="workout_Кардио")],
            [InlineKeyboardButton(text="🧘 Растяжка", callback_data="workout_Растяжка")],
            [InlineKeyboardButton(text="🎲 Микс дня (Ganina AI)", callback_data="workout_Микс")],
        ]
    )
    
    await callback.message.edit_text(
        "Какую тренировку должна составить Ganina сегодня?",
        reply_markup=keyboard
    )
    await callback.answer()

@dp.callback_query(F.data.startswith("back_to_focus_"))
async def back_to_focus(callback: types.CallbackQuery):
    goal = callback.data.split("_")[-1]
    
    focus_keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="💪 Верх тела", callback_data=f"focus_{goal}_верх")],
            [InlineKeyboardButton(text="🦵 Ноги и ягодицы", callback_data=f"focus_{goal}_ноги")],
            [InlineKeyboardButton(text="🔥 Пресс и кор", callback_data=f"focus_{goal}_пресс")],
            [InlineKeyboardButton(text="🧘 Все тело", callback_data=f"focus_{goal}_все")],
            [InlineKeyboardButton(text="← Назад к выбору тренировки", callback_data="back_to_workout_menu")]
        ]
    )

    goal_name = WORKOUT_GOALS.get(goal, {}).get("ru", goal)
    await callback.message.edit_text(
        f"✨ Вы выбрали: **{goal_name}**\n\n"
        f"На какую зону сосредоточиться?",
        reply_markup=focus_keyboard
    )
    await callback.answer()

@dp.callback_query(F.data.startswith("back_to_intensity_"))
async def back_to_intensity(callback: types.CallbackQuery):
    parts = callback.data.split("_")
    goal = parts[3]
    focus_zone = parts[4]

    focus_info = FOCUS_ZONES.get(focus_zone, FOCUS_ZONES["все"])

    intensity_keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🟢 Лёгкая", callback_data=f"intensity_{goal}_{focus_zone}_🟢 Лёгкая")],
            [InlineKeyboardButton(text="🟡 Средняя", callback_data=f"intensity_{goal}_{focus_zone}_🟡 Средняя")],
            [InlineKeyboardButton(text="🔴 Интенсивная", callback_data=f"intensity_{goal}_{focus_zone}_🔴 Интенсивная")],
            [InlineKeyboardButton(text="← Назад к выбору фокуса", callback_data=f"back_to_focus_{goal}")]
        ]
    )

    goal_name = WORKOUT_GOALS.get(goal, {}).get("ru", goal)
    await callback.message.edit_text(
        f"✨ **{goal_name}**\n"
        f"🎯 **Фокус:** {focus_info['name']}\n\n"
        f"Выберите уровень интенсивности:",
        reply_markup=intensity_keyboard
    )
    await callback.answer()
async def main():
    print("🤖 Бот запускается...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())