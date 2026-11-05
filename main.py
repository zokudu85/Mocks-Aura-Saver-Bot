# Copyright github.com/devgaganin

import os
import asyncio
import requests
from threading import Thread
from urllib.parse import urljoin

from bs4 import BeautifulSoup
from flask import Flask
from telethon import TelegramClient, events

from config import API_ID, API_HASH, BOT_TOKEN, COOKIES, OWNER_ID

# Initialize the Telethon client
bot = TelegramClient("olive_bot", API_ID, API_HASH).start(bot_token=BOT_TOKEN)


@bot.on(events.NewMessage(pattern="/start"))
async def start(event):
    """Handle /start command"""
    await event.reply(
        "**Welcome to the Mock Extractor Bot!**\n\n"
        "Send `/fetch exam testid` for oliveboard\n"
        "Or send `/url <full test link>`\n\n"
        "**__Example: `/fetch ntpc1 1`__**\n\n"
        "__**Powered by Banking Aura**__"
    )


# --- OLIVEBOARD ---

# Headers for HTTP requests
HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
    "Accept-Encoding": "gzip, deflate, br, zstd",
    "Accept-Language": "en-US,en;q=0.9",
    "Connection": "keep-alive",
    "Cookie": COOKIES,
    "Host": "u1.oliveboard.in",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Sec-Fetch-User": "?1",
    "Upgrade-Insecure-Requests": "1",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/132.0.0.0 Safari/537.36",
    "sec-ch-ua": '"Not A(Brand";v="8", "Chromium";v="132", "Google Chrome";v="132"',
    "sec-ch-ua-mobile": "?0",
    "sec-ch-ua-platform": '"Windows"',
}


# Base URIs for different exam types
BASE_URIS = {
    "cgl1": "https://u1.oliveboard.in/exams/tests/?c=ssc2019&testid={test_id}",
    "chsl": "https://u1.oliveboard.in/exams/tests/?c=chsl&testid={test_id}",
    "chsl2": "https://u1.oliveboard.in/exams/tests/?c=chsl2&testid={test_id}",
    "sscmts": "https://u1.oliveboard.in/exams/tests/?c=sscmts&testid={test_id}",
    "ntpc1": "https://u1.oliveboard.in/exams/tests/?c=ntpc1&os=1&testid={test_id}",
    "ntpc2": "https://u1.oliveboard.in/exams/tests/?c=ntpc2&os=1&testid={test_id}",
    "rrbalp1": "https://u1.oliveboard.in/exams/tests/?c=rrbalp1&os=1&testid={test_id}",
    "rrbalp2": "https://u1.oliveboard.in/exams/tests/?c=rrbalp2&os=1&testid={test_id}",
    "rrbgrpd": "https://u1.oliveboard.in/exams/tests/?c=rrbgrpd&os=1&testid={test_id}",
    # Banking exams (c= codes NOT verified: check them against a real Oliveboard test URL)
    "ibpspo": "https://u1.oliveboard.in/exams/tests/?c=ibpspo&testid={test_id}",
    "ibpsclerk": "https://u1.oliveboard.in/exams/tests/?c=ibpsclerk&testid={test_id}",
    "sbipo": "https://u1.oliveboard.in/exams/tests/?c=sbipo&testid={test_id}",
    "sbiclerk": "https://u1.oliveboard.in/exams/tests/?c=sbiclerk&testid={test_id}",
    "rrbpo": "https://u1.oliveboard.in/exams/tests/?c=rrbpo&testid={test_id}",
    "rrbclerk": "https://u1.oliveboard.in/exams/tests/?c=rrbclerk&testid={test_id}",
}


def get_page(url):
    """Blocking GET (run in a thread so the bot stays responsive)."""
    return requests.get(url, headers=HEADERS, timeout=30)


