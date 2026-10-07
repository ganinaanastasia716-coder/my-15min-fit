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
WEB_APP_BASE_URL = os.getenv("WEB_APP_BASE_URL", "").strip().rstrip("/")
if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN must be set in .env")
if not WEB_APP_BASE_URL:
    raise ValueError("WEB_APP_BASE_URL must be set to the HTTPS URL containing index.html")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# ---------------- EXERCISE DATABASE ----------------
EXERCISES_DATABASE = {
 "Силовая":{
  "верх":["Отжимания классические","Отжимания с широкой постановкой","Обратные отжимания от стула","Планка с касанием плеч","Динамическая планка","Медленные отжимания","Отжимания в пайке"],
  "ноги":["Приседания","Выпады назад","Боковые выпады","Болгарские сплит-приседания","Ягодичный мостик","Приседания сумо","Стульчик у стены"],
  "пресс":["Скручивания","Велосипед","Обратные скручивания","Планка","Книжка","Боковая планка","Подъемы ног"],
  "все":["Приседания","Отжимания","Выпады","Ягодичный мостик","Планка","Супермен","Русский твист"]
 },
 "Кардио":{
  "верх":["Боксерские удары","Plank Jacks","Бег в планке","Взрывные отжимания","Переходы в планке"],
  "ноги":["Выпады с прыжком","Приседания с выпрыгиванием","Высокие колени","Захлест голени","Прыжки конькобежца","Jumping Jack"],
  "пресс":["Горный альпинист","Динамический русский твист","Планка со скручиванием","Велосипед в быстром темпе","Альпинист по диагонали"],
  "все":["Бёрпи","Jumping Jack","Горный альпинист","Бег на месте","Прыжки конькобежца","Планка с выпрыгиванием"]
 },
 "Растяжка":{
  "верх":["Растяжка плеч поперек груди","Растяжка трицепса","Замок рук за спиной","Растяжка грудных у стены","Растяжка предплечий"],
  "ноги":["Складка","Глубокий выпад","Бабочка","Растяжка задней поверхности бедра","Поза голубя","Полушпагат","Растяжка квадрицепса"],
  "пресс":["Кобра","Кошка-корова","Боковое вытягивание корпуса","Скручивание лежа","Поза ребенка","Сфинкс"],
  "все":["Поза ребенка","Складка","Собака мордой вниз","Бабочка","Кобра","Поза голубя"]
 }
}
EXERCISES_DATABASE["Микс"]={z:EXERCISES_DATABASE["Силовая"][z]+EXERCISES_DATABASE["Кардио"][z] for z in ("верх","ноги","пресс","все")}

LOAD_LEVELS={
 "light":{"label":"🟢 Лёгкая","met":3.5,"work":20,"rest":10,"rounds":6},
 "medium":{"label":"🟡 Средняя","met":6.0,"work":30,"rest":15,"rounds":8},
 "high":{"label":"🔴 Интенсивная","met":8.5,"work":40,"rest":20,"rounds":10},
}
FOCUS={"верх":"Верх тела","ноги":"Ноги и ягодицы","пресс":"Пресс и кор","все":"Все тело"}

# Authentic CrossFit movement library. Reps change with intensity.
CROSSFIT={
 "low":[
  ("Goblet Squat",8),("Push-up",6),("Box Step-up",8),("Single-under",20),("Dumbbell Deadlift",8),
  ("Kettlebell Swing",8),("Walking Lunge",8),("Burpee",4),("Row",10)
 ],
 "medium":[
  ("Thruster",10),("Push-up",10),("Box Jump",8),("Double-under",20),("Dumbbell Snatch",8),
  ("Kettlebell Swing",12),("Burpee",8),("Toes-to-Bar",8),("Row",12),("Air Squat",15)
 ],
 "high":[
  ("Thruster",15),("Chest-to-Bar Pull-up",8),("Box Jump-over",10),("Double-under",30),("Power Clean",8),
  ("Kettlebell Snatch",10),("Burpee Box Jump-over",8),("Toes-to-Bar",12),("Handstand Push-up",8),("Run",15)
 ]}

# ---------------- SQLITE ----------------
BASE_DIR=os.path.dirname(os.path.abspath(__file__))
JSON_FILE=os.path.join(BASE_DIR,"workout_stats.json")
DB_FILE=os.getenv("STATS_DB_FILE","").strip() or ("/data/workout_stats.db" if os.path.isdir("/data") else os.path.join(BASE_DIR,"workout_stats.db"))

