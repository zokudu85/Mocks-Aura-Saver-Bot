# Copyright github.com/devgaganin

import os
import re
import asyncio
import requests
from threading import Thread
from urllib.parse import urljoin, urlparse, parse_qs

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
        "Many tests: `/fetch exam 1,2,3` or `/fetch exam 1-6`\n"
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
    "rrbpo": "https://u1.oliveboard.in/exams/tests/?c=ibpsrrbscp&testid={test_id}",
    "rrbclerk": "https://u1.oliveboard.in/exams/tests/?c=rrbclerk&testid={test_id}",
    "rrbassecpre": "https://u1.oliveboard.in/exams/tests/?c=rrbassecpre&testid={test_id}",
    "rrbpolive": "https://u1.oliveboard.in/exams/tests/?c=rrbpolive&testid={test_id}",
   "ibpsrrbasp": "https://u1.oliveboard.in/exams/tests/?c=ibpsrrbasp&testid={test_id}",
    "ibpsrrbassmains": "https://u1.oliveboard.in/exams/tests/?c=ibpsrrbsecas&testid={test_id}",
   "rrbclerk2025": "https://u1.oliveboard.in/exams/tests/?c=ibpsrrbasp22&testid={test_id}",
    "rrbmains25mains": "https://u1.oliveboard.in/exams/tests/?c=ibpsrrbasm&testid={test_id}",
    "rrbclerksectional": "https://u1.oliveboard.in/exams/tests/?c=sectional&testid={test_id}",
    "rrbmainssec": "https://u1.oliveboard.in/exams/tests/?c=sectionalm&testid={test_id}",  
    "sectestmains": "https://u1.oliveboard.in/exams/tests/?c=sectionalm&testid={test_id}",
    "rrbpre": "https://u1.oliveboard.in/exams/tests/?c=ibpsrrbscp&testid={test_id}",
}

def get_page(url):
    """Blocking GET (run in a thread so the bot stays responsive)."""
    return requests.get(url, headers=HEADERS, timeout=30)


# Optional: your own test names. Key = "exam testid" exactly as in /fetch (or "c testid" from a /url link).
TEST_NAMES = {
    # "rrbclerk 1": "IBPS RRB PO PRELIMS MOCK 1",
}


def clean_name(text):
    text = re.sub(r"[^A-Za-z0-9 _-]", " ", str(text))
    return re.sub(r"\s+", " ", text).strip()[:100]


def test_title(html, exam, test_id):
    """Test name. Order: TEST_NAMES, title inside the page, exam + id."""
    names = {k.lower(): v for k, v in TEST_NAMES.items()}
    title = names.get(f"{exam} {test_id}".lower(), "")
    if not title:
        m = re.search(r"testQpid\s*=\s*'([^']+)'", html)
        title = m.group(1) if m else ""
    return clean_name(title) or clean_name(f"{exam} {test_id}")


def file_name_for(html, exam, test_id):
    """File name: '<test name>@Dark_V1rus.html'."""
    return f"{test_title(html, exam, test_id)}@Dark_V1rus.html"



def _page_url(url):
    """Test page address for a test or solution link."""
    q = parse_qs(urlparse(url).query)
    c = q.get("c", [""])[0]
    t = q.get("testid", [""])[0]
    path = urlparse(url).path.rstrip("/")
    if path == "/exams/tests" or not c or not t:
        return url
    return f"https://u1.oliveboard.in/exams/tests/?c={c}&testid={t}"


async def send_test(event, url, caption, exam, test_id):
    """Attempted test -> ONE offline HTML (all sections + result page) that never sends anything to Oliveboard."""
    su = solution_url(url)
    if not su:
        await event.respond("Link mein c= aur testid= chahiye.")
        return "fail"
    try:
        sol = await asyncio.to_thread(get_page, su)
        sol.raise_for_status()
    except requests.exceptions.RequestException as e:
        await event.respond(f"Failed to fetch test {test_id}: {e}")
        return "fail"
    if urlparse(sol.url).netloc != "u1.oliveboard.in":
        await event.respond("Login page aaya. Cookies expire ho gayi hain, naya AUTH_CODE daalo.")
        return "login"
    have_sol = "questionssols" in sol.text

    try:
        response = await asyncio.to_thread(get_page, _page_url(url))
        response.raise_for_status()
    except requests.exceptions.RequestException as e:
        await event.respond(f"Failed to fetch test {test_id}: {e}")
        return "fail"
    if urlparse(response.url).netloc != "u1.oliveboard.in":
        await event.respond("Login page aaya. Cookies expire ho gayi hain, naya AUTH_CODE daalo.")
        return "login"

    note = ""
    try:
        if have_sol:
            html = await asyncio.to_thread(build_combined, response.text, sol.text, url)
        else:
            html = await asyncio.to_thread(build_basic, response.text, url)
            note = "\n\n⚠️ Solution abhi nahi mila: file mein sirf questions hain (answers/solution nahi). Sectional test ho toh sirf section 1. Test Oliveboard par attempt karke dobara /fetch karo, tab poori file banegi."
    except Exception as e:
        print("build failed:", repr(e))
        await event.respond(f"Test {test_id}: offline file nahi ban payi ({e}).")
        return "fail"

    title = test_title(response.text, exam, test_id)
    file_name = f"{title}@Dark_V1rus.html"
    caption = caption.replace("{test_name}", title) + note
    with open(file_name, "w", encoding="utf-8") as f:
        f.write(html)
    try:
        await event.respond(caption, file=file_name)
    finally:
        os.remove(file_name)
    return "ok"


