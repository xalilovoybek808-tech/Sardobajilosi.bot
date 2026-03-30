# Sardoba Jilosi Bot - Klaviatura (ReplyKeyboard) versiyasi
# python-telegram-bot bilan - toza va xatosiz

import logging
import sqlite3
from datetime import datetime, timedelta
import pytz

# O'zbekiston vaqti
UZ_TZ = pytz.timezone("Asia/Tashkent")

from telegram import Update, ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters,
    ContextTypes,
)

# --------------------------------------------------
# O'ZINGIZNIKINI O'ZGARTIRING!
# --------------------------------------------------
BOT_TOKEN = "8657935059:AAE4-g3V-QQu2JCBGCYQDus_M3WPiRDN-Kk"
ADMIN_IDS = [1140333236, 5442902953]  # ← ikkinchi ID ni o'zingizniki bilan almashtiring

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

DB_FILE = "sardoba.db"

# --------------------------------------------------
# DATABASE
# --------------------------------------------------
def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()

    c.execute('''CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY,
        username TEXT,
        full_name TEXT,
        role TEXT DEFAULT 'ishchi'
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS shifts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        work_date TEXT,
        start_time TEXT,
        end_time TEXT,
        duration REAL DEFAULT 0
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS expenses (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        type TEXT,
        amount REAL,
        comment TEXT,
        created_at TEXT DEFAULT (datetime('now'))
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS settings (
        key TEXT PRIMARY KEY,
        value TEXT
    )''')

    c.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('hourly_rate', '500000')")
    c.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('total_expense', '0')")

    conn.commit()
    conn.close()


def get_role(user_id: int) -> str:
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT role FROM users WHERE user_id = ?", (user_id,))
    row = c.fetchone()
    conn.close()
    return row[0] if row else "ishchi"


def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS or get_role(user_id) in ("boshliq", "buxgalter")

# --------------------------------------------------
# MENYULAR
# --------------------------------------------------
ISHCHI_MENU = ReplyKeyboardMarkup(
    [
        [KeyboardButton("Ishni boshlash"), KeyboardButton("Ishni yakunlash")],
        [KeyboardButton("Ish kunlarim")]
    ],
    resize_keyboard=True,
    one_time_keyboard=False
)

ADMIN_MENU = ReplyKeyboardMarkup(
    [
        [KeyboardButton("Narx o'zgartirish")],
        [KeyboardButton("Chiqim kiritish")],
        [KeyboardButton("Balans ko'rish")]
    ],
    resize_keyboard=True,
    one_time_keyboard=False
)

BOSHLIQ_MENU = ReplyKeyboardMarkup(
    [
        [KeyboardButton("Ishchilar"), KeyboardButton("Narx o'zgartirish")],
        [KeyboardButton("Chiqim kiritish"), KeyboardButton("Balans ko'rish")]
    ],
    resize_keyboard=True,
    one_time_keyboard=False
)

CHIQIM_MENU = ReplyKeyboardMarkup(
    [
        [KeyboardButton("Boshqa chiqim"), KeyboardButton("Zapchast")],
        [KeyboardButton("Chiqimlar ro'yxati"), KeyboardButton("Orqaga")]
    ],
    resize_keyboard=True,
    one_time_keyboard=False
)

BALANS_MENU = ReplyKeyboardMarkup(
    [
        [KeyboardButton("Balans"), KeyboardButton("ishni 0 qilish")],
        [KeyboardButton("Orqaga")]
    ],
    resize_keyboard=True,
    one_time_keyboard=False
)

# --------------------------------------------------
# START
# --------------------------------------------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    uid = user.id

    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute(
        "INSERT OR IGNORE INTO users (user_id, username, full_name) VALUES (?, ?, ?)",
        (uid, user.username or "", user.full_name or "")
    )

    # ADMIN_IDS dagi foydalanuvchi boshliq bo'ladi
    if uid in ADMIN_IDS:
        c.execute("UPDATE users SET role = 'boshliq' WHERE user_id = ?", (uid,))
    elif get_role(uid) == 'inactive':
        c.execute("UPDATE users SET role = 'ishchi' WHERE user_id = ?", (uid,))
    
    conn.commit()
    conn.close()

    role = get_role(uid)

    if role == "ishchi":
        await update.message.reply_text(
            f"Assalomu alaykum, {user.full_name}!",
            reply_markup=ISHCHI_MENU
        )
    elif role == "inactive":
        await update.message.reply_text("Siz faol ishchi emassiz.")
    elif role == "boshliq":
        await update.message.reply_text(
            f"Xush kelibsiz, Boshliq {user.full_name}!",
            reply_markup=BOSHLIQ_MENU
        )
    else:
        await update.message.reply_text(
            f"Xush kelibsiz, {role.upper()} {user.full_name}!",
            reply_markup=ADMIN_MENU
        )

