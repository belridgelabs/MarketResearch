from playwright.sync_api import sync_playwright
import requests
import random
import time
import os
from dotenv import load_dotenv

load_dotenv()

# ── CONFIG ───────────────────────────────────────────────────────────────────────

# 1) Your LinkedIn creds
LINKEDIN_USER = os.getenv("LI_USER")
LINKEDIN_PASS = os.getenv("LI_PASS")

# 2) Proxy list (with auth if needed: "http://user:pass@host:port")
PROXIES = [
    {
        "server": "http://198.23.239.134:8000",
        "username": "tpbbbjlr",
        "password": "ksyqay7fnula"
    },
    {
        "server": "http://207.244.217.165:8000",
        "username": "tpbbbjlr",
        "password": "ksyqay7fnula"
    },
]

# 3) Rotate these traits on every context
USER_AGENTS = [
    # A handful of real-world UA strings
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64)…Chrome/114.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)…Safari/605.1.15",
    # …
]
VIEWPORTS = [
    {"width": 1920, "height": 1080},
    {"width": 1366, "height": 768},
    {"width": 1440, "height": 900},
    {"width": 1536, "height": 864},
    {"width": 1280, "height": 720},
    {"width": 1680, "height": 1050},
    {"width": 1024, "height": 768},
    {"width": 2560, "height": 1440},
    {"width": 3840, "height": 2160},
    {"width": 1600, "height": 900},
    {"width": 1920, "height": 1200},
    {"width": 2048, "height": 1152},
]
LANGUAGES = ["en-US", "en-GB", "fr-FR", "de-DE"]
TIMEZONES = ["America/New_York", "Europe/London", "Asia/Tokyo"]

OUTPUT_DIR = "linkedin_html_dumps"
os.makedirs(OUTPUT_DIR, exist_ok=True)

# ── STEALTH PATCH ────────────────────────────────────────────────────────────────
STEALTH_JS = """
// pass every headless check
Object.defineProperty(navigator, 'webdriver', {get: () => false});
window.chrome = {runtime: {}};
Object.defineProperty(navigator, 'plugins', {get: () => [1, 2, 3, 4, 5]});
Object.defineProperty(navigator, 'languages', {get: () => ['en-US', 'en']});
"""

# ── HELPERS ──────────────────────────────────────────────────────────────────────

def is_proxy_working(proxy_url: str, timeout: int = 10) -> bool:
    """Quick HTTP check to weed out dead proxies."""
    try:
        r = requests.get(
            "https://www.linkedin.com", 
            proxies={"http": proxy_url, "https": proxy_url},
            timeout=timeout
        )
        return r.status_code == 200
    except Exception:
        return False

# ── SCRAPER ──────────────────────────────────────────────────────────────────────

def save_linkedin_page(url: str):
    # Prefilter live proxies
    live_proxies = [p for p in PROXIES]
    if not live_proxies:
        raise RuntimeError("No working proxies found!")
    random.shuffle(live_proxies)

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=[
                "--no-sandbox",
                "--disable-dev-shm-usage",
                "--disable-blink-features=AutomationControlled",
            ]
        )

        for idx, proxy in enumerate(live_proxies, start=1):
            ua    = random.choice(USER_AGENTS)
            vp    = random.choice(VIEWPORTS)
            lang  = random.choice(LANGUAGES)
            tz    = random.choice(TIMEZONES)
            print(f"[{idx}/{len(live_proxies)}] ▶ Proxy={proxy}, UA={ua}, TZ={tz}")

            context = browser.new_context(
                proxy=proxy,
                user_agent=ua,
                locale=lang,
                timezone_id=tz,
                viewport=vp,
                ignore_https_errors=True,
            )
            context.add_init_script(STEALTH_JS)
            page = context.new_page()
            page.set_default_navigation_timeout(60_000)  # 60s timeout

            # — LOGIN w/ retries & backoff —
            login_url = "https://www.linkedin.com/login"
            for attempt in range(1, 4):
                try:
                    page.goto(login_url, wait_until="networkidle")
                    page.fill('input[name="session_key"]', LINKEDIN_USER)
                    page.fill('input[name="session_password"]', LINKEDIN_PASS)
                    page.click('button[type="submit"]')
                    page.wait_for_load_state("networkidle")
                    break
                except Exception as e:
                    wait = 2 ** attempt
                    print(f"⚠️ Login attempt {attempt} failed ({e}), retry in {wait}s")
                    time.sleep(wait)
            else:
                print(f"✖ All login retries failed on proxy {proxy}. Skipping.")
                context.close()
                continue

            time.sleep(random.uniform(2, 5))

            # — FETCH TARGET w/ retry/backoff —
            for attempt in range(1, 4):
                try:
                    page.goto(url, wait_until="networkidle")
                    time.sleep(random.uniform(3, 6))
                    break
                except Exception as e:
                    wait = 2 ** attempt
                    print(f"⚠️ Fetch attempt {attempt} failed ({e}), retry in {wait}s")
                    time.sleep(wait)
            else:
                print(f"✖ All fetch retries failed on proxy {proxy}. Skipping.")
                context.close()
                continue

            # — DUMP HTML —
            html = page.content()
            filename = os.path.join(OUTPUT_DIR, f"linkedin_{idx}.html")
            with open(filename, "w", encoding="utf-8") as f:
                f.write(html)
            print(f"✅ Saved → {filename}")

            context.close()

        browser.close()

if __name__ == "__main__":
    target_url = "https://www.linkedin.com/in/steven-grunch-a2b0a55/"
    save_linkedin_page(target_url)