MAX_TESTS = 30     # max tests per /fetch command
GAP_SECONDS = 2    # pause between tests (keeps Telegram and your Oliveboard account safe)


def parse_ids(text):
    """'1,2,3' or '1-6' or '1 2 3' -> ['1','2','3'] (no duplicates, order kept)."""
    ids = []
    for part in re.split(r"[,\s]+", text.strip()):
        if part.isdigit():
            ids.append(str(int(part)))
        elif "-" in part:
            lo, _, hi = part.partition("-")
            if lo.isdigit() and hi.isdigit() and 0 <= int(hi) - int(lo) < 500:
                ids.extend(str(i) for i in range(int(lo), int(hi) + 1))
    return list(dict.fromkeys(ids))


@bot.on(events.NewMessage(pattern=r"/fetch (\w+) ([\d,\s-]+)"))
async def fetch_exam(event):
    """/fetch exam 1   or   /fetch exam 1,2,3   or   /fetch exam 1-6"""
    if event.sender_id != OWNER_ID:
        await event.reply("Not allowed")
        return
    exam = event.pattern_match.group(1).lower()
    ids = parse_ids(event.pattern_match.group(2))

    if exam not in BASE_URIS:
        await event.respond("Invalid exam type! Supported types are: " + ", ".join(BASE_URIS.keys()))
        return
    if not ids:
        await event.respond("Test ID sahi likho, jaise: `/fetch " + exam + " 1,2,3` ya `/fetch " + exam + " 1-6`")
        return
    if len(ids) > MAX_TESTS:
        await event.respond(f"Ek baar mein max {MAX_TESTS} tests. Pehle {MAX_TESTS} bhej raha hoon.")
        ids = ids[:MAX_TESTS]

    done, failed = [], []
    for n, test_id in enumerate(ids, 1):
        url = BASE_URIS[exam].format(test_id=test_id)
        caption = (
            "**📕 Test Name: {test_name}**\n"
            f"**🆔 Test ID: {test_id}**\n"
            "**✅ Type: Offline mock + result**\n\n__**Powered by @Dark_V1rus**__"
        )
        result = await send_test(event, url, caption, exam, test_id)
        if result == "ok":
            done.append(test_id)
        else:
            failed.append(test_id)
        if result == "login":
            break
        if n < len(ids):
            await asyncio.sleep(GAP_SECONDS)

    if len(ids) > 1:
        msg = f"Done: {len(done)}/{len(ids)}"
        if failed:
            msg += "\nNahi aaye: " + ", ".join(failed)
        await event.respond(msg)


@bot.on(events.NewMessage(pattern=r"/url (https://u1\.oliveboard\.in/\S+)"))
async def fetch_url(event):
    """Fetches the question paper from a full Oliveboard test link."""
    if event.sender_id != OWNER_ID:
        await event.reply("Not allowed")
        return
    url = event.pattern_match.group(1)
    caption = "**📕 Test Name: {test_name}**\n**✅ Type: Offline mock + result**\n\n__**Powered by Banking Aura**__"
    q = parse_qs(urlparse(url).query)
    await send_test(event, url, caption, q.get("c", ["test"])[0], q.get("testid", ["x"])[0])


DEFAULT_BASE_URL = "https://u1.oliveboard.in/exams/tests/"

WATERMARK_TEXT = "BANKING AURA"
WATERMARK_HTML = """<style>
#ba-watermark{position:fixed;inset:0;z-index:2147483000;pointer-events:none;overflow:hidden;display:flex;align-items:center;justify-content:center;user-select:none}
#ba-watermark span{font-family:Arial,Helvetica,sans-serif;font-weight:800;font-size:9vw;letter-spacing:.05em;white-space:nowrap;color:rgba(0,0,0,.07);transform:rotate(-30deg)}
@media print{#ba-watermark span{color:rgba(0,0,0,.12)}}
</style>
<div id="ba-watermark" aria-hidden="true"><span>%s</span></div>
""" % WATERMARK_TEXT


