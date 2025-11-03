import asyncio
import re
import json
import csv
import time
import random
import aiohttp
from urllib.parse import urljoin, urlparse
from playwright.async_api import async_playwright
from collections import deque
import logging
from typing import Set, List

# Disable noisy logs
logging.getLogger("asyncio").setLevel(logging.WARNING)

# =============== CONFIG ===============
TARGET_DOMAIN = "duet.edu.pk"  # Will auto-detect from input
MAX_PAGES = 500
MAX_SUBDOMAINS = 10
CONCURRENT = 15
DELAY = (0.8, 2.2)
TIMEOUT = 12
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36"
]

# Common subdomains for universities
COMMON_SUBDOMAINS = [
    "www", "mail", "webmail", "staff", "faculty", "cs", "it", "eee", "me", "ce",
    "admissions", "students", "library", "research", "alumni", "contact"
]

# =============== EMAIL INTELLIGENCE ===============
def extract_and_clean_emails(text: str, base_domain: str) -> Set[str]:
    """Advanced email extraction with de-obfuscation"""
    emails = set()
    base_domain = base_domain.lower()
    
    # 1. Standard emails
    std_emails = re.findall(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', text)
    for email in std_emails:
        if is_target_domain(email, base_domain):
            emails.add(email.lower())
    
    # 2. De-obfuscate: "john [at] duet [dot] edu [dot] pk"
    if "[at]" in text or "(at)" in text:
        # Normalize
        clean = re.sub(r'[\[\(]at[\]\)]', '@', text, flags=re.IGNORECASE)
        clean = re.sub(r'[\[\(]dot[\]\)]', '.', clean, flags=re.IGNORECASE)
        clean = re.sub(r'\s+dot\s+', '.', clean, flags=re.IGNORECASE)
        clean = re.sub(r'\s+at\s+', '@', clean, flags=re.IGNORECASE)
        # Now extract
        deob_emails = re.findall(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', clean)
        for email in deob_emails:
            if is_target_domain(email, base_domain):
                emails.add(email.lower())
    
    # 3. Handle "name at domain dot pk" patterns
    patterns = [
        r'([a-z0-9._-]+)\s+at\s+([a-z0-9.-]+)\s+dot\s+([a-z]{2,})',
        r'([a-z0-9._-]+) at ([a-z0-9.-]+) dot ([a-z]{2,})'
    ]
    for pattern in patterns:
        matches = re.findall(pattern, text, re.IGNORECASE)
        for local, domain_part, tld in matches:
            email = f"{local}@{domain_part}.{tld}"
            if is_target_domain(email, base_domain):
                emails.add(email.lower())
    
    return emails

def is_target_domain(email: str, base_domain: str) -> bool:
    """Check if email belongs to base domain or its subdomains"""
    if '@' not in email:
        return False
    _, domain = email.lower().rsplit('@', 1)
    base_domain = base_domain.lower()
    return domain == base_domain or domain.endswith('.' + base_domain)

# =============== STEALTHY FETCHER ===============
class EliteHarvester:
    def __init__(self, root_url: str):
        self.root_url = root_url.rstrip('/')
        self.base_domain = urlparse(root_url).netloc.lower()
        if self.base_domain.startswith('www.'):
            self.base_domain = self.base_domain[4:]
            
        self.emails: Set[str] = set()
        self.visited: Set[str] = set()
        self.session = None
        self.browser = None
        self.pages = 0

    async def init_session(self):
        connector = aiohttp.TCPConnector(limit=CONCURRENT, ssl=False)
        timeout = aiohttp.ClientTimeout(total=TIMEOUT)
        self.session = aiohttp.ClientSession(
            connector=connector,
            timeout=timeout,
            headers={"User-Agent": random.choice(USER_AGENTS)}
        )

    async def close(self):
        if self.session:
            await self.session.close()
        if self.browser:
            await self.browser.close()

    async def fetch_static(self, url: str) -> str:
        """Fast static fetch with retries"""
        for attempt in range(3):
            try:
                async with self.session.get(url) as resp:
                    if resp.status == 200:
                        return await resp.text()
                    elif resp.status == 403 or resp.status == 429:
                        await asyncio.sleep(5)
            except Exception as e:
                if attempt == 2:
                    print(f"❌ Static fetch failed for {url}: {str(e)[:50]}")
                await asyncio.sleep(2)
        return ""

    async def fetch_dynamic(self, url: str) -> str:
        """Stealthy Playwright fetch with evasion"""
        if not self.browser:
            pw = await async_playwright().start()
            self.browser = await pw.chromium.launch(
                headless=True,
                args=[
                    "--disable-blink-features=AutomationControlled",
                    "--disable-web-security",
                    "--no-sandbox",
                    "--disable-features=IsolateOrigins,site-per-process"
                ]
            )
        
        context = await self.browser.new_context(
            user_agent=random.choice(USER_AGENTS),
            viewport={"width": 1920, "height": 1080},
            java_script_enabled=True,
            bypass_csp=True
        )
        await context.add_init_script("""
            delete navigator.__proto__.webdriver;
            window.chrome = {runtime: {}};
            Object.defineProperty(navigator, 'plugins', {get: () => [1, 2, 3, 4, 5]});
            Object.defineProperty(navigator, 'languages', {get: () => ['en-US', 'en']});
        """)
        
        page = await context.new_page()
        try:
            await page.goto(url, wait_until="networkidle", timeout=TIMEOUT*1000)
            await page.wait_for_timeout(2000)
            content = await page.content()
            return content
        except Exception as e:
            print(f"⚠️  Dynamic fetch failed: {str(e)[:60]}")
            return ""
        finally:
            await context.close()

    async def scrape_page(self, url: str):
        """Scrape with fallback: static → dynamic"""
        if url in self.visited or self.pages >= MAX_PAGES:
            return
        self.visited.add(url)
        self.pages += 1
        print(f"[{self.pages}] 🔍 {url}")

        # Try fast static first
        html = await self.fetch_static(url)
        if not html or "<noscript>" in html or "enable JavaScript" in html.lower():
            html = await self.fetch_dynamic(url)
        
        if not html:
            return

        # Extract emails
        new_emails = extract_and_clean_emails(html, self.base_domain)
        self.emails.update(new_emails)

        # Extract links (same domain only)
        if self.pages < MAX_PAGES:
            urls = re.findall(r'href=[\'"]?([^\'" >]+)', html)
            for raw_link in urls:
                if raw_link.startswith(('http://', 'https://')):
                    full_url = raw_link
                elif raw_link.startswith('/'):
                    full_url = urljoin(url, raw_link)
                else:
                    continue
                
                parsed = urlparse(full_url)
                domain = parsed.netloc.lower()
                if domain == self.base_domain or domain.endswith('.' + self.base_domain):
                    if full_url not in self.visited:
                        yield full_url

    async def crawl(self):
        """Multi-layer crawl with subdomains"""
        await self.init_session()
        
        # Start with root + common subdomains
        urls_to_crawl = [self.root_url]
        for sub in COMMON_SUBDOMAINS[:MAX_SUBDOMAINS]:
            urls_to_crawl.append(f"https://{sub}.{self.base_domain}")
        
        queue = deque(urls_to_crawl)
        tasks = set()
        
        while (queue or tasks) and self.pages < MAX_PAGES:
            # Add new URLs to queue
            while queue and len(tasks) < CONCURRENT:
                url = queue.popleft()
                task = asyncio.create_task(self._process_url(url, queue))
                tasks.add(task)
                task.add_done_callback(tasks.discard)
            
            if tasks:
                await asyncio.sleep(0.1)  # Prevent busy wait
        
        print(f"\n✅ Crawled {self.pages} pages. Found {len(self.emails)} emails.")

    async def _process_url(self, url: str, queue: deque):
        async for new_url in self.scrape_page(url):
            queue.append(new_url)
        await asyncio.sleep(random.uniform(*DELAY))

    def export(self):
        clean_name = self.base_domain.replace(".", "_")
        timestamp = int(time.time())
        
        # JSON (Hunter format)
        result = {
            "domain": self.base_domain,
            "total": len(self.emails),
            "emails": [{"value": e, "type": "personal", "confidence": "high"} for e in sorted(self.emails)]
        }
        with open(f"emails_{clean_name}_{timestamp}.json", "w") as f:
            json.dump(result, f, indent=2)
        
        # CSV
        with open(f"emails_{clean_name}_{timestamp}.csv", "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["Email", "Source Domain"])
            for email in sorted(self.emails):
                writer.writerow([email, self.base_domain])
        
        print(f"\n📁 Exported to:\n - emails_{clean_name}_{timestamp}.json\n - emails_{clean_name}_{timestamp}.csv")

# =============== RUN ===============
async def main():
    target = input("🎯 Enter domain (e.g., duet.edu.pk): ").strip()
    if not target.startswith(("http://", "https://")):
        target = "https://" + target
    
    print(f"\n🚀 Launching elite harvester on {target}...")
    harvester = EliteHarvester(target)
    
    try:
        await harvester.crawl()
        harvester.export()
    finally:
        await harvester.close()

if __name__ == "__main__":
    asyncio.run(main())
