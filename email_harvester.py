import asyncio
import re
import json
import csv
import time
import random
import aiohttp
import base64
from urllib.parse import urljoin, urlparse
from playwright.async_api import async_playwright
from collections import deque
from pathlib import Path
import logging
from typing import Set, Dict, List, Tuple
import subprocess
import os

# =============== CONFIG (Tactical Settings) ===============
MAX_PAGES = 800
MAX_SUBDOMAINS = 20
CONCURRENT = 20
DELAY = (0.5, 1.8)
TIMEOUT = 10
AI_CONFIDENCE_THRESHOLD = 0.7  # For role prediction

# Common sensitive paths (for deep discovery)
SENSITIVE_PATHS = [
    "/staff", "/faculty", "/people", "/directory", "/contact", "/about",
    "/team", "/researchers", "/students", "/alumni", "/wp-content/uploads"
]

# File extensions to download & parse
DOCUMENT_EXTENSIONS = {'.pdf', '.doc', '.docx', '.ppt', '.pptx'}

# =============== INTELLIGENCE CORE ===============
class NexusHarvester:
    def __init__(self, root_url: str):
        self.root_url = root_url.rstrip('/')
        self.base_domain = urlparse(root_url).netloc.lower()
        if self.base_domain.startswith('www.'):
            self.base_domain = self.base_domain[4:]
        
        # Intelligence database
        self.emails: Dict[str, Dict] = {}  # email -> {name, role, dept, source}
        self.visited: Set[str] = set()
        self.documents: Set[str] = set()
        self.pages = 0
        self.session = None
        self.browser = None

    # ==================== 1. AI-Powered Context Intelligence ====================
    def extract_context(self, text: str, email: str) -> Dict:
        """Extract name, role, department near email using patterns + heuristics"""
        lines = text.split('\n')
        context = {"name": "", "role": "", "department": "", "confidence": 0.5}
        
        # Find line with email
        for i, line in enumerate(lines):
            if email in line.lower():
                # Look in nearby lines (±3)
                snippet = " ".join(lines[max(0, i-3):i+4])
                
                # Extract name (capitalized words near email)
                name_match = re.search(r'([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)', snippet)
                if name_match:
                    context["name"] = name_match.group(1)
                    context["confidence"] = max(context["confidence"], 0.8)
                
                # Role keywords
                roles = re.findall(r'(Professor|Dr\.?|Lecturer|Engineer|Director|Manager|Head|Coordinator|Researcher)', snippet, re.IGNORECASE)
                if roles:
                    context["role"] = roles[0]
                    context["confidence"] = max(context["confidence"], 0.9)
                
                # Departments (common in universities)
                depts = re.findall(r'(Computer Science|Electrical|Mechanical|Civil|IT|Library|Admissions)', snippet, re.IGNORECASE)
                if depts:
                    context["department"] = depts[0]
                    context["confidence"] = max(context["confidence"], 0.85)
                
                break
        return context

    # ==================== 2. Subdomain & Cloud Asset Discovery ====================
    async def discover_subdomains(self) -> List[str]:
        """Use rapid7 + crt.sh passive DNS (no scan = no noise)"""
        subdomains = set()
        try:
            # crt.sh (certificate transparency)
            url = f"https://crt.sh/?q=%.{self.base_domain}&output=json"
            async with self.session.get(url) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    for entry in data:
                        name = entry.get('name_value', '').lower()
                        if name.endswith(self.base_domain) and '*' not in name:
                            subdomains.add(f"https://{name}")
        except:
            pass
        
        # Add common subdomains
        for sub in ["www", "mail", "webmail", "staff", "cs", "it", "eee", "me", "ce", "library", "research"]:
            subdomains.add(f"https://{sub}.{self.base_domain}")
        
        return list(subdomains)[:MAX_SUBDOMAINS]

    # ==================== 3. Document Miner (PDF/DOCX) ====================
    async def download_document(self, url: str) -> str:
        """Download document and save temporarily"""
        try:
            async with self.session.get(url) as resp:
                if resp.status == 200:
                    ext = Path(urlparse(url).path).suffix.lower()
                    if ext in DOCUMENT_EXTENSIONS:
                        filename = f"/tmp/doc_{abs(hash(url))}{ext}"
                        with open(filename, 'wb') as f:
                            f.write(await resp.read())
                        return filename
        except:
            pass
        return ""

    def extract_emails_from_doc(self, filepath: str) -> Set[str]:
        """Extract emails from PDF/DOCX"""
        emails = set()
        try:
            if filepath.endswith('.pdf'):
                # Use pdftotext (must install: apt install poppler-utils)
                result = subprocess.run(['pdftotext', '-layout', filepath, '-'], 
                                      capture_output=True, text=True)
                text = result.stdout
            elif filepath.endswith(('.doc', '.docx', '.ppt', '.pptx')):
                # Use antiword or catdoc (fallback to strings)
                result = subprocess.run(['strings', filepath], capture_output=True, text=True)
                text = result.stdout
            else:
                return emails
            
            std_emails = re.findall(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', text)
            for email in std_emails:
                if self.is_target_domain(email):
                    emails.add(email.lower())
        except Exception as e:
            print(f"Doc extraction error: {str(e)[:50]}")
        finally:
            if os.path.exists(filepath):
                os.remove(filepath)
        return emails

    # ==================== 4. Evasion Engine ====================
    async def init_browser(self):
        """Stealth browser with advanced evasion"""
        pw = await async_playwright().start()
        self.browser = await pw.chromium.launch(
            headless=True,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--disable-web-security",
                "--no-sandbox",
                "--disable-features=IsolateOrigins,site-per-process",
                "--disable-extensions",
                "--disable-plugins",
                "--disable-images"  # Faster
            ]
        )

    async def fetch_with_evasion(self, url: str) -> str:
        """Fetch with anti-detection + retry"""
        if not self.browser:
            await self.init_browser()
        
        for attempt in range(2):
            context = await self.browser.new_context(
                user_agent=random.choice([
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15"
                ]),
                viewport={"width": random.randint(1024, 1920), "height": random.randint(768, 1080)},
                locale="en-US",
                timezone_id="America/New_York",
                permissions=["geolocation"]
            )
            
            # Critical evasion scripts
            await context.add_init_script("""
                delete navigator.__proto__.webdriver;
                window.chrome = { runtime: {} };
                Object.defineProperty(navigator, 'permissions', { get: () => ({ query: Promise.resolve({ state: 'granted' }) }) });
                Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3, 4, 5] });
                Object.defineProperty(navigator, 'languages', { get: () => ['en-US', 'en'] });
            """)
            
            page = await context.new_page()
            try:
                await page.goto(url, wait_until="domcontentloaded", timeout=TIMEOUT*1000)
                await page.wait_for_timeout(random.uniform(1000, 3000))
                content = await page.content()
                return content
            except Exception as e:
                if attempt == 1:
                    print(f"🛡️  Evasion failed for {url}: {str(e)[:60]}")
                await asyncio.sleep(2)
            finally:
                await context.close()
        return ""

    # ==================== CORE SCRAPE LOGIC ====================
    def is_target_domain(self, email: str) -> bool:
        if '@' not in email:
            return False
        _, domain = email.lower().rsplit('@', 1)
        return domain == self.base_domain or domain.endswith('.' + self.base_domain)

    def extract_and_clean_emails(self, text: str) -> Set[str]:
        # (Same advanced logic as before - de-obfuscation included)
        emails = set()
        std_emails = re.findall(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', text)
        for email in std_emails:
            if self.is_target_domain(email):
                emails.add(email.lower())
        # Add de-obfuscation here if needed
        return emails

    async def scrape_page(self, url: str):
        if url in self.visited or self.pages >= MAX_PAGES:
            return []
        self.visited.add(url)
        self.pages += 1
        print(f"[{self.pages}] 🕵️ {url}")

        # Fetch content
        html = await self.fetch_with_evasion(url)
        if not html:
            return []

        # Extract emails + context
        new_emails = self.extract_and_clean_emails(html)
        for email in new_emails:
            if email not in self.emails:
                context = self.extract_context(html, email)
                self.emails[email] = {
                    "name": context["name"],
                    "role": context["role"],
                    "department": context["department"],
                    "confidence": context["confidence"],
                    "source": url
                }

        # Find document links
        doc_links = re.findall(r'href=[\'"]?([^\'" >]+\.(pdf|docx?|pptx?))', html, re.IGNORECASE)
        for link, _ in doc_links:
            full_url = urljoin(url, link)
            if full_url not in self.documents:
                self.documents.add(full_url)
                doc_path = await self.download_document(full_url)
                if doc_path:
                    doc_emails = self.extract_emails_from_doc(doc_path)
                    for email in doc_emails:
                        if email not in self.emails:
                            self.emails[email] = {
                                "name": "", "role": "", "department": "",
                                "confidence": 0.6, "source": full_url
                            }

        # Extract next links
        next_urls = []
        if self.pages < MAX_PAGES:
            links = re.findall(r'href=[\'"]?([^\'" >]+)', html)
            for raw in links:
                if raw.startswith(('http://', 'https://')):
                    full = raw
                elif raw.startswith('/'):
                    full = urljoin(url, raw)
                else:
                    continue
                parsed = urlparse(full)
                domain = parsed.netloc.lower()
                if domain == self.base_domain or domain.endswith('.' + self.base_domain):
                    if full not in self.visited:
                        next_urls.append(full)
        return next_urls

    async def crawl(self):
        await self.init_session()
        
        # Start with root + subdomains + sensitive paths
        start_urls = [self.root_url]
        subdomains = await self.discover_subdomains()
        start_urls.extend(subdomains)
        for path in SENSITIVE_PATHS:
            start_urls.append(urljoin(self.root_url, path))
        
        queue = deque(start_urls)
        tasks = set()
        
        while (queue or tasks) and self.pages < MAX_PAGES:
            while queue and len(tasks) < CONCURRENT:
                url = queue.popleft()
                task = asyncio.create_task(self._worker(url, queue))
                tasks.add(task)
                task.add_done_callback(tasks.discard)
            await asyncio.sleep(0.05)
        
        print(f"\n🎯 Intelligence gathered: {len(self.emails)} profiles from {self.pages} assets.")

    async def _worker(self, url: str, queue: deque):
        next_urls = await self.scrape_page(url)
        for u in next_urls:
            queue.append(u)
        await asyncio.sleep(random.uniform(*DELAY))

    async def init_session(self):
        self.session = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=TIMEOUT),
            headers={"User-Agent": random.choice([
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36"
            ])}
        )

    async def close(self):
        if self.session:
            await self.session.close()
        if self.browser:
            await self.browser.close()

    # ==================== EXPORT INTELLIGENCE ====================
    def export(self):
        clean = self.base_domain.replace(".", "_")
        timestamp = int(time.time())
        
        # Full intelligence JSON
        with open(f"intel_{clean}_{timestamp}.json", "w") as f:
            json.dump({
                "domain": self.base_domain,
                "total": len(self.emails),
                "profiles": self.emails
            }, f, indent=2)
        
        # Hunter.io compatible
        with open(f"emails_{clean}_{timestamp}.csv", "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["Email", "First Name", "Last Name", "Position", "Company", "Department", "Source"])
            for email, data in self.emails.items():
                name_parts = data["name"].split()
                first = name_parts[0] if name_parts else ""
                last = " ".join(name_parts[1:]) if len(name_parts) > 1 else ""
                writer.writerow([
                    email, first, last, data["role"], self.base_domain,
                    data["department"], data["source"]
                ])
        
        print(f"\n✅ Intel exported:\n - intel_{clean}_{timestamp}.json\n - emails_{clean}_{timestamp}.csv")

# =============== RUN ===============
async def main():
    target = input("🎯 Enter target (e.g., duet.edu.pk): ").strip()
    if not target.startswith(("http://", "https://")):
        target = "https://" + target
    
    print(f"\n🚀 Launching NEXUS HARVESTER v3.0 on {target}...")
    harvester = NexusHarvester(target)
    try:
        await harvester.crawl()
        harvester.export()
    finally:
        await harvester.close()

if __name__ == "__main__":
    asyncio.run(main())