# Layout fix for PHONE mode only: question/directions on top, options below, whole page scrolls as one.
# Desktop mode (desktop site ON in the browser) keeps the original left/right layout.
# (display is NOT touched, because the test's own JS shows/hides each question with it.)
LAYOUT_STYLE = """<style id="stack-layout">
html.m-stack,html.m-stack body{height:auto !important;overflow:auto !important}
html.m-stack #left-container-post,html.m-stack #question-outer-pane,html.m-stack #question-inner-pane{height:auto !important;max-height:none !important;overflow:visible !important}
html.m-stack .leftpane,html.m-stack .rightpane{float:none !important;width:100% !important;height:auto !important;max-height:none !important;overflow:visible !important;box-sizing:border-box !important}
html.m-stack .leftpane{margin-bottom:12px !important;border-right:0 !important}
html.m-stack .rightpane{border-left:0 !important}
html.m-stack .leftpane img,html.m-stack .rightpane img{max-width:100% !important;height:auto !important}
</style>
<script>
(function(){try{if(/Android|iPhone|iPad|iPod|Mobile/i.test(navigator.userAgent||"")){document.documentElement.classList.add("m-stack");}}catch(e){}})();
</script>
"""


# Safety: the test page can never send anything (answers, timings) anywhere. Only GET downloads
# of Oliveboard's own scripts/images/styles are left, so the page still looks the same.
GUARD_HTML = """<script>
(function(){try{
var X=XMLHttpRequest.prototype,o=X.open,s=X.send;
X.open=function(m){this.__m=String(m||"GET").toUpperCase();return o.apply(this,arguments);};
X.send=function(){if(this.__m!=="GET"){return;}return s.apply(this,arguments);};
if(navigator.sendBeacon){navigator.sendBeacon=function(){return true;};}
if(window.fetch){var f=window.fetch;window.fetch=function(u,opt){if(opt&&opt.method&&String(opt.method).toUpperCase()!=="GET"){return Promise.resolve(new Response(""));}return f.apply(this,arguments);};}
}catch(e){}})();
</script>
"""


def finalize_html(soup):
    """Fix button links (they must not navigate/open a new tab) and add the watermark."""
    for a in soup.find_all("a"):
        if a.has_attr("onclick"):
            a["href"] = "javascript:void(0)"
            a.attrs.pop("target", None)
    head = soup.head or soup.body
    if head is not None and not soup.find(id="no-post-guard"):
        g = BeautifulSoup(GUARD_HTML, "html.parser")
        g.script["id"] = "no-post-guard"
        head.insert(0, g)
    if head is not None and not soup.find(id="stack-layout"):
        head.append(BeautifulSoup(LAYOUT_STYLE, "html.parser"))
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


@bot.on(events.NewMessage(pattern=r"/codes(?: (https://u1\.oliveboard\.in/\S+))?"))
async def list_codes(event):
    """/codes  or  /codes <any Oliveboard list page link>  -> every exam code (c=) found on that page."""
    if event.sender_id != OWNER_ID:
        await event.reply("Not allowed")
        return
    url = event.pattern_match.group(1) or "https://u1.oliveboard.in/tests/index.php?c=tests&i=banking"
    try:
        r = await asyncio.to_thread(get_page, url)
        r.raise_for_status()
    except requests.exceptions.RequestException as e:
        await event.respond(f"Failed: {e}")
        return
    if urlparse(r.url).netloc != "u1.oliveboard.in":
        await event.respond("Login page aaya. Cookies expire ho gayi hain, naya AUTH_CODE daalo.")
        return
    soup = BeautifulSoup(r.text, "html.parser")
    found = {}
    for a in soup.find_all("a", href=True):
        c = parse_qs(urlparse(urljoin(url, a["href"])).query).get("c", [""])[0]
        if c and c != "tests":
            found.setdefault(c, a.get_text(" ", strip=True)[:60])
    for c in re.findall(r"[?&]c=([A-Za-z0-9_]+)", r.text):
        if c != "tests":
            found.setdefault(c, "")
    if not found:
        await event.respond("Is page par koi c= code nahi mila. Doosra list page ka link do: /codes <link>")
        return
    lines = ["# c= codes found on: " + url, ""]
    lines += [f"{c}   {name}".rstrip() for c, name in found.items()]
    lines += ["", "# Paste into BASE_URIS in main.py (change the first name if you want):"]
    lines += [f'    "{c}": "https://u1.oliveboard.in/exams/tests/?c={c}&testid={{test_id}}",' for c in found]
    path = f"codes_{event.id}.txt"
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    try:
        await event.respond(f"{len(found)} exam codes mile.", file=path)
    finally:
        os.remove(path)


