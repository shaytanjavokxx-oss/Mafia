# ═══════════════════════════════════════════════
#  TRUE MAFIA STYLE BOT — by Jony
#  python-telegram-bot==20.3
# ═══════════════════════════════════════════════
import logging
import random
import asyncio
import sqlite3
import time
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (Application, CommandHandler, CallbackQueryHandler,
                          ContextTypes)
from config import *

logging.basicConfig(level=logging.INFO)

games = {}
chat_settings = {}

WIN_MONEY = 300
LOSE_MONEY = 100
SUISID_MONEY = 500
KAMIKAZE_TIME = 30

# ═══════════ ROLLAR ═══════════

ROLES_INFO = {
    "mafia":     "🤵🏻 Mafia",
    "komissar":  "🕵️ Komissar Katani",
    "qotil":     "🔪 Qotil",
    "daydi":     "🤠 Daydi",
    "kezuvchi":  "🚶 Kezuvchi",
    "shifokor":  "👨‍⚕️ Shifokor",
    "civilian":  "👱🏻 Tinch aholi",
    "jony":      "👑 Jony",
    "suisid":    "👨 Suisid",
    "omadli":    "🤞 Omadli",
    "kamikaze":  "💣 Kamikaze",
}

ROLES_DESC = {
    "mafia":    "Siz - 🤵🏻 Mafiasiz!\nTunda sheriklaringiz bilan qurbonni tanlaysiz. Shahar uxlaganda — siz ishlaysiz.",
    "komissar": "Siz - 🕵️ Komissar Katanisiz!\nHar tun bitta odamni tekshirasiz va uning kimligini bilib olasiz.",
    "qotil":    "Siz - 🔪 Qotilsiz!\nSiz yolg'iz bo'risiz. Tunda istalgan odamni o'ldirasiz. Oxirgi bo'lib tirik qolsangiz — siz yutasiz.",
    "daydi":    "Siz - 🤠 Daydisiz!\nSiz xoxlagan odamning uyiga shisha olish uchun borishingiz va qotillikning guvohi bo'lib qolishingiz mumkin.",
    "kezuvchi": "Siz - 🚶 Kezuvchisiz!\nTunda birovning uyiga tashrif buyurasiz va uning shu tungi harakatini bloklab qo'yasiz.",
    "shifokor": "Siz - 👨‍⚕️ Shifokorsiz!\nHar tun bitta odamni davolaysiz. Agar unga hujum qilishsa — u tirik qoladi.",
    "civilian": "Siz - 👱🏻 Tinch aholisiz!\nSizning qurolingiz — kunduzgi ovoz. Mafiyani toping va osib yuboring!",
    "jony":     "Siz - 👑 Jonysiz!\nSiz o'zingiz uchun istalgan rolni tanlashingiz mumkin. Tanlang:",
    "suisid":   "Siz - 👨 Suisidsiz!\nSeni osib o'ldirishsa sen yutasan! :)",
    "omadli":   "Siz - 🤞 Omadlisiz!\nSizga tunda hujum qilishsa, 50% ehtimol bilan omad sizni qutqaradi.",
    "kamikaze": "Siz - 💣 Kamikazesiz!\nTun va kunda siz tinch aholisiz, ammo sizni osishganda, siz xohlagan o'yinchini o'zingiz bilan qabrga olib ketishingiz mumkin.",
}

# tun boshlanganda guruhga chiqadigan atmosfera xabarlari
NIGHT_FLAVOR = {
    "mafia":    "🤵🏻 Mafia qurbonini tanladi...",
    "komissar": "🕵️ Komissar Katani pistoletini o'qladi...",
    "qotil":    "🔪 Qotil butalar orasiga yashirinib oldi...",
    "daydi":    "🤠 Daydi kimnikigadir shisha olish uchun ketdi...",
    "kezuvchi": "🚶 Kezuvchi ko'chaga chiqib ketdi...",
    "shifokor": "👨‍⚕️ Shifokor tungi navbatchilikka ketdi...",
    "omadli":   "🤞 O'yinchilardan biriga omad kulib boqdi",
}

NIGHT_QUESTION = {
    "mafia":    "🌃 Qurbon kim bo'ladi?",
    "komissar": "🌃 Kimni tekshirasiz?",
    "qotil":    "🌃 Kimni so'yasiz?",
    "daydi":    "🌃 Kimning uyiga shisha olgani borasiz?",
    "kezuvchi": "🌃 Kimning uyiga tashrif buyurasiz?",
    "shifokor": "🌃 Kimni davolaysiz?",
}

NIGHT_ROLES = ["mafia", "komissar", "qotil", "daydi", "kezuvchi", "shifokor"]
TOGGLEABLE_ROLES = ["komissar", "shifokor", "qotil", "daydi", "kezuvchi",
                    "omadli", "suisid", "kamikaze", "jony"]
