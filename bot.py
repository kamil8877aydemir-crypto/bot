import os
import asyncio
import sqlite3
from telegram import Update, ChatMember
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "8695660286:AAGZQtt1k1TAwpPmbqb7Bo0q_D2tmyPyuKM")
DB_PATH = "bot_data.db"
CATEGORIES = ["pos", "saha"]


def init_db():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS members (
            id       INTEGER PRIMARY KEY AUTOINCREMENT,
            category TEXT NOT NULL,
            username TEXT NOT NULL,
            note     TEXT NOT NULL DEFAULT '',
            UNIQUE(category, username)
        )
    """)
    conn.commit()
    conn.close()


def db_get(category: str):
    conn = sqlite3.connect(DB_PATH)
    rows = conn.execute(
        "SELECT username, note FROM members WHERE category = ?", (category,)
    ).fetchall()
    conn.close()
    return rows


def db_add(category: str, username: str, note: str) -> bool:
    username = username.lower().lstrip("@")
    conn = sqlite3.connect(DB_PATH)
    try:
        conn.execute(
            "INSERT INTO members (category, username, note) VALUES (?, ?, ?)",
            (category, username, note),
        )
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        conn.execute(
            "UPDATE members SET note = ? WHERE category = ? AND username = ?",
            (note, category, username),
        )
        conn.commit()
        return False
    finally:
        conn.close()


def db_remove(username: str) -> list:
    username = username.lower().lstrip("@")
    conn = sqlite3.connect(DB_PATH)
    cats = [r[0] for r in conn.execute(
        "SELECT category FROM members WHERE username = ?", (username,)
    ).fetchall()]
    conn.execute("DELETE FROM members WHERE username = ?", (username,))
    conn.commit()
    conn.close()
    return cats


async def is_admin(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id
    try:
        member = await context.bot.get_chat_member(chat_id, user_id)
        return member.status in (ChatMember.ADMINISTRATOR, ChatMember.OWNER)
    except Exception:
        return False


async def yetkisiz(update: Update):
    await update.message.reply_text("🚫 Bu komutu sadece grup adminleri kullanabilir.")


async def cmd_eklepos(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update, context):
        await yetkisiz(update)
        return
    if not context.args:
        await update.message.reply_text(
            "Kullanım: /eklepos @nick [not]\n"
            "Örnek:    /eklepos @ahmet 10 bin dolar teminatlı"
        )
        return
    username = context.args[0].lstrip("@")
    note = " ".join(context.args[1:])
    yeni = db_add("pos", username, note)
    ek = f" — {note}" if note else ""
    msg = f"✅ @{username}{ek} → POS kategorisine eklendi." if yeni else \
          f"🔄 @{username}{ek} → POS notu güncellendi."
    await update.message.reply_text(msg)


async def cmd_eklesaha(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update, context):
        await yetkisiz(update)
        return
    if not context.args:
        await update.message.reply_text(
            "Kullanım: /eklesaha @nick [not]\n"
            "Örnek:    /eklesaha @ahmet 5 bin euro teminatlı"
        )
        return
    username = context.args[0].lstrip("@")
    note = " ".join(context.args[1:])
    yeni = db_add("saha", username, note)
    ek = f" — {note}" if note else ""
    msg = f"✅ @{username}{ek} → SAHA kategorisine eklendi." if yeni else \
          f"🔄 @{username}{ek} → SAHA notu güncellendi."
    await update.message.reply_text(msg)


async def cmd_sil(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update, context):
        await yetkisiz(update)
        return
    if not context.args:
        await update.message.reply_text("Kullanım: /sil @nick")
        return
    username = context.args[0].lstrip("@")
    removed = db_remove(username)
    if removed:
        cats = ", ".join(c.upper() for c in removed)
        await update.message.reply_text(f"✅ @{username} → {cats} kategorisinden çıkarıldı.")
    else:
        await update.message.reply_text(f"⚠️ @{username} hiçbir kategoride bulunamadı.")


async def cmd_liste(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lines = []
    for cat in CATEGORIES:
        members = db_get(cat)
        lines.append(f"📌 *{cat.upper()}*")
        if members:
            for uname, note in members:
                entry = f"  • @{uname}"
                if note:
                    entry += f" — {note}"
                lines.append(entry)
        else:
            lines.append("  (boş)")
        lines.append("")
    await update.message.reply_text("\n".join(lines), parse_mode="Markdown")


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        return
    words = update.message.text.lower().split()
    matched = next((cat for cat in CATEGORIES if cat in words), None)
    if not matched:
        return
    members = db_get(matched)
    if not members:
        return
    lines = []
    for uname, note in members:
        line = f"@{uname}"
        if note:
            line += f" — {note}"
        lines.append(line)
    reply = f"📢 <b>{matched.upper()}</b> teminatlı üyeler:\n" + "\n".join(lines)
    await update.message.reply_text(
        reply,
        parse_mode="HTML",
        reply_to_message_id=update.message.message_id,
    )


def main():
    init_db()
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("eklepos",  cmd_eklepos))
    app.add_handler(CommandHandler("eklesaha", cmd_eklesaha))
    app.add_handler(CommandHandler("sil",      cmd_sil))
    app.add_handler(CommandHandler("liste",    cmd_liste))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    print("Bot başlatıldı...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()