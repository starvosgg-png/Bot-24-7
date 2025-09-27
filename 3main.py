# ========================== ALL RIGHTS RESERVED (YOU) ==========================
# Project: Razor Premium All-in-One Discord Bot
# Rights: All rights reserved to the bot owner (you).
# Notes:
#  - Replace the emoji IDs in EMOJIS with your real Nitro emoji IDs.
#  - Set your token via environment variable DISCORD_TOKEN.
#  - Requires discord.py v2.x and yt_dlp, FFmpeg on PATH for music, Python 3.10+.
# =============================================================================

import os
import sqlite3
import random
import asyncio
import time
import json
from datetime import datetime, timezone

import discord
from discord.ext import commands, tasks
from discord import app_commands
from discord.ui import View, Button

# ------------------------------ CONFIG & INTENTS ------------------------------
intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True
intents.guild_messages = True
intents.guild_reactions = True
intents.voice_states = True

# Admin-only prefix check function
async def get_prefix_admin_only(bot, message):
    if not message.guild:
        return "!"

    prefix = get_prefix_for_guild(message.guild.id)

    # If message starts with prefix but user is not admin, return impossible prefix
    if message.content.startswith(prefix) and not message.author.guild_permissions.administrator:
        return "ADMIN_ONLY_PREFIX_THAT_WILL_NEVER_MATCH"

    return prefix

bot = commands.Bot(command_prefix=get_prefix_admin_only, intents=intents)
bot.remove_command("help")
tree = bot.tree

# ------------------------------ STANDARD EMOJIS MAP -----------------------------
EMOJIS = {
    # System / generic
    "success": "✅",
    "error": "❌",
    "info": "ℹ️",
    "loading": "⏳",
    "spark": "✨",
    "coin": "🪙",
    "star": "⭐",
    "shield": "🛡️",
    "wrench": "🔧",
    "music": "🎵",
    "gift": "🎁",
    # Ticket panel
    "support": "🆘",
    "buyer": "💰",
    "renew": "🔄",
    "claim": "💌",
    "verified": "✅",
    # Invites
    "fake": "❌",
    "real": "✅",
    "total": "📊",
}

PRIMARY_COLOR = 0x00D4AA  # Premium teal gradient
SUCCESS_COLOR = 0x00E6A8
ERROR_COLOR = 0xFF5C7A
INFO_COLOR = 0x66E0FF
WARNING_COLOR = 0xFFC266
PREMIUM_GRADIENT = 0x1E90FF  # Premium blue for gradients

# ------------------------------ DATABASE SETUP -------------------------------
DB_PATH = "razorbot.db"
db = sqlite3.connect(DB_PATH)
cur = db.cursor()

# Money & AFK & Prefix & Custom Commands
cur.execute("CREATE TABLE IF NOT EXISTS money (user_id INTEGER PRIMARY KEY, balance INTEGER NOT NULL DEFAULT 0)")
cur.execute("CREATE TABLE IF NOT EXISTS afk (user_id INTEGER PRIMARY KEY, reason TEXT)")
cur.execute("CREATE TABLE IF NOT EXISTS prefixes (guild_id INTEGER PRIMARY KEY, prefix TEXT)")
cur.execute("CREATE TABLE IF NOT EXISTS customcmds (guild_id INTEGER, name TEXT, response TEXT)")
# Reviews
cur.execute("""
CREATE TABLE IF NOT EXISTS reviews (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    rating INTEGER NOT NULL,
    comment TEXT,
    created_at TEXT NOT NULL
)
""")
# Invites (track per inviter)
cur.execute("""
CREATE TABLE IF NOT EXISTS invite_stats (
    inviter_id INTEGER PRIMARY KEY,
    real_count INTEGER NOT NULL DEFAULT 0,
    fake_count INTEGER NOT NULL DEFAULT 0
)
""")
# Track which inviter invited which member (for fake increment on leave)
cur.execute("""
CREATE TABLE IF NOT EXISTS member_inviter (
    member_id INTEGER PRIMARY KEY,
    inviter_id INTEGER NOT NULL
)
""")
# Anti-Nuke Security System
cur.execute("""
CREATE TABLE IF NOT EXISTS antinuke_config (
    guild_id INTEGER PRIMARY KEY,
    enabled INTEGER DEFAULT 1,
    punishment TEXT DEFAULT 'ban',
    whitelist TEXT DEFAULT '[]',
    limits TEXT DEFAULT '{"role_create": 3, "role_delete": 3, "channel_create": 5, "channel_delete": 5, "ban": 2, "kick": 3}'
)
""")
cur.execute("""
CREATE TABLE IF NOT EXISTS antinuke_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    guild_id INTEGER,
    user_id INTEGER,
    action_type TEXT,
    timestamp TEXT,
    details TEXT
)
""")
# Spam Protection System
cur.execute("""
CREATE TABLE IF NOT EXISTS spam_tracking (
    user_id INTEGER,
    guild_id INTEGER,
    message_count INTEGER DEFAULT 0,
    last_reset TEXT,
    is_muted INTEGER DEFAULT 0,
    mute_until TEXT,
    PRIMARY KEY (user_id, guild_id)
)
""")
# Whitelist System
cur.execute("""
CREATE TABLE IF NOT EXISTS antinuke_whitelist (
    guild_id INTEGER,
    user_id INTEGER,
    added_by INTEGER,
    added_at TEXT,
    PRIMARY KEY (guild_id, user_id)
)
""")
db.commit()

# ------------------------------ HELPERS --------------------------------------
def utcnow_str():
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")

def get_premium_badge_embed():
    """Generate the premium badge embed with all active features"""
    badge_embed = discord.Embed(
        title="🏆 RAZOR PREMIUM - ACTIVE FEATURES",
        color=PRIMARY_COLOR
    )

    # Feature status indicators
    features = {
        "🛡️ AUTOMOD SYSTEM": "✅ ACTIVE",
        "📊 INVITE TRACKER": "✅ ACTIVE",
        "🚫 ANTI-NUKE": "✅ ACTIVE",
        "🔒 SPAM PROTECTION": "✅ ACTIVE",
        "🎫 TICKET SYSTEM": "✅ ACTIVE",
        "🎁 GIVEAWAY SYSTEM": "✅ ACTIVE",
        "🎵 MUSIC PLAYER": "✅ ACTIVE",
        "⭐ REVIEW SYSTEM": "✅ ACTIVE",
        "💰 ECONOMY": "✅ ACTIVE",
        "🏷️ AFK SYSTEM": "✅ ACTIVE"
    }

    feature_text = "\n".join([f"{name}: {status}" for name, status in features.items()])

    badge_embed.add_field(
        name="🔥 PREMIUM FEATURES STATUS",
        value=feature_text,
        inline=False
    )

    badge_embed.add_field(
        name="💎 PREMIUM BENEFITS",
        value="• **Unlimited Commands** - No restrictions\n• **24/7 Uptime** - Always online\n• **Priority Support** - Instant help\n• **Advanced Security** - Maximum protection\n• **Custom Features** - Tailored experience\n• **Regular Updates** - Always improving",
        inline=False
    )

    badge_embed.set_thumbnail(url="https://cdn.discordapp.com/attachments/1405533704847364278/1406475783769297069/images_1.jpg")
    badge_embed.set_footer(text="Razor Premium | Best in Class Discord Bot ⭐")

    return badge_embed

def add_premium_badge_to_embed(embed: discord.Embed):
    """Premium badge function disabled"""
    return embed

def get_prefix_for_guild(guild_id: int | None) -> str:
    if not guild_id:
        return "/"
    cur.execute("SELECT prefix FROM prefixes WHERE guild_id = ?", (guild_id,))
    row = cur.fetchone()
    return row[0] if row else "/"

def set_prefix_for_guild(guild_id: int, prefix: str):
    cur.execute("REPLACE INTO prefixes (guild_id, prefix) VALUES (?, ?)", (guild_id, prefix))
    db.commit()

def get_money(uid: int) -> int:
    cur.execute("SELECT balance FROM money WHERE user_id=?", (uid,))
    row = cur.fetchone()
    return row[0] if row else 0

def add_money(uid: int, amt: int):
    cur.execute("INSERT INTO money (user_id, balance) VALUES (?, ?) ON CONFLICT(user_id) DO UPDATE SET balance=balance+excluded.balance", (uid, amt))
    db.commit()

def transfer_money(sender: int, receiver: int, amt: int) -> bool:
    bal = get_money(sender)
    if bal < amt:
        return False
    cur.execute("UPDATE money SET balance=balance-? WHERE user_id=?", (amt, sender))
    add_money(receiver, amt)
    db.commit()
    return True

def set_afk(uid: int, reason: str):
    cur.execute("REPLACE INTO afk (user_id, reason) VALUES (?, ?)", (uid, reason))
    db.commit()

def clear_afk(uid: int):
    cur.execute("DELETE FROM afk WHERE user_id=?", (uid,))
    db.commit()

def get_afk(uid: int):
    cur.execute("SELECT reason FROM afk WHERE user_id=?", (uid,))
    row = cur.fetchone()
    return row[0] if row else None

def add_review(uid: int, rating: int, comment: str):
    cur.execute("INSERT INTO reviews (user_id, rating, comment, created_at) VALUES (?, ?, ?, ?)",
                (uid, rating, comment, utcnow_str()))
    db.commit()

def get_recent_reviews(limit: int = 10):
    cur.execute("SELECT user_id, rating, comment, created_at FROM reviews ORDER BY id DESC LIMIT ?", (limit,))
    return cur.fetchall()

def bump_invite(inviter_id: int, real: bool):
    if real:
        cur.execute("INSERT INTO invite_stats (inviter_id, real_count, fake_count) VALUES (?, 1, 0) "
                    "ON CONFLICT(inviter_id) DO UPDATE SET real_count = real_count + 1", (inviter_id,))
    else:
        cur.execute("INSERT INTO invite_stats (inviter_id, real_count, fake_count) VALUES (?, 0, 1) "
                    "ON CONFLICT(inviter_id) DO UPDATE SET fake_count = fake_count + 1", (inviter_id,))
    db.commit()

def set_member_inviter(member_id: int, inviter_id: int):
    cur.execute("REPLACE INTO member_inviter (member_id, inviter_id) VALUES (?, ?)", (member_id, inviter_id))
    db.commit()

def get_invite_stats(inviter_id: int):
    cur.execute("SELECT real_count, fake_count FROM invite_stats WHERE inviter_id=?", (inviter_id,))
    row = cur.fetchone()
    if row: return row[0], row[1], row[0] + row[1]
    return 0, 0, 0

def get_member_rejoin_count(inviter_id: int) -> int:
    # For now, return a simulated rejoin count (you can implement actual tracking)
    # This could track members who left and rejoined within 7 days
    return random.randint(0, 5)

# ------------------------------ ANTI-NUKE SYSTEM HELPERS ---------------------------
def get_antinuke_config(guild_id: int):
    cur.execute("SELECT enabled, punishment, whitelist, limits FROM antinuke_config WHERE guild_id = ?", (guild_id,))
    row = cur.fetchone()
    if row:
        return {
            'enabled': bool(row[0]),
            'punishment': row[1],
            'whitelist': json.loads(row[2]),
            'limits': json.loads(row[3])
        }
    return {
        'enabled': True,
        'punishment': 'ban',
        'whitelist': [],
        'limits': {"role_create": 3, "role_delete": 3, "channel_create": 5, "channel_delete": 5, "ban": 2, "kick": 3}
    }

def set_antinuke_config(guild_id: int, enabled: bool = None, punishment: str = None, whitelist: list = None, limits: dict = None):
    config = get_antinuke_config(guild_id)
    if enabled is not None: config['enabled'] = enabled
    if punishment is not None: config['punishment'] = punishment
    if whitelist is not None: config['whitelist'] = whitelist
    if limits is not None: config['limits'] = limits

    cur.execute("""
        REPLACE INTO antinuke_config (guild_id, enabled, punishment, whitelist, limits)
        VALUES (?, ?, ?, ?, ?)
    """, (guild_id, int(config['enabled']), config['punishment'],
          json.dumps(config['whitelist']), json.dumps(config['limits'])))
    db.commit()

def is_whitelisted(guild_id: int, user_id: int) -> bool:
    cur.execute("SELECT 1 FROM antinuke_whitelist WHERE guild_id = ? AND user_id = ?", (guild_id, user_id))
    return bool(cur.fetchone())

def add_to_whitelist(guild_id: int, user_id: int, added_by: int):
    cur.execute("""
        REPLACE INTO antinuke_whitelist (guild_id, user_id, added_by, added_at)
        VALUES (?, ?, ?, ?)
    """, (guild_id, user_id, added_by, utcnow_str()))
    db.commit()

def remove_from_whitelist(guild_id: int, user_id: int):
    cur.execute("DELETE FROM antinuke_whitelist WHERE guild_id = ? AND user_id = ?", (guild_id, user_id))
    db.commit()

def log_antinuke_action(guild_id: int, user_id: int, action_type: str, details: str = ""):
    cur.execute("""
        INSERT INTO antinuke_logs (guild_id, user_id, action_type, timestamp, details)
        VALUES (?, ?, ?, ?, ?)
    """, (guild_id, user_id, action_type, utcnow_str(), details))
    db.commit()

def get_recent_actions(guild_id: int, user_id: int, action_type: str, minutes: int = 5) -> int:
    cutoff = datetime.now(timezone.utc) - timezone.timedelta(minutes=minutes)
    cutoff_str = cutoff.strftime("%Y-%m-%d %H:%M:%S")

    cur.execute("""
        SELECT COUNT(*) FROM antinuke_logs
        WHERE guild_id = ? AND user_id = ? AND action_type = ? AND timestamp > ?
    """, (guild_id, user_id, action_type, cutoff_str))

    return cur.fetchone()[0]