def db():
    os.makedirs(os.path.dirname(DB_FILE) or ".",exist_ok=True)
    c=sqlite3.connect(DB_FILE,timeout=30);c.row_factory=sqlite3.Row
    c.execute("PRAGMA journal_mode=WAL");c.execute("PRAGMA busy_timeout=30000");return c

def init_db():
    with db() as c:c.execute("CREATE TABLE IF NOT EXISTS stats(user_id TEXT PRIMARY KEY,data TEXT NOT NULL)")

def import_old():
    init_db()
    with db() as c:
        if c.execute("SELECT COUNT(*) FROM stats").fetchone()[0]:return
    if not os.path.exists(JSON_FILE):return
    try:
        old=json.load(open(JSON_FILE,encoding="utf-8"))
        if isinstance(old,dict) and old:
            with db() as c:
                for uid,data in old.items():c.execute("INSERT OR REPLACE INTO stats VALUES(?,?)",(str(uid),json.dumps(data,ensure_ascii=False)))
    except Exception as e:print("Import warning:",e)
init_db();import_old();print("SQLite:",DB_FILE)

def load_stats():
    with db() as c:rows=c.execute("SELECT user_id,data FROM stats").fetchall()
    out={}
    for r in rows:
        try:out[str(r["user_id"])]=json.loads(r["data"])
        except:out[str(r["user_id"])]={}
    return out

def save_stats(stats):
    with db() as c:
        for uid,data in stats.items():
            c.execute("INSERT INTO stats VALUES(?,?) ON CONFLICT(user_id) DO UPDATE SET data=excluded.data",(str(uid),json.dumps(data,ensure_ascii=False)))
        c.commit()

def num(v,default=0):
    try:return float(v)
    except:return default

def duration(data):
    if num(data.get("duration_seconds"),-1)>=0:return int(num(data.get("duration_seconds")))
    if num(data.get("minutes"),-1)>=0:return int(num(data.get("minutes"))*60)
    return 0

def record(uid,data):
    stats=load_stats();uid=str(uid);now=datetime.now().isoformat()
    u=stats.setdefault(uid,{"total_workouts":0,"total_calories":0.0,"total_minutes":0,"workouts":[],"last_workout_at":None,"reminders_sent":[]})
    sec=duration(data);cal=num(data.get("calories"));mins=round(sec/60,2)
    w={"timestamp":now,"workout_type":data.get("workout_type") or data.get("mode") or "Тренировка",
       "mode":data.get("mode",""),"workout_format":data.get("workout_format",""),"load":data.get("load",""),
       "focus":data.get("focus",""),"details":data.get("details",""),"exercises":data.get("exercises",[]),
       "calories":cal,"duration_seconds":sec,"minutes":mins,"weight":data.get("weight",""),
       "rounds_completed":data.get("rounds_completed",0),"total_rounds":data.get("total_rounds",0),
       "round_times":data.get("round_times",[]),"work_time":data.get("work_time",0),"rest_time":data.get("rest_time",0)}
    u["total_workouts"]=u.get("total_workouts",0)+1;u["total_calories"]=u.get("total_calories",0)+cal
    u["total_minutes"]=u.get("total_minutes",0)+mins;u["last_workout_at"]=now;u["reminders_sent"]=[];u.setdefault("workouts",[]).append(w)
    save_stats(stats);return w

def register(user):
    s=load_stats();uid=str(user.id)
    u=s.setdefault(uid,{"total_workouts":0,"total_calories":0.0,"total_minutes":0,"workouts":[],"last_workout_at":None,"reminders_sent":[]})
    u["first_name"]=user.first_name or "";u["username"]=user.username or "";save_stats(s)

def streak(uid,stats=None):
    stats=stats or load_stats();w=stats.get(str(uid),{}).get("workouts",[])
    dates=sorted(set(datetime.fromisoformat(x["timestamp"]).date() for x in w if x.get("timestamp")))
    if not dates:return 0,0
    best=run=1
    for i in range(1,len(dates)):
        run=run+1 if (dates[i]-dates[i-1]).days==1 else 1;best=max(best,run)
    cur=1;d=dates[-1]
    if (datetime.now().date()-d).days>1:cur=0
    else:
        for x in reversed(dates[:-1]):
            if (d-x).days==1:cur+=1;d=x
            else:break
    return cur,best