# ===== COMBINE START (sections + result page) =====
import base64
import json
import html as htmllib

NEGATIVE_MARK = 0.25  # wrong answer cuts this fraction of the question's marks (IBPS prelims style)

_KEY = re.compile(r"^([A-Z0-9]{32})")


def _dec(t):
    """Solution page hides text as KEY + base64 + KEY. Return the real HTML."""
    t = (t or "").strip()
    m = _KEY.match(t)
    if not m:
        return t
    k = m.group(1)
    b = t[32:]
    if b.endswith(k):
        b = b[:-32]
    try:
        return base64.b64decode(b + "=" * (-len(b) % 4)).decode("utf-8", "replace")
    except Exception:
        return t


def parse_solution(sol_html):
    """All questions, options, correct option and explanation from the solution page."""
    soup = BeautifulSoup(sol_html, "html.parser")
    items = []
    for b in soup.select(".questionssols > *"):
        parts = (b.get("id") or "").split("-")
        if len(parts) < 3 or not parts[2].isdigit():
            continue
        m = re.search(r"viewsolution\((\d+),\s*(\d+)\)", str(b))
        if not m:
            continue
        qb = b.select_one(".qblock")
        dr = b.select_one(".panetxt")
        sl = b.select_one(".solutiontxt")
        items.append({
            "qid": int(parts[2]),
            "kind": "single" if "singleqid" in (b.get("class") or []) else "pane",
            "q": _dec(qb.get_text()) if qb else "",
            "dir": _dec(dr.get_text()) if dr else "",
            "opts": [_dec(o.get_text()) for o in b.select(".rightopt")],
            "key": int(m.group(2)) + 1,
            "sol": _dec(sl.get_text()) if sl else "",
        })
    return items


def parse_sections(test_html):
    """Section table (name, questions, marks, minutes) from the test's instruction page."""
    soup = BeautifulSoup(test_html, "html.parser")
    body = soup.find(id="in-tab-body")
    secs = []
    if body:
        for tr in body.find_all("tr"):
            td = [x.get_text(" ", strip=True) for x in tr.find_all("td")]
            if len(td) >= 5 and td[2].isdigit():
                try:
                    secs.append({"name": td[1], "n": int(td[2]), "marks": float(td[3]), "minutes": int(float(td[4]))})
                except ValueError:
                    pass
    return secs


def _both_langs(h):
    """Show English + Hindi like the original test page does (both use class eqt)."""
    return h.replace('class="hqt" style="display:none"', 'class="eqt"').replace("class='hqt' style='display:none'", "class='eqt'")


def _opt_rows(qid, opts, pane):
    rows = []
    for j, o in enumerate(opts, 1):
        body = re.sub(r"</span>", "</span><br/>", _both_langs(o))
        rows.append(
            ('<tr class="vtop">' if pane else "<tr>")
            + f'<td><input id="radio{qid}" name="option{qid}" onclick="clearme({j})" type="radio" value="{j}"/></td>'
            + f'<td><span class="optcl" onclick="clearme({j})">{chr(96 + j)})</span></td>'
            + f'<td><span class="optcl lpad opn{qid}" onclick="clearme({j})">{body}</span></td></tr>'
        )
    return "".join(rows)


