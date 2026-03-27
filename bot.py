# Sardoba Jilosi Bot - Klaviatura (ReplyKeyboard) versiyasi

import logging
import sqlite3
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo  # ✅ qo‘shildi

from telegram import Update, ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters,
    ContextTypes,
)

# ✅ TIMEZONE
TZ = ZoneInfo("Asia/Tashkent")

BOT_TOKEN = "TOKENINGNI ALMASHTIR!"
ADMIN_IDS = [1140333236, 5442902953]

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

DB_FILE = "sardoba.db"

# ------------------ DB ------------------

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

# ------------------ ISH ------------------

async def clock_in(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id

    now_dt = datetime.now(TZ)  # ✅
    today = now_dt.strftime("%Y-%m-%d")

    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()

    c.execute("SELECT id FROM shifts WHERE user_id = ? AND work_date = ? AND end_time IS NULL", (uid, today))

    if c.fetchone():
        await update.message.reply_text("Bugun allaqachon boshlagansiz!")
    else:
        now = now_dt.strftime("%H:%M:%S")  # ✅
        c.execute("INSERT INTO shifts (user_id, work_date, start_time) VALUES (?, ?, ?)", (uid, today, now))
        await update.message.reply_text(f"Ish boshlandi: {now}")

    conn.commit()
    conn.close()


async def clock_out(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id

    now_dt = datetime.now(TZ)  # ✅
    today = now_dt.strftime("%Y-%m-%d")

    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()

    c.execute("SELECT id, work_date, start_time FROM shifts WHERE user_id = ? AND work_date = ? AND end_time IS NULL", (uid, today))
    row = c.fetchone()

    if not row:
        await update.message.reply_text("Bugun ish boshlamagansiz.")
    else:
        sid, work_date, st = row

        start = datetime.strptime(f"{work_date} {st}", "%Y-%m-%d %H:%M:%S")
        end = now_dt  # ✅

        if end < start:
            end += timedelta(days=1)

        dur = (end - start).total_seconds() / 3600
        et = end.strftime("%H:%M:%S")

        c.execute("UPDATE shifts SET end_time = ?, duration = ? WHERE id = ?", (et, dur, sid))

        await update.message.reply_text(
            f"Yakunlandi!\nBoshlanish: {st}\nTugash: {et}\nJami: {dur:.2f} soat"
        )

    conn.commit()
    conn.close()

# ------------------ BOSHQA ------------------

async def my_days(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id

    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()

    c.execute("SELECT work_date, start_time, end_time, duration FROM shifts WHERE user_id = ? ORDER BY work_date DESC LIMIT 30", (uid,))
    rows = c.fetchall()

    if not rows:
        text = "Hali ish kuni yo'q."
    else:
        text = "Oxirgi kunlar:\n\n"
        total = 0.0
        for r in rows:
            dur = r[3] or 0
            total += dur
            et = r[2] or "ochik"
            text += f"{r[0]} | {r[1]} - {et} | {dur:.2f} soat\n"
        text += f"\nJami: {total:.2f} soat"

    await update.message.reply_text(text)
    conn.close()


async def show_balance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()

    c.execute("SELECT value FROM settings WHERE key = 'hourly_rate'")
    rate = float(c.fetchone()[0])

    c.execute("SELECT SUM(duration) FROM shifts")
    hours = c.fetchone()[0] or 0.0

    c.execute("SELECT value FROM settings WHERE key = 'total_expense'")
    exp = float(c.fetchone()[0])

    income = hours * rate
    bal = income - exp

    text = (
        f"Balans:\n"
        f"Soatlik narx: {rate:,.0f} so'm\n"
        f"Jami soat: {hours:.2f}\n"
        f"Taxminiy kirim: {income:,.0f} so'm\n"
        f"Chiqim: {exp:,.0f} so'm\n"
        f"Qoldiq: {bal:,.0f} so'm"
    )

    await update.message.reply_text(text)
    conn.close()

# ------------------ MAIN ------------------

def main():
    init_db()
    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", lambda u, c: u.message.reply_text("Bot ishlayapti")))
    app.add_handler(MessageHandler(filters.TEXT, clock_in))

    print("Bot ishga tushdi...")
    app.run_polling()

if __name__ == "__main__":
    main()