# ---------------- KEYBOARDS ----------------
def main_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
      [InlineKeyboardButton(text="🏋️ Силовая",callback_data="workout_Силовая")],
      [InlineKeyboardButton(text="🏃 Кардио / Жиросжигание",callback_data="workout_Кардио")],
      [InlineKeyboardButton(text="🧘 Растяжка",callback_data="workout_Растяжка")],
      [InlineKeyboardButton(text="🎲 Микс дня",callback_data="workout_Микс")],
      [InlineKeyboardButton(text="🏋️ CrossFit",callback_data="crossfit_menu")],
      [InlineKeyboardButton(text="📊 Моя статистика",callback_data="stats_show")]])

def url(params):
    return WEB_APP_BASE_URL+"?"+urllib.parse.urlencode(params)

# ---------------- NORMAL WORKOUT FLOW ----------------
@dp.callback_query(F.data.startswith("workout_"))
async def workout_type(c):
    goal=c.data.split("_",1)[1]
    kb=InlineKeyboardMarkup(inline_keyboard=[
      [InlineKeyboardButton(text="💪 Верх тела",callback_data=f"focus_{goal}_верх")],
      [InlineKeyboardButton(text="🦵 Ноги и ягодицы",callback_data=f"focus_{goal}_ноги")],
      [InlineKeyboardButton(text="🔥 Пресс и кор",callback_data=f"focus_{goal}_пресс")],
      [InlineKeyboardButton(text="🧘 Все тело",callback_data=f"focus_{goal}_все")],
      [InlineKeyboardButton(text="← Назад",callback_data="back_menu")]])
    await c.message.edit_text(f"✨ **{goal}**\n\nНа какую зону сосредоточиться?",reply_markup=kb);await c.answer()

@dp.callback_query(F.data.startswith("focus_"))
async def focus(c):
    _,goal,zone=c.data.split("_",2)
    kb=InlineKeyboardMarkup(inline_keyboard=[
      [InlineKeyboardButton(text="🟢 Лёгкая",callback_data=f"intensity_{goal}_{zone}_light")],
      [InlineKeyboardButton(text="🟡 Средняя",callback_data=f"intensity_{goal}_{zone}_medium")],
      [InlineKeyboardButton(text="🔴 Интенсивная",callback_data=f"intensity_{goal}_{zone}_high")],
      [InlineKeyboardButton(text="← Назад",callback_data=f"back_focus_{goal}")]])
    await c.message.edit_text(f"🎯 **{FOCUS.get(zone,zone)}**\n\nВыберите интенсивность:",reply_markup=kb);await c.answer()

@dp.callback_query(F.data.startswith("intensity_"))
async def intensity(c):
    await c.answer()
    try:
        _,goal,zone,level=c.data.split("_",3);info=LOAD_LEVELS.get(level,LOAD_LEVELS["medium"])
        pool=EXERCISES_DATABASE.get(goal,EXERCISES_DATABASE["Микс"]).get(zone,EXERCISES_DATABASE["Микс"]["все"])
        ex=[{"name":x} for x in random.sample(pool,min(5,len(pool)))]
        params={"workout":json.dumps(ex,ensure_ascii=False),"workout_type":goal,"format":"intervals","load":info["label"],
                "focus":zone,"work_time":info["work"],"rest_time":info["rest"],"rounds":info["rounds"],"met":info["met"]}
        text="\n".join(f"{i+1}. {x['name']}" for i,x in enumerate(ex))
        kb=InlineKeyboardMarkup(inline_keyboard=[
          [InlineKeyboardButton(text="🚀 Открыть тренировку",web_app=WebAppInfo(url=url(params)))],
          [InlineKeyboardButton(text="📊 Статистика",callback_data="stats_show")],
          [InlineKeyboardButton(text="← Назад",callback_data=f"back_focus_{goal}")]])
        await c.message.answer(f"📋 **План тренировки**\n\n**Тип:** {goal}\n**Фокус:** {FOCUS.get(zone,zone)}\n**Интенсивность:** {info['label']}\n\n{text}\n\nТаймер откроется уже с этим планом.",reply_markup=kb)
    except Exception as e:
        print("Workout generation error:",repr(e))
        await c.message.answer("❌ Не удалось сформировать тренировку. Попробуй ещё раз.",reply_markup=main_kb())

