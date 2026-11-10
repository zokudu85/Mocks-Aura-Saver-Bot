# Copyright github.com/devgagan

import os
import re
import json
import asyncio
import requests
from threading import Thread
from urllib.parse import urljoin, urlparse, parse_qs

from bs4 import BeautifulSoup
from flask import Flask
from telethon import TelegramClient, events

# ==========================================
# 🔐 RENDER SE DETAILS UTHA RAHE HAIN
# ==========================================
API_ID = int(os.environ.get("API_ID", 0))
API_HASH = os.environ.get("API_HASH", "")
BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
OWNER_ID = int(os.environ.get("OWNER_ID", 0))

# 👇 YAHAN AUTH_CODE KO HI COOKIE MAAN RAHE HAIN 👇
COOKIE = os.environ.get("AUTH_CODE", "")

# Initialize the Telethon client
bot = TelegramClient("olive_bot", API_ID, API_HASH).start(bot_token=BOT_TOKEN)


# ==========================================
# COOKIE HANDLER (JSON ko string mein badalta hai)
# ==========================================
def get_cookie_string(cookie_data):
    cookie_data = cookie_data.strip()
    if cookie_data.startswith("[") and cookie_data.endswith("]"):
        try:
            cookies = json.loads(cookie_data)
            return "; ".join([f"{c['name']}={c['value']}" for c in cookies])
        except:
            return cookie_data
    return cookie_data

# Final string cookie
FINAL_COOKIE = get_cookie_string(COOKIE)


# ==========================================
# HEADERS & URLS
# ==========================================
HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
    "Accept-Encoding": "gzip, deflate, br, zstd",
    "Accept-Language": "en-US,en;q=0.9",
    "Connection": "keep-alive",
    "Host": "u1.oliveboard.in",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/132.0.0.0 Safari/537.36",
    "Cookie": FINAL_COOKIE
}

BASE_URIS = {
    "rrbpo": "https://u1.oliveboard.in/exams/tests/part.php?c=ibpsrrbscp&testid={test_id}",
    "ibpspo": "https://u1.oliveboard.in/exams/tests/part.php?c=ibpspo&testid={test_id}",
    # Aur exams yahan add kar sakte ho
}


def get_page(url):
    return requests.get(url, headers=HEADERS, timeout=30)


# ==========================================
# MERGE LOGIC (Dono sections ko jodta hai)
# ==========================================
def merge_sections(html1, html2):
    soup1 = BeautifulSoup(html1, "html.parser")
    soup2 = BeautifulSoup(html2, "html.parser")

    pane1 = soup1.find(id="question-inner-pane")
    pane2 = soup2.find(id="question-inner-pane")

    if not pane1 or not pane2:
        raise Exception("Questions nahi mil rahe.")

    q_divs1 = pane1.find_all("div", class_="question-outer-div")
    q_divs2 = pane2.find_all("div", class_="question-outer-div")

    if not q_divs1 or not q_divs2:
         raise Exception("Question divs nahi mile.")

    pane1.clear()

    for div in q_divs1:
        pane1.append(div)

    for div in q_divs2:
        pane1.append(div)

    total_questions = len(q_divs1) + len(q_divs2)
    pane1.insert(0, BeautifulSoup(f"<script>var firstQid=1; var nq={total_questions}; var lastQid=nq;</script>", "html.parser"))

    if soup1.title:
        soup1.title.string = "MERGED MOCK TEST"

    return str(soup1)


# ==========================================
# SEND TEST FUNCTION
# ==========================================
async def send_test(event, url, exam, test_id):
    try:
        await event.respond(f"⏳ Test {test_id}: Fetching Section 1...")
        res1 = await asyncio.to_thread(get_page, url)
        
        if urlparse(res1.url).netloc != "u1.oliveboard.in":
            await event.respond("❌ Cookie expire ho gayi hai. Nayi cookie daalo.")
            return "login"

        await event.respond(f"⏳ Test {test_id}: Fetching Section 2...")
        url2 = f"{url}&from=test"
        res2 = await asyncio.to_thread(get_page, url2)

        await event.respond(f"🧩 Test {test_id}: Merging both sections...")
        merged_html = merge_sections(res1.text, res2.text)

        final_soup = BeautifulSoup(merged_html, "html.parser")
        final_soup = apply_watermark(final_soup)

        file_name = f"Test_{test_id}@Dark_V1rus.html"
        with open(file_name, "w", encoding="utf-8") as f:
            f.write(str(final_soup))

        await event.respond(f"✅ **Test ID: {test_id}**\n__Powered by Banking Aura__", file=file_name)
        os.remove(file_name)
        return "ok"

    except Exception as e:
        await event.respond(f"❌ Error in {test_id}: {str(e)}")
        return "fail"


# ==========================================
# WATERMARK & LAYOUT FIX
# ==========================================
DEFAULT_BASE_URL = "https://u1.oliveboard.in/exams/tests/"

WATERMARK_HTML = """<style>
#ba-watermark{position:fixed;inset:0;z-index:2147483000;pointer-events:none;overflow:hidden;display:flex;align-items:center;justify-content:center;user-select:none}
#ba-watermark span{font-family:Arial,sans-serif;font-weight:900;font-size:10vw;letter-spacing:2px;white-space:nowrap;color:rgba(0,0,0,0.06);transform:rotate(-35deg)}
</style>
<div id="ba-watermark"><span>BANKING AURA</span></div>"""

def apply_watermark(soup):
    for tag in soup.find_all(["a", "img", "link", "script"]):
        if tag.has_attr("href") and not tag["href"].startswith("http"):
            tag["href"] = urljoin(DEFAULT_BASE_URL, tag["href"])
        if tag.has_attr("src") and not tag["src"].startswith("http"):
            tag["src"] = urljoin(DEFAULT_BASE_URL, tag["src"])

    for a in soup.find_all("a"):
        if a.has_attr("onclick"):
            a["href"] = "javascript:void(0)"

    if soup.body and not soup.find(id="ba-watermark"):
        soup.body.append(BeautifulSoup(WATERMARK_HTML, "html.parser"))

    return soup


# ==========================================
# BOT COMMANDS
# ==========================================
@bot.on(events.NewMessage(pattern="/start"))
async def start(event):
    await event.reply(
        "**Welcome to the Mock Extractor Bot!**\n\n"
        "Send `/fetch exam testid`\n"
        "**__Example: `/fetch rrbpo 18`__**\n\n"
        "__**Powered by Banking Aura**__"
    )

@bot.on(events.NewMessage(pattern=r"/fetch (\w+) (\d+)"))
async def fetch_exam(event):
    if event.sender_id != OWNER_ID:
        return

    exam = event.pattern_match.group(1).lower()
    test_id = event.pattern_match.group(2)

    if exam not in BASE_URIS:
        await event.respond("❌ Invalid exam type. Supported: " + ", ".join(BASE_URIS.keys()))
        return

    url = BASE_URIS[exam].format(test_id=test_id)
    status = await send_test(event, url, exam, test_id)
    
    if status == "ok":
        await event.respond(f"🏁 Test {test_id} Done!")


# Flask Server for Render
app = Flask(__name__)

@app.route("/")
def home():
    return "Bot is Alive!"

def run_web():
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))

Thread(target=run_web, daemon=True).start()

print("Bot Started...")
bot.run_until_disconnected()

# Copyright github.com/devgaganin
# no part of this code/edits is allowed to use for commercial / sale purposes