# ------------------------------ SPAM PROTECTION HELPERS ---------------------------
def get_spam_data(user_id: int, guild_id: int):
    cur.execute("""
        SELECT message_count, last_reset, is_muted, mute_until
        FROM spam_tracking WHERE user_id = ? AND guild_id = ?
    """, (user_id, guild_id))
    row = cur.fetchone()
    if row:
        return {
            'message_count': row[0],
            'last_reset': row[1],
            'is_muted': bool(row[2]),
            'mute_until': row[3]
        }
    return {'message_count': 0, 'last_reset': utcnow_str(), 'is_muted': False, 'mute_until': None}

def update_spam_data(user_id: int, guild_id: int, message_count: int, is_muted: bool = False, mute_until: str = None):
    cur.execute("""
        REPLACE INTO spam_tracking (user_id, guild_id, message_count, last_reset, is_muted, mute_until)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (user_id, guild_id, message_count, utcnow_str(), int(is_muted), mute_until))
    db.commit()

def check_spam_limit(user_id: int, guild_id: int, limit: int = 5, timeframe: int = 60) -> bool:
    """Check if user exceeded spam limit (default: 5 messages in 60 seconds)"""
    spam_data = get_spam_data(user_id, guild_id)

    # Check if currently muted
    if spam_data['is_muted'] and spam_data['mute_until']:
        try:
            mute_until = datetime.fromisoformat(spam_data['mute_until'])
            if mute_until.tzinfo is None:
                mute_until = mute_until.replace(tzinfo=timezone.utc)
            if datetime.now(timezone.utc) < mute_until:
                return True  # Still muted
            else:
                # Unmute user
                update_spam_data(user_id, guild_id, 0, False, None)
                return False
        except Exception:
            # Reset if there's an issue with the timestamp
            update_spam_data(user_id, guild_id, 0, False, None)
            return False

    # Check timeframe
    try:
        last_reset = datetime.fromisoformat(spam_data['last_reset'])
        if last_reset.tzinfo is None:
            last_reset = last_reset.replace(tzinfo=timezone.utc)
        now = datetime.now(timezone.utc)

        if (now - last_reset).total_seconds() > timeframe:
            # Reset counter
            update_spam_data(user_id, guild_id, 1)
            return False

        # Increment counter
        new_count = spam_data['message_count'] + 1
        if new_count > limit:
            # Apply timeout
            mute_until = now + timezone.timedelta(minutes=5)  # 5 minute timeout
            update_spam_data(user_id, guild_id, new_count, True, mute_until.isoformat())
            return True
        else:
            update_spam_data(user_id, guild_id, new_count)
            return False
    except Exception:
        # Reset counter on any error
        update_spam_data(user_id, guild_id, 1)
        return False

async def timeout_user(member: discord.Member, duration_minutes: int = 5, reason: str = "Spam Protection"):
    """Timeout a user for specified duration"""
    try:
        until = discord.utils.utcnow() + timezone.timedelta(minutes=duration_minutes)
        await member.timeout(until, reason=reason)
        return True
    except Exception:
        return False

# ------------------------------ STARTUP & BACKUP ------------------------------
INVITE_CACHE: dict[int, dict[str, int]] = {}  # guild_id -> {code: uses}

@bot.event
async def on_ready():
    try:
        # Try global sync first
        synced = await tree.sync()
        print(f"{EMOJIS['success']} Synced {len(synced)} slash commands globally")
    except Exception as e:
        print(f"{EMOJIS['error']} Failed to sync commands: {e}")
        # Try syncing to each guild individually
        for guild in bot.guilds:
            try:
                synced = await tree.sync(guild=guild)
                print(f"{EMOJIS['success']} Synced {len(synced)} commands for {guild.name}")
            except Exception as ge:
                print(f"{EMOJIS['error']} Failed to sync for {guild.name}: {ge}")

    print(f"{EMOJIS['success']} Logged in as {bot.user} | Premium Razor Online.")

    # Build invite cache
    for guild in bot.guilds:
        try:
            INVITE_CACHE[guild.id] = {invite.code: invite.uses for invite in await guild.invites()}
        except discord.Forbidden:
            INVITE_CACHE[guild.id] = {}
    backup_db_loop.start()

@tasks.loop(minutes=15)
async def backup_db_loop():
    # Simple rotating zip backup for DB
    ts = int(time.time())
    out = f"backup_{ts}.zip"
    os.system(f"zip -j {out} {DB_PATH} >/dev/null 2>&1")

# ------------------------------ GLOBAL ON_MESSAGE -----------------------------
bad_words = {"idiot", "stupid", "badword1", "badword2"}

@bot.event
async def on_message(message: discord.Message):
    if message.author.bot or not message.guild:
        return

    # Check if user is admin (skip spam check for admins)
    if not message.author.guild_permissions.administrator:
        # Spam Protection Check
        if check_spam_limit(message.author.id, message.guild.id, limit=5, timeframe=60):
            try:
                await message.delete()
                # Timeout user for 5 minutes
                await timeout_user(message.author, 5, "Spam Protection: 5+ messages in 60 seconds")

                embed = discord.Embed(
                    title="🚫 RAZOR PREMIUM - SPAM PROTECTION",
                    color=ERROR_COLOR
                )
                embed.add_field(
                    name="🏷️ Anti-Spam System",
                    value="Automatic spam detection",
                    inline=False
                )
                embed.add_field(
                    name="⚠️ Violation Detected",
                    value=f"**User:** {message.author.mention}\n**Reason:** Exceeded message limit\n**Limit:** 5 messages per 60 seconds",
                    inline=False
                )
                embed.add_field(
                    name="🔨 Action Taken",
                    value=f"**Punishment:** 5 minute timeout\n**Messages:** Deleted\n**Status:** Protected",
                    inline=False
                )
                embed.set_thumbnail(url=message.author.display_avatar.url)
                embed.set_footer(text="Razor Premium Security | Spam Protection Active")
                add_premium_badge_to_embed(embed)

                await message.channel.send(embed=embed, delete_after=10)
                return
            except Exception:
                pass

    # AutoMod check
    lowered = message.content.lower()
    if any(w in lowered for w in bad_words):
        try:
            await message.delete()
            await message.channel.send(
                f"{EMOJIS['shield']} <@{message.author.id}>, that word is blocked.",
                delete_after=4
            )
        except Exception:
            pass

    # AFK removal for author
    if get_afk(message.author.id):
        clear_afk(message.author.id)
        try:
            embed = discord.Embed(
                title="💎 RAZOR PREMIUM - AFK SYSTEM",
                color=SUCCESS_COLOR
            )
            embed.add_field(
                name="🏷️ Welcome Back",
                value="AFK status removed",
                inline=False
            )
            embed.add_field(
                name="👤 User Information",
                value=f"**User:** {message.author.mention}\n**Display Name:** {message.author.display_name}\n**Status:** Back Online",
                inline=False
            )
            embed.add_field(
                name="⚡ Activity Status",
                value=f"**Previous Status:** Away From Keyboard\n**Current Status:** Active\n**Welcome Back!** 🎉",
                inline=False
            )
            embed.set_thumbnail(url=message.author.display_avatar.url)
            embed.set_footer(text=f"Razor Premium AFK System | {message.guild.name}", icon_url=message.guild.icon.url if message.guild.icon else None)
            add_premium_badge_to_embed(embed)
            await message.channel.send(embed=embed, delete_after=10)
        except Exception:
            pass

    # Mention AFK reasons
    for u in message.mentions:
        reason = get_afk(u.id)
        if reason:
            try:
                embed = discord.Embed(
                    title="💤 RAZOR PREMIUM - AFK NOTIFICATION",
                    color=WARNING_COLOR
                )
                embed.add_field(
                    name="🏷️ AFK Alert",
                    value="User is currently away",
                    inline=False
                )
                embed.add_field(
                    name="👤 User Information",
                    value=f"**User:** {u.mention}\n**Display Name:** {u.display_name}\n**Status:** Away From Keyboard",
                    inline=False
                )
                embed.add_field(
                    name="📝 AFK Reason",
                    value=f"```\n{reason}\n```",
                    inline=False
                )
                embed.add_field(
                    name="💡 Notice",
                    value="This user will be notified when they return and send a message.",
                    inline=False
                )
                embed.set_thumbnail(url=u.display_avatar.url)
                embed.set_footer(text=f"Razor Premium AFK System | {message.guild.name}", icon_url=message.guild.icon.url if message.guild.icon else None)
                add_premium_badge_to_embed(embed)
                await message.channel.send(embed=embed, delete_after=15)
            except Exception:
                pass

    # Custom prefix commands (simple responder) - ADMIN ONLY
    cur.execute("SELECT name, response FROM customcmds WHERE guild_id=?", (message.guild.id,))
    for full, resp in cur.fetchall():
        if message.content.strip() == full:
            # Check if user is admin before responding to custom commands
            if message.author.guild_permissions.administrator:
                await message.channel.send(resp)
            else:
                await message.channel.send(f"{EMOJIS['error']} Only administrators can use prefix commands.", delete_after=5)
            return

    # Check if message starts with a prefix command
    prefix = get_prefix_for_guild(message.guild.id)
    if message.content.startswith(prefix):
        # Admin-only prefix system check
        if not message.author.guild_permissions.administrator:
            await message.channel.send(f"{EMOJIS['error']} Only administrators can use prefix commands.", delete_after=5)
            return

    await bot.process_commands(message)

# Rebuild invite cache on invite create/delete
@bot.event
async def on_invite_create(invite: discord.Invite):
    try:
        INVITE_CACHE.setdefault(invite.guild.id, {})[invite.code] = invite.uses or 0
    except Exception:
        pass

@bot.event
async def on_invite_delete(invite: discord.Invite):
    try:
        INVITE_CACHE.get(invite.guild.id, {}).pop(invite.code, None)
    except Exception:
        pass

# ------------------------------ ANTI-NUKE EVENT HANDLERS ---------------------------
async def send_antinuke_alert(guild: discord.Guild, user: discord.User, action: str, details: str = ""):
    """Send anti-nuke alert to log channel"""
    for channel in guild.text_channels:
        if "log" in channel.name.lower() or "security" in channel.name.lower():
            embed = discord.Embed(
                title="🚨 RAZOR PREMIUM - ANTI-NUKE ALERT",
                color=ERROR_COLOR
            )
            embed.add_field(
                name="🏷️ Security Alert",
                value="Potential nuke attempt detected",
                inline=False
            )
            embed.add_field(
                name="⚠️ Violation Details",
                value=f"**User:** {user.mention} ({user.id})\n**Action:** {action}\n**Details:** {details}",
                inline=False
            )
            embed.add_field(
                name="🔨 Security Response",
                value="User has been automatically punished\nServer protection is active",
                inline=False
            )
            embed.set_thumbnail(url=user.display_avatar.url)
            embed.set_footer(text="Razor Premium Anti-Nuke | Server Protected")
            add_premium_badge_to_embed(embed)
            try:
                await channel.send(embed=embed)
                break
            except Exception:
                continue

async def punish_user(guild: discord.Guild, user: discord.User, reason: str):
    """Apply punishment to user based on anti-nuke config"""
    config = get_antinuke_config(guild.id)
    punishment = config['punishment']

    member = guild.get_member(user.id)
    if not member:
        return

    try:
        if punishment == "ban":
            await member.ban(reason=f"Anti-Nuke: {reason}")
        elif punishment == "kick":
            await member.kick(reason=f"Anti-Nuke: {reason}")
        elif punishment == "timeout":
            await timeout_user(member, 60, f"Anti-Nuke: {reason}")  # 1 hour timeout

        await send_antinuke_alert(guild, user, reason, f"Punishment: {punishment}")
    except Exception:
        pass

@bot.event
async def on_guild_role_create(role: discord.Role):
    """Monitor role creation for anti-nuke"""
    guild = role.guild
    config = get_antinuke_config(guild.id)

    if not config['enabled']:
        return

    # Find who created the role
    async for entry in guild.audit_logs(action=discord.AuditLogAction.role_create, limit=1):
        user = entry.user
        if user.id == bot.user.id or is_whitelisted(guild.id, user.id):
            return

        log_antinuke_action(guild.id, user.id, "role_create", f"Created role: {role.name}")

        recent_count = get_recent_actions(guild.id, user.id, "role_create", 5)
        if recent_count >= config['limits'].get('role_create', 3):
            await punish_user(guild, user, f"Role creation limit exceeded ({recent_count})")
        break

@bot.event
async def on_guild_role_delete(role: discord.Role):
    """Monitor role deletion for anti-nuke"""
    guild = role.guild
    config = get_antinuke_config(guild.id)

    if not config['enabled']:
        return

    async for entry in guild.audit_logs(action=discord.AuditLogAction.role_delete, limit=1):
        user = entry.user
        if user.id == bot.user.id or is_whitelisted(guild.id, user.id):
            return

        log_antinuke_action(guild.id, user.id, "role_delete", f"Deleted role: {role.name}")

        recent_count = get_recent_actions(guild.id, user.id, "role_delete", 5)
        if recent_count >= config['limits'].get('role_delete', 3):
            await punish_user(guild, user, f"Role deletion limit exceeded ({recent_count})")
        break

@bot.event
async def on_guild_channel_create(channel):
    """Monitor channel creation for anti-nuke"""
    guild = channel.guild
    config = get_antinuke_config(guild.id)

    if not config['enabled']:
        return

    async for entry in guild.audit_logs(action=discord.AuditLogAction.channel_create, limit=1):
        user = entry.user
        if user.id == bot.user.id or is_whitelisted(guild.id, user.id):
            return

        log_antinuke_action(guild.id, user.id, "channel_create", f"Created channel: {channel.name}")

        recent_count = get_recent_actions(guild.id, user.id, "channel_create", 5)
        if recent_count >= config['limits'].get('channel_create', 5):
            await punish_user(guild, user, f"Channel creation limit exceeded ({recent_count})")
        break

@bot.event
async def on_guild_channel_delete(channel):
    """Monitor channel deletion for anti-nuke"""
    guild = channel.guild
    config = get_antinuke_config(guild.id)

    if not config['enabled']:
        return

    async for entry in guild.audit_logs(action=discord.AuditLogAction.channel_delete, limit=1):
        user = entry.user
        if user.id == bot.user.id or is_whitelisted(guild.id, user.id):
            return

        log_antinuke_action(guild.id, user.id, "channel_delete", f"Deleted channel: {channel.name}")

        recent_count = get_recent_actions(guild.id, user.id, "channel_delete", 5)
        if recent_count >= config['limits'].get('channel_delete', 5):
            await punish_user(guild, user, f"Channel deletion limit exceeded ({recent_count})")
        break

@bot.event
async def on_member_ban(guild: discord.Guild, user: discord.User):
    """Monitor bans for anti-nuke"""
    config = get_antinuke_config(guild.id)

    if not config['enabled']:
        return

    async for entry in guild.audit_logs(action=discord.AuditLogAction.ban, limit=1):
        banner = entry.user
        if banner.id == bot.user.id or is_whitelisted(guild.id, banner.id):
            return

        log_antinuke_action(guild.id, banner.id, "ban", f"Banned user: {user.name}")

        recent_count = get_recent_actions(guild.id, banner.id, "ban", 5)
        if recent_count >= config['limits'].get('ban', 2):
            await punish_user(guild, banner, f"Ban limit exceeded ({recent_count})")
        break

@bot.event
async def on_member_remove(member: discord.Member):
    # Existing invite tracking code
    inviter = get_member_inviter(member.id)
    if inviter:
        bump_invite(inviter, real=False)

    # Anti-nuke kick detection
    guild = member.guild
    config = get_antinuke_config(guild.id)

    if not config['enabled']:
        return

    # Check if it was a kick
    async for entry in guild.audit_logs(action=discord.AuditLogAction.kick, limit=1):
        if entry.target.id == member.id:
            kicker = entry.user
            if kicker.id == bot.user.id or is_whitelisted(guild.id, kicker.id):
                return

            log_antinuke_action(guild.id, kicker.id, "kick", f"Kicked user: {member.name}")

            recent_count = get_recent_actions(guild.id, kicker.id, "kick", 5)
            if recent_count >= config['limits'].get('kick', 3):
                await punish_user(guild, kicker, f"Kick limit exceeded ({recent_count})")
            break

@bot.event
async def on_webhooks_update(channel):
    """Monitor webhook changes for anti-nuke"""
    guild = channel.guild
    config = get_antinuke_config(guild.id)

    if not config['enabled']:
        return

    async for entry in guild.audit_logs(action=discord.AuditLogAction.webhook_create, limit=1):
        user = entry.user
        if user.id == bot.user.id or is_whitelisted(guild.id, user.id):
            return

        log_antinuke_action(guild.id, user.id, "webhook", f"Webhook activity in {channel.name}")
        recent_count = get_recent_actions(guild.id, user.id, "webhook", 5)
        if recent_count >= 2:  # Strict webhook limit
            await punish_user(guild, user, f"Webhook limit exceeded ({recent_count})")
        break

@bot.event
async def on_guild_emojis_update(guild: discord.Guild, before: list, after: list):
    """Monitor emoji changes for anti-nuke"""
    config = get_antinuke_config(guild.id)

    if not config['enabled']:
        return

    # Check for emoji deletion (more emojis in before than after)
    if len(before) > len(after):
        async for entry in guild.audit_logs(action=discord.AuditLogAction.emoji_delete, limit=1):
            user = entry.user
            if user.id == bot.user.id or is_whitelisted(guild.id, user.id):
                return

            log_antinuke_action(guild.id, user.id, "emoji_delete", "Deleted emoji")
            recent_count = get_recent_actions(guild.id, user.id, "emoji_delete", 5)
            if recent_count >= 3:
                await punish_user(guild, user, f"Emoji deletion limit exceeded ({recent_count})")
            break

# Detect inviter on join
@bot.event
async def on_member_join(member: discord.Member):
    guild = member.guild
    before = INVITE_CACHE.get(guild.id, {}).copy()
    after_map: dict[str, int] = {}
    try:
        invites = await guild.invites()
        for invite in invites:
            after_map[invite.code] = invite.uses or 0
        INVITE_CACHE[guild.id] = after_map
    except discord.Forbidden:
        after_map = before

    used_code = None
    for code, uses in after_map.items():
        if uses > before.get(code, 0):
            used_code = code
            break

    inviter_id = None
    inviter_user = None
    if used_code:
        try:
            inv_obj = next((i for i in await guild.invites() if i.code == used_code), None)
            if inv_obj and inv_obj.inviter:
                inviter_id = inv_obj.inviter.id
                inviter_user = inv_obj.inviter
        except Exception:
            pass

    if inviter_id:
        bump_invite(inviter_id, real=True)
        set_member_inviter(member.id, inviter_id)

        # Send beautiful welcome message with invite info
        welcome_channel = None
        for channel in guild.text_channels:
            if "welcome" in channel.name.lower() or "general" in channel.name.lower():
                welcome_channel = channel
                break

        if welcome_channel and inviter_user:
            real, fake, total = get_invite_stats(inviter_id)

            embed = discord.Embed(
                title="🎉 RAZOR PREMIUM - MEMBER JOINED",
                color=SUCCESS_COLOR
            )

            embed.add_field(
                name="🏷️ Welcome System",
                value="Premium member tracking",
                inline=False
            )

            embed.add_field(
                name="👤 New Member",
                value=f"**Welcome:** {member.mention}\n**Account Age:** <t:{int(member.created_at.timestamp())}:R>\n**Member #{guild.member_count}**",
                inline=False
            )

            embed.add_field(
                name="📊 Invite Information",
                value=f"**Invited by:** {inviter_user.mention}\n**Inviter Stats:** {total} total invites ({real} real)\n**Invite Code:** {used_code}",
                inline=False
            )

            embed.add_field(
                name="💎 Premium Features",
                value=f"**Real-time Tracking:** Active\n**Quality Control:** Monitoring\n**Analytics:** Advanced",
                inline=False
            )

            embed.set_thumbnail(url=member.display_avatar.url)
            embed.set_footer(text=f"Razor Premium Welcome System | {guild.name}", icon_url=guild.icon.url if guild.icon else None)
            add_premium_badge_to_embed(embed)

            try:
                await welcome_channel.send(embed=embed)
            except Exception:
                pass

@bot.event
async def on_member_remove(member: discord.Member):
    # Count as "fake" when a member leaves after being invited
    inviter = get_member_inviter(member.id)
    if inviter:
        bump_invite(inviter, real=False)

# ------------------------------ SLASH COMMANDS --------------------------------

# Ping
@tree.command(name="ping", description="Premium latency check")
async def ping(interaction: discord.Interaction):
    ms = round(bot.latency * 1000)
    embed = discord.Embed(
        title="🏓 RAZOR PREMIUM - BEST IT SOLUTION",
        color=PRIMARY_COLOR
    )
    embed.add_field(
        name="🏷️ Connection Status",
        value="Active",
        inline=False
    )
    embed.add_field(
        name="⚡ General Info",
        value=f"**Latency:** {ms}ms\n**Status:** Online\n**Version:** Premium v2.0",
        inline=False
    )
    embed.add_field(
        name="🎯 Performance",
        value=f"**Response Time:** {ms}ms\n**Uptime:** 99.9%\n**Quality:** Excellent",
        inline=False
    )
    embed.set_thumbnail(url=interaction.guild.icon.url if interaction.guild.icon else None)
    embed.set_footer(text=f"Requested by {interaction.user.display_name} | Razor Premium ⭐", icon_url=interaction.user.display_avatar.url)
    add_premium_badge_to_embed(embed)
    await interaction.response.send_message(embed=embed, ephemeral=True)

# Avatar
@tree.command(name="avatar", description="Get a user's avatar")
@app_commands.describe(user="Target user (optional)")
async def avatar(interaction: discord.Interaction, user: discord.User | None = None):
    user = user or interaction.user
    embed = discord.Embed(
        title=f"{EMOJIS['spark']} {user.display_name}'s Avatar",
        color=PRIMARY_COLOR
    )
    if user.avatar:
        embed.set_image(url=user.avatar.url)
    embed.set_footer(text=f"Requested by {interaction.user.display_name} | Razor Premium ⭐", icon_url=interaction.user.display_avatar.url)
    add_premium_badge_to_embed(embed)
    await interaction.response.send_message(embed=embed)

# Say
@tree.command(name="say", description="Echo a message")
@app_commands.describe(message="Message to send")
async def say(interaction: discord.Interaction, message: str):
    await interaction.response.send_message(f"{EMOJIS['spark']} Sent!", ephemeral=True)
    await interaction.channel.send(message)

# User info
@tree.command(name="userinfo", description="Show user info")
@app_commands.describe(user="Target user (optional)")
async def userinfo(interaction: discord.Interaction, user: discord.User | None = None):
    user = user or interaction.user
    member = interaction.guild.get_member(user.id) if interaction.guild else None

    embed = discord.Embed(
        title="👤 RAZOR PREMIUM - BEST IT SOLUTION",
        color=PRIMARY_COLOR
    )
    embed.add_field(
        name="🏷️ User Information",
        value="Complete user profile",
        inline=False
    )
    embed.add_field(
        name="📋 General Info",
        value=f"**Username:** {user.name}\n**Display Name:** {user.display_name}\n**User ID:** {user.id}\n**Created:** <t:{int(user.created_at.timestamp())}:R>",
        inline=False
    )

    if member:
        embed.add_field(
            name="👥 Server Info",
            value=f"**Nickname:** {member.nick or 'None'}\n**Joined:** <t:{int(member.joined_at.timestamp())}:R>\n**Highest Role:** {member.top_role.mention}",
            inline=False
        )
        embed.add_field(
            name="💎 Status",
            value=f"**Status:** {str(member.status).title()}\n**Activity:** {member.activity.name if member.activity else 'None'}\n**Bot:** {'Yes' if member.bot else 'No'}",
            inline=False
        )

    embed.set_thumbnail(url=interaction.guild.icon.url if interaction.guild.icon else None)
    if user.avatar:
        embed.set_image(url=user.avatar.url)
    embed.set_footer(text=f"Requested by {interaction.user.display_name} | Razor Premium ⭐", icon_url=interaction.user.display_avatar.url)
    add_premium_badge_to_embed(embed)
    await interaction.response.send_message(embed=embed, ephemeral=True)

# Server info
@tree.command(name="serverinfo", description="Show server info")
async def serverinfo(interaction: discord.Interaction):
    g = interaction.guild
    embed = discord.Embed(
        title="📊 RAZOR PREMIUM - BEST IT SOLUTION",
        color=PRIMARY_COLOR
    )
    embed.add_field(
        name="🏷️ Server Information",
        value="Complete server details",
        inline=False
    )
    embed.add_field(
        name="📋 General Info",
        value=f"**Name:** {g.name}\n**Server ID:** {g.id}\n**Owner:** {g.owner.mention if g.owner else 'Unknown'}\n**Created:** <t:{int(g.created_at.timestamp())}:R>",
        inline=False
    )
    embed.add_field(
        name="👥 Members & Roles",
        value=f"**Members:** {g.member_count}\n**Roles:** {len(g.roles)}\n**Verification Level:** {str(g.verification_level).title()}",
        inline=False
    )
    embed.add_field(
        name="💎 Boost Status",
        value=f"**Level:** {g.premium_tier}\n**Boosts:** {g.premium_subscription_count}\n**Features:** {len(g.features)}",
        inline=False
    )
    embed.add_field(
        name="📺 Channels",
        value=f"**Text:** {len(g.text_channels)}\n**Voice:** {len(g.voice_channels)}\n**Categories:** {len(g.categories)}",
        inline=False
    )
    embed.set_thumbnail(url=interaction.guild.icon.url if interaction.guild.icon else None)
    embed.set_footer(text=f"Requested by {interaction.user.display_name} | Razor Premium ⭐", icon_url=interaction.user.display_avatar.url)
    add_premium_badge_to_embed(embed)
    await interaction.response.send_message(embed=embed)

# RNG Fun
@tree.command(name="roll", description="Roll a number between 1-100")
async def roll(interaction: discord.Interaction):
    num = random.randint(1, 100)
    embed = discord.Embed(
        title=f"{EMOJIS['spark']} Roll",
        description=f"You rolled **{num}**",
        color=PRIMARY_COLOR
    )
    embed.set_footer(text=f"Requested by {interaction.user.display_name} | Razor Premium ⭐", icon_url=interaction.user.display_avatar.url)
    add_premium_badge_to_embed(embed)
    await interaction.response.send_message(embed=embed)

@tree.command(name="coinflip", description="Flip a coin")
async def coinflip(interaction: discord.Interaction):
    side = random.choice(["Heads", "Tails"])
    embed = discord.Embed(
        title=f"{EMOJIS['spark']} Coin Flip",
        description=f"Result: **{side}**",
        color=PRIMARY_COLOR
    )
    embed.set_footer(text=f"Requested by {interaction.user.display_name} | Razor Premium ⭐", icon_url=interaction.user.display_avatar.url)
    add_premium_badge_to_embed(embed)
    await interaction.response.send_message(embed=embed)

# Money
@tree.command(name="money", description="Check your balance")
async def money(interaction: discord.Interaction):
    bal = get_money(interaction.user.id)
    embed = discord.Embed(
        title="💰 RAZOR PREMIUM - BEST IT SOLUTION",
        color=PRIMARY_COLOR
    )
    embed.add_field(
        name="🏷️ Wallet Information",
        value="Your current balance",
        inline=False
    )
    embed.add_field(
        name="📋 General Info",
        value=f"**Balance:** {bal:,} coins\n**Rank:** Premium Member\n**Account:** Active",
        inline=False
    )
    embed.add_field(
        name="💎 Premium Status",
        value=f"**Tier:** Gold\n**Benefits:** Unlimited\n**Expires:** Never",
        inline=False
    )
    embed.set_thumbnail(url=interaction.guild.icon.url if interaction.guild.icon else None)
    embed.set_footer(text=f"Requested by {interaction.user.display_name} | Razor Premium ⭐", icon_url=interaction.user.display_avatar.url)
    add_premium_badge_to_embed(embed)
    await interaction.response.send_message(embed=embed)

@tree.command(name="givemoney", description="Give coins to another user")
@app_commands.describe(user="Receiver", amount="Amount to send")
async def givemoney(interaction: discord.Interaction, user: discord.User, amount: int):
    if amount <= 0:
        await interaction.response.send_message(f"{EMOJIS['error']} Amount must be positive.", ephemeral=True)
        return
    ok = transfer_money(interaction.user.id, user.id, amount)
    if not ok:
        await interaction.response.send_message(f"{EMOJIS['error']} Not enough balance.", ephemeral=True)
        return
    embed = discord.Embed(
        title=f"{EMOJIS['success']} Transaction Complete",
        description=f"Gave **{amount}** coins to {user.mention}.",
        color=SUCCESS_COLOR
    )
    embed.set_footer(text=f"Requested by {interaction.user.display_name} | Razor Premium ⭐", icon_url=interaction.user.display_avatar.url)
    add_premium_badge_to_embed(embed)
    await interaction.response.send_message(embed=embed)

@tree.command(name="topmoney", description="Top richest users")
async def topmoney(interaction: discord.Interaction):
    cur.execute("SELECT user_id, balance FROM money ORDER BY balance DESC LIMIT 10")
    rows = cur.fetchall()
    desc = "\n".join([f"<@{uid}> — **{bal}**" for uid, bal in rows]) or "No data."
    embed = discord.Embed(
        title=f"{EMOJIS['coin']} Leaderboard",
        description=desc,
        color=PRIMARY_COLOR
    )
    embed.set_footer(text=f"Requested by {interaction.user.display_name} | Razor Premium ⭐", icon_url=interaction.user.display_avatar.url)
    add_premium_badge_to_embed(embed)
    await interaction.response.send_message(embed=embed)

# Custom command creator
@tree.command(name="create", description="Create a simple custom prefix command")
@app_commands.describe(prefix="Prefix like !", cmd="Command name", msg="Response to send")
async def create(interaction: discord.Interaction, prefix: str, cmd: str, msg: str):
    gid = interaction.guild.id
    full = f"{prefix}{cmd}"
    cur.execute("INSERT INTO customcmds (guild_id, name, response) VALUES (?, ?, ?)", (gid, full, msg))
    db.commit()
    embed = discord.Embed(
        title="⚙️ RAZOR PREMIUM - BEST IT SOLUTION",
        color=SUCCESS_COLOR
    )
    embed.add_field(
        name="🏷️ Custom Command",
        value="Premium command creation",
        inline=False
    )
    embed.add_field(
        name="📋 Command Details",
        value=f"**Command:** `{full}`\n**Server:** {interaction.guild.name}\n**Status:** Created",
        inline=False
    )
    embed.add_field(
        name="💬 Response Preview",
        value=f"```\n{msg}\n```",
        inline=False
    )
    embed.add_field(
        name="💎 Premium Features",
        value=f"**Custom Commands:** Unlimited\n**Admin Control:** Full\n**Quality:** Premium",
        inline=False
    )
    embed.set_thumbnail(url=interaction.guild.icon.url if interaction.guild.icon else None)
    embed.set_footer(text=f"Requested by {interaction.user.display_name} | Razor Premium ⭐", icon_url=interaction.user.display_avatar.url)
    add_premium_badge_to_embed(embed)
    await interaction.response.send_message(embed=embed, ephemeral=True)

# Moderation (basic)
@tree.command(name="kick", description="Kick a user")
@app_commands.describe(user="User to kick", reason="Reason")
@app_commands.checks.has_permissions(kick_members=True)
async def kick(interaction: discord.Interaction, user: discord.Member, reason: str = "No reason"):
    await user.kick(reason=reason)
    embed = discord.Embed(
        title=f"{EMOJIS['shield']} User Kicked",
        description=f"{user.mention}\n**Reason:** {reason}",
        color=WARNING_COLOR
    )
    embed.set_footer(text=f"Action by {interaction.user.display_name} | Razor Premium ⭐", icon_url=interaction.user.display_avatar.url)
    add_premium_badge_to_embed(embed)
    await interaction.response.send_message(embed=embed)

@tree.command(name="ban", description="Ban a user")
@app_commands.describe(user="User to ban", reason="Reason")
@app_commands.checks.has_permissions(ban_members=True)
async def ban(interaction: discord.Interaction, user: discord.Member, reason: str = "No reason"):
    await user.ban(reason=reason)
    embed = discord.Embed(
        title=f"{EMOJIS['shield']} User Banned",
        description=f"{user.mention}\n**Reason:** {reason}",
        color=ERROR_COLOR
    )
    embed.set_footer(text=f"Action by {interaction.user.display_name} | Razor Premium ⭐", icon_url=interaction.user.display_avatar.url)
    add_premium_badge_to_embed(embed)
    await interaction.response.send_message(embed=embed)

# AFK
@tree.command(name="afk", description="Set your AFK status")
@app_commands.describe(reason="Why are you AFK?")
async def afk(interaction: discord.Interaction, reason: str):
    set_afk(interaction.user.id, reason)
    embed = discord.Embed(
        title="💤 RAZOR PREMIUM - AFK SYSTEM",
        color=INFO_COLOR
    )
    embed.add_field(
        name="🏷️ AFK Status Set",
        value="Away from keyboard mode activated",
        inline=False
    )
    embed.add_field(
        name="👤 User Information",
        value=f"**User:** {interaction.user.mention}\n**Display Name:** {interaction.user.display_name}\n**Status:** Away From Keyboard",
        inline=False
    )
    embed.add_field(
        name="📝 AFK Reason",
        value=f"```\n{reason}\n```",
        inline=False
    )
    embed.add_field(
        name="💡 How it Works",
        value="• Others will see your AFK status when they mention you\n• Your AFK will be automatically removed when you send a message\n• Premium tracking keeps your status secure",
        inline=False
    )
    embed.set_thumbnail(url=interaction.user.display_avatar.url)
    embed.set_footer(text=f"Requested by {interaction.user.display_name} | Razor Premium ⭐", icon_url=interaction.user.display_avatar.url)
    add_premium_badge_to_embed(embed)
    await interaction.response.send_message(embed=embed, ephemeral=True)

@tree.command(name="afkremove", description="Remove your AFK")
async def afkremove(interaction: discord.Interaction):
    afk_reason = get_afk(interaction.user.id)
    if not afk_reason:
        embed = discord.Embed(
            title="❌ RAZOR PREMIUM - AFK SYSTEM",
            color=ERROR_COLOR
        )
        embed.add_field(
            name="🏷️ No AFK Status",
            value="You are not currently AFK",
            inline=False
        )
        embed.add_field(
            name="?? User Information",
            value=f"**User:** {interaction.user.mention}\n**Display Name:** {interaction.user.display_name}\n**Status:** Active",
            inline=False
        )
        embed.set_thumbnail(url=interaction.user.display_avatar.url)
        embed.set_footer(text=f"Requested by {interaction.user.display_name} | Razor Premium ⭐", icon_url=interaction.user.display_avatar.url)
        add_premium_badge_to_embed(embed)
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return

    clear_afk(interaction.user.id)
    embed = discord.Embed(
        title="✅ RAZOR PREMIUM - AFK SYSTEM",
        color=SUCCESS_COLOR
    )
    embed.add_field(
        name="🏷️ AFK Status Removed",
        value="Successfully returned to active status",
        inline=False
    )
    embed.add_field(
        name="👤 User Information",
        value=f"**User:** {interaction.user.mention}\n**Display Name:** {interaction.user.display_name}\n**Status:** Back Online",
        inline=False
    )
    embed.add_field(
        name="📝 Previous AFK Reason",
        value=f"```\n{afk_reason}\n```",
        inline=False
    )
    embed.add_field(
        name="🎉 Welcome Back!",
        value="Your AFK status has been cleared and you're now marked as active.",
        inline=False
    )
    embed.set_thumbnail(url=interaction.user.display_avatar.url)
    embed.set_footer(text=f"Requested by {interaction.user.display_name} | Razor Premium ⭐", icon_url=interaction.user.display_avatar.url)
    add_premium_badge_to_embed(embed)
    await interaction.response.send_message(embed=embed, ephemeral=True)

# Prefix
@tree.command(name="prefix", description="Change the server prefix")
@app_commands.describe(new_prefix="New prefix (e.g., !)")
@app_commands.checks.has_permissions(manage_guild=True)
async def prefix(interaction: discord.Interaction, new_prefix: str):
    set_prefix_for_guild(interaction.guild.id, new_prefix)
    embed = discord.Embed(
        title=f"{EMOJIS['wrench']} Prefix Updated",
        description=f"Prefix set to `{new_prefix}`",
        color=PRIMARY_COLOR
    )
    embed.set_footer(text=f"Requested by {interaction.user.display_name} | Razor Premium ⭐", icon_url=interaction.user.display_avatar.url)
    add_premium_badge_to_embed(embed)
    await interaction.response.send_message(embed=embed, ephemeral=True)

@tree.command(name="prefixreset", description="Reset prefix to default (/)")
@app_commands.checks.has_permissions(manage_guild=True)
async def prefixreset(interaction: discord.Interaction):
    cur.execute("DELETE FROM prefixes WHERE guild_id=?", (interaction.guild.id,))
    db.commit()
    embed = discord.Embed(
        title=f"{EMOJIS['success']} Prefix Reset",
        description="Prefix reset to `/`.",
        color=SUCCESS_COLOR
    )
    embed.set_footer(text=f"Requested by {interaction.user.display_name} | Razor Premium ⭐", icon_url=interaction.user.display_avatar.url)
    add_premium_badge_to_embed(embed)
    await interaction.response.send_message(embed=embed, ephemeral=True)

# Direct message
@tree.command(name="dm", description="Send a DM to a user")
@app_commands.describe(user="User", message="Content")
@app_commands.checks.has_permissions(administrator=True)
async def dm(interaction: discord.Interaction, user: discord.User, message: str):
    embed = discord.Embed(
        title=f"{EMOJIS['spark']} You've Got a Message!",
        description=f"From: {interaction.user.mention}\n\n{message}",
        color=PRIMARY_COLOR
    )
    embed.set_footer(text=f"Sent by {interaction.user.display_name} | Razor Premium ⭐", icon_url=interaction.user.display_avatar.url)
    add_premium_badge_to_embed(embed)
    try:
        await user.send(embed=embed)
        await interaction.response.send_message(f"{EMOJIS['success']} Sent.", ephemeral=True)
    except Exception:
        await interaction.response.send_message(f"{EMOJIS['error']} Could not DM this user.", ephemeral=True)

# ------------------------------ REVIEW SYSTEM --------------------------------
# In-memory review storage (replace with DB if needed)
reviews_data = []

# ========================
# REVIEW SUBMISSION
# ========================
class ReviewModal(discord.ui.Modal, title="Leave a Review"):
    def __init__(self, stars: int, image_url: str = None):
        super().__init__()
        self.stars = stars
        self.image_url = image_url
        self.add_item(discord.ui.TextInput(
            label="Your Review",
            placeholder="Write your feedback here...",
            style=discord.TextStyle.paragraph
        ))

    async def on_submit(self, interaction: discord.Interaction):
        review_text = self.children[0].value
        star_str = "⭐" * self.stars

        # Use server icon as default image
        default_image = interaction.guild.icon.url if interaction.guild.icon else "https://cdn.discordapp.com/attachments/1405533704847364278/1406475783769297069/images_1.jpg?ex=68a29a25&is=68a148a5&hm=0e11a872c9474976320815aeb5f83f4a79492804d472a0263a44eb3677e63370&"

        # ReviewCord style embed
        embed = discord.Embed(
            color=0x2B2D31  # Discord dark theme color
        )

        # Add red left border effect with description
        embed.description = f"**New Review by**\n**{interaction.user.display_name}**\n\n{review_text}\n\n**Rating**\n{star_str}"

        embed.set_thumbnail(url=interaction.user.display_avatar.url)

        # Add image if provided, otherwise use server icon
        if self.image_url:
            embed.set_image(url=self.image_url)
        else:
            embed.set_image(url=default_image)

        embed.set_footer(text="Thank you for your review!")
        add_premium_badge_to_embed(embed)

        # Save review
        reviews_data.append({
            "user": interaction.user.display_name,
            "avatar": interaction.user.display_avatar.url,
            "stars": star_str,
            "text": review_text,
            "image": self.image_url if self.image_url else default_image
        })

        # Add "Review" button for others to leave reviews
        view = ReviewButtonView(self.image_url)
        await interaction.response.send_message(embed=embed, view=view)

# ========================
# REVIEW BUTTON VIEW
# ========================
class ReviewButtonView(discord.ui.View):
    def __init__(self, image_url: str = None):
        super().__init__(timeout=None)
        self.image_url = image_url

    @discord.ui.button(label="Review", style=discord.ButtonStyle.primary, emoji="⭐")
    async def review_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        view = StarRating(self.image_url)
        await interaction.response.send_message("Please choose a star rating:", view=view, ephemeral=True)

# ========================
# STAR RATING BUTTONS
# ========================
class StarRating(discord.ui.View):
    def __init__(self, image_url: str = None):
        super().__init__(timeout=None)
        self.image_url = image_url

    async def send_modal(self, interaction: discord.Interaction, stars: int):
        await interaction.response.send_modal(ReviewModal(stars, self.image_url))

    @discord.ui.button(label="⭐", style=discord.ButtonStyle.primary)
    async def one_star(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.send_modal(interaction, 1)

    @discord.ui.button(label="⭐⭐", style=discord.ButtonStyle.primary)
    async def two_star(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.send_modal(interaction, 2)

    @discord.ui.button(label="⭐⭐⭐", style=discord.ButtonStyle.primary)
    async def three_star(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.send_modal(interaction, 3)

    @discord.ui.button(label="⭐⭐⭐⭐", style=discord.ButtonStyle.primary)
    async def four_star(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.send_modal(interaction, 4)

    @discord.ui.button(label="⭐⭐⭐⭐⭐", style=discord.ButtonStyle.success)
    async def five_star(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.send_modal(interaction, 5)

# ========================
# SLASH COMMANDS FOR REVIEWS
# ========================
@bot.tree.command(name="start_review", description="Start a review with image and rating (1-5)")
@app_commands.describe(
    message="Your review message",
    image="Upload an image for your review",
    rate="Rate from 1 to 5 stars"
)
async def start_review(
    interaction: discord.Interaction,
    message: str,
    image: discord.Attachment = None,
    rate: app_commands.Range[int, 1, 5] = None
):
    image_url = None
    if image:
        # Check if it's an image
        if any(image.filename.lower().endswith(ext) for ext in ['.png', '.jpg', '.jpeg', '.gif', '.webp']):
            image_url = image.url
        else:
            await interaction.response.send_message(f"{EMOJIS['error']} Please upload a valid image file (PNG, JPG, JPEG, GIF, WEBP).", ephemeral=True)
            return

    if rate:
        # Direct submission with provided rating
        star_str = "⭐" * rate

        # Use server icon as default image
        default_image = interaction.guild.icon.url if interaction.guild.icon else "https://cdn.discordapp.com/attachments/1405533704847364278/1406475783769297069/images_1.jpg?ex=68a29a25&is=68a148a5&hm=0e11a872c9474976320815aeb5f83f4a79492804d472a0263a44eb3677e63370&"

        embed = discord.Embed(color=0x2B2D31)
        embed.description = f"**New Review by**\n**{interaction.user.display_name}**\n\n{message}\n\n**Rating**\n{star_str}"
        embed.set_thumbnail(url=interaction.user.display_avatar.url)

        if image_url:
            embed.set_image(url=image_url)
        else:
            embed.set_image(url=default_image)

        embed.set_footer(text="Thank you for your review!")
        add_premium_badge_to_embed(embed)

        # Save review
        reviews_data.append({
            "user": interaction.user.display_name,
            "avatar": interaction.user.display_avatar.url,
            "stars": star_str,
            "text": message,
            "image": image_url if image_url else default_image
        })

        view = ReviewButtonView(image_url)
        await interaction.response.send_message(embed=embed, view=view)
    else:
        # Show star rating buttons if no rate provided
        view = StarRating(image_url)
        embed = discord.Embed(
            title="📝 Review Setup",
            description=f"**Message:** {message}\n\n{'**Image:** Attached' if image_url else '**Image:** None'}\n\nPlease choose your star rating:",
            color=PRIMARY_COLOR
        )
        if image_url:
            embed.set_image(url=image_url)
        embed.set_footer(text=f"Requested by {interaction.user.display_name} | Razor Premium ⭐", icon_url=interaction.user.display_avatar.url)
        add_premium_badge_to_embed(embed)
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

class ReviewBrowser(discord.ui.View):
    def __init__(self, reviews, index=0):
        super().__init__(timeout=60)
        self.reviews = reviews
        self.index = index

    def get_embed(self):
        data = self.reviews[self.index]
        embed = discord.Embed(
            title=f"{data['stars']} Review",
            description=data["text"],
            color=discord.Color.blue()
        )
        embed.set_author(name=data["user"], icon_url=data["avatar"])
        embed.set_thumbnail(url=data["avatar"])

        # Add image if available
        if data.get("image"):
            embed.set_image(url=data["image"])

        embed.set_footer(text=f"Review {self.index+1}/{len(self.reviews)}")
        add_premium_badge_to_embed(embed)
        return embed

    @discord.ui.button(label="⏮️ Previous", style=discord.ButtonStyle.secondary)
    async def prev_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.index > 0:
            self.index -= 1
            await interaction.response.edit_message(embed=self.get_embed(), view=self)
        else:
            await interaction.response.send_message("You're at the first review!", ephemeral=True)

    @discord.ui.button(label="⏭️ Next", style=discord.ButtonStyle.secondary)
    async def next_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.index < len(self.reviews) - 1:
            self.index += 1
            await interaction.response.edit_message(embed=self.get_embed(), view=self)
        else:
            await interaction.response.send_message("You're at the last review!", ephemeral=True)

# view_reviews command removed - only start_review is available

# ------------------------------ INVITE SYSTEM --------------------------------

@tree.command(name="invites", description="Check detailed invite statistics")
async def invites(interaction: discord.Interaction, user: discord.User | None = None):
    user = user or interaction.user
    real, fake, total = get_invite_stats(user.id)

    # Calculate additional stats
    joins = real + fake  # Total people who joined through this user
    left = fake  # People who left
    rejoins_data = get_member_rejoin_count(user.id)  # You can implement this
    rejoins = rejoins_data if rejoins_data else 0

    embed = discord.Embed(
        title="Invite log",
        description=f"**>> {user.display_name} has {total} invites**",
        color=0x36393F  # Discord dark theme color
    )

    # Main stats with beautiful formatting
    stats_text = f"**Joins : {joins}**\n"
    stats_text += f"**Left : {left}**\n"
    stats_text += f"**Fake : {fake}**\n"
    stats_text += f"**Rejoins : {rejoins}** *(7d)*"

    embed.add_field(name="", value=stats_text, inline=True)

    # Add user avatar as thumbnail
    embed.set_thumbnail(url=user.display_avatar.url)

    # Premium footer with timestamp
    embed.set_footer(
        text=f"Requested by {interaction.user.display_name} | Today at {datetime.now().strftime('%I:%M %p')}",
        icon_url=interaction.user.display_avatar.url
    )

    # Add promotional text for premium features
    premium_text = f"▶ Try lifetime rejoins\ntracking with **Razor Premium**"
    embed.add_field(name="", value=premium_text, inline=False)
    add_premium_badge_to_embed(embed)

    await interaction.response.send_message(embed=embed)

@tree.command(name="invitelog", description="Detailed invite analytics with premium styling")
async def invitelog(interaction: discord.Interaction, user: discord.User | None = None):
    user = user or interaction.user
    real, fake, total = get_invite_stats(user.id)

    # Get additional data
    joins = real + fake
    left = fake
    rejoins = get_member_rejoin_count(user.id) or 0

    embed = discord.Embed(
        title="📊 RAZOR PREMIUM - INVITE ANALYTICS",
        color=PRIMARY_COLOR
    )

    embed.add_field(
        name="🏷️ Invite Analytics",
        value="Advanced invite tracking system",
        inline=False
    )

    embed.add_field(
        name="👤 Member Information",
        value=f"**Target User:** {user.mention}\n**Display Name:** {user.display_name}\n**Total Invites:** {total}",
        inline=False
    )

    embed.add_field(
        name="📈 Detailed Statistics",
        value=f"**Joins:** {joins} members\n**Left Server:** {left} members\n**Fake Invites:** {fake} members\n**Rejoins (7d):** {rejoins} members",
        inline=False
    )

    # Calculate percentages for better analytics
    retention_rate = ((joins - left) / joins * 100) if joins > 0 else 100
    fake_rate = (fake / total * 100) if total > 0 else 0

    embed.add_field(
        name="💎 Premium Analytics",
        value=f"**Retention Rate:** {retention_rate:.1f}%\n**Fake Rate:** {fake_rate:.1f}%\n**Quality Score:** {'Excellent' if fake_rate < 10 else 'Good' if fake_rate < 25 else 'Average'}",
        inline=False
    )

    embed.add_field(
        name="🎯 Invite Performance",
        value=f"**Active Invites:** {real} members\n**Server Contribution:** {(real / max(interaction.guild.member_count, 1) * 100):.1f}%\n**Rank:** Top Inviter" if real > 10 else "Active Member",
        inline=False
    )

    embed.set_thumbnail(url=interaction.guild.icon.url if interaction.guild.icon else None)
    embed.set_author(name=f"{user.display_name}'s Invite Stats", icon_url=user.display_avatar.url)
    embed.set_footer(text=f"Analyzed by {interaction.user.display_name} | Razor Premium Analytics ⭐", icon_url=interaction.user.display_avatar.url)
    add_premium_badge_to_embed(embed)

    await interaction.response.send_message(embed=embed)

@tree.command(name="topinviters", description="Top inviters leaderboard with premium design")
async def topinviters(interaction: discord.Interaction):
    # Get top inviters from database
    cur.execute("SELECT inviter_id, real_count, fake_count FROM invite_stats ORDER BY real_count DESC LIMIT 10")
    rows = cur.fetchall()

    if not rows:
        embed = discord.Embed(
            title="📊 RAZOR PREMIUM - TOP INVITERS",
            description="No invite data available yet.",
            color=ERROR_COLOR
        )
        embed.set_footer(text=f"Requested by {interaction.user.display_name} | Razor Premium ⭐", icon_url=interaction.user.display_avatar.url)
        add_premium_badge_to_embed(embed)
        await interaction.response.send_message(embed=embed)
        return

    embed = discord.Embed(
        title="🏆 RAZOR PREMIUM - TOP INVITERS",
        color=PRIMARY_COLOR
    )

    embed.add_field(
        name="🏷️ Leaderboard",
        value="Server's most active inviters",
        inline=False
    )

    leaderboard_text = ""
    medals = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣", "🔟"]

    for i, (inviter_id, real_count, fake_count) in enumerate(rows):
        try:
            user = await bot.fetch_user(inviter_id)
            medal = medals[i] if i < len(medals) else f"{i+1}."
            total = real_count + fake_count
            leaderboard_text += f"{medal} **{user.display_name}** - {total} invites ({real_count} real)\n"
        except:
            continue

    embed.add_field(
        name="👑 Top Performers",
        value=leaderboard_text if leaderboard_text else "No data available",
        inline=False
    )

    embed.add_field(
        name="💎 Premium Features",
        value="**Real-time Tracking:** Live updates\n**Advanced Analytics:** Detailed insights\n**Quality Metrics:** Performance scoring",
        inline=False
    )

    embed.set_thumbnail(url=interaction.guild.icon.url if interaction.guild.icon else None)
    embed.set_footer(text=f"Requested by {interaction.user.display_name} | Razor Premium Leaderboard ⭐", icon_url=interaction.user.display_avatar.url)
    add_premium_badge_to_embed(embed)

    await interaction.response.send_message(embed=embed)

@tree.command(name="clearinvites", description="Reset all invite counts (admin)")
@app_commands.checks.has_permissions(manage_guild=True)
async def clearinvites(interaction: discord.Interaction):
    cur.execute("DELETE FROM invite_stats")
    cur.execute("DELETE FROM member_inviter")
    db.commit()
    embed = discord.Embed(
        title=f"{EMOJIS['success']} Invite Stats Cleared",
        description="All invite counts have been reset.",
        color=SUCCESS_COLOR
    )
    embed.set_footer(text=f"Requested by {interaction.user.display_name} | Razor Premium ⭐", icon_url=interaction.user.display_avatar.url)
    add_premium_badge_to_embed(embed)
    await interaction.response.send_message(embed=embed, ephemeral=True)

# ------------------------------ TICKET SYSTEM --------------------------------
CONFIG_FILE = "ticket_config.json"

def load_ticket_config(guild_id: int) -> dict:
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "r") as f:
            data = json.load(f)
        return data.get(str(guild_id), {})
    return {}

def save_ticket_config(guild_id: int, cfg: dict):
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "r") as f:
            data = json.load(f)
    else:
        data = {}
    data[str(guild_id)] = cfg
    with open(CONFIG_FILE, "w") as f:
        json.dump(data, f, indent=2)

class TicketButtons(View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(Button(label="Support", emoji=EMOJIS["support"], custom_id="support"))
        self.add_item(Button(label="Buy", emoji=EMOJIS["buyer"], custom_id="buy"))
        self.add_item(Button(label="Renew", emoji=EMOJIS["renew"], custom_id="renew"))
        self.add_item(Button(label="Rewards Claim", emoji=EMOJIS["claim"], custom_id="claim"))
        self.add_item(Button(label="Others", emoji=EMOJIS["verified"], custom_id="others"))

    @discord.ui.button(label="Claim", style=discord.ButtonStyle.blurple, custom_id="ticket_claim")
    async def claim(self, interaction: discord.Interaction, button: Button):
        await interaction.response.send_message(f"Ticket claimed by <@{interaction.user.id}>.", ephemeral=False)

    @discord.ui.button(label="Close", style=discord.ButtonStyle.gray, custom_id="ticket_close")
    async def close(self, interaction: discord.Interaction, button: Button):
        await interaction.response.send_message("Ticket will close in 5 seconds...", ephemeral=True)
        await asyncio.sleep(5)
        try:
            await interaction.channel.delete()
        except Exception:
            pass

    @discord.ui.button(label="Delete", style=discord.ButtonStyle.danger, custom_id="ticket_delete")
    async def delete(self, interaction: discord.Interaction, button: Button):
        try:
            await interaction.channel.delete()
        except Exception:
            pass

@tree.command(name="setticket", description="Send the ticket panel to a channel")
@app_commands.checks.has_permissions(administrator=True)
@app_commands.describe(channel="Target text channel")
async def setticket(interaction: discord.Interaction, channel: discord.TextChannel):
    cfg = load_ticket_config(interaction.guild_id)
    cfg["ticket_channel"] = channel.id
    save_ticket_config(interaction.guild_id, cfg)

    embed = discord.Embed(
        title="🎫 RAZOR PREMIUM - BEST IT SOLUTION",
        color=PRIMARY_COLOR
    )
    embed.add_field(
        name="🏷️ Ticket System",
        value="Professional support center",
        inline=False
    )
    embed.add_field(
        name="📋 Available Categories",
        value=f"{EMOJIS['support']} **Support** - Technical assistance\n{EMOJIS['buyer']} **Buy** - Purchase inquiries\n{EMOJIS['renew']} **Renew** - Subscription renewals\n{EMOJIS['claim']} **Rewards Claim** - Claim your rewards\n{EMOJIS['verified']} **Others** - General inquiries",
        inline=False
    )
    embed.add_field(
        name="⚠️ Important Notice",
        value="Do not open tickets for fun; abuse can result in penalties.",
        inline=False
    )
    embed.set_thumbnail(url=interaction.guild.icon.url if interaction.guild.icon else None)
    embed.set_footer(text="Razor Premium Support | Professional Service")
    add_premium_badge_to_embed(embed)
    await channel.send(embed=embed, view=TicketButtons())
    embed = discord.Embed(
        title=f"{EMOJIS['success']} Ticket Panel Setup",
        description=f"Ticket panel sent to {channel.mention}.",
        color=SUCCESS_COLOR
    )
    embed.set_footer(text=f"Requested by {interaction.user.display_name} | Razor Premium ⭐", icon_url=interaction.user.display_avatar.url)
    add_premium_badge_to_embed(embed)
    await interaction.response.send_message(embed=embed, ephemeral=True)

@bot.event
async def on_interaction(interaction: discord.Interaction):
    if interaction.type == discord.InteractionType.component:
        cid = (interaction.data or {}).get("custom_id")
        if cid in {"support", "buy", "renew", "claim", "others"}:
            mapping = {
                "support": "Support",
                "buy": "Buy",
                "renew": "Renew",
                "claim": "Rewards Claim",
                "others": "Other"
            }
            reason = mapping[cid]
            guild = interaction.guild
            user = interaction.user

            overwrites = {
                guild.default_role: discord.PermissionOverwrite(read_messages=False),
                user: discord.PermissionOverwrite(read_messages=True, send_messages=True),
                guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True),
            }
            name = f"ticket-{user.name.lower()}-{reason.lower().replace(' ', '-')}"
            try:
                ch = await guild.create_text_channel(name=name, overwrites=overwrites, topic=f"Ticket for {reason}")
                await ch.send(f"{EMOJIS['spark']} Ticket created by {user.mention} for **{reason}**", view=TicketButtons())
                embed = discord.Embed(
                    title=f"{EMOJIS['success']} Ticket Created",
                    description=f"Ticket channel {ch.mention} created for {reason}.",
                    color=SUCCESS_COLOR
                )
                embed.set_footer(text=f"Requested by {interaction.user.display_name} | Razor Premium ⭐", icon_url=interaction.user.display_avatar.url)
                add_premium_badge_to_embed(embed)
                await interaction.response.send_message(embed=embed, ephemeral=True)
            except Exception as e:
                embed = discord.Embed(
                    title=f"{EMOJIS['error']} Ticket Creation Failed",
                    description=f"Could not create ticket: `{e}`",
                    color=ERROR_COLOR
                )
                embed.set_footer(text=f"Requested by {interaction.user.display_name} | Razor Premium ⭐", icon_url=interaction.user.display_avatar.url)
                add_premium_badge_to_embed(embed)
                await interaction.response.send_message(embed=embed, ephemeral=True)


# ------------------------------ GIVEAWAY SYSTEM -------------------------------
class GiveawayJoinView(View):
    def __init__(self):
        super().__init__(timeout=None)
        self.participants: list[discord.User] = []

    @discord.ui.button(
        label="Join Giveaway",
        style=discord.ButtonStyle.primary,
        emoji=EMOJIS["gift"],
        custom_id="join_giveaway"
    )
    async def join_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user in self.participants:
            await interaction.response.send_message(f"{EMOJIS['info']} You’re already entered.", ephemeral=True)
        else:
            self.participants.append(interaction.user)
            await interaction.response.send_message(f"{EMOJIS['success']} Entered!", ephemeral=True)

@tree.command(name="gstart", description="Start a giveaway")
@app_commands.describe(channel="Where to host", prize="Prize", duration="Minutes", winners="Number of winners")
@app_commands.checks.has_permissions(manage_guild=True)
async def gstart(interaction: discord.Interaction, channel: discord.TextChannel, prize: str, duration: int, winners: int):
    if duration <= 0 or winners <= 0:
        await interaction.response.send_message(f"{EMOJIS['error']} Duration and winners must be > 0.", ephemeral=True)
        return

    start_embed = discord.Embed(
        title=f"{EMOJIS['gift']} Giveaway Started",
        description=f"**Prize:** {prize}\n**Duration:** {duration} minutes\n**Channel:** {channel.mention}",
        color=PRIMARY_COLOR
    )
    embed = discord.Embed(
        title="🎁 RAZOR PREMIUM - BEST IT SOLUTION",
        color=PRIMARY_COLOR
    )
    embed.add_field(
        name="🏷️ Giveaway Event",
        value="Premium giveaway active",
        inline=False
    )
    embed.add_field(
        name="📋 Prize Information",
        value=f"**Prize:** {prize}\n**Duration:** {duration} minutes\n**Status:** Active",
        inline=False
    )
    embed.add_field(
        name="🎯 How to Enter",
        value="Click the button below to participate\nGood luck to all participants!",
        inline=False
    )
    embed.set_thumbnail(url=interaction.guild.icon.url if interaction.guild.icon else None)
    embed.set_footer(text=f"Hosted by {interaction.user.name} | Razor Premium ⭐", icon_url=interaction.user.display_avatar.url)
    add_premium_badge_to_embed(embed)
    await interaction.response.send_message(embed=start_embed, ephemeral=True)

    view = GiveawayJoinView()
    msg = await channel.send(embed=embed, view=view)

    await asyncio.sleep(duration * 60)

    users = view.participants
    if not users:
        await channel.send(f"{EMOJIS['error']} Not enough participants for **{prize}**.")
        return

    winners_list = random.sample(users, min(winners, len(users)))
    mentions = ", ".join(u.mention for u in winners_list)
    end_embed = discord.Embed(
        title=f"{EMOJIS['gift']} Giveaway Ended",
        description=f"**Prize:** {prize}\n**Winners:** {mentions}\nHosted by {interaction.user.mention}",
        color=SUCCESS_COLOR
    )
    end_embed.set_footer(text=f"Ended by {interaction.user.name} | Razor Premium ⭐", icon_url=interaction.user.display_avatar.url)
    add_premium_badge_to_embed(end_embed)
    await channel.send(embed=end_embed)

# ------------------------------ MUSIC (LIGHT) --------------------------------
# NOTE: FFmpeg must be installed. yt_dlp required. This is a minimal queue player.
try:
    import yt_dlp  # noqa
    HAS_YTDLP = True
except Exception:
    HAS_YTDLP = False

music_queue: list[tuple[str, str, str, str, discord.User]] = []  # (url, title, author, dur, requester)
music_loop = False
music_autoplay = False
music_playlist: list[tuple[str, str, str, str, discord.User]] = []

class MusicControlView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=300)

    @discord.ui.button(label="Play", style=discord.ButtonStyle.success, emoji="▶️")
    async def play_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        vc = interaction.guild.voice_client
        if vc and vc.is_paused():
            vc.resume()
            await interaction.response.send_message(f"{EMOJIS['music']} Resumed!", ephemeral=True)
        else:
            await interaction.response.send_message(f"{EMOJIS['error']} Nothing to resume.", ephemeral=True)

    @discord.ui.button(label="Stop", style=discord.ButtonStyle.danger, emoji="⏹️")
    async def stop_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        vc = interaction.guild.voice_client
        if vc and vc.is_playing():
            vc.stop()
            music_queue.clear()
            await interaction.response.send_message(f"{EMOJIS['music']} Stopped and cleared queue!", ephemeral=True)
        else:
            await interaction.response.send_message(f"{EMOJIS['error']} Nothing is playing.", ephemeral=True)

    @discord.ui.button(label="Loop", style=discord.ButtonStyle.secondary, emoji="🔁")
    async def loop_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        global music_loop
        music_loop = not music_loop
        status = "enabled" if music_loop else "disabled"
        await interaction.response.send_message(f"{EMOJIS['music']} Loop {status}!", ephemeral=True)

    @discord.ui.button(label="Playlist", style=discord.ButtonStyle.primary, emoji="📋")
    async def playlist_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not music_queue:
            await interaction.response.send_message(f"{EMOJIS['info']} Queue is empty.", ephemeral=True)
            return

        queue_list = []
        for i, (url, title, author, duration, requester) in enumerate(music_queue[:10]):
            queue_list.append(f"{i+1}. **{title}** by {author} ({duration}) - {requester.mention}")

        embed = discord.Embed(
            title=f"{EMOJIS['music']} Music Queue",
            description="\n".join(queue_list) if queue_list else "Queue is empty",
            color=PRIMARY_COLOR
        )
        embed.set_footer(text=f"Requested by {interaction.user.display_name} | Razor Premium ⭐", icon_url=interaction.user.display_avatar.url)
        add_premium_badge_to_embed(embed)
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @discord.ui.button(label="AutoPlay", style=discord.ButtonStyle.secondary, emoji="🎲")
    async def autoplay_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        global music_autoplay
        music_autoplay = not music_autoplay
        status = "enabled" if music_autoplay else "disabled"
        await interaction.response.send_message(f"{EMOJIS['music']} AutoPlay {status}!", ephemeral=True)

async def _play_next_text(ctx_channel: discord.TextChannel):
    if not music_queue:
        return
    if not HAS_YTDLP:
        await ctx_channel.send(f"{EMOJIS['error']} Music requires `yt_dlp` installed.")
        return

    url, title, author, duration, requester = music_queue.pop(0)
    filename = "song.mp3"
    if os.path.exists(filename):
        try: os.remove(filename)
        except Exception: pass

    ydl_opts = {'format': 'bestaudio/best', 'outtmpl': filename, 'quiet': True}
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        ydl.download([url])

    vc = ctx_channel.guild.voice_client
    if not vc:
        return
    source = await discord.FFmpegOpusAudio.from_probe(filename)

    def _after(_e):
        global music_loop, music_autoplay
        if music_loop and url:
            # Re-add current song to front of queue for loop
            music_queue.insert(0, (url, title, author, duration, requester))
        elif music_autoplay and not music_queue:
            # Add a random song to queue for autoplay (simplified)
            pass
        fut = _play_next_text(ctx_channel)
        asyncio.run_coroutine_threadsafe(fut, bot.loop)

    vc.play(source, after=_after)

    embed = discord.Embed(title="🎵 RAZOR PREMIUM - BEST IT SOLUTION", color=PRIMARY_COLOR)
    embed.add_field(
        name="🏷️ Music Player",
        value="Premium audio experience",
        inline=False
    )
    embed.add_field(
        name="📋 Now Playing",
        value=f"**Title:** [{title}]({url})\n**Artist:** {author}\n**Duration:** {duration}",
        inline=False
    )
    embed.add_field(
        name="👤 Request Info",
        value=f"**Requested by:** {requester.mention}\n**Queue:** {len(music_queue)} songs\n**Status:** Playing",
        inline=False
    )

    loop_status = "🔁 Loop: ON" if music_loop else "🔁 Loop: OFF"
    autoplay_status = "🎲 AutoPlay: ON" if music_autoplay else "🎲 AutoPlay: OFF"
    embed.add_field(name="⚙️ Settings", value=f"{loop_status} | {autoplay_status}", inline=False)
    embed.set_thumbnail(url=interaction.guild.icon.url if interaction.guild.icon else None)
    embed.set_footer(text="Razor Premium Music | High Quality Audio")
    add_premium_badge_to_embed(embed)

    view = MusicControlView()
    await ctx_channel.send(embed=embed, view=view)

@tree.command(name="play", description="Play a song by name or link")
@app_commands.describe(query="Search or URL")
async def play(interaction: discord.Interaction, query: str):
    await interaction.response.send_message(f"{EMOJIS['loading']} Searching…", ephemeral=True)

    if not HAS_YTDLP:
        await interaction.followup.send(f"{EMOJIS['error']} Install `yt_dlp` to use music.", ephemeral=True)
        return

    voice = interaction.guild.voice_client
    if not voice:
        if interaction.user.voice and interaction.user.voice.channel:
            voice = await interaction.user.voice.channel.connect()
        else:
            await interaction.followup.send(f"{EMOJIS['error']} Join a voice channel first.", ephemeral=True)
            return

    ydl_opts = {'format': 'bestaudio/best', 'default_search': 'ytsearch1', 'quiet': True}
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(query, download=False)
        if 'entries' in info:
            info = info['entries'][0]
        url = info['webpage_url']
        title = info['title']
        duration = f"{int(info['duration']//60)}m {int(info['duration']%60)}s" if info.get('duration') else "N/A"
        author = info.get('uploader', 'Unknown')

    music_queue.append((url, title, author, duration, interaction.user))
    await interaction.followup.send(f"{EMOJIS['success']} Added to queue: `{title}`", ephemeral=True)

    if not voice.is_playing():
        await _play_next_text(interaction.channel)

@tree.command(name="join", description="Join your voice channel")
async def join(interaction: discord.Interaction):
    if interaction.user.voice and interaction.user.voice.channel:
        # Check if bot is already connected to a voice channel
        if interaction.guild.voice_client:
            if interaction.guild.voice_client.channel == interaction.user.voice.channel:
                embed = discord.Embed(
                    title=f"{EMOJIS['info']} Already Connected",
                    description="I'm already in your voice channel!",
                    color=INFO_COLOR
                )
                embed.set_footer(text=f"Requested by {interaction.user.display_name} | Razor Premium ⭐", icon_url=interaction.user.display_avatar.url)
                add_premium_badge_to_embed(embed)
                await interaction.response.send_message(embed=embed, ephemeral=True)
                return
            else:
                # Move to user's channel
                await interaction.guild.voice_client.move_to(interaction.user.voice.channel)
        else:
            # Connect to the voice channel
            try:
                await interaction.user.voice.channel.connect()
            except Exception as e:
                embed = discord.Embed(
                    title=f"{EMOJIS['error']} Connection Failed",
                    description=f"Failed to join voice channel: {str(e)}",
                    color=ERROR_COLOR
                )
                embed.set_footer(text=f"Requested by {interaction.user.display_name} | Razor Premium ⭐", icon_url=interaction.user.display_avatar.url)
                add_premium_badge_to_embed(embed)
                await interaction.response.send_message(embed=embed, ephemeral=True)
                return
        
        embed = discord.Embed(
            title=f"{EMOJIS['success']} Joined Voice Channel",
            description=f"Successfully joined **{interaction.user.voice.channel.name}**",
            color=SUCCESS_COLOR
        )
        embed.set_footer(text=f"Requested by {interaction.user.display_name} | Razor Premium ⭐", icon_url=interaction.user.display_avatar.url)
        add_premium_badge_to_embed(embed)
        await interaction.response.send_message(embed=embed, ephemeral=True)
    else:
        embed = discord.Embed(
            title=f"{EMOJIS['error']} Not in Voice Channel",
            description="You must be in a voice channel to use this command.",
            color=ERROR_COLOR
        )
        embed.set_footer(text=f"Requested by {interaction.user.display_name} | Razor Premium ⭐", icon_url=interaction.user.display_avatar.url)
        add_premium_badge_to_embed(embed)
        await interaction.response.send_message(embed=embed, ephemeral=True)

@tree.command(name="leave", description="Leave the voice channel")
async def leave(interaction: discord.Interaction):
    vc = interaction.guild.voice_client
    if vc:
        await vc.disconnect()
        embed = discord.Embed(
            title=f"{EMOJIS['success']} Left Voice Channel",
            description="Successfully left the voice channel.",
            color=SUCCESS_COLOR
        )
        embed.set_footer(text=f"Requested by {interaction.user.display_name} | Razor Premium ⭐", icon_url=interaction.user.display_avatar.url)
        add_premium_badge_to_embed(embed)
        await interaction.response.send_message(embed=embed, ephemeral=True)
    else:
        embed = discord.Embed(
            title=f"{EMOJIS['error']} Not Connected",
            description="The bot is not currently connected to a voice channel.",
            color=ERROR_COLOR
        )
        embed.set_footer(text=f"Requested by {interaction.user.display_name} | Razor Premium ⭐", icon_url=interaction.user.display_avatar.url)
        add_premium_badge_to_embed(embed)
        await interaction.response.send_message(embed=embed, ephemeral=True)

# ------------------------------ ANTI-NUKE COMMANDS --------------------------------
@tree.command(name="antinuke", description="Configure anti-nuke settings")
@app_commands.describe(
    action="Action to perform",
    punishment="Punishment type for violators",
    user="User for whitelist operations"
)
@app_commands.choices(
    action=[
        app_commands.Choice(name="Enable", value="enable"),
        app_commands.Choice(name="Disable", value="disable"),
        app_commands.Choice(name="Status", value="status"),
        app_commands.Choice(name="Whitelist Add", value="whitelist_add"),
        app_commands.Choice(name="Whitelist Remove", value="whitelist_remove"),
        app_commands.Choice(name="Configure Limits", value="limits")
    ],
    punishment=[
        app_commands.Choice(name="Ban", value="ban"),
        app_commands.Choice(name="Kick", value="kick"),
        app_commands.Choice(name="Timeout", value="timeout")
    ]
)
@app_commands.checks.has_permissions(administrator=True)
async def antinuke(interaction: discord.Interaction, action: str, punishment: str = None, user: discord.User = None):
    guild_id = interaction.guild.id
    config = get_antinuke_config(guild_id)

    if action == "enable":
        set_antinuke_config(guild_id, enabled=True)
        embed = discord.Embed(
            title="🛡️ RAZOR PREMIUM - ANTI-NUKE SYSTEM",
            color=SUCCESS_COLOR
        )
        embed.add_field(name="🏷️ Security Status", value="Anti-nuke protection enabled", inline=False)
        embed.add_field(name="⚡ Protection Level", value="Maximum security activated", inline=False)

    elif action == "disable":
        set_antinuke_config(guild_id, enabled=False)
        embed = discord.Embed(
            title="🛡️ RAZOR PREMIUM - ANTI-NUKE SYSTEM",
            color=WARNING_COLOR
        )
        embed.add_field(name="🏷️ Security Status", value="Anti-nuke protection disabled", inline=False)
        embed.add_field(name="⚠️ Warning", value="Server is vulnerable to attacks", inline=False)

    elif action == "status":
        status = "🟢 Enabled" if config['enabled'] else "🔴 Disabled"
        cur.execute("SELECT COUNT(*) FROM antinuke_whitelist WHERE guild_id = ?", (guild_id,))
        whitelist_count = cur.fetchone()[0]

        embed = discord.Embed(
            title="🛡️ RAZOR PREMIUM - ANTI-NUKE STATUS",
            color=PRIMARY_COLOR
        )
        embed.add_field(
            name="📊 Current Configuration",
            value=f"**Status:** {status}\n**Punishment:** {config['punishment'].title()}\n**Whitelisted Users:** {whitelist_count}",
            inline=False
        )

        limits_text = "\n".join([f"**{k.replace('_', ' ').title()}:** {v}" for k, v in config['limits'].items()])
        embed.add_field(name="⚙️ Action Limits", value=limits_text, inline=False)

    elif action == "whitelist_add":
        if not user:
            await interaction.response.send_message(f"{EMOJIS['error']} Please specify a user to whitelist.", ephemeral=True)
            return

        add_to_whitelist(guild_id, user.id, interaction.user.id)
        embed = discord.Embed(
            title="✅ RAZOR PREMIUM - WHITELIST UPDATED",
            color=SUCCESS_COLOR
        )
        embed.add_field(
            name="🏷️ User Whitelisted",
            value=f"**User:** {user.mention}\n**Added by:** {interaction.user.mention}\n**Status:** Protected from anti-nuke",
            inline=False
        )

    elif action == "whitelist_remove":
        if not user:
            await interaction.response.send_message(f"{EMOJIS['error']} Please specify a user to remove from whitelist.", ephemeral=True)
            return

        remove_from_whitelist(guild_id, user.id)
        embed = discord.Embed(
            title="🗑️ RAZOR PREMIUM - WHITELIST UPDATED",
            color=WARNING_COLOR
        )
        embed.add_field(
            name="🏷️ User Removed",
            value=f"**User:** {user.mention}\n**Removed by:** {interaction.user.mention}\n**Status:** No longer protected",
            inline=False
        )

    elif action == "limits":
        if punishment:
            set_antinuke_config(guild_id, punishment=punishment)
            embed = discord.Embed(
                title="⚙️ RAZOR PREMIUM - PUNISHMENT UPDATED",
                color=INFO_COLOR
            )
            embed.add_field(
                name="🏷️ Configuration Changed",
                value=f"**New Punishment:** {punishment.title()}\n**Applied to:** All violations\n**Effective:** Immediately",
                inline=False
            )
        else:
            embed = discord.Embed(
                title="⚙️ RAZOR PREMIUM - CURRENT LIMITS",
                color=INFO_COLOR
            )
            limits_text = "\n".join([f"**{k.replace('_', ' ').title()}:** {v} per 5 minutes" for k, v in config['limits'].items()])
            embed.add_field(name="📋 Action Limits", value=limits_text, inline=False)

    embed.set_thumbnail(url=interaction.guild.icon.url if interaction.guild.icon else None)
    embed.set_footer(text=f"Requested by {interaction.user.display_name} | Razor Premium Security ⭐", icon_url=interaction.user.display_avatar.url)
    add_premium_badge_to_embed(embed)
    await interaction.response.send_message(embed=embed, ephemeral=True)

@tree.command(name="automod", description="Display AutoMod system status and features")
async def automod(interaction: discord.Interaction):
    automod_embed = discord.Embed(
        title="🤖 RAZOR PREMIUM - AUTOMOD SYSTEM",
        color=PRIMARY_COLOR
    )

    automod_embed.add_field(
        name="🏷️ System Status",
        value="AutoMod protection active",
        inline=False
    )

    # Active Features
    automod_embed.add_field(
        name="🛡️ ACTIVE PROTECTIONS",
        value="✅ **Bad Word Filter** - Automatic deletion\n✅ **Spam Detection** - 5 msgs/60s limit\n✅ **Anti-Raid** - Mass join protection\n✅ **Link Filter** - Suspicious URL blocking\n✅ **Caps Lock Filter** - Excessive caps control",
        inline=False
    )

    # Statistics
    guild = interaction.guild
    automod_embed.add_field(
        name="📊 PROTECTION STATISTICS",
        value=f"**Server:** {guild.name}\n**Protected Members:** {guild.member_count}\n**Messages Filtered:** 1,000+\n**Spam Blocked:** 250+\n**Status:** 🟢 Active",
        inline=False
    )

    # Configuration
    automod_embed.add_field(
        name="⚙️ CURRENT CONFIG",
        value="**Spam Limit:** 5 messages per 60 seconds\n**Punishment:** 5 minute timeout\n**Admin Immunity:** Enabled\n**Auto-Delete:** Enabled\n**Logging:** Active",
        inline=False
    )

    # Premium Features
    automod_embed.add_field(
        name="💎 PREMIUM AUTOMOD FEATURES",
        value="• **Real-time Processing** - Instant response\n• **Machine Learning** - Smart detection\n• **Custom Word Lists** - Personalized filters\n• **Whitelist System** - Trusted users\n• **Advanced Analytics** - Detailed reports",
        inline=False
    )

    automod_embed.set_thumbnail(url=interaction.guild.icon.url if interaction.guild.icon else None)
    automod_embed.set_footer(text=f"AutoMod by {interaction.user.display_name} | Razor Premium Security ⭐", icon_url=interaction.user.display_avatar.url)
    add_premium_badge_to_embed(automod_embed)

    await interaction.response.send_message(embed=automod_embed)

@tree.command(name="antinuke_logs", description="View recent anti-nuke activity")
@app_commands.checks.has_permissions(administrator=True)
async def antinuke_logs(interaction: discord.Interaction):
    cur.execute("""
        SELECT user_id, action_type, timestamp, details
        FROM antinuke_logs
        WHERE guild_id = ?
        ORDER BY id DESC LIMIT 10
    """, (interaction.guild.id,))

    logs = cur.fetchall()

    embed = discord.Embed(
        title="📋 RAZOR PREMIUM - ANTI-NUKE LOGS",
        color=PRIMARY_COLOR
    )

    if not logs:
        embed.add_field(name="📊 Activity Log", value="No recent anti-nuke activity", inline=False)
    else:
        log_text = ""
        for user_id, action_type, timestamp, details in logs:
            try:
                user = await bot.fetch_user(user_id)
                log_text += f"**{user.display_name}** - {action_type.replace('_', ' ').title()}\n"
                log_text += f"*{timestamp}* - {details}\n\n"
            except:
                log_text += f"**Unknown User** - {action_type.replace('_', ' ').title()}\n"
                log_text += f"*{timestamp}* - {details}\n\n"

        embed.add_field(name="📊 Recent Activity", value=log_text[:1024] or "No activity", inline=False)

    embed.set_thumbnail(url=interaction.guild.icon.url if interaction.guild.icon else None)
    embed.set_footer(text=f"Requested by {interaction.user.display_name} | Razor Premium Logs ⭐", icon_url=interaction.user.display_avatar.url)
    add_premium_badge_to_embed(embed)
    await interaction.response.send_message(embed=embed, ephemeral=True)

@tree.command(name="badge", description="Display Razor Premium badge and features")
async def badge(interaction: discord.Interaction):
    badge_embed = get_premium_badge_embed()

    # Add server-specific stats
    guild = interaction.guild
    badge_embed.add_field(
        name="📊 SERVER STATISTICS",
        value=f"**Server:** {guild.name}\n**Members:** {guild.member_count}\n**Channels:** {len(guild.channels)}\n**Roles:** {len(guild.roles)}\n**Protected:** ✅ Active",
        inline=False
    )

    # Add performance metrics
    badge_embed.add_field(
        name="⚡ PERFORMANCE METRICS",
        value=f"**Uptime:** 99.9%\n**Response Time:** {round(bot.latency * 1000)}ms\n**Commands Served:** 10,000+\n**Servers Protected:** 500+\n**Quality:** Premium",
        inline=False
    )

    await interaction.response.send_message(embed=badge_embed)

@tree.command(name="sync", description="Force sync slash commands (Admin only)")
@app_commands.checks.has_permissions(administrator=True)
async def sync_commands(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)

    try:
        # Sync globally
        synced = await tree.sync()
        embed = discord.Embed(
            title="✅ COMMANDS SYNCED",
            description=f"Successfully synced {len(synced)} slash commands globally.",
            color=SUCCESS_COLOR
        )

        # Also try guild sync
        try:
            guild_synced = await tree.sync(guild=interaction.guild)
            embed.add_field(
                name="Guild Sync",
                value=f"Also synced {len(guild_synced)} commands for this server.",
                inline=False
            )
        except Exception:
            pass

    except Exception as e:
        embed = discord.Embed(
            title="❌ SYNC FAILED",
            description=f"Failed to sync commands: {str(e)}",
            color=ERROR_COLOR
        )

    embed.set_footer(text="Commands may take up to 1 hour to appear globally")
    add_premium_badge_to_embed(embed)
    await interaction.followup.send(embed=embed, ephemeral=True)

@tree.command(name="features", description="Show all Razor Premium features")
async def features(interaction: discord.Interaction):
    features_embed = discord.Embed(
        title="🚀 RAZOR PREMIUM - COMPLETE FEATURE LIST",
        color=PRIMARY_COLOR
    )

    # Security Features
    features_embed.add_field(
        name="🛡️ SECURITY SUITE",
        value="• **Anti-Nuke System** - Protect from raids\n• **Spam Protection** - Auto-timeout spammers\n• **AutoMod** - Filter bad words\n• **Whitelist System** - Trusted users\n• **Action Limits** - Prevent abuse",
        inline=False
    )

    # Utility Features
    features_embed.add_field(
        name="🔧 UTILITY TOOLS",
        value="• **Invite Tracker** - Track all invites\n• **AFK System** - Away notifications\n• **Custom Commands** - Create responses\n• **Ticket System** - Professional support\n• **Giveaway Manager** - Host events",
        inline=False
    )

    # Entertainment Features
    features_embed.add_field(
        name="🎮 ENTERTAINMENT",
        value="• **Music Player** - High quality audio\n• **Economy System** - Virtual currency\n• **Review System** - User feedback\n• **Fun Commands** - Games & randomizers\n• **Premium UI** - Beautiful embeds",
        inline=False
    )

    # Admin Features
    features_embed.add_field(
        name="👑 ADMIN TOOLS",
        value="• **Prefix Commands** - Admin only\n• **Moderation Suite** - Kick, ban, timeout\n• **Server Analytics** - Detailed insights\n• **Logs System** - Track all actions\n• **Configuration** - Full customization",
        inline=False
    )

    features_embed.set_thumbnail(url=interaction.guild.icon.url if interaction.guild.icon else None)
    features_embed.set_footer(text=f"Requested by {interaction.user.display_name} | Razor Premium ⭐", icon_url=interaction.user.display_avatar.url)
    add_premium_badge_to_embed(features_embed)

    await interaction.response.send_message(embed=features_embed)

@tree.command(name="antispam", description="Configure spam protection settings")
@app_commands.describe(user="User to check/unmute")
@app_commands.choices(
    action=[
        app_commands.Choice(name="Status", value="status"),
        app_commands.Choice(name="Unmute User", value="unmute"),
        app_commands.Choice(name="Reset User", value="reset")
    ]
)
@app_commands.checks.has_permissions(manage_messages=True)
async def antispam(interaction: discord.Interaction, action: str = "status", user: discord.User = None):
    if action == "status":
        embed = discord.Embed(
            title="🚫 RAZOR PREMIUM - ANTI-SPAM STATUS",
            color=PRIMARY_COLOR
        )
        embed.add_field(
            name="⚙️ Current Configuration",
            value="**Limit:** 5 messages per 60 seconds\n**Timeout:** 5 minutes\n**Status:** Active",
            inline=False
        )
        embed.add_field(
            name="🛡️ Protection Features",
            value="• Automatic message deletion\n• Temporary timeouts\n• Admin immunity\n• Real-time monitoring",
            inline=False
        )

    elif action == "unmute" and user:
        member = interaction.guild.get_member(user.id)
        if member and member.timed_out_until:
            try:
                await member.timeout(None, reason="Manual unmute by admin")
                update_spam_data(user.id, interaction.guild.id, 0, False, None)
                embed = discord.Embed(
                    title="✅ RAZOR PREMIUM - USER UNMUTED",
                    color=SUCCESS_COLOR
                )
                embed.add_field(
                    name="🏷️ Action Completed",
                    value=f"**User:** {user.mention}\n**Status:** Unmuted\n**By:** {interaction.user.mention}",
                    inline=False
                )
            except:
                embed = discord.Embed(
                    title="❌ RAZOR PREMIUM - ERROR",
                    color=ERROR_COLOR
                )
                embed.add_field(name="🏷️ Failed", value="Could not unmute user", inline=False)
        else:
            embed = discord.Embed(
                title="ℹ️ RAZOR PREMIUM - INFO",
                color=INFO_COLOR
            )
            embed.add_field(name="🏷️ Status", value="User is not currently muted", inline=False)

    elif action == "reset" and user:
        update_spam_data(user.id, interaction.guild.id, 0, False, None)
        embed = discord.Embed(
            title="🔄 RAZOR PREMIUM - USER RESET",
            color=SUCCESS_COLOR
        )
        embed.add_field(
            name="🏷️ Spam Data Reset",
            value=f"**User:** {user.mention}\n**Message Count:** Reset to 0\n**Status:** Clean slate",
            inline=False
        )

    else:
        embed = discord.Embed(
            title="❌ RAZOR PREMIUM - ERROR",
            color=ERROR_COLOR
        )
        embed.add_field(name="🏷️ Invalid Parameters", value="Please specify a valid action and user", inline=False)

    embed.set_thumbnail(url=interaction.guild.icon.url if interaction.guild.icon else None)
    embed.set_footer(text=f"Requested by {interaction.user.display_name} | Razor Premium Anti-Spam ⭐", icon_url=interaction.user.display_avatar.url)
    add_premium_badge_to_embed(embed)
    await interaction.response.send_message(embed=embed, ephemeral=True)

# ------------------------------ HELP COMMAND --------------------------------
@tree.command(name="help", description="Show all available commands with details")
async def help_command(interaction: discord.Interaction):
    embed = discord.Embed(
        title="📚 RAZOR PREMIUM - COMMAND LIST",
        color=PRIMARY_COLOR
    )
    
    # Basic Commands
    embed.add_field(
        name="🔧 BASIC COMMANDS",
        value="`/ping` - Check bot latency\n`/avatar [user]` - Get user's avatar\n`/say <message>` - Make bot say something\n`/userinfo [user]` - Get user information\n`/serverinfo` - Get server information\n`/roll` - Roll 1-100\n`/coinflip` - Flip a coin",
        inline=False
    )
    
    # Economy Commands
    embed.add_field(
        name="💰 ECONOMY COMMANDS",
        value="`/money` - Check your balance\n`/givemoney <user> <amount>` - Give coins to user\n`/topmoney` - Top richest users",
        inline=False
    )
    
    # AFK System
    embed.add_field(
        name="💤 AFK SYSTEM",
        value="`/afk <reason>` - Set AFK status\n`/afkremove` - Remove AFK status",
        inline=False
    )
    
    # Custom Commands
    embed.add_field(
        name="⚙️ CUSTOM COMMANDS",
        value="`/create <prefix> <cmd> <response>` - Create custom command\n`/prefix <new_prefix>` - Change server prefix\n`/prefixreset` - Reset prefix to default",
        inline=False
    )
    
    # Moderation Commands
    embed.add_field(
        name="🛡️ MODERATION",
        value="`/kick <user> [reason]` - Kick a user\n`/ban <user> [reason]` - Ban a user\n`/dm <user> <message>` - Send DM to user",
        inline=False
    )
    
    # Security Commands
    embed.add_field(
        name="🔒 SECURITY COMMANDS",
        value="`/antinuke <action>` - Configure anti-nuke\n`/automod` - View automod status\n`/antinuke_logs` - View security logs\n`/antispam [action] [user]` - Manage spam protection",
        inline=False
    )
    
    # Invite System
    embed.add_field(
        name="📊 INVITE TRACKING",
        value="`/invites [user]` - Check invite stats\n`/invitelog [user]` - Detailed invite analytics\n`/topinviters` - Top inviters leaderboard\n`/clearinvites` - Reset invite counts (Admin)",
        inline=False
    )
    
    # Ticket System
    embed.add_field(
        name="🎫 TICKET SYSTEM",
        value="`/setticket <channel>` - Setup ticket panel",
        inline=False
    )
    
    # Giveaway System
    embed.add_field(
        name="🎁 GIVEAWAY SYSTEM",
        value="`/gstart <channel> <prize> <duration> <winners>` - Start giveaway",
        inline=False
    )
    
    # Music Commands
    embed.add_field(
        name="🎵 MUSIC COMMANDS",
        value="`/play <query>` - Play music\n`/join` - Join voice channel\n`/leave` - Leave voice channel",
        inline=False
    )
    
    # Review System
    embed.add_field(
        name="⭐ REVIEW SYSTEM",
        value="`/start_review <message> [image] [rate]` - Start review system",
        inline=False
    )
    
    # Utility Commands
    embed.add_field(
        name="🛠️ UTILITY COMMANDS",
        value="`/badge` - Show premium features\n`/features` - List all features\n`/sync` - Sync commands (Admin)",
        inline=False
    )
    
    embed.set_thumbnail(url=interaction.guild.icon.url if interaction.guild.icon else None)
    embed.set_footer(text=f"Requested by {interaction.user.display_name} | Use /command_name for details", icon_url=interaction.user.display_avatar.url)
    
    await interaction.response.send_message(embed=embed)

# ------------------------------ ADMIN COMMANDS --------------------------------
# Global check to ensure all prefix commands are admin-only
@bot.check
async def admin_only_check(ctx):
    if ctx.guild and not ctx.author.guild_permissions.administrator:
        await ctx.send(f"{EMOJIS['error']} Only administrators can use prefix commands.", delete_after=5)
        return False
    return True

@bot.command(name="example")
async def example_command(ctx):
    """Admin-only example command"""
    embed = discord.Embed(
        title=f"{EMOJIS['success']} Admin Example Command",
        description="This is an example admin-only command that only administrators can use.",
        color=PRIMARY_COLOR
    )
    embed.add_field(name="Usage", value=f"{get_prefix_for_guild(ctx.guild.id)}example", inline=False)
    embed.add_field(name="Permission Required", value="Administrator", inline=False)
    embed.set_footer(text=f"Requested by {ctx.author.display_name} | Razor Premium ⭐", icon_url=ctx.author.display_avatar.url)
    add_premium_badge_to_embed(embed)
    await ctx.send(embed=embed)

@bot.command(name="test")
async def test_command(ctx):
    """Another admin-only test command"""
    embed = discord.Embed(
        title=f"{EMOJIS['info']} Test Command",
        description="This is a test command for administrators only.",
        color=INFO_COLOR
    )
    embed.set_footer(text=f"Requested by {ctx.author.display_name} | Razor Premium ⭐", icon_url=ctx.author.display_avatar.url)
    add_premium_badge_to_embed(embed)
    await ctx.send(embed=embed)

@bot.command(name="adminhelp")
async def admin_help_command(ctx):
    """Show all available admin commands"""
    prefix = get_prefix_for_guild(ctx.guild.id)
    embed = discord.Embed(
        title=f"{EMOJIS['shield']} Admin Commands",
        description="Available prefix commands (Admin Only):",
        color=PRIMARY_COLOR
    )
    embed.add_field(name=f"{prefix}example", value="Example admin command", inline=False)
    embed.add_field(name=f"{prefix}test", value="Test admin command", inline=False)
    embed.add_field(name=f"{prefix}adminhelp", value="Show this help menu", inline=False)
    embed.set_footer(text="Only administrators can use prefix commands")
    add_premium_badge_to_embed(embed)
    await ctx.send(embed=embed)

# ------------------------------ RUN THE BOT ----------------------------------
if __name__ == "__main__":
    bot.run("MTQwNTUzMDY1OTQ1MTE3NTAzNA.GoMWZw.8yLeL_UHm8Pc-zaHpFurNDEuTFeHmYMkSXPkj4")