# ---------------- CROSSFIT: INTENSITY -> FORMAT -> ONE TIMER ----------------
@dp.callback_query(F.data=="crossfit_menu")
async def cf_menu(c):
    kb=InlineKeyboardMarkup(inline_keyboard=[
      [InlineKeyboardButton(text="🟢 Лёгкая",callback_data="cfintensity_low")],
      [InlineKeyboardButton(text="🟡 Средняя",callback_data="cfintensity_medium")],
      [InlineKeyboardButton(text="🔴 Высокая",callback_data="cfintensity_high")],
      [InlineKeyboardButton(text="← Назад",callback_data="back_menu")]])
    await c.message.edit_text("🏋️ **CROSSFIT**\n\nСначала выбери реальную интенсивность WOD:",reply_markup=kb);await c.answer()

@dp.callback_query(F.data.startswith("cfintensity_"))
async def cf_intensity(c):
    level=c.data.split("_",1)[1]
    labels={"low":"🟢 Лёгкая","medium":"🟡 Средняя","high":"🔴 Высокая"}
    kb=InlineKeyboardMarkup(inline_keyboard=[
      [InlineKeyboardButton(text="⏱ EMOM",callback_data=f"cfformat_{level}_emom")],
      [InlineKeyboardButton(text="🔥 AMRAP",callback_data=f"cfformat_{level}_amrap")],
      [InlineKeyboardButton(text="🏁 RFT / Раунды",callback_data=f"cfformat_{level}_rft")],
      [InlineKeyboardButton(text="← Назад",callback_data="crossfit_menu")]])
    await c.message.edit_text(f"🏋️ CrossFit • **{labels[level]}**\n\nВыбери формат:",reply_markup=kb);await c.answer()

@dp.callback_query(F.data.startswith("cfformat_"))
async def cf_format(c):
    await c.answer()
    try:
        _,level,fmt=c.data.split("_",2)
        labels={"low":"🟢 Лёгкая","medium":"🟡 Средняя","high":"🔴 Высокая"}
        # Difficulty controls movement choice and reps.
        pool=CROSSFIT[level][:]
        random.shuffle(pool)
        count=4 if level=="low" else 5
        selected=pool[:count]
        exercises=[{"name":name,"reps":reps} for name,reps in selected]
        if fmt=="emom":
            rounds={"low":6,"medium":8,"high":10}[level];work=45;rest=15;duration=rounds
        elif fmt=="amrap":
            duration={"low":8,"medium":12,"high":15}[level];rounds=0;work=0;rest=0
        else:
            rounds={"low":3,"medium":4,"high":5}[level];duration=0;work=0;rest=0
        params={"workout":json.dumps(exercises,ensure_ascii=False),"workout_type":"CrossFit","format":fmt,
                "mode":fmt,"load":labels[level],"intensity":labels[level],"focus":"все","rounds":rounds,
                "duration":duration,"work_time":work,"rest_time":rest,"met":{"low":5.5,"medium":8,"high":11}[level],"cf_level":level}
        if fmt=="emom":desc=f"EMOM {rounds} минут • 1 движение каждую минуту"
        elif fmt=="amrap":desc=f"AMRAP {duration} минут • максимум раундов"
        else:desc=f"RFT • {rounds} раундов на время"
        plan="\n".join(f"{i+1}. {x['name']} — {x['reps']} повтор." for i,x in enumerate(exercises))
        kb=InlineKeyboardMarkup(inline_keyboard=[
          [InlineKeyboardButton(text="🚀 Открыть единый таймер",web_app=WebAppInfo(url=url(params)))],
          [InlineKeyboardButton(text="← Другой формат",callback_data=f"cfintensity_{level}")],
          [InlineKeyboardButton(text="🏠 Главное меню",callback_data="back_menu")]])
        await c.message.answer(f"🏋️ **CrossFit WOD**\n\n**Интенсивность:** {labels[level]}\n**Формат:** {desc}\n\n**Движения:**\n{plan}\n\nВсе это откроется в том же FIT15 таймере — без второго приложения.",reply_markup=kb)
    except Exception as e:
        print("CrossFit WOD generation error:",repr(e))
        await c.message.answer("❌ Не удалось сформировать CrossFit WOD. Попробуй ещё раз.",reply_markup=main_kb())

# ---------------- STATS / START ----------------
@dp.message(CommandStart())
async def start(m:types.Message):
    register(m.from_user);await m.answer(f"Привет, {m.from_user.first_name}! 👋\n\nКакую тренировку сделаем сегодня?",reply_markup=main_kb())

@dp.message(Command("stats"))
async def stats_cmd(m:types.Message):await show_stats(m.from_user.id,m)