# --------------------------------------------------
# SHOW EXPENSES
# --------------------------------------------------
async def show_expenses(update: Update, context: ContextTypes.DEFAULT_TYPE):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT type, amount, created_at FROM expenses ORDER BY id DESC LIMIT 20")
    rows = c.fetchall()
    conn.close()

    if not rows:
        text = "Chiqimlar hali yo'q."
    else:
        text = "Oxirgi chiqimlar:\n\n"
        for r in rows:
            text += f"{r[2]} | {r[0]} | {r[1]:,.0f} so'm\n"

    await update.message.reply_text(text, reply_markup=CHIQIM_MENU)

# --------------------------------------------------
# HANDLE MESSAGE
# --------------------------------------------------
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    text_lower = text.lower()
    uid = update.effective_user.id
    role = get_role(uid)

    awaiting = context.user_data.get("awaiting")

    # Ishchi xatti-harakatlari
    if role == "ishchi":
        if text == "Ishni boshlash":
            await clock_in(update, context)
            return
        elif text == "Ishni yakunlash":
            await clock_out(update, context)
            return
        elif text == "Ish kunlarim":
            await my_days(update, context)
            return

    # Orqaga tugmasi
    if text == "Orqaga":
        context.user_data.clear()
        reply_markup = BOSHLIQ_MENU if role == "boshliq" else ADMIN_MENU
        await update.message.reply_text("Bosh menyuga qaytdingiz.", reply_markup=reply_markup)
        return

    # Admin / Boshliq xatti-harakatlari
    if is_admin(uid):
        if text == "Narx o'zgartirish":
            context.user_data["awaiting"] = "set_rate"
            await update.message.reply_text("Yangi soatlik narxni yozing (masalan: 600000)", reply_markup=ReplyKeyboardRemove())
            return
        elif text == "Chiqim kiritish":
            await update.message.reply_text("Chiqim turini tanlang:", reply_markup=CHIQIM_MENU)
            return
        elif text == "Chiqimlar ro'yxati":
            await show_expenses(update, context)
            return
        elif text in ["Zapchast", "Oylik", "Boshqa chiqim"]:
            context.user_data["exp_type"] = text
            context.user_data["awaiting"] = "exp_amount"
            await update.message.reply_text(f"{text} summasini yozing (masalan: 1500000)", reply_markup=ReplyKeyboardRemove())
            return
        elif text == "Balans ko'rish":
            await update.message.reply_text("Balans menyusi:", reply_markup=BALANS_MENU)
            return
        elif text == "Balans":
            await show_balance(update, context)
            return
        elif text_lower == "ishni 0 qilish" and role == "boshliq":
            conn = sqlite3.connect(DB_FILE)
            c = conn.cursor()
            c.execute("UPDATE shifts SET duration = 0")
            c.execute("UPDATE settings SET value = '0' WHERE key = 'total_expense'")
            conn.commit()
            conn.close()
            await update.message.reply_text("Kirim, chiqim va ishlagan soat 0 ga qaytarildi.", reply_markup=BOSHLIQ_MENU)
            return

    # Foydalanuvchi kiritayotgan holatlarni tekshirish
    if awaiting == "set_rate":
        try:
            rate = int(text.replace(" ", "").replace(",", ""))
            conn = sqlite3.connect(DB_FILE)
            c = conn.cursor()
            c.execute("UPDATE settings SET value = ? WHERE key = 'hourly_rate'", (rate,))
            conn.commit()
            conn.close()
            reply_markup = BOSHLIQ_MENU if role == "boshliq" else ADMIN_MENU
            await update.message.reply_text(f"Soatlik narx yangilandi: {rate:,} so'm", reply_markup=reply_markup)
        except ValueError:
            await update.message.reply_text("Faqat raqam kiriting.")
        context.user_data.clear()
        return

    if awaiting == "exp_amount":
        try:
            amount = float(text.replace(" ", "").replace(",", ""))
            exp_type = context.user_data.get("exp_type", "NoType")
            conn = sqlite3.connect(DB_FILE)
            c = conn.cursor()
            c.execute("INSERT INTO expenses (type, amount) VALUES (?, ?)", (exp_type, amount))
            c.execute("SELECT value FROM settings WHERE key = 'total_expense'")
            current = float(c.fetchone()[0])
            new_total = current + amount
            c.execute("UPDATE settings SET value = ? WHERE key = 'total_expense'", (new_total,))
            conn.commit()
            conn.close()
            reply_markup = BOSHLIQ_MENU if role == "boshliq" else ADMIN_MENU
            await update.message.reply_text(f"Saqlandi!\n{exp_type}: {amount:,.0f} so'm\nJami chiqim: {new_total:,.0f} so'm", reply_markup=reply_markup)
        except ValueError:
            await update.message.reply_text("Faqat raqam kiriting.")
        context.user_data.clear()
        return

