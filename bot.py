# Sardoba Jilosi Bot - toza va ishlaydigan versiya

import logging
import sqlite3
from datetime import datetime, timedelta
import pytz

from telegram import (
    Update, ReplyKeyboardMarkup, KeyboardButton,
    ReplyKeyboardRemove, InlineKeyboardMarkup, InlineKeyboardButton
)

from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    CallbackQueryHandler, filters, ContextTypes
)

UZ_TZ = pytz.timezone("Asia/Tashkent")

BOT_TOKEN = "TOKENNI_BU_YERGA_QOYING"
ADMIN_IDS = [1140333236, 5442902953]

logging.basicConfig(level=logging.INFO)

DB_FILE = "sardoba.db"


# ---------------- DATABASE ----------------

def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()

    c.execute("""
    CREATE TABLE IF NOT EXISTS users(
        user_id INTEGER PRIMARY KEY,
        username TEXT,
        full_name TEXT,
        role TEXT DEFAULT 'ishchi'
    )
    """)

    c.execute("""
    CREATE TABLE IF NOT EXISTS shifts(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        work_date TEXT,
        start_time TEXT,
        end_time TEXT,
        duration REAL DEFAULT 0
    )
    """)

    c.execute("""
    CREATE TABLE IF NOT EXISTS expenses(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        type TEXT,
        amount REAL,
        comment TEXT,
        created_at TEXT DEFAULT(datetime('now'))
    )
    """)

    c.execute("""
    CREATE TABLE IF NOT EXISTS settings(
        key TEXT PRIMARY KEY,
        value TEXT
    )
    """)

    c.execute("INSERT OR IGNORE INTO settings VALUES('hourly_rate','500000')")
    c.execute("INSERT OR IGNORE INTO settings VALUES('total_expense','0')")

    conn.commit()
    conn.close()


def get_role(uid):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT role FROM users WHERE user_id=?", (uid,))
    r = c.fetchone()
    conn.close()
    return r[0] if r else "ishchi"


def is_admin(uid):
    return uid in ADMIN_IDS or get_role(uid) in ("boshliq", "buxgalter")


# ---------------- MENUS ----------------

ISHCHI_MENU = ReplyKeyboardMarkup(
    [
        ["Ishni boshlash", "Ishni yakunlash"],
        ["Ish kunlarim"]
    ],
    resize_keyboard=True
)

ADMIN_MENU = ReplyKeyboardMarkup(
    [
        ["Narx o'zgartirish"],
        ["Chiqim kiritish"],
        ["Balans ko'rish"]
    ],
    resize_keyboard=True
)

BOSHLIQ_MENU = ReplyKeyboardMarkup(
    [
        ["Ishchilar", "Narx o'zgartirish"],
        ["Chiqim kiritish", "Balans ko'rish"]
    ],
    resize_keyboard=True
)

CHIQIM_MENU = ReplyKeyboardMarkup(
    [
        ["Boshqa chiqim", "Zapchast"],
        ["Chiqimlar ro'yxati", "Orqaga"]
    ],
    resize_keyboard=True
)

BALANS_MENU = ReplyKeyboardMarkup(
    [
        ["Balans", "ishni 0 qilish"],
        ["Orqaga"]
    ],
    resize_keyboard=True
)


# ---------------- START ----------------

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):

    user = update.effective_user
    uid = user.id

    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()

    c.execute(
        "INSERT OR IGNORE INTO users VALUES(?,?,?,?)",
        (uid, user.username, user.full_name, "ishchi")
    )

    if uid in ADMIN_IDS:
        c.execute("UPDATE users SET role='boshliq' WHERE user_id=?", (uid,))

    conn.commit()
    conn.close()

    role = get_role(uid)

    if role == "ishchi":
        await update.message.reply_text("Xush kelibsiz!", reply_markup=ISHCHI_MENU)

    elif role == "boshliq":
        await update.message.reply_text("Boshliq paneli", reply_markup=BOSHLIQ_MENU)

    else:
        await update.message.reply_text("Admin paneli", reply_markup=ADMIN_MENU)


# ---------------- EXPENSE LIST ----------------

async def show_expenses(update: Update, context: ContextTypes.DEFAULT_TYPE):

    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()

    c.execute("SELECT type,amount,comment,created_at FROM expenses ORDER BY id DESC LIMIT 20")
    rows = c.fetchall()

    conn.close()

    if not rows:
        text = "Chiqimlar yo'q"
    else:
        text = "Oxirgi chiqimlar:\n\n"
        for r in rows:
            name = r[2] if r[2] else ""
            text += f"{r[3]} | {r[0]} | {name} | {r[1]:,.0f} so'm\n"

    await update.message.reply_text(text, reply_markup=CHIQIM_MENU)