def build_part(test_html, idx, secs, shorts, items):
    """Make the test page for section idx (idx >= 1) from the solution data, same engine as section 1."""
    start = sum(s["n"] for s in secs[:idx])
    mine = items[start:start + secs[idx]["n"]]
    sec = secs[idx]
    raw = test_html

    def sub1(pattern, repl):
        nonlocal raw
        new, n = re.subn(pattern, lambda m: repl, raw, count=1)
        if n != 1:
            raise ValueError("test page format changed: " + pattern)
        raw = new

    sub1(r"totalTime\s*=\s*'\d*'", f"totalTime='{sec['minutes'] * 60}'")
    sub1(r"timeTotal\s*=\s*'[^']*'", f"timeTotal='{sec['minutes']} Minutes'")
    sub1(r"secList\.push\(\s*(['\"])[^'\"]*\1\s*\)", "secList.push(" + json.dumps(sec["name"]) + ")")
    sub1(r"secTracker\.push\(\s*['\"]\d*['\"]\s*\)", f"secTracker.push('{sec['n']}')")
    sub1(r"secShortList\.push\(\s*(['\"])[^'\"]*\1\s*\)", "secShortList.push(" + json.dumps(shorts[idx] if idx < len(shorts) else sec["name"][:2]) + ")")
    sub1(r"firstQid\s*=\s*\d+", f"firstQid={mine[0]['qid']}")
    sub1(r"\bnq\s*=\s*\d+", f"nq={len(mine)}")

    soup = BeautifulSoup(raw, "html.parser")
    pane = soup.find(id="question-inner-pane")
    for c in list(pane.find_all(recursive=False)):
        if c.name != "script":
            c.decompose()
    chunks = []
    for it in mine:
        qid = it["qid"]
        q = _both_langs(it["q"])
        if it["kind"] == "single":
            chunks.append(
                '<div class="question-outer-div">'
                f'<table id="myquestion{qid}" name="myquestion{qid}" style="display:none"><tbody>'
                f'<tr><td id="question-box">{q}</td></tr>'
                f'<tr><td><table cellpadding="0" cellspacing="0" class="answer-outer-div opts-table" id="myanswer{qid}" name="myanswer{qid}" style="display:none;">'
                f'{_opt_rows(qid, it["opts"], False)}</table></td></tr></tbody></table></div>'
            )
        else:
            chunks.append(
                f'<div class="leftpane" id="leftpane{qid}" style="display:none"><table><tbody><tr><td id="pane-direction-box">{_both_langs(it["dir"])}</td></tr></tbody></table></div>'
                f'<div class="rightpane" id="rightpane{qid}" style="display:none"><table><tbody>'
                f'<tr><td id="pane-question-box">{q}</td></tr>'
                f'<tr><td><table cellpadding="0" cellspacing="0" class="opts-table" id="rightpane-answer{qid}">{_opt_rows(qid, it["opts"], True)}</table></td></tr>'
                "</tbody></table></div>"
            )
    pane.append(BeautifulSoup("".join(chunks), "html.parser"))

    ql = soup.find(id="question-list-onbutton")
    if ql is not None:
        ql.clear()
        lst = "".join(
            f'Qno {n}) <span class="qlistl">{_both_langs(it["dir"]) if it["kind"] == "pane" else ""}{_both_langs(it["q"])}</span><br/><hr/>'
            for n, it in enumerate(mine, 1)
        )
        ql.append(BeautifulSoup(lst, "html.parser"))
    return str(soup)


_WRAP_CSS = r"""
html,body{margin:0;height:100%;background:#fff;font-family:Arial,Helvetica,sans-serif}
#f{position:fixed;left:0;top:0;width:100%;height:100%;border:0;background:#fff}
#res{display:none;max-width:900px;margin:0 auto;padding:14px 12px 60px;color:#1b2a3a}
#res h1{font-size:19px;margin:6px 0 2px}#res .sub{color:#5a6b7d;font-size:13px;margin-bottom:12px}
.cards{display:flex;flex-wrap:wrap;gap:10px;margin:10px 0 16px}
.card{flex:1 1 140px;background:#fff;border-radius:12px;padding:12px 14px;box-shadow:0 1px 4px rgba(20,50,90,.15)}
.card b{display:block;font-size:22px;margin-top:2px}.card span{font-size:12px;color:#5a6b7d}
.c-ok b{color:#12803c}.c-bad b{color:#c62828}.c-na b{color:#6b7785}.c-sc b{color:#1a56c9}
table.st{width:100%;border-collapse:collapse;background:#fff;border-radius:10px;overflow:hidden;font-size:13px;box-shadow:0 1px 4px rgba(20,50,90,.15)}
table.st th{background:#1a56c9;color:#fff;padding:8px 6px;text-align:center}table.st td{padding:8px 6px;text-align:center;border-top:1px solid #e3e9f1}
table.st td:first-child,table.st th:first-child{text-align:left;padding-left:10px}
.flt{display:flex;gap:8px;flex-wrap:wrap;margin:18px 0 10px}
.flt button{border:1px solid #c5d1e0;background:#fff;border-radius:20px;padding:7px 14px;font-size:13px;color:#1b2a3a}
.flt button.on{background:#1a56c9;border-color:#1a56c9;color:#fff}
.it{background:#fff;border-radius:12px;padding:12px 14px;margin:10px 0;box-shadow:0 1px 4px rgba(20,50,90,.15);border-left:5px solid #9aa7b5;overflow-x:auto}
.it.c{border-left-color:#12803c}.it.w{border-left-color:#c62828}
.ih{display:flex;gap:8px;align-items:center;flex-wrap:wrap;font-size:13px;margin-bottom:6px}
.chip{border-radius:10px;padding:2px 9px;font-size:12px;color:#fff;background:#6b7785}.c .chip{background:#12803c}.w .chip{background:#c62828}
.meta{color:#5a6b7d;font-size:12px}.iq{font-size:15px;line-height:1.5;margin:6px 0}
.op{border:1px solid #d5deea;border-radius:8px;padding:7px 10px;margin:5px 0;font-size:14px}
.op.ok{border-color:#12803c;background:#e8f6ee}.op.bad{border-color:#c62828;background:#fdeaea}
.op .tg{float:right;font-size:11px;font-weight:bold}.op.ok .tg{color:#12803c}.op.bad .tg{color:#c62828}
details{margin:6px 0}summary{cursor:pointer;color:#1a56c9;font-size:13px}
.sol,.dirb{font-size:14px;line-height:1.5;margin-top:6px;overflow-x:auto}.sol img,.dirb img,.iq img{max-width:100%;height:auto}
.btns{margin-top:18px}.btns button{border:0;background:#1a56c9;color:#fff;border-radius:8px;padding:10px 16px;font-size:14px}
#wm{position:fixed;inset:0;z-index:5;pointer-events:none;display:none;align-items:center;justify-content:center;overflow:hidden}
#wm span{font-weight:800;font-size:9vw;letter-spacing:.05em;white-space:nowrap;color:rgba(0,0,0,.06);transform:rotate(-30deg)}
"""