TIME_OPTIONS = [30, 45, 60, 75, 90, 120, 180, 240, 300]

DEFAULT_SETTINGS = {
    "join_time": JOIN_TIME,
    "night_time": NIGHT_TIME,
    "day_time": DAY_TIME,
    "roles": {r: True for r in TOGGLEABLE_ROLES},
}

# ═══════════ DATABASE ═══════════

def db():
    return sqlite3.connect("mafia.db")

def init_db():
    con = db()
    con.execute("""CREATE TABLE IF NOT EXISTS users(
        user_id INTEGER PRIMARY KEY,
        name TEXT,
        games INTEGER DEFAULT 0,
        wins INTEGER DEFAULT 0,
        money INTEGER DEFAULT 0,
        diamonds INTEGER DEFAULT 0)""")
    con.commit()
    con.close()

def ensure_user(uid, name):
    con = db()
    con.execute("INSERT OR IGNORE INTO users(user_id, name) VALUES(?,?)", (uid, name))
    con.execute("UPDATE users SET name=? WHERE user_id=?", (name, uid))
    con.commit()
    con.close()

def add_result(uid, won, bonus=0):
    con = db()
    money = (WIN_MONEY if won else LOSE_MONEY) + bonus
    con.execute("UPDATE users SET games=games+1, wins=wins+?, money=money+? WHERE user_id=?",
                (1 if won else 0, money, uid))
    con.commit()
    con.close()

def get_profile(uid):
    con = db()
    row = con.execute("SELECT name, games, wins, money, diamonds FROM users WHERE user_id=?",
                      (uid,)).fetchone()
    con.close()
    return row

# ═══════════ YORDAMCHI ═══════════

def get_settings(chat_id):
    if chat_id not in chat_settings:
        chat_settings[chat_id] = {
            "join_time": DEFAULT_SETTINGS["join_time"],
            "night_time": DEFAULT_SETTINGS["night_time"],
            "day_time": DEFAULT_SETTINGS["day_time"],
            "roles": dict(DEFAULT_SETTINGS["roles"]),
        }
    return chat_settings[chat_id]

def new_game(chat_id):
    s = get_settings(chat_id)
    games[chat_id] = {
        "status": "lobby",
        "players": {},
        "night_actions": {},
        "votes": {},
        "round": 0,
        "start_time": None,
        "kami_choice": None,
        "suisid_winners": [],
        "settings": {
            "join_time": s["join_time"],
            "night_time": s["night_time"],
            "day_time": s["day_time"],
            "roles": dict(s["roles"]),
        },
    }

def alive_players(game):
    return {uid: p for uid, p in game["players"].items() if p["alive"]}

def role_label(role):
    return ROLES_INFO[role]

def alive_list_text(game):
    alive = alive_players(game)
    lines = [f"{i+1}. {p['name']}" for i, p in enumerate(alive.values())]
    counts = {}
    for p in alive.values():
        counts[p["role"]] = counts.get(p["role"], 0) + 1
    parts = []
    if counts.get("civilian"):
        parts.append(f"👱🏻 Tinch aholi - {counts['civilian']}")
    if counts.get("mafia"):
        parts.append(f"🤵🏻 Mafia - {counts['mafia']}")
    for r in ["komissar", "qotil", "daydi", "kezuvchi", "shifokor", "suisid", "omadli", "kamikaze"]:
        if counts.get(r):
            parts.append(role_label(r))
    return ("Tirik o'yinchilar:\n" + "\n".join(lines) +
            "\n\nUlardan kimlar:\n" + ", ".join(parts) +
            f"\nJami: {len(alive)} kishi.")

def duration_text(game):
    sec = int(time.time() - game["start_time"])
    return f"O'yin: {sec // 60} min. {sec % 60} sek. davom etdi"

# ═══════════ /MAFIA — LOBBY ═══════════

async def unpin_lobby(context, chat_id):
    if chat_id in games and games[chat_id].get("lobby_msg_id"):
        try:
            await context.bot.unpin_chat_message(chat_id, games[chat_id]["lobby_msg_id"])
        except Exception:
            pass