# ---------------- BALANCE ----------------

async def show_balance(update: Update, context: ContextTypes.DEFAULT_TYPE):

    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()

    c.execute("SELECT value FROM settings WHERE key='hourly_rate'")
    rate = float(c.fetchone()[0])

    c.execute("SELECT SUM(duration) FROM shifts")
    hours = c.fetchone()[0] or 0

    c.execute("SELECT value FROM settings WHERE key='total_expense'")
    exp = float(c.fetchone()[0])

    income = hours * rate
    bal = income - exp

    conn.close()

    text = (
        f"Soatlik narx: {rate:,.0f}\n"
        f"Jami soat: {hours:.2f}\n"
        f"Kirim: {income:,.0f}\n"
        f"Chiqim: {exp:,.0f}\n"
        f"Qoldiq: {bal:,.0f}"
    )

    await update.message.reply_text(text)


# ---------------- HANDLE MESSAGE ----------------

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):

    text = update.message.text
    uid = update.effective_user.id
    role = get_role(uid)

    if text == "Orqaga":
        context.user_data.clear()
        await update.message.reply_text("Bosh menu", reply_markup=BOSHLIQ_MENU)
        return

    if text == "Chiqim kiritish":
        await update.message.reply_text("Tanlang:", reply_markup=CHIQIM_MENU)
        return

    if text == "Chiqimlar ro'yxati":
        await show_expenses(update, context)
        return

    if text == "Zapchast":
        context.user_data["awaiting"] = "zap_name"
        await update.message.reply_text("Zapchast nomi:", reply_markup=ReplyKeyboardRemove())
        return

    if text == "Balans ko'rish":
        await update.message.reply_text("Balans menyusi", reply_markup=BALANS_MENU)
        return

    if text == "Balans":
        await show_balance(update, context)
        return

    awaiting = context.user_data.get("awaiting")

    if awaiting == "zap_name":

        context.user_data["zap_name"] = text
        context.user_data["awaiting"] = "zap_amount"

        await update.message.reply_text("Summasini yozing:")

    elif awaiting == "zap_amount":

        try:

            amount = float(text)
            name = context.user_data["zap_name"]

            conn = sqlite3.connect(DB_FILE)
            c = conn.cursor()

            c.execute(
                "INSERT INTO expenses(type,amount,comment) VALUES(?,?,?)",
                ("Zapchast", amount, name)
            )

            c.execute("SELECT value FROM settings WHERE key='total_expense'")
            total = float(c.fetchone()[0]) + amount

            c.execute(
                "UPDATE settings SET value=? WHERE key='total_expense'",
                (total,)
            )

            conn.commit()
            conn.close()

            await update.message.reply_text(
                f"Zapchast saqlandi\n{name}\n{amount:,.0f} so'm",
                reply_markup=BOSHLIQ_MENU
            )

        except:
            await update.message.reply_text("Raqam kiriting")

        context.user_data.clear()


# ---------------- WORKER FUNCTIONS ----------------

async def clock_in(update: Update, context: ContextTypes.DEFAULT_TYPE):

    uid = update.effective_user.id
    now = datetime.now(UZ_TZ)

    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()

    c.execute(
        "INSERT INTO shifts(user_id,work_date,start_time) VALUES(?,?,?)",
        (uid, now.strftime("%Y-%m-%d"), now.strftime("%H:%M:%S"))
    )

    conn.commit()
    conn.close()

    await update.message.reply_text("Ish boshlandi")


async def clock_out(update: Update, context: ContextTypes.DEFAULT_TYPE):

    uid = update.effective_user.id

    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()

    c.execute(
        "SELECT id,work_date,start_time FROM shifts WHERE user_id=? AND end_time IS NULL",
        (uid,)
    )

    row = c.fetchone()

    if not row:
        await update.message.reply_text("Ish boshlanmagan")
        return

    sid, date, st = row

    start = UZ_TZ.localize(datetime.strptime(date + " " + st, "%Y-%m-%d %H:%M:%S"))
    end = datetime.now(UZ_TZ)

    dur = (end - start).total_seconds() / 3600

    c.execute(
        "UPDATE shifts SET end_time=?,duration=? WHERE id=?",
        (end.strftime("%H:%M:%S"), dur, sid)
    )

    conn.commit()
    conn.close()

    await update.message.reply_text(f"Ish tugadi {dur:.2f} soat")


# ---------------- MAIN ----------------

def main():

    init_db()

    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    print("Bot ishga tushdi...")

    app.run_polling()


if __name__ == "__main__":
    main()