_WRAP_JS = r"""
(function(){
var PARTS=__PARTS__, DATA=__DATA__, results=[];
var F=document.getElementById('f'), R=document.getElementById('res');
function secs(t){var p=String(t).split(':');return (+p[0]||0)*3600+(+p[1]||0)*60+(+p[2]||0);}
function fmt(s){s=Math.round(s);var m=Math.floor(s/60),x=s%60;return (m<10?'0':'')+m+':'+(x<10?'0':'')+x;}
function f2(n){return (Math.round(n*100)/100).toFixed(2);}
function load(i){F.onload=function(){try{patch(F.contentWindow,i);}catch(e){}};F.srcdoc=PARTS[i];}
function patch(w,i){
  w.onbeforeunload=null;
  w.pauseTest=function(){};
  try{w.$.post=function(){};w.$.ajax=function(){};}catch(e){}
  w.sendData=function(){
    if(w.__done)return; w.__done=true;
    collect(w,i);
    if(i+1<PARTS.length){load(i+1);}else{show();}
  };
}
function collect(w,i){
  var ans={},tm={};
  try{w.clearInterval(w.intId);}catch(e){}
  try{
    var d=w.hourt+":"+w.minst+":"+w.secst;
    if(w.questionIdent&&d!=w.myDatep){w.resp[w.questionIdent].t.push({st:w.myDatep,end:d});}
  }catch(e){}
  for(var ip=1;ip<=w.nq;ip++){
    var q=ip+w.firstQid-1,tt=0,a=0,els=w.document.getElementsByName('option'+q);
    if(els.length){for(var k=0;k<els.length;k++){if(els[k].checked){a=parseInt(els[k].value,10);break;}}}
    else if(w.quesAnswer[ip]){a=parseInt(w.quesAnswer[ip],10);}
    ans[q]=a||0;
    try{(w.resp[q].t||[]).forEach(function(s){var x=secs(s.st)-secs(s.end);if(x>0)tt+=x;});}catch(e){}
    tm[q]=tt;
  }
  results[i]={ans:ans,time:tm};
}
function showBasic(){
  F.style.display='none';R.style.display='block';document.getElementById('wm').style.display='flex';
  document.body.style.background='#f3f6fb';window.scrollTo(0,0);
  var S=DATA.secs,tot=0,att=0,tt=0,rows='';
  results.forEach(function(r,i){
    var n=S[i]?S[i].n:Object.keys(r.ans).length,a=0,t=0,k;
    for(k in r.ans){if(r.ans[k])a++;}
    for(k in r.time){t+=r.time[k];}
    tot+=n;att+=a;tt+=t;
    rows+='<tr><td>'+(S[i]?S[i].name:'Section '+(i+1))+'</td><td>'+n+'</td><td>'+a+'</td><td>'+(n-a)+'</td><td>'+fmt(t)+'</td></tr>';
  });
  R.innerHTML='<h1>'+DATA.title+'</h1><div class="sub">Test summary</div><div class="cards">'+
   '<div class="card c-sc"><span>Attempted</span><b>'+att+' / '+tot+'</b></div>'+
   '<div class="card c-na"><span>Unattempted</span><b>'+(tot-att)+'</b></div>'+
   '<div class="card"><span>Time spent</span><b>'+fmt(tt)+'</b></div></div>'+
   '<table class="st"><tr><th>Section</th><th>Questions</th><th>Attempted</th><th>Skipped</th><th>Time</th></tr>'+rows+'</table>'+
   '<p class="sub" style="margin-top:14px">Sahi answers aur solution abhi available nahi hain, isliye score nahi nikla. Test Oliveboard par ek baar attempt karke bot se dobara mangwao, toh poora result page milega.</p>'+
   '<div class="btns"><button onclick="location.reload()">Retake test</button></div>';
}
function show(){
  if(!DATA.items.length){showBasic();return;}
  F.style.display='none';R.style.display='block';document.getElementById('wm').style.display='flex';
  document.body.style.background='#f3f6fb';window.scrollTo(0,0);
  var ans={},tm={};
  results.forEach(function(r){for(var k in r.ans)ans[k]=r.ans[k];for(var k2 in r.time)tm[k2]=r.time[k2];});
  var S=DATA.secs,sr=S.map(function(s){return {name:s.name,n:s.n,max:s.marks,c:0,w:0,u:0,sc:0,t:0};});
  var T={c:0,w:0,u:0,sc:0,max:0,t:0},no=[];
  DATA.items.forEach(function(it){
    var s=S[it.s],per=s.marks/s.n,a=ans[it.qid]||0,st=!a?'u':(a===it.key?'c':'w'),r=sr[it.s];
    it.st=st;it.a=a;it.t=tm[it.qid]||0;no[it.s]=(no[it.s]||0)+1;it.no=no[it.s];
    if(st==='c'){r.c++;r.sc+=per;}else if(st==='w'){r.w++;r.sc-=per*DATA.neg;}else{r.u++;}
    r.t+=it.t;
  });
  sr.forEach(function(r){T.c+=r.c;T.w+=r.w;T.u+=r.u;T.sc+=r.sc;T.max+=r.max;T.t+=r.t;});
  var att=T.c+T.w,acc=att?(T.c/att*100):0;
  var h='<h1>'+DATA.title+'</h1><div class="sub">Result</div><div class="cards">'+
   '<div class="card c-sc"><span>Score</span><b>'+f2(T.sc)+' / '+T.max+'</b></div>'+
   '<div class="card c-sc"><span>Accuracy</span><b>'+f2(acc)+'%</b></div>'+
   '<div class="card c-ok"><span>Correct</span><b>'+T.c+'</b></div>'+
   '<div class="card c-bad"><span>Wrong</span><b>'+T.w+'</b></div>'+
   '<div class="card c-na"><span>Unattempted</span><b>'+T.u+'</b></div>'+
   '<div class="card"><span>Time spent</span><b>'+fmt(T.t)+'</b></div></div>'+
   '<table class="st"><tr><th>Section</th><th>Score</th><th>Right</th><th>Wrong</th><th>Skipped</th><th>Time</th></tr>';
  sr.forEach(function(r){h+='<tr><td>'+r.name+'</td><td>'+f2(r.sc)+'/'+r.max+'</td><td>'+r.c+'</td><td>'+r.w+'</td><td>'+r.u+'</td><td>'+fmt(r.t)+'</td></tr>';});
  h+='</table><div class="flt"><button class="on" data-f="all">All</button><button data-f="w">Wrong</button><button data-f="u">Unattempted</button><button data-f="c">Correct</button></div><div id="list">';
  var L='ABCDEFGH',lastDir=-2;
  DATA.items.forEach(function(it){
    h+='<div class="it '+it.st+'" data-st="'+it.st+'"><div class="ih"><b>Q'+it.no+'</b><span class="chip">'+(it.st==='c'?'Correct':it.st==='w'?'Wrong':'Skipped')+'</span><span class="meta">'+S[it.s].name+' &middot; '+fmt(it.t)+'</span></div>';
    if(it.d>=0){h+='<details'+(it.d!==lastDir?' open':'')+'><summary>Directions</summary><div class="dirb">'+DATA.dirs[it.d]+'</div></details>';}
    lastDir=it.d;
    h+='<div class="iq">'+it.q+'</div>';
    it.opts.forEach(function(o,j){
      var n=j+1,cls=n===it.key?'ok':(n===it.a?'bad':''),tg=n===it.key?'Correct answer':(n===it.a?'Your answer':'');
      if(n===it.key&&n===it.a)tg='Your answer (correct)';
      h+='<div class="op '+cls+'"><span class="tg">'+tg+'</span><b>'+L[j]+'.</b> '+o+'</div>';
    });
    h+='<details><summary>Solution</summary><div class="sol">'+it.sol+'</div></details></div>';
  });
  h+='</div><div class="btns"><button onclick="location.reload()">Retake test</button></div>';
  R.innerHTML=h;
  var bs=R.querySelectorAll('.flt button');
  Array.prototype.forEach.call(bs,function(b){b.onclick=function(){
    Array.prototype.forEach.call(bs,function(x){x.className=(x===b)?'on':'';});
    var f=b.getAttribute('data-f');
    Array.prototype.forEach.call(R.querySelectorAll('.it'),function(e){e.style.display=(f==='all'||e.getAttribute('data-st')===f)?'':'none';});
  };});
}
window.__showResult=show;
load(0);
})();
"""


