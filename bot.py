import json
import os
from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, CommandHandler, ContextTypes, filters
from flask import Flask
from threading import Thread
import time
import random

# ✅ TOKEN from environment
TOKEN = os.getenv("TOKEN")

DATA_FILE = "data.json"
users = {}

# ---------- LOAD & SAVE ----------
def load_data():
    global users
    try:
        if os.path.exists(DATA_FILE):
            with open(DATA_FILE, "r") as f:
                users = json.load(f)
        else:
            users = {}
    except:
        users = {}

def save_data():
    with open(DATA_FILE, "w") as f:
        json.dump(users, f)

# ---------- WEB SERVER ----------
app_web = Flask('')

@app_web.route('/')
def home():
    return "Bot Running"

def run():
    app_web.run(host='0.0.0.0', port=8080)

def keep_alive():
    Thread(target=run).start()

# ---------- RANK ----------
def get_rank(xp):
    if xp < 120:
        return "🪖 Cadet"
    elif xp < 350:
        return "⭐ Lieutenant"
    elif xp < 800:
        return "🔥 Captain"
    elif xp < 1800:
        return "🧠 Major"
    else:
        return "👑 Recommended"

# ---------- IDENTITY ----------
def get_identity(xp):
    if xp < 120:
        return "Consistent Cadet"
    elif xp < 800:
        return "Rising Officer"
    else:
        return "Top Performer"

# ---------- MESSAGE ----------
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message:
        return

    user = update.message.from_user
    uid = str(user.id)
    name = user.first_name
    text = update.message.text or ""
    now = time.time()

    if uid not in users:
        users[uid] = {
            "name": name,
            "xp": 0,
            "streak": 1,
            "last_active": now,
            "last_msg_time": 0
        }

    if now - users[uid]["last_msg_time"] < 3:
        return

    users[uid]["last_msg_time"] = now

    xp_gain = 5 if len(text.split()) > 15 else 2
    users[uid]["xp"] += xp_gain

    diff = now - users[uid]["last_active"]
    if diff > 172800:
        users[uid]["streak"] = 1
    elif diff > 86400:
        users[uid]["streak"] += 1

    users[uid]["last_active"] = now

    if random.random() < 0.3:
        await update.message.reply_text(f"+{xp_gain} XP | {get_rank(users[uid]['xp'])}")

    save_data()

# ---------- COMMANDS ----------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🔥 SSB Selection System Active")

async def rank(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = str(update.message.from_user.id)

    if uid in users:
        data = users[uid]
        xp = data["xp"]

        msg = f"XP: {xp}\nRank: {get_rank(xp)}\nIdentity: {get_identity(xp)}"

        for lvl in [120, 350, 800, 1800]:
            if xp < lvl:
                msg += f"\n🔥 {lvl - xp} XP to next level"
                break

        await update.message.reply_text(msg)
    else:
        await update.message.reply_text("No data yet")

async def profile(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = str(update.message.from_user.id)

    if uid in users:
        data = users[uid]
        await update.message.reply_text(
            f"🪖 {data['name']}\nXP: {data['xp']}\nRank: {get_rank(data['xp'])}\nStreak: {data['streak']} days"
        )
    else:
        await update.message.reply_text("No data yet")

# ---------- ADMIN ----------
def is_admin(update, context):
    return update.message.from_user.id in context.bot_data.get("admins", [])

async def addxp(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update, context):
        return

    try:
        username = context.args[0].lower()
        xp = int(context.args[1])

        for uid, data in users.items():
            if username in data["name"].lower():
                data["xp"] += xp
                save_data()
                await update.message.reply_text(f"🔥 {data['name']} +{xp} XP")
                return
    except:
        await update.message.reply_text("Usage: /addxp name amount")

async def removexp(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update, context):
        return

    try:
        username = context.args[0].lower()
        xp = int(context.args[1])

        for uid, data in users.items():
            if username in data["name"].lower():
                data["xp"] -= xp
                save_data()
                await update.message.reply_text(f"❌ {data['name']} -{xp} XP")
                return
    except:
        await update.message.reply_text("Usage: /removexp name amount")

# ---------- LEADERBOARD ----------
async def leaderboard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    top = sorted(users.values(), key=lambda x: x["xp"], reverse=True)[:5]

    msg = "🏆 SSB WEEKLY BOARD\n\n"
    for i, u in enumerate(top):
        msg += f"{i+1}. {u['name']} — {get_rank(u['xp'])} ({u['xp']} XP)\n"

    await update.message.reply_text(msg)

# ---------- INACTIVITY ----------
async def inactivity_check(context: ContextTypes.DEFAULT_TYPE):
    now = time.time()

    for uid, data in users.items():
        diff = now - data["last_active"]

        if 86400 < diff < 172800:
            await context.bot.send_message(int(uid), "⚠️ 24 hrs inactive")
        elif diff > 172800:
            data["xp"] -= 10
            await context.bot.send_message(int(uid), "❌ -10 XP")

    save_data()

# ---------- MAIN ----------
def main():
    print("TOKEN:", TOKEN)

    if not TOKEN:
        print("❌ TOKEN missing")
        return

    app = ApplicationBuilder().token(TOKEN).build()

    load_data()

    app.bot_data["admins"] = [799810129]

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("rank", rank))
    app.add_handler(CommandHandler("profile", profile))
    app.add_handler(CommandHandler("leaderboard", leaderboard))
    app.add_handler(CommandHandler("addxp", addxp))
    app.add_handler(CommandHandler("removexp", removexp))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    keep_alive()

    if app.job_queue:
        app.job_queue.run_repeating(inactivity_check, interval=3600)

    print("✅ Bot running...")

    app.run_polling()

if __name__ == "__main__":
    main()
