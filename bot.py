import logging
import random
import asyncio
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (Application, CommandHandler, CallbackQueryHandler,
                           MessageHandler, filters, ContextTypes)
from config import *

logging.basicConfig(level=logging.INFO)

# games[chat_id] = game dict
games = {}

# chat_settings[chat_id] = sozlamalar
chat_settings = {}

ROLES_INFO = {
    "mafia": "🔴 Mafia — kechasi birovni o'ldiradi",
    "doctor": "🟢 Shifokor — kechasi birovni davolaydi",
    "detective": "🔵 Detektiv — kechasi birovni tekshiradi",
    "kezuvchi": "🚶 Kezuvchi — kechasi birovga tashrif qiladi, uning harakatini bloklaydi",
    "merosxor": "🎒 Merosxor — birov o'lganda, ehtimol uning rolini meros qiladi",
    "suisid": "💣 Suisid — portlatib o'zi va nishonni o'ldirishi mumkin (1 marta)",
    "jony": "👑 Jony — o'yin boshida o'zi uchun istalgan rolni tanlaydi",
    "civilian": "⚪ Tinch aholi — maxsus qobiliyati yo'q",
}

ROLE_EMOJI = {
    "mafia": "🔴", "doctor": "🟢", "detective": "🔵", "kezuvchi": "🚶",
    "merosxor": "🎒", "suisid": "💣", "jony": "👑", "civilian": "⚪",
}

# Sozlanadigan rollar (civilian va mafia doim yoqilgan)
TOGGLEABLE_ROLES = ["doctor", "detective", "kezuvchi", "merosxor", "suisid", "jony"]

TIME_OPTIONS = [30, 45, 60, 75, 90, 120, 180, 240, 300, 360]

DEFAULT_SETTINGS = {
    "join_time": JOIN_TIME,
    "night_time": NIGHT_TIME,
    "day_time": DAY_TIME,
    "roles": {r: True for r in TOGGLEABLE_ROLES},
}

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
        "status": "lobby",  # lobby, night, day, voting, ended
        "players": {},  # user_id: {"name":..., "role":..., "alive":True}
        "host": None,
        "night_actions": {},  # role -> target_id
        "votes": {},  # voter_id -> target_id
        "round": 0,
        "suisid_used": False,
        "settings": dict(s),  # o'yin boshlanganda sozlamalar saqlanadi
    }

def alive_players(game):
    return {uid: p for uid, p in game["players"].items() if p["alive"]}

def alive_by_role(game, role):
    return [uid for uid, p in alive_players(game).items() if p["role"] == role]