def build_combined(part1_page, sol_html, url):
    """One HTML file: section 1 (original page) -> section 2 ... -> result page. Works offline."""
    secs = parse_sections(part1_page)
    items = parse_solution(sol_html)
    if not secs:
        nqm = re.search(r"\bnq\s*=\s*(\d+)", part1_page)
        ttm = re.search(r"totalTime\s*=\s*'(\d+)'", part1_page)
        if nqm:
            n = int(nqm.group(1))
            secs = [{"name": "Section 1", "n": n, "marks": float(n), "minutes": (int(ttm.group(1)) // 60) if ttm else 0}]
    if not secs or len(items) != sum(s["n"] for s in secs):
        raise ValueError("solution does not match the test sections")
    sm = re.search(r"ssnames\s*=\s*(\[[^\]]*\])", sol_html)
    try:
        shorts = json.loads(sm.group(1)) if sm else []
    except ValueError:
        shorts = []
    tm = re.search(r"testQpid\s*=\s*'([^']*)'", part1_page)
    title = tm.group(1) if tm and tm.group(1) else "Mock Test"

    fq = re.search(r"firstQid\s*=\s*(\d+)", part1_page)
    nqm2 = re.search(r"\bnq\s*=\s*(\d+)", part1_page)
    is_first = bool(fq and nqm2 and int(fq.group(1)) == items[0]["qid"] and int(nqm2.group(1)) == secs[0]["n"])
    if is_first:
        pages = [modify_html(part1_page, url)]
    else:
        pages = [modify_html(build_part(part1_page, 0, secs, shorts, items), url)]
    for i in range(1, len(secs)):
        pages.append(modify_html(build_part(part1_page, i, secs, shorts, items), url))

    dirs, data_items, pos = [], [], 0
    for si, s in enumerate(secs):
        for it in items[pos:pos + s["n"]]:
            d = -1
            if it["kind"] == "pane" and it["dir"]:
                if it["dir"] in dirs:
                    d = dirs.index(it["dir"])
                else:
                    dirs.append(it["dir"])
                    d = len(dirs) - 1
            data_items.append({"qid": it["qid"], "s": si, "q": it["q"], "opts": it["opts"], "key": it["key"], "sol": it["sol"], "d": d})
        pos += s["n"]
    data = {"title": htmllib.escape(title), "neg": NEGATIVE_MARK, "secs": secs, "dirs": dirs, "items": data_items}
    return _wrap(pages, data, title)


def _wrap(pages, data, title):
    def js(o):
        return json.dumps(o, ensure_ascii=True).replace("</", "<\\/")

    script = _WRAP_JS.replace("__PARTS__", js(pages)).replace("__DATA__", js(data))
    return (
        '<!DOCTYPE html><html><head><meta charset="utf-8"><title>' + htmllib.escape(title) + "</title>"
        "<style>" + _WRAP_CSS + "</style></head><body>"
        '<iframe id="f" allowfullscreen></iframe><div id="res"></div>'
        '<div id="wm"><span>' + WATERMARK_TEXT + "</span></div>"
        "<script>" + script + "</script></body></html>"
    )


def build_basic(part1_page, url):
    """No solution available yet: offline file with the questions only (no answer key)."""
    secs = parse_sections(part1_page)
    nqm = re.search(r"\bnq\s*=\s*(\d+)", part1_page)
    ttm = re.search(r"totalTime\s*=\s*'(\d+)'", part1_page)
    n = int(nqm.group(1)) if nqm else 0
    if secs and secs[0]["n"] == n:
        sec = secs[0]
    else:
        sec = {"name": "Section 1", "n": n, "marks": float(n), "minutes": (int(ttm.group(1)) // 60) if ttm else 0}
    tm = re.search(r"testQpid\s*=\s*'([^']*)'", part1_page)
    title = tm.group(1) if tm and tm.group(1) else "Mock Test"
    data = {"title": htmllib.escape(title), "neg": NEGATIVE_MARK, "secs": [sec], "dirs": [], "items": []}
    return _wrap([modify_html(part1_page, url)], data, title)


def solution_url(url):
    q = parse_qs(urlparse(url).query)
    c = q.get("c", [""])[0]
    t = q.get("testid", [""])[0]
    if not c or not t:
        return None
    return f"https://u1.oliveboard.in/exams/solution/index3.php?c={c}&testid={t}&from=test"


def make_combined(part1_page, url):
    """Blocking: fetch the solution page and build the combined file. None if it is not available."""
    su = solution_url(url)
    if not su:
        return None
    r = get_page(su)
    if urlparse(r.url).netloc != "u1.oliveboard.in" or "questionssols" not in r.text:
        return None
    return build_combined(part1_page, r.text, url)
# ===== COMBINE END =====


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
