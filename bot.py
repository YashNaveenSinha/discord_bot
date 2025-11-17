import discord
from discord.ext import commands
import easyocr
import pandas as pd
import io
import os
from datetime import datetime

bot = commands.Bot(command_prefix="!")

CSV_PATH = "bear_hunt_data.csv"
LOG_PATH = "upload_log.txt"
reader = easyocr.Reader(['en'])

# ------------------------------
# PROTECTION SETTINGS
# ------------------------------

# 1️⃣ Allowed user IDs
ALLOWED_USERS = [
    123456789012345678,   # your Discord ID
    987654321012345678,  
]

# 2️⃣ Only allow users with the "OCR Access" role
ALLOWED_ROLE_NAME = "OCR Access"

# 3️⃣ Only allow commands in these channels
ALLOWED_CHANNELS = [
    112233445566778899,
]

# ------------------------------
# Setup CSV and Log if missing
# ------------------------------
if not os.path.exists(CSV_PATH):
    pd.DataFrame(columns=["name", "damage"]).to_csv(CSV_PATH, index=False)

if not os.path.exists(LOG_PATH):
    with open(LOG_PATH, "w") as f:
        f.write("=== Upload Log ===\n\n")

# ------------------------------
# OCR PARSER
# ------------------------------
def parse_ocr_text(ocr_lines):
    data = []
    current_name = None

    for line in ocr_lines:
        line = line.strip()

        # Extract name
        if line.startswith("[") and "Damage" not in line:
            current_name = line

        # Extract damage
        elif "Damage" in line and current_name:
            damage = line.split(":")[-1].replace(",", "").strip()
            data.append((current_name, int(damage)))
            current_name = None

    return data


# ------------------------------
# SECURITY CHECKER
# ------------------------------
def is_authorized(ctx):
    author = ctx.author
    channel = ctx.channel
    guild = ctx.guild

    # Channel check
    if channel.id not in ALLOWED_CHANNELS:
        return False, "⛔ This command is not allowed in this channel."

    # User ID check
    if author.id not in ALLOWED_USERS:
        return False, "⛔ You are not authorized to use this bot."

    # Role check
    allowed_role = discord.utils.get(guild.roles, name=ALLOWED_ROLE_NAME)
    if allowed_role not in author.roles:
        return False, f"⛔ You must have the **{ALLOWED_ROLE_NAME}** role to use this command."

    return True, ""


# ------------------------------
# (5) — MULTI IMAGE OCR + LOGGING + CSV UPDATE COMMAND
# ------------------------------
@bot.command()
async def process(ctx):
    ok, error = is_authorized(ctx)
    if not ok:
        await ctx.send(error)
        return

    if len(ctx.message.attachments) == 0:
        await ctx.send("⚠️ Please attach 1 or more Bear Hunt screenshots.")
        return

    df = pd.read_csv(CSV_PATH)
    total_found = 0

    log_entries = []

    for attachment in ctx.message.attachments:
        img_bytes = await attachment.read()
        ocr_lines = reader.readtext(img_bytes, detail=0)
        extracted = parse_ocr_text(ocr_lines)

        for name, dmg in extracted:
            total_found += 1

            # Update or insert
            if name in df["name"].values:
                df.loc[df["name"] == name, "damage"] = dmg
            else:
                df.loc[len(df)] = [name, dmg]

            # Logging
            log_entries.append(
                f"{datetime.now()} | {ctx.author} uploaded {attachment.filename} → {name}: {dmg}"
            )

    # Save CSV
    df.to_csv(CSV_PATH, index=False)

    # Save log entries
    with open(LOG_PATH, "a") as f:
        f.write("\n".join(log_entries) + "\n")

    await ctx.send(f"✅ Successfully processed **{total_found} entries** from **{len(ctx.message.attachments)} images**.\nCSV updated on server.")


# ------------------------------
# (2) — LEADERBOARD COMMAND
# ------------------------------
@bot.command()
async def top(ctx, limit: int = 10):

    ok, error = is_authorized(ctx)
    if not ok:
        await ctx.send(error)
        return

    df = pd.read_csv(CSV_PATH)

    if df.empty:
        await ctx.send("⚠️ No data found.")
        return

    df = df.sort_values(by="damage", ascending=False)
    df = df.head(limit)

    msg = "**🏆 Top Damage Rankings:**\n\n"
    for i, row in df.iterrows():
        msg += f"**{row['name']}** — `{row['damage']:,}`\n"

    await ctx.send(msg)


# ------------------------------
# (4) — RESET EVENT COMMAND
# ------------------------------
@bot.command()
async def reset(ctx):

    ok, error = is_authorized(ctx)
    if not ok:
        await ctx.send(error)
        return

    pd.DataFrame(columns=["name", "damage"]).to_csv(CSV_PATH, index=False)

    with open(LOG_PATH, "a") as f:
        f.write(f"\n[{datetime.now()}] EVENT RESET by {ctx.author}\n\n")

    await ctx.send("🧹 **Event data has been reset.** CSV cleared.")


# ----------------------------------------------------
# Bot Ready
# ----------------------------------------------------
@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}")
    print("Bot is running with full protection + logging.")