async def send_test(event, url, caption):
    """Download a test page, rewrite its links, and send it as an HTML file."""
    try:
        response = await asyncio.to_thread(get_page, url)
        response.raise_for_status()
    except requests.exceptions.RequestException as e:
        await event.respond(f"Failed to fetch the test details: {e}")
        return

    if "login" in response.url.lower():
        await event.respond("Login page aaya. Cookies expire ho gayi hain, naya AUTH_CODE daalo.")
        return

    html = modify_html(response.text, url)
    file_name = f"test_{event.id}.html"
    with open(file_name, "w", encoding="utf-8") as f:
        f.write(html)
    try:
        await event.respond(caption, file=file_name)
    finally:
        os.remove(file_name)


@bot.on(events.NewMessage(pattern=r"/fetch (\w+) (\d+)"))
async def fetch_exam(event):
    """Fetches the question paper based on exam type and test ID."""
    if event.sender_id != OWNER_ID:
        await event.reply("Not allowed")
        return
    exam = event.pattern_match.group(1).lower()
    test_id = event.pattern_match.group(2)

    if exam not in BASE_URIS:
        await event.respond("Invalid exam type! Supported types are: " + ", ".join(BASE_URIS.keys()))
        return

    url = BASE_URIS[exam].format(test_id=test_id)
    caption = (
        f"**📕 Exam Name: {exam}**\n**🆔 Test ID: {test_id}**\n"
        f"**✅ Type: Question**\n\n__**Powered by @Dark_V1rus**__"
    )
    await send_test(event, url, caption)


@bot.on(events.NewMessage(pattern=r"/url (https://u1\.oliveboard\.in/\S+)"))
async def fetch_url(event):
    """Fetches the question paper from a full Oliveboard test link."""
    if event.sender_id != OWNER_ID:
        await event.reply("Not allowed")
        return
    url = event.pattern_match.group(1)
    caption = "**✅ Type: Question**\n\n__**Powered by Banking Aura**__"
    await send_test(event, url, caption)


DEFAULT_BASE_URL = "https://u1.oliveboard.in/exams/tests/"

WATERMARK_TEXT = "BANKING AURA"
WATERMARK_HTML = """<style>
#ba-watermark{position:fixed;inset:0;z-index:2147483000;pointer-events:none;overflow:hidden;display:flex;align-items:center;justify-content:center;user-select:none}
#ba-watermark span{font-family:Arial,Helvetica,sans-serif;font-weight:800;font-size:9vw;letter-spacing:.05em;white-space:nowrap;color:rgba(0,0,0,.07);transform:rotate(-30deg)}
@media print{#ba-watermark span{color:rgba(0,0,0,.12)}}
</style>
<div id="ba-watermark" aria-hidden="true"><span>%s</span></div>
""" % WATERMARK_TEXT


def finalize_html(soup):
    """Fix button links (they must not navigate/open a new tab) and add the watermark."""
    for a in soup.find_all("a"):
        if a.has_attr("onclick"):
            a["href"] = "javascript:void(0)"
            a.attrs.pop("target", None)
    if soup.body is not None and not soup.find(id="ba-watermark"):
        soup.body.append(BeautifulSoup(WATERMARK_HTML, "html.parser"))
    return soup.prettify()


def modify_html(html, full_url):
    """
    Modifies the HTML content by appending the appropriate base URL
    to relative links for 'href' and 'src' attributes.
    """
    soup = BeautifulSoup(html, "html.parser")

    for tag in soup.find_all(["a", "img", "link", "script"]):
        # Handle 'href' attribute for <a> and <link> tags
        if tag.has_attr("href"):
            if not tag["href"].startswith("http"):  # Only modify relative links
                tag["href"] = urljoin(DEFAULT_BASE_URL, tag["href"])

        # Handle 'src' attribute for <img> and <script> tags
        if tag.has_attr("src"):
            if not tag["src"].startswith("http"):  # Only modify relative sources
                tag["src"] = urljoin(DEFAULT_BASE_URL, tag["src"])

    return finalize_html(soup)


# Tiny web server so Render's free Web Service sees an open port
app = Flask(__name__)


@app.route("/")
def home():
    return "ok"


def run_web():
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))


Thread(target=run_web, daemon=True).start()

# Run the bot
print("Bot started...")
bot.run_until_disconnected()

# Copyright github.com/devgaganin
# no part of this code/edits is allowed to use for commercial / sale purposes