async def show_stats(uid,ctx):
    s=load_stats().get(str(uid),{})
    total=int(s.get("total_workouts",0))
    if not total:text="📊 **Тренировок пока нет.**\n\nСоздай первую тренировку! 💪"
    else:
        cur,best=streak(uid)
        text=f"📊 **СТАТИСТИКА**\n\n💪 Тренировок: {total}\n🔥 Калории: {float(s.get('total_calories',0)):.0f} ккал\n⏱️ Время: {float(s.get('total_minutes',0)):.0f} мин\n🔥 Текущая серия: {cur} дней\n🏆 Рекорд: {best} дней"
    kb=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🏠 Новая тренировка",callback_data="back_menu")],[InlineKeyboardButton(text="🏋️ CrossFit",callback_data="crossfit_menu")]])
    if isinstance(ctx,types.CallbackQuery):await ctx.message.answer(text,reply_markup=kb)
    else:await ctx.answer(text,reply_markup=kb)

@dp.callback_query(F.data=="stats_show")
async def stats_cb(c):await show_stats(c.from_user.id,c);await c.answer()

@dp.callback_query(F.data=="back_menu")
async def back_menu(c):await c.message.edit_text("Какую тренировку сделаем сегодня?",reply_markup=main_kb());await c.answer()

@dp.callback_query(F.data.startswith("back_focus_"))
async def back_focus(c):
    goal=c.data.split("_",2)[2]
    kb=InlineKeyboardMarkup(inline_keyboard=[
      [InlineKeyboardButton(text="💪 Верх тела",callback_data=f"focus_{goal}_верх")],
      [InlineKeyboardButton(text="🦵 Ноги и ягодицы",callback_data=f"focus_{goal}_ноги")],
      [InlineKeyboardButton(text="🔥 Пресс и кор",callback_data=f"focus_{goal}_пресс")],
      [InlineKeyboardButton(text="🧘 Все тело",callback_data=f"focus_{goal}_все")],
      [InlineKeyboardButton(text="← Назад",callback_data="back_menu")]])
    await c.message.edit_text("На какую зону сосредоточиться?",reply_markup=kb);await c.answer()

# ---------------- WEB APP RESULT ----------------
@dp.message(F.web_app_data)
async def web_data(m:types.Message):
    try:
        data=json.loads(m.web_app_data.data)
        rec=record(m.from_user.id,data);cur,best=streak(m.from_user.id)
        sec=int(rec["duration_seconds"]);mm,ss=divmod(sec,60)
        fmt=data.get("workout_format","")
        extra=f"\n🔁 **Раунды:** {rec.get('rounds_completed',0)} / {rec.get('total_rounds',0)}" if fmt in ("emom","rft","intervals") else ""
        await m.answer(f"🎉 **Тренировка завершена!**\n\n🏋️ **Тип:** {rec['workout_type']}\n⚡ **Интенсивность:** {rec['load'] or '—'}\n🎯 **Фокус:** {rec['focus'] or '—'}\n📋 **Формат:** {fmt.upper() or '—'}\n⏱️ **Время:** {mm} мин {ss:02d} сек\n🔥 **Сожжено:** {rec['calories']:.0f} ккал{extra}\n\n🔥 Серия: {cur} дней подряд • рекорд {best}",reply_markup=main_kb())
    except Exception as e:
        print("WebApp save error:",e)
        await m.answer("❌ Не удалось сохранить результат.",reply_markup=main_kb())

# ---------------- REMINDERS ----------------
REMINDER_DAYS=(3,7,14,30)
async def reminder_loop():
    while True:
        try:
            stats=load_stats();changed=False;now=datetime.now()
            for uid,u in stats.items():
                last=u.get("last_workout_at")
                if not last:continue
                try:days=(now-datetime.fromisoformat(last)).days
                except:continue
                sent=set(u.get("reminders_sent",[]))
                reached=[d for d in REMINDER_DAYS if days>=d and d not in sent]
                if reached:
                    d=max(reached);name=u.get("first_name","")
                    text=f"👋 {name}, уже {d} дней без тренировки.\n\nВернёмся в ритм? 💪"
                    try:
                        await bot.send_message(int(uid),text,reply_markup=main_kb());u.setdefault("reminders_sent",[]).extend(reached);changed=True
                    except Exception as e:print("Reminder:",e)
            if changed:save_stats(stats)
        except Exception as e:print("Reminder loop:",e)
        await asyncio.sleep(3600)

async def main():
    print("🤖 Ganina Fit bot started")
    task=asyncio.create_task(reminder_loop())
    try:await dp.start_polling(bot)
    finally:
        task.cancel()
        await bot.session.close()

if __name__=="__main__":asyncio.run(main())