# --------------------------------------------------
# CALLBACK HANDLER
# --------------------------------------------------
async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    uid = query.from_user.id
    role = get_role(uid)

    if data.startswith("worker_") and role == "boshliq":
        worker_id = int(data.split("_")[1])
        context.user_data["selected_worker"] = worker_id
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.execute("SELECT full_name FROM users WHERE user_id = ?", (worker_id,))
        name = c.fetchone()[0]
        conn.close()
        keyboard = [
            [InlineKeyboardButton("Oylik to'lash", callback_data=f"pay_{worker_id}")],
            [InlineKeyboardButton("Ish kunlarim", callback_data=f"days_{worker_id}")],
            [InlineKeyboardButton("Ishchini o'chirish", callback_data=f"remove_{worker_id}")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(f"Ishchi: {name}\nTanlang:", reply_markup=reply_markup)

# --------------------------------------------------
# Clock Functions
# --------------------------------------------------
async def clock_in(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    today = datetime.now(UZ_TZ).strftime("%Y-%m-%d")
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT id FROM shifts WHERE user_id = ? AND work_date = ? AND end_time IS NULL", (uid, today))
    if c.fetchone():
        await update.message.reply_text("Bugun allaqachon boshlagansiz!")
    else:
        now = datetime.now(UZ_TZ).strftime("%H:%M:%S")
        c.execute("INSERT INTO shifts (user_id, work_date, start_time) VALUES (?, ?, ?)", (uid, today, now))
        await update.message.reply_text(f"Ish boshlandi: {now}")
    conn.commit()
    conn.close()


async def clock_out(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT id, work_date, start_time FROM shifts WHERE user_id = ? AND work_date = ? AND end_time IS NULL", (uid, datetime.now(UZ_TZ).strftime("%Y-%m-%d")))
    row = c.fetchone()
    if not row:
        await update.message.reply_text("Bugun ish boshlamagansiz.")
    else:
        sid, work_date, st = row
        start = UZ_TZ.localize(datetime.strptime(f"{work_date} {st}", "%Y-%m-%d %H:%M:%S"))
        end = datetime.now(UZ_TZ)
        dur = (end - start).total_seconds() / 3600
        et = end.strftime("%H:%M:%S")
        c.execute("UPDATE shifts SET end_time = ?, duration = ? WHERE id = ?", (et, dur, sid))
        await update.message.reply_text(f"Yakunlandi!\nBoshlanish: {st}\nTugash: {et}\nJami: {dur:.2f} soat")
    conn.commit()
    conn.close()

# --------------------------------------------------
# My Days
# --------------------------------------------------
async def my_days(update: Update, context: ContextTypes.DEFAULT_TYPE, worker_id=None):
    if worker_id is None:
        worker_id = update.effective_user.id
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT work_date, start_time, end_time, duration FROM shifts WHERE user_id = ? ORDER BY work_date DESC LIMIT 30", (worker_id,))
    rows = c.fetchall()
    conn.close()
    if not rows:
        text = "Hali ish kuni yo'q."
    else:
        text = "Oxirgi kunlar:\n\n"
        total = 0
        for r in rows:
            dur = r[3] or 0
            total += dur
            et = r[2] or "ochik"
            text += f"{r[0]} | {r[1]} - {et} | {dur:.2f} soat\n"
        text += f"\nJami: {total:.2f} soat"
    await update.message.reply_text(text)

# --------------------------------------------------
# Show Balance
# --------------------------------------------------
async def show_balance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT value FROM settings WHERE key = 'hourly_rate'")
    rate = float(c.fetchone()[0])
    c.execute("SELECT SUM(duration) FROM shifts")
    hours = c.fetchone()[0] or 0
    c.execute("SELECT value FROM settings WHERE key = 'total_expense'")
    exp = float(c.fetchone()[0])
    bal = hours * rate - exp
    text = (
        f"Balans:\n"
        f"Soatlik narx: {rate:,.0f} so'm\n"
        f"Jami soat: {hours:.2f}\n"
        f"Chiqim: {exp:,.0f} so'm\n"
        f"Qoldiq: {bal:,.0f} so'm"
    )
    await update.message.reply_text(text)
    conn.close()

# --------------------------------------------------
# MAIN
# --------------------------------------------------
def main():
    init_db()
    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_handler(CallbackQueryHandler(handle_callback))

    print("Bot ishga tushdi...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