async def mafia_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    if update.effective_chat.type == "private":
        await update.message.reply_text("Bu o'yin faqat guruhda o'ynaladi!")
        return
    if chat_id in games and games[chat_id]["status"] != "ended":
        await update.message.reply_text("O'yin allaqachon boshlangan! /stop bilan to'xtatish mumkin.")
        return

    new_game(chat_id)
    s = games[chat_id]["settings"]
    kb = [[InlineKeyboardButton("✅ Qatnashish", callback_data="join")]]
    lobby_msg = await update.message.reply_text(
        f"🎭 SHAHARDA YANGI O'YIN!\n"
        f"━━━━━━━━━━━━━━━━━━\n\n"
        f"Qatnashish uchun tugmani bosing!\n"
        f"Kamida {MIN_PLAYERS} kishi kerak.\n\n"
        f"⏳ {s['join_time']} soniya...\n\n"
        f"👥 Qatnashchilar (0):",
        reply_markup=InlineKeyboardMarkup(kb)
    )
    games[chat_id]["lobby_msg_id"] = lobby_msg.message_id
    try:
        await context.bot.pin_chat_message(
            chat_id, lobby_msg.message_id, disable_notification=False
        )
    except Exception:
        pass
    await asyncio.sleep(s["join_time"])

    if chat_id not in games or games[chat_id]["status"] != "lobby":
        return
    if len(games[chat_id]["players"]) < MIN_PLAYERS:
        await update.message.reply_text(
            f"❌ Yetarli o'yinchi yo'q! Kamida {MIN_PLAYERS} kerak.\nO'yin bekor qilindi."
        )
        await unpin_lobby(context, chat_id)
        games[chat_id]["status"] = "ended"
        return
    await assign_roles(update, context, chat_id)

async def join_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    chat_id = update.effective_chat.id
    user = query.from_user
    if chat_id not in games or games[chat_id]["status"] != "lobby":
        await query.answer("O'yin tugagan yoki boshlanmagan!", show_alert=True)
        return
    if user.id in games[chat_id]["players"]:
        await query.answer("Siz allaqachon qatnashyapsiz!", show_alert=True)
        return

    games[chat_id]["players"][user.id] = {
        "name": user.first_name, "role": None, "alive": True,
    }
    ensure_user(user.id, user.first_name)
    await query.answer("✅ Qo'shildingiz!")

    names = "\n".join([f"• {p['name']}" for p in games[chat_id]["players"].values()])
    kb = [[InlineKeyboardButton("✅ Qatnashish", callback_data="join")]]
    try:
        await query.edit_message_text(
            f"🎭 SHAHARDA YANGI O'YIN!\n"
            f"━━━━━━━━━━━━━━━━━━\n\n"
            f"Qatnashish uchun tugmani bosing!\n"
            f"Kamida {MIN_PLAYERS} kishi kerak.\n\n"
            f"👥 Qatnashchilar ({len(games[chat_id]['players'])}):\n{names}",
            reply_markup=InlineKeyboardMarkup(kb)
        )
    except Exception:
        pass

# ═══════════ ROLLARNI TAQSIMLASH ═══════════

