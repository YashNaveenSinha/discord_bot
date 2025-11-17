import os
os.environ["DISCORD_NO_AUDIO"] = "1"


# --------------------------
# KEEP-ALIVE FLASK WEB SERVER
# --------------------------
from flask import Flask
import threading

app = Flask(__name__)

@app.route("/")
def home():
    return "Bot is running!"

def run_web():
    app.run(host="0.0.0.0", port=8080)


# --------------------------
# IMPORTS
# --------------------------
import discord
from discord.ext import commands
import pandas as pd
import io
import os
from datetime import datetime

from paddleocr import PaddleOCR
from PIL import Image
import numpy as np


# --------------------------
# DISCORD BOT SETUP
# --------------------------
bot = commands.Bot(command_prefix="!")

CSV_PATH = "bear_hunt_data.csv"
LOG_PATH = "upload_log.txt"

# PaddleOCR (NO TORCH, FAST, WORKS ON RENDER)
ocr = PaddleOCR(use_angle_cls=True, lang='en')


# ------------------------------
# PROTECTION SETTINGS
# ------------------------------
ALLOWED_USERS = [
    1130187090261463130,   # your Discord ID
    817852292295688202,
]

ALLOWED_ROLE_NAME = "OCR Access"

ALLOWED_CHANNELS = [
    112233445566778899,
]


# ------------------------------
# Setup CSV + Log if missing
# ------------------------------
if not os.path.exists(CSV_PATH):
    pd.DataFrame(columns=["name", "damage"]).to_csv(CSV_PATH, index=False)

if not os.path.exists(LOG_PATH):
    with open(LOG_PATH, "w") as f:
        f.write("=== Upload Log ===\n\n")


# ------------------------------
# PADDLE OCR EXTRACTOR
# ------------------------------
def extract_text_from_image(img_bytes):
    """Convert image bytes → full OCR line list using PaddleOCR."""
    img = Image.open(io.BytesIO(img_bytes)).convert("RGB")
    img_np = np.array(img)

    result = ocr.ocr(img_np, cls=True)
    if not result or not result[0]:
        return []

    lines = [line[1][0] for line in result[0]]
    return lines


# ------------------------------
# OCR PARSER FOR GAME FORMAT
# ------------------------------
def parse_ocr_text(ocr_lines):
    data = []
    current_name = None

    for line in ocr_lines:
        line = line.strip()

        # Detect player name
        if line.startswith("[") and "Damage" not in line:
            current_name = line

        # Detect "Damage: X" line
        elif "Damage" in line and current_name:
            damage = line.split(":")[-1].replace(",", "").strip()

            if damage.isdigit():
                data.append((current_name, int(damage)))

            current_name = None

    return data


# ------------------------------
# SECURITY CHECK
# ------------------------------
def is_authorized(ctx):
    author = ctx.author
    channel = ctx.channel
    guild = ctx.guild

    if channel.id not in ALLOWED_CHANNELS:
        return False, "⛔ This command is not allowed in this channel."

    if author.id not in ALLOWED_USERS:
        return False, "⛔ You are not authorized to use this bot."

    allowed_role = discord.utils.get(guild.roles, name=ALLOWED_ROLE_NAME)
    if allowed_role not in author.roles:
        return False, f"⛔ You must have the **{ALLOWED_ROLE_NAME}** role."

    return True, ""


# ------------------------------
# PROCESS IMAGES COMMAND
# ------------------------------
@bot.command()
async def process(ctx):
    ok, error = is_authorized(ctx)
    if not ok:
        await ctx.send(error)
        return

    if len(ctx.message.attachments) == 0:
        await ctx.send("⚠️ Please attach 1+ Bear Hunt screenshots.")
        return

    df = pd.read_csv(CSV_PATH)
    total_found = 0
    log_entries = []

    for attachment in ctx.message.attachments:
        img_bytes = await attachment.read()

        ocr_lines = extract_text_from_image(img_bytes)
        extracted = parse_ocr_text(ocr_lines)

        for name, dmg in extracted:
            total_found += 1

            # update existing or add new
            if name in df["name"].values:
                df.loc[df["name"] == name, "damage"] = dmg
            else:
                df.loc[len(df)] = [name, dmg]

            log_entries.append(
                f"{datetime.now()} | {ctx.author} uploaded {attachment.filename} → {name}: {dmg}"
            )

    df.to_csv(CSV_PATH, index=False)

    with open(LOG_PATH, "a") as f:
        f.write("\n".join(log_entries) + "\n")

    await ctx.send(
        f"✅ Processed **{total_found} entries** from **{len(ctx.message.attachments)} images**."
    )


# ------------------------------
# LEADERBOARD COMMAND
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

    df = df.sort_values(by="damage", ascending=False).head(limit)

    msg = "**🏆 Top Damage Rankings:**\n\n"
    for i, row in df.iterrows():
        msg += f"**{row['name']}** — `{row['damage']:,}`\n"

    await ctx.send(msg)


# ------------------------------
# RESET COMMAND
# ------------------------------
@bot.command()
async def reset(ctx):

    ok, error = is_authorized(ctx)
    if not ok:
        await ctx.send(error)
        return

    pd.DataFrame(columns=["name", "damage"]).to_csv(CSV_PATH, index=False)

    with open(LOG_PATH, "a") as f:
        f.write(f"\n[{datetime.now()}] RESET by {ctx.author}\n\n")

    await ctx.send("🧹 Data reset. CSV cleared.")


# ----------------------------------------------------
# Bot Ready
# ----------------------------------------------------
@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}")
    print("Bot is running with PaddleOCR + protection + logging.")


# Start keepalive server
threading.Thread(target=run_web).start()


# Start bot
bot.run(os.environ["DISCORD_TOKEN"])