# ═══════════════════════════════════════
#         /MAFIA — LOBBY BOSHLASH
# ═══════════════════════════════════════
async def mafia_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id

    if update.effective_chat.type == "private":
        await update.message.reply_text("Bu o'yin faqat guruhda o'ynaladi!")
        return

    if chat_id in games and games[chat_id]["status"] != "ended":
        await update.message.reply_text("O'yin allaqachon boshlangan! /stop bilan to'xtatish mumkin.")
        return

    new_game(chat_id)
    games[chat_id]["host"] = update.effective_user.id
    s = games[chat_id]["settings"]

    keyboard = [[InlineKeyboardButton("✅ Qatnashish", callback_data="join")]]
    msg = await update.message.reply_text(
        f"🎭 MAFIA O'YINI BOSHLANDI!\n"
        f"━━━━━━━━━━━━━━━━━━\n\n"
        f"Qatnashish uchun tugmani bosing!\n"
        f"Kamida {MIN_PLAYERS} kishi kerak.\n\n"
        f"⏳ {s['join_time']} soniya...\n\n"
        f"👥 Qatnashchilar (0):",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    games[chat_id]["lobby_msg_id"] = msg.message_id

    await asyncio.sleep(s["join_time"])

    if chat_id not in games or games[chat_id]["status"] != "lobby":
        return

    if len(games[chat_id]["players"]) < MIN_PLAYERS:
        await update.message.reply_text(
            f"❌ Yetarli o'yinchi yo'q! Kamida {MIN_PLAYERS} kerak.\n"
            f"O'yin bekor qilindi."
        )
        games[chat_id]["status"] = "ended"
        return

    await assign_roles(update, context, chat_id)

# ═══════════════════════════════════════
#         QATNASHISH
# ═══════════════════════════════════════
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
        "name": user.first_name,
        "username": user.username,
        "role": None,
        "alive": True,
        "blocked": False,
    }

    await query.answer("✅ Qo'shildingiz!")

    names = "\n".join([f"• {p['name']}" for p in games[chat_id]["players"].values()])
    keyboard = [[InlineKeyboardButton("✅ Qatnashish", callback_data="join")]]

    try:
        await query.edit_message_text(
            f"🎭 MAFIA O'YINI BOSHLANDI!\n"
            f"━━━━━━━━━━━━━━━━━━\n\n"
            f"Qatnashish uchun tugmani bosing!\n"
            f"Kamida {MIN_PLAYERS} kishi kerak.\n\n"
            f"👥 Qatnashchilar ({len(games[chat_id]['players'])}):\n{names}",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    except:
        pass

# ═══════════════════════════════════════
#         ROLLARNI TAQSIMLASH
# ═══════════════════════════════════════
async def assign_roles(update, context, chat_id):
    game = games[chat_id]
    s = game["settings"]
    enabled_roles = s["roles"]

    players = list(game["players"].keys())
    n = len(players)
    random.shuffle(players)

    # Mafia soni: ~1/4
    mafia_count = max(1, n // 4)
    role_pool = ["mafia"] * mafia_count

    # Faqat yoqilgan rollarni qo'shamiz, o'yinchi soniga qarab
    optional_roles = []
    if enabled_roles.get("jony"):
        optional_roles.append("jony")
    if enabled_roles.get("doctor") and n >= 4:
        optional_roles.append("doctor")
    if enabled_roles.get("detective") and n >= 5:
        optional_roles.append("detective")
    if enabled_roles.get("kezuvchi") and n >= 6:
        optional_roles.append("kezuvchi")
    if enabled_roles.get("merosxor") and n >= 7:
        optional_roles.append("merosxor")
    if enabled_roles.get("suisid") and n >= 8:
        optional_roles.append("suisid")

    role_pool += optional_roles

    while len(role_pool) < n:
        role_pool.append("civilian")
    role_pool = role_pool[:n]
    random.shuffle(role_pool)

    bot_username = (await context.bot.get_me()).username
    failed_dm = []

    for uid, role in zip(players, role_pool):
        game["players"][uid]["role"] = role
        try:
            extra = ""
            if role == "jony":
                kb = [[InlineKeyboardButton(ROLES_INFO[r].split(" —")[0], callback_data=f"jonypick_{r}")]
                      for r in ["mafia","doctor","detective","kezuvchi","merosxor","suisid","civilian"]]
                await context.bot.send_message(
                    chat_id=uid,
                    text=f"👑 Sizning rolingiz: JONY!\n\n"
                         f"Siz o'zingiz uchun istalgan rolni tanlashingiz mumkin:\n\n"
                         f"Tanlang:",
                    reply_markup=InlineKeyboardMarkup(kb)
                )
            else:
                await context.bot.send_message(
                    chat_id=uid,
                    text=f"🎭 Sizning rolingiz:\n\n{ROLES_INFO[role]}\n\n"
                         f"O'yin boshlandi! Kecha kelishini kuting."
                )
        except:
            failed_dm.append(game["players"][uid]["name"])

    if failed_dm:
        names = ", ".join(failed_dm)
        await update.message.reply_text(
            f"⚠️ Quyidagi o'yinchilar botga shaxsiy yozmagan, rolni ololmadilar:\n{names}\n\n"
            f"Iltimos botga /start yozib qaytadan urinib ko'ring!"
        )

    game["status"] = "night"
    game["round"] = 1

    mafia_names = [game["players"][uid]["name"] for uid in players if game["players"][uid]["role"] == "mafia" or (game["players"][uid]["role"]=="jony")]

    await update.message.reply_text(
        f"🎲 Rollar tarqatildi!\n"
        f"👥 Jami: {n} o'yinchi\n"
        f"🔴 Mafia soni: {mafia_count}\n\n"
        f"🌙 1-KECHA boshlandi!\n"
        f"Maxsus rolga ega o'yinchilar botga shaxsiy yozishmada harakat qilsin.\n\n"
        f"⏳ {s['night_time']} soniya..."
    )

    await start_night(update, context, chat_id)

# ═══════════════════════════════════════
#         JONY ROL TANLASH
# ═══════════════════════════════════════
async def jony_pick_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    uid = query.from_user.id
    role = query.data.replace("jonypick_", "")

    # Find chat
    for chat_id, game in games.items():
        if uid in game["players"] and game["players"][uid]["role"] == "jony":
            game["players"][uid]["role"] = role
            await query.edit_message_text(
                f"✅ Siz tanladingiz: {ROLES_INFO[role]}\n\nO'yin boshlandi!"
            )
            await query.answer("Rol tanlandi!")
            return
    await query.answer("Topilmadi.")

# ═══════════════════════════════════════
#         KECHA BOSHLASH
# ═══════════════════════════════════════
async def start_night(update, context, chat_id):
    game = games[chat_id]
    game["night_actions"] = {}
    game["status"] = "night"

    alive = alive_players(game)

    for uid, p in alive.items():
        role = p["role"]
        if role in ["mafia", "doctor", "detective", "kezuvchi"]:
            await send_night_action(context, chat_id, uid, role, alive)
        elif role == "suisid" and not game["suisid_used"]:
            kb = [[InlineKeyboardButton(f"💣 {pl['name']}", callback_data=f"night_suisid_{chat_id}_{ouid}")]
                  for ouid, pl in alive.items() if ouid != uid]
            kb.append([InlineKeyboardButton("⏭ Hech kim (kutaman)", callback_data=f"night_suisid_{chat_id}_skip")])
            try:
                await context.bot.send_message(
                    chat_id=uid,
                    text="💣 Portlatishni xohlaysizmi? Tanlang (1 marta ishlatish mumkin):",
                    reply_markup=InlineKeyboardMarkup(kb)
                )
            except:
                pass

    await asyncio.sleep(game["settings"]["night_time"])

    if chat_id not in games or games[chat_id]["status"] != "night":
        return

    await resolve_night(update, context, chat_id)

async def send_night_action(context, chat_id, uid, role, alive):
    targets = {ouid: p for ouid, p in alive.items() if ouid != uid or role == "doctor"}
    if role == "doctor":
        targets = alive  # doctor can heal self too

    role_names = {"mafia":"🔴 kim o'ldirilsin?","doctor":"🟢 kimni davolaysiz?",
                   "detective":"🔵 kimni tekshirasiz?","kezuvchi":"🚶 kimga tashrif qilasiz?"}

    kb = [[InlineKeyboardButton(p["name"], callback_data=f"night_{role}_{chat_id}_{ouid}")]
          for ouid, p in targets.items()]
    try:
        await context.bot.send_message(
            chat_id=uid,
            text=f"🌙 KECHA — {role_names.get(role,'tanlang')}",
            reply_markup=InlineKeyboardMarkup(kb)
        )
    except:
        pass

# ═══════════════════════════════════════
#         KECHA TUGMALARI
# ═══════════════════════════════════════
async def night_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data.split("_")
    role = data[1]
    chat_id = int(data[2])
    target = data[3]
    uid = query.from_user.id

    if chat_id not in games or games[chat_id]["status"] != "night":
        await query.answer("Kecha tugadi!", show_alert=True)
        return

    game = games[chat_id]

    if role == "suisid":
        if target == "skip":
            await query.edit_message_text("⏭ Bekor qilindi.")
            await query.answer()
            return
        game["night_actions"]["suisid"] = (uid, int(target))
        await query.edit_message_text("💣 Tayyor turing...")
    else:
        game["night_actions"][role] = int(target)
        await query.edit_message_text(f"✅ Tanlov qabul qilindi!")

    await query.answer()

# ═══════════════════════════════════════
#         KECHA NATIJALARINI HISOBLASH
# ═══════════════════════════════════════
async def resolve_night(update, context, chat_id):
    game = games[chat_id]
    actions = game["night_actions"]
    alive = alive_players(game)
    deaths = []
    messages = []

    kezuvchi_target = actions.get("kezuvchi")
    blocked_uid = kezuvchi_target

    # Mafia kill
    mafia_target = actions.get("mafia")
    if mafia_target and mafia_target != blocked_uid:
        doctor_target = actions.get("doctor")
        if mafia_target != doctor_target:
            deaths.append(mafia_target)

    # Suisid
    if "suisid" in actions:
        suisid_uid, target_uid = actions["suisid"]
        if suisid_uid != blocked_uid:
            deaths.append(suisid_uid)
            deaths.append(target_uid)
            game["suisid_used"] = True

    # Detective result
    detective_uid = None
    for uid_, p in alive.items():
        if p["role"] == "detective":
            detective_uid = uid_
    if detective_uid and "detective" in actions and detective_uid != blocked_uid:
        target = actions["detective"]
        target_role = game["players"][target]["role"]
        is_mafia = target_role == "mafia"
        try:
            await context.bot.send_message(
                chat_id=detective_uid,
                text=f"🔍 Tekshirish natijasi:\n{game['players'][target]['name']} — "
                     f"{'🔴 MAFIA!' if is_mafia else '✅ Tinch fuqaro'}"
            )
        except:
            pass

    # Apply deaths
    deaths = list(set([d for d in deaths if d in game["players"] and game["players"][d]["alive"]]))
    for d in deaths:
        game["players"][d]["alive"] = False

    # Merosxor inheritance
    merosxor_uid = next((uid_ for uid_, p in alive.items() if p["role"] == "merosxor"), None)
    if merosxor_uid and merosxor_uid not in deaths and deaths:
        dead_player = game["players"][deaths[0]]
        if random.random() < 0.5 and dead_player["role"] not in ["merosxor", "jony"]:
            game["players"][merosxor_uid]["role"] = dead_player["role"]
            try:
                await context.bot.send_message(
                    chat_id=merosxor_uid,
                    text=f"🎒 Siz {dead_player['name']} rolini meros qildingiz: {ROLES_INFO[dead_player['role']]}"
                )
            except:
                pass

    if deaths:
        names = ", ".join([game["players"][d]["name"] for d in deaths])
        text = f"🌙 Kecha tugadi!\n\n☠️ O'lganlar: {names}"
    else:
        text = f"🌙 Kecha tugadi!\n\n✅ Hech kim o'lmadi!"

    await context.bot.send_message(chat_id=chat_id, text=text)

    if await check_winner(context, chat_id):
        return

    await start_day(update, context, chat_id)

# ═══════════════════════════════════════
#         KUNDUZ — OVOZ BERISH
# ═══════════════════════════════════════
async def start_day(update, context, chat_id):
    game = games[chat_id]
    game["status"] = "day"
    game["votes"] = {}

    alive = alive_players(game)
    names = "\n".join([f"• {p['name']}" for p in alive.values()])

    kb = [[InlineKeyboardButton(p["name"], callback_data=f"vote_{chat_id}_{uid}")]
          for uid, p in alive.items()]
    kb.append([InlineKeyboardButton("⏭ Hech kim", callback_data=f"vote_{chat_id}_skip")])

    msg = await context.bot.send_message(
        chat_id=chat_id,
        text=f"☀️ KUNDUZ — OVOZ BERISH\n"
             f"━━━━━━━━━━━━━━━━━━\n\n"
             f"👥 Tirik qolganlar:\n{names}\n\n"
             f"Kimni chiqarib yubormoqchisiz?\n"
             f"⏳ {game['settings']['day_time']} soniya",
        reply_markup=InlineKeyboardMarkup(kb)
    )
    game["day_msg_id"] = msg.message_id

    await asyncio.sleep(game["settings"]["day_time"])

    if chat_id not in games or games[chat_id]["status"] != "day":
        return

    await resolve_day(update, context, chat_id)

async def vote_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data.split("_")
    chat_id = int(data[1])
    target = data[2]
    uid = query.from_user.id

    if chat_id not in games or games[chat_id]["status"] != "day":
        await query.answer("Ovoz berish vaqti tugadi!", show_alert=True)
        return

    game = games[chat_id]
    if uid not in alive_players(game):
        await query.answer("Siz tirik emassiz!", show_alert=True)
        return

    game["votes"][uid] = target
    await query.answer("Ovoz qabul qilindi!")

async def resolve_day(update, context, chat_id):
    game = games[chat_id]
    votes = game["votes"]

    counts = {}
    for v in votes.values():
        if v != "skip":
            counts[v] = counts.get(v, 0) + 1

    if not counts:
        await context.bot.send_message(chat_id=chat_id, text="☀️ Hech kim chiqarilmadi!")
    else:
        max_votes = max(counts.values())
        candidates = [uid for uid, c in counts.items() if c == max_votes]
        chosen = random.choice(candidates)
        chosen_uid = int(chosen)
        game["players"][chosen_uid]["alive"] = False
        role = game["players"][chosen_uid]["role"]
        await context.bot.send_message(
            chat_id=chat_id,
            text=f"☀️ {game['players'][chosen_uid]['name']} chiqarib yuborildi!\n"
                 f"Uning roli: {ROLES_INFO[role]}"
        )

    if await check_winner(context, chat_id):
        return

    game["round"] += 1
    await context.bot.send_message(
        chat_id=chat_id,
        text=f"🌙 {game['round']}-KECHA boshlandi!\n⏳ {game['settings']['night_time']} soniya..."
    )
    await start_night(update, context, chat_id)

# ═══════════════════════════════════════
#         GOLIBNI TEKSHIRISH
# ═══════════════════════════════════════
async def check_winner(context, chat_id):
    game = games[chat_id]
    alive = alive_players(game)
    mafia_alive = [uid for uid, p in alive.items() if p["role"] == "mafia"]
    others_alive = [uid for uid, p in alive.items() if p["role"] != "mafia"]

    if not mafia_alive:
        await context.bot.send_message(
            chat_id=chat_id,
            text="🎉 TINCH AHOLI G'OLIB BO'LDI!\n\nBarcha mafiyalar yo'q qilindi!"
        )
        await end_game(context, chat_id)
        return True

    if len(mafia_alive) >= len(others_alive):
        await context.bot.send_message(
            chat_id=chat_id,
            text="🔴 MAFIYA G'OLIB BO'LDI!\n\nMafiya shaharni egalladi!"
        )
        await end_game(context, chat_id)
        return True

    return False

async def end_game(context, chat_id):
    game = games[chat_id]
    text = "📋 BARCHA ROLLAR:\n━━━━━━━━━━━━━━━━━━\n\n"
    for uid, p in game["players"].items():
        status = "✅" if p["alive"] else "☠️"
        text += f"{status} {p['name']} — {ROLES_INFO[p['role']]}\n"
    await context.bot.send_message(chat_id=chat_id, text=text)
    games[chat_id]["status"] = "ended"

# ═══════════════════════════════════════
#         /STOP
# ═══════════════════════════════════════
async def stop_game(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    if chat_id in games:
        games[chat_id]["status"] = "ended"
        await update.message.reply_text("🛑 O'yin to'xtatildi.")
    else:
        await update.message.reply_text("O'yin yo'q.")

# ═══════════════════════════════════════
#         /START
# ═══════════════════════════════════════
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        f"🎭 MAFIA BOT\n"
        f"━━━━━━━━━━━━━━━━━━\n\n"
        f"Guruhda /mafia yozing — o'yin boshlanadi!\n\n"
        f"Rollar:\n"
        + "\n".join([f"• {v}" for v in ROLES_INFO.values()]) +
        f"\n\n/stop — o'yinni to'xtatish\n/setting — sozlamalar (faqat admin)"
    )

# ═══════════════════════════════════════
#         /SETTING — SOZLAMALAR
# ═══════════════════════════════════════
async def is_group_admin(update, context):
    if update.effective_chat.type == "private":
        return True
    member = await context.bot.get_chat_member(update.effective_chat.id, update.effective_user.id)
    return member.status in ["administrator", "creator"]

async def setting_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type == "private":
        await update.message.reply_text("Sozlamalar faqat guruhda ishlaydi!")
        return

    if not await is_group_admin(update, context):
        await update.message.reply_text("❌ Faqat guruh adminlari sozlashlarni o'zgartirishi mumkin!")
        return

    await show_settings_menu(update.message, context)

async def show_settings_menu(message, context, edit=False):
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

# ───────── ROLLAR MENYUSI ─────────
async def show_roles_menu(message, chat_id):
    s = get_settings(chat_id)
    kb = []
    for r in TOGGLEABLE_ROLES:
        status = "✅" if s["roles"][r] else "❌"
        label = ROLES_INFO[r].split(" —")[0]
        kb.append([InlineKeyboardButton(f"{status} {label}", callback_data=f"set_role_{r}")])
    kb.append([InlineKeyboardButton("◀️ Ortga", callback_data="set_back")])

    text = (
        "🎭 ROLLAR SOZLAMASI\n━━━━━━━━━━━━━━━━━━\n\n"
        "✅ — yoqilgan, ❌ — o'chirilgan\n"
        "Bosish bilan yoqing/o'chiring.\n\n"
        "🔴 Mafia va ⚪ Tinch aholi doim yoqilgan."
    )
    await message.edit_text(text, reply_markup=InlineKeyboardMarkup(kb))

# ───────── VAQTLAR MENYUSI ─────────
async def show_times_menu(message, chat_id):
    kb = [
        [InlineKeyboardButton("📝 Registratsiya", callback_data="set_time_join_time")],
        [InlineKeyboardButton("🌙 Tun", callback_data="set_time_night_time")],
        [InlineKeyboardButton("☀️ Kun (ovoz berish)", callback_data="set_time_day_time")],
        [InlineKeyboardButton("◀️ Ortga", callback_data="set_back")],
    ]
    s = get_settings(chat_id)
    text = (
        "⏱ VAQTLAR SOZLAMASI\n━━━━━━━━━━━━━━━━━━\n\n"
        f"📝 Registratsiya: {s['join_time']} sek\n"
        f"🌙 Tun: {s['night_time']} sek\n"
        f"☀️ Kun: {s['day_time']} sek\n\n"
        "Qaysi vaqtni o'zgartirmoqchisiz?"
    )
    await message.edit_text(text, reply_markup=InlineKeyboardMarkup(kb))

# ───────── VAQT QIYMATLARI MENYUSI ─────────
async def show_time_options(message, chat_id, time_key):
    s = get_settings(chat_id)
    current = s[time_key]
    kb = []
    row = []
    for val in TIME_OPTIONS:
        mark = "🔘" if val == current else "⚪"
        row.append(InlineKeyboardButton(f"{mark} {val}", callback_data=f"set_timeval_{time_key}_{val}"))
        if len(row) == 2:
            kb.append(row)
            row = []
    if row:
        kb.append(row)
    kb.append([InlineKeyboardButton("◀️ Ortga", callback_data="set_times")])

    names = {"join_time": "Registratsiya", "night_time": "Tun", "day_time": "Kun"}
    text = f"⏱ {names[time_key]} vaqtini tanlang (sekund):"
    await message.edit_text(text, reply_markup=InlineKeyboardMarkup(kb))

# ───────── CALLBACK HANDLER ─────────
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
        await query.answer()
        return

    if data == "set_back":
        await show_settings_menu(query.message, context, edit=True)
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
        time_key = data.replace("set_time_", "")
        await show_time_options(query.message, chat_id, time_key)

    await query.answer()



# ═══════════════════════════════════════
#         MAIN
# ═══════════════════════════════════════
def main():
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("mafia", mafia_start))
    app.add_handler(CommandHandler("stop", stop_game))
    app.add_handler(CommandHandler("setting", setting_command))
    app.add_handler(CallbackQueryHandler(join_callback, pattern="^join$"))
    app.add_handler(CallbackQueryHandler(jony_pick_callback, pattern="^jonypick_"))
    app.add_handler(CallbackQueryHandler(night_callback, pattern="^night_"))
    app.add_handler(CallbackQueryHandler(vote_callback, pattern="^vote_"))
    app.add_handler(CallbackQueryHandler(settings_callback, pattern="^set_"))
    print("✅ Mafia Bot ishga tushdi!")
    app.run_polling()

if __name__ == "__main__":
    main()