async def assign_roles(update, context, chat_id):
    game = games[chat_id]
    en = game["settings"]["roles"]
    players = list(game["players"].keys())
    n = len(players)
    random.shuffle(players)

    mafia_count = max(1, n // 4)
    pool = ["mafia"] * mafia_count

    if en.get("komissar") and n >= 4: pool.append("komissar")
    if en.get("shifokor") and n >= 4: pool.append("shifokor")
    if en.get("daydi") and n >= 5: pool.append("daydi")
    if en.get("qotil") and n >= 6: pool.append("qotil")
    if en.get("omadli") and n >= 6: pool.append("omadli")
    if en.get("kezuvchi") and n >= 7: pool.append("kezuvchi")
    if en.get("suisid") and n >= 8: pool.append("suisid")
    if en.get("kamikaze") and n >= 8: pool.append("kamikaze")
    if en.get("jony"): pool.append("jony")

    pool = pool[:n]
    while len(pool) < n:
        pool.append("civilian")
    random.shuffle(pool)

    for uid, role in zip(players, pool):
        game["players"][uid]["role"] = role

    game["status"] = "night"
    game["round"] = 1
    game["start_time"] = time.time()

    mafia_team = [uid for uid in players if game["players"][uid]["role"] == "mafia"]
    failed = []
    for uid in players:
        role = game["players"][uid]["role"]
        try:
            if role == "jony":
                kb = [[InlineKeyboardButton(role_label(r), callback_data=f"jonypick_{r}")]
                      for r in ["mafia", "komissar", "qotil", "daydi", "kezuvchi",
                                "shifokor", "suisid", "omadli", "kamikaze", "civilian"]]
                await context.bot.send_message(uid, ROLES_DESC["jony"],
                                               reply_markup=InlineKeyboardMarkup(kb))
            else:
                text = ROLES_DESC[role]
                if role == "mafia" and len(mafia_team) > 1:
                    mates = ", ".join(game["players"][m]["name"] for m in mafia_team if m != uid)
                    text += f"\n\nSheriklaringiz: {mates}"
                await context.bot.send_message(uid, text)
        except Exception:
            failed.append(game["players"][uid]["name"])

    if failed:
        await context.bot.send_message(
            chat_id,
            "⚠️ Quyidagilar botga shaxsiy yozmagan, rol ololmadi:\n" + ", ".join(failed) +
            "\n\nBotga /start yozib, keyingi o'yinda qatnashing!"
        )

    await context.bot.send_message(
        chat_id,
        "O'yin boshlandi!\n\nBir necha soniya ichida bot sizga rol va uning tavsifi bilan "
        "shaxsiy xabar yuboradi."
    )
    await start_night(context, chat_id)

async def jony_pick_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    uid = query.from_user.id
    role = query.data.replace("jonypick_", "")
    for chat_id, game in games.items():
        if game["status"] != "ended" and uid in game["players"] and game["players"][uid]["role"] == "jony":
            game["players"][uid]["role"] = role
            await query.edit_message_text(f"✅ Siz tanladingiz:\n\n{ROLES_DESC[role]}")
            await query.answer("Rol tanlandi!")
            return
    await query.answer("Topilmadi.")

# ═══════════ TUN ═══════════

async def start_night(context, chat_id):
    game = games[chat_id]
    game["night_actions"] = {}
    game["status"] = "night"
    alive = alive_players(game)

    flavor = []
    roles_alive = {p["role"] for p in alive.values()}
    for r in ["shifokor", "daydi", "komissar", "qotil", "mafia"]:
        if r in roles_alive:
            flavor.append(NIGHT_FLAVOR[r])
    if "kezuvchi" in roles_alive:
        flavor.append(NIGHT_FLAVOR["kezuvchi"])
    if "omadli" in roles_alive:
        flavor.append(NIGHT_FLAVOR["omadli"])

    await context.bot.send_message(
        chat_id,
        f"🌃 TUN — {game['round']}-kecha\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"Shahar uxlamoqda... Ko'chaga faqat jasur va qo'rqmas odamlar chiqishdi. "
        f"Ertalab tirik qolganlarni sanaymiz...\n\n"
        + "\n".join(flavor) +
        f"\n\n⏳ Tonggacha {game['settings']['night_time']} sek. qoldi"
    )

    for uid, p in alive.items():
        if p["role"] in NIGHT_ROLES:
            await send_night_action(context, chat_id, uid, p["role"], alive)

    await asyncio.sleep(game["settings"]["night_time"])
    if chat_id not in games or games[chat_id]["status"] != "night":
        return
    await resolve_night(context, chat_id)

async def send_night_action(context, chat_id, uid, role, alive):
    if role == "shifokor":
        targets = alive
    else:
        targets = {ouid: p for ouid, p in alive.items() if ouid != uid}
    kb = [[InlineKeyboardButton(p["name"], callback_data=f"night_{role}_{chat_id}_{ouid}")]
          for ouid, p in targets.items()]
    try:
        await context.bot.send_message(uid, NIGHT_QUESTION[role],
                                       reply_markup=InlineKeyboardMarkup(kb))
    except Exception:
        pass

async def night_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    parts = query.data.split("_")
    role, chat_id, target = parts[1], int(parts[2]), int(parts[3])
    uid = query.from_user.id

    if chat_id not in games or games[chat_id]["status"] != "night":
        await query.answer("Tun tugadi!", show_alert=True)
        return
    game = games[chat_id]
    if uid not in alive_players(game):
        await query.answer("Siz tirik emassiz!", show_alert=True)
        return

    game["night_actions"][role] = (uid, target)
    tname = game["players"][target]["name"]
    await query.edit_message_text(f"✅ Tanlov qabul qilindi: {tname}")
    await query.answer()

async def resolve_night(context, chat_id):
    game = games[chat_id]
    actions = game["night_actions"]
    players = game["players"]

    # Kezuvchi bloklaydi
    blocked = None
    if "kezuvchi" in actions:
        actor, target = actions["kezuvchi"]
        if players[actor]["alive"]:
            blocked = target

    def act(role):
        if role in actions:
            actor, target = actions[role]
            if players[actor]["alive"] and actor != blocked:
                return actor, target
        return None, None

    deaths = {}   # uid -> killer_role
    saved_by_doc = False
    saved_by_luck = False

    doc_actor, doc_target = act("shifokor")

    for killer_role in ["mafia", "qotil"]:
        actor, target = act(killer_role)
        if target is None:
            continue
        if target == doc_target:
            saved_by_doc = True
            continue
        if players[target]["role"] == "omadli" and random.random() < 0.5:
            saved_by_luck = True
            try:
                await context.bot.send_message(target, "🤞 Bu tun sizga hujum qilishdi, ammo omad sizni qutqardi!")
            except Exception:
                pass
            continue
        deaths[target] = killer_role

    # Komissar tekshiruvi
    kom_actor, kom_target = act("komissar")
    if kom_target is not None:
        try:
            await context.bot.send_message(
                kom_actor,
                f"🕵️ Tekshiruv natijasi:\n{players[kom_target]['name']} — {role_label(players[kom_target]['role'])}"
            )
        except Exception:
            pass

    # Daydi guvohlik
    day_actor, day_target = act("daydi")
    if day_target is not None and day_target in deaths:
        try:
            await context.bot.send_message(
                day_actor,
                f"🤠 Siz shisha olgani borganingizda qotillikning guvohi bo'ldingiz!\n"
                f"{players[day_target]['name']}ni {role_label(deaths[day_target])} o'ldirdi!"
            )
        except Exception:
            pass

    # O'limlarni qo'llash
    for uid in deaths:
        players[uid]["alive"] = False

    # ═══ KUN BOSHLANISHI ═══
    game["round_day"] = game["round"]
    text = (f"🏙 {game['round']}-kun\n"
            f"Quyosh chiqib, tunda to'kilgan qonlarni quritdi...\n\n")
    if deaths:
        lines = []
        for uid, killer in deaths.items():
            lines.append(f"Tunda {role_label(players[uid]['role'])} {players[uid]['name']} "
                         f"vaxshiylarcha o'ldirildi...\nAytishlaricha unikiga {role_label(killer)} kelgan")
        text += "\n\n".join(lines)
    else:
        text += "Bu tun hech kim o'lmadi. Shahar tinch uyg'ondi!"
        if saved_by_doc:
            text += "\n👨‍⚕️ Aytishlaricha, shifokor kimnidir o'limdan qutqarib qolibdi..."
    await context.bot.send_message(chat_id, text)

    if await check_winner(context, chat_id):
        return
    await start_day(context, chat_id)

# ═══════════ KUN — OVOZ BERISH ═══════════

async def start_day(context, chat_id):
    game = games[chat_id]
    game["status"] = "day"
    game["votes"] = {}
    alive = alive_players(game)

    await context.bot.send_message(chat_id, alive_list_text(game) +
                                   "\n\nTunda bo'lgan xodisalarni muxokama qilishning ayni vaqti...")

    kb = [[InlineKeyboardButton(p["name"], callback_data=f"vote_{chat_id}_{uid}")]
          for uid, p in alive.items()]
    kb.append([InlineKeyboardButton("⏭ Hech kim", callback_data=f"vote_{chat_id}_skip")])
    await context.bot.send_message(
        chat_id,
        f"Aybdorlarni aniqlash va jazolash vaqti keldi.\n"
        f"Ovoz berish uchun {game['settings']['day_time']} sekund",
        reply_markup=InlineKeyboardMarkup(kb)
    )
    await asyncio.sleep(game["settings"]["day_time"])
    if chat_id not in games or games[chat_id]["status"] != "day":
        return
    await resolve_day(context, chat_id)

async def vote_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    parts = query.data.split("_")
    chat_id, target = int(parts[1]), parts[2]
    uid = query.from_user.id

    if chat_id not in games or games[chat_id]["status"] != "day":
        await query.answer("Ovoz berish vaqti tugadi!", show_alert=True)
        return
    game = games[chat_id]
    if uid not in alive_players(game):
        await query.answer("Siz tirik emassiz!", show_alert=True)
        return
    if uid in game["votes"]:
        await query.answer("Siz allaqachon ovoz berdingiz!", show_alert=True)
        return

    game["votes"][uid] = target
    await query.answer("Ovoz qabul qilindi!")
    voter = game["players"][uid]["name"]
    if target == "skip":
        await context.bot.send_message(chat_id, f"{voter} hech kimga ovoz bermadi")
    else:
        tname = game["players"][int(target)]["name"]
        await context.bot.send_message(chat_id, f"{voter} - {tname}ga ovoz berdi")

async def resolve_day(context, chat_id):
    game = games[chat_id]
    counts = {}
    for v in game["votes"].values():
        if v != "skip":
            counts[v] = counts.get(v, 0) + 1

    if not counts:
        await context.bot.send_message(
            chat_id,
            "Ovoz berish yakunlandi\nOvoz berish janjalga aylanib ketdi... "
            "Xamma o'z uy-uylariga tarqaldi..."
        )
    else:
        mx = max(counts.values())
        cands = [u for u, c in counts.items() if c == mx]
        chosen = int(random.choice(cands))
        role = game["players"][chosen]["role"]
        name = game["players"][chosen]["name"]
        game["players"][chosen]["alive"] = False

        await context.bot.send_message(
            chat_id,
            f"☀️ Xalq qarori bilan {name} osib o'ldirildi!\n"
            f"Uning roli: {role_label(role)} edi"
        )

        # Suisid yutadi
        if role == "suisid":
            game["suisid_winners"].append(chosen)
            await context.bot.send_message(
                chat_id,
                f"👨 {name} aynan shuni xoxlagan edi!\nSuisid o'z maqsadiga erishdi va YUTDI! :)"
            )

        # Kamikaze birovni olib ketadi
        if role == "kamikaze":
            await kamikaze_revenge(context, chat_id, chosen)

    if await check_winner(context, chat_id):
        return

    game["round"] += 1
    await context.bot.send_message(
        chat_id,
        "🌃 Shaharga tun cho'kmoqda... Hamma uyiga tarqaldi."
    )
    await start_night(context, chat_id)

async def kamikaze_revenge(context, chat_id, kami_uid):
    game = games[chat_id]
    game["kami_choice"] = None
    alive = alive_players(game)
    if not alive:
        return
    kb = [[InlineKeyboardButton(p["name"], callback_data=f"kami_{chat_id}_{uid}")]
          for uid, p in alive.items()]
    name = game["players"][kami_uid]["name"]
    await context.bot.send_message(
        chat_id,
        f"💣 {name} cho'ntagidan granata chiqardi!\n"
        f"U kimnidir o'zi bilan qabrga olib ketadi... ({KAMIKAZE_TIME} sek)",
        reply_markup=InlineKeyboardMarkup(kb)
    )
    game["kami_uid"] = kami_uid
    await asyncio.sleep(KAMIKAZE_TIME)
    target = game.get("kami_choice")
    if target and game["players"][target]["alive"]:
        game["players"][target]["alive"] = False
        await context.bot.send_message(
            chat_id,
            f"💥 Portlash! {game['players'][target]['name']} "
            f"({role_label(game['players'][target]['role'])}) kamikaze bilan birga qabrga ketdi!"
        )
    else:
        await context.bot.send_message(chat_id, "💣 Granata portlamadi... Hamma omon qoldi.")

async def kami_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    parts = query.data.split("_")
    chat_id, target = int(parts[1]), int(parts[2])
    uid = query.from_user.id
    if chat_id not in games:
        await query.answer()
        return
    game = games[chat_id]
    if uid != game.get("kami_uid"):
        await query.answer("Bu tugma faqat kamikaze uchun!", show_alert=True)
        return
    if game.get("kami_choice"):
        await query.answer("Siz tanlab bo'ldingiz!", show_alert=True)
        return
    game["kami_choice"] = target
    await query.answer("💥 Tanlandi!")
    try:
        await query.edit_message_reply_markup(reply_markup=None)
    except Exception:
        pass

# ═══════════ G'OLIBNI ANIQLASH ═══════════

async def check_winner(context, chat_id):
    game = games[chat_id]
    alive = alive_players(game)
    mafia = [u for u, p in alive.items() if p["role"] == "mafia"]
    qotil = [u for u, p in alive.items() if p["role"] == "qotil"]
    town = [u for u, p in alive.items() if p["role"] not in ("mafia", "qotil")]

    # Qotil g'alabasi
    if qotil and not mafia and len(town) <= 1:
        await end_game(context, chat_id, "qotil")
        return True
    # Tinch aholi g'alabasi
    if not mafia and not qotil:
        await end_game(context, chat_id, "town")
        return True
    # Mafia g'alabasi
    if mafia and not qotil and len(mafia) >= len(town):
        await end_game(context, chat_id, "mafia")
        return True
    return False

async def end_game(context, chat_id, winner):
    game = games[chat_id]
    players = game["players"]

    titles = {"town": "Tinch axoli", "mafia": "Mafia", "qotil": "🔪 Qotil"}

    def is_winner(uid, p):
        if uid in game["suisid_winners"]:
            return True
        if winner == "town":
            return p["role"] not in ("mafia", "qotil") and p["role"] != "suisid"
        if winner == "mafia":
            return p["role"] == "mafia"
        if winner == "qotil":
            return p["role"] == "qotil"
        return False

    winners, losers = [], []
    for uid, p in players.items():
        line = f"   {p['name']} - {role_label(p['role'])}"
        if is_winner(uid, p):
            winners.append(line)
            bonus = SUISID_MONEY - WIN_MONEY if uid in game["suisid_winners"] else 0
            add_result(uid, True, bonus)
        else:
            losers.append(line)
            add_result(uid, False)

    text = (f"O'yin tugadi!\nG'olib: {titles[winner]}\n\n"
            f"G'oliblar: (+{WIN_MONEY}💰)\n" + "\n".join(winners))
    if losers:
        text += f"\n\nQolgan o'yinchilar: (+{LOSE_MONEY}💰)\n" + "\n".join(losers)
    text += f"\n\n{duration_text(game)}"
    await context.bot.send_message(chat_id, text)
    await unpin_lobby(context, chat_id)
    game["status"] = "ended"

# ═══════════ /PROFIL VA DO'KON ═══════════

async def profil(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    ensure_user(user.id, user.first_name)
    name, g, w, money, diamonds = get_profile(user.id)
    kb = [[InlineKeyboardButton("🛒 Do'kon", callback_data="shop")]]
    await update.message.reply_text(
        f"👤 PROFIL\n"
        f"━━━━━━━━━━━━━━━━━━\n\n"
        f"Ism: {name}\n"
        f"🎮 O'yinlar: {g}\n"
        f"🏆 G'alabalar: {w}\n\n"
        f"💰 Pul: {money}\n"
        f"💎 Olmos: {diamonds}",
        reply_markup=InlineKeyboardMarkup(kb)
    )

async def shop_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data
    if data == "shop":
        kb = [
            [InlineKeyboardButton("💎 Olmos sotib olish", callback_data="buy_diamond")],
            [InlineKeyboardButton("◀️ Ortga", callback_data="shop_back")],
        ]
        await query.edit_message_text(
            "🛒 DO'KON\n━━━━━━━━━━━━━━━━━━\n\n"
            "💎 Olmos — maxsus imkoniyatlar uchun\n\n"
            "Nimani sotib olasiz?",
            reply_markup=InlineKeyboardMarkup(kb)
        )
        await query.answer()
    elif data == "buy_diamond":
        await query.answer("⏳ Olmos sotib olish tez kunda ishga tushadi!", show_alert=True)
    elif data == "shop_back":
        user = query.from_user
        name, g, w, money, diamonds = get_profile(user.id)
        kb = [[InlineKeyboardButton("🛒 Do'kon", callback_data="shop")]]
        await query.edit_message_text(
            f"👤 PROFIL\n"
            f"━━━━━━━━━━━━━━━━━━\n\n"
            f"Ism: {name}\n"
            f"🎮 O'yinlar: {g}\n"
            f"🏆 G'alabalar: {w}\n\n"
            f"💰 Pul: {money}\n"
            f"💎 Olmos: {diamonds}",
            reply_markup=InlineKeyboardMarkup(kb)
        )
        await query.answer()

# ═══════════ /START /STOP ═══════════

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    ensure_user(update.effective_user.id, update.effective_user.first_name)
    roles = "\n".join([f"• {role_label(r)}" for r in ROLES_INFO])
    await update.message.reply_text(
        f"🎭 MAFIA BOT\n"
        f"━━━━━━━━━━━━━━━━━━\n\n"
        f"Guruhda /mafia yozing — o'yin boshlanadi!\n\n"
        f"Mavjud rollar:\n{roles}\n\n"
        f"/profil — profilingiz va do'kon\n"
        f"/stop — o'yinni to'xtatish\n"
        f"/setting — sozlamalar (faqat admin)"
    )

async def stop_game(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    if chat_id in games and games[chat_id]["status"] != "ended":
        await unpin_lobby(context, chat_id)
        games[chat_id]["status"] = "ended"
        await update.message.reply_text("🛑 O'yin to'xtatildi.")
    else:
        await update.message.reply_text("O'yin yo'q.")

# ═══════════ /SETTING ═══════════

async def is_group_admin(update, context):
    if update.effective_chat.type == "private":
        return True
    m = await context.bot.get_chat_member(update.effective_chat.id, update.effective_user.id)
    return m.status in ["administrator", "creator"]

async def setting_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type == "private":
        await update.message.reply_text("Sozlamalar faqat guruhda ishlaydi!")
        return
    if not await is_group_admin(update, context):
        await update.message.reply_text("❌ Faqat guruh adminlari sozlamalarni o'zgartirishi mumkin!")
        return
    await show_settings_menu(update.message, edit=False)

async def show_settings_menu(message, edit=True):
    kb = [
        [InlineKeyboardButton("🎭 Rollar", callback_data="set_roles")],
        [InlineKeyboardButton("⏱ Vaqtlar", callback_data="set_times")],
        [InlineKeyboardButton("◀️ Yopish", callback_data="set_close")],
    ]
    text = "⚙️ SOZLAMALAR\n━━━━━━━━━━━━━━━━━━\n\nQaysi bo'limni sozlamoqchisiz?"
    if edit:
        await message.edit_text(text, reply_markup=InlineKeyboardMarkup(kb))
    else:
        await message.reply_text(text, reply_markup=InlineKeyboardMarkup(kb))

async def show_roles_menu(message, chat_id):
    s = get_settings(chat_id)
    kb = []
    for r in TOGGLEABLE_ROLES:
        mark = "✅" if s["roles"][r] else "❌"
        kb.append([InlineKeyboardButton(f"{mark} {role_label(r)}", callback_data=f"set_role_{r}")])
    kb.append([InlineKeyboardButton("◀️ Ortga", callback_data="set_back")])
    await message.edit_text(
        "🎭 ROLLAR SOZLAMASI\n━━━━━━━━━━━━━━━━━━\n\n"
        "✅ — yoqilgan, ❌ — o'chirilgan\n"
        "🤵🏻 Mafia va 👱🏻 Tinch aholi doim yoqilgan.",
        reply_markup=InlineKeyboardMarkup(kb)
    )

async def show_times_menu(message, chat_id):
    s = get_settings(chat_id)
    kb = [
        [InlineKeyboardButton("📝 Registratsiya", callback_data="set_time_join_time")],
        [InlineKeyboardButton("🌃 Tun", callback_data="set_time_night_time")],
        [InlineKeyboardButton("☀️ Kun (ovoz berish)", callback_data="set_time_day_time")],
        [InlineKeyboardButton("◀️ Ortga", callback_data="set_back")],
    ]
    await message.edit_text(
        "⏱ VAQTLAR SOZLAMASI\n━━━━━━━━━━━━━━━━━━\n\n"
        f"📝 Registratsiya: {s['join_time']} sek\n"
        f"🌃 Tun: {s['night_time']} sek\n"
        f"☀️ Kun: {s['day_time']} sek",
        reply_markup=InlineKeyboardMarkup(kb)
    )

async def show_time_options(message, chat_id, time_key):
    s = get_settings(chat_id)
    kb, row = [], []
    for val in TIME_OPTIONS:
        mark = "🔘" if val == s[time_key] else "⚪"
        row.append(InlineKeyboardButton(f"{mark} {val}", callback_data=f"set_timeval_{time_key}_{val}"))
        if len(row) == 2:
            kb.append(row); row = []
    if row:
        kb.append(row)
    kb.append([InlineKeyboardButton("◀️ Ortga", callback_data="set_times")])
    names = {"join_time": "Registratsiya", "night_time": "Tun", "day_time": "Kun"}
    await message.edit_text(f"⏱ {names[time_key]} vaqtini tanlang (sekund):",
                            reply_markup=InlineKeyboardMarkup(kb))

async def settings_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    chat_id = query.message.chat_id
    data = query.data
    if update.effective_chat.type != "private":
        if not await is_group_admin(update, context):
            await query.answer("Faqat adminlar uchun!", show_alert=True)
            return
    s = get_settings(chat_id)

    if data == "set_close":
        await query.message.delete()
    elif data == "set_back":
        await show_settings_menu(query.message)
    elif data == "set_roles":
        await show_roles_menu(query.message, chat_id)
    elif data == "set_times":
        await show_times_menu(query.message, chat_id)
    elif data.startswith("set_role_"):
        role = data.replace("set_role_", "")
        s["roles"][role] = not s["roles"][role]
        await show_roles_menu(query.message, chat_id)
    elif data.startswith("set_timeval_"):
        rest = data.replace("set_timeval_", "")
        time_key, val = rest.rsplit("_", 1)
        s[time_key] = int(val)
        await show_time_options(query.message, chat_id, time_key)
    elif data.startswith("set_time_"):
        await show_time_options(query.message, chat_id, data.replace("set_time_", ""))
    await query.answer()

# ═══════════ MAIN ═══════════

def main():
    init_db()
    app = (Application.builder()
           .token(BOT_TOKEN)
           .concurrent_updates(True)
           .connect_timeout(30).read_timeout(30).write_timeout(30)
           .build())

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("mafia", mafia_start))
    app.add_handler(CommandHandler("stop", stop_game))
    app.add_handler(CommandHandler("profil", profil))
    app.add_handler(CommandHandler("setting", setting_command))

    app.add_handler(CallbackQueryHandler(join_callback, pattern="^join$"))
    app.add_handler(CallbackQueryHandler(jony_pick_callback, pattern="^jonypick_"))
    app.add_handler(CallbackQueryHandler(night_callback, pattern="^night_"))
    app.add_handler(CallbackQueryHandler(vote_callback, pattern="^vote_"))
    app.add_handler(CallbackQueryHandler(kami_callback, pattern="^kami_"))
    app.add_handler(CallbackQueryHandler(shop_callback, pattern="^(shop|buy_diamond|shop_back)$"))
    app.add_handler(CallbackQueryHandler(settings_callback, pattern="^set_"))

    print("✅ True Mafia Bot ishga tushdi!")
    app.run_polling()

if __name__ == "__main__":
    main()
