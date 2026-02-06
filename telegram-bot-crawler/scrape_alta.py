# Alta.ru TNVED Scraper v2
# Scrapes TNVED codes from alta.ru by iterating through known 10-digit codes
# Uses existing tnved_dump.json to get the list of codes, then fetches fresh descriptions

import asyncio
import aiohttp
import json
import re
from pathlib import Path
from bs4 import BeautifulSoup
from typing import List, Dict, Optional
import time

# Input: existing codes (we'll read codes from here)
INPUT_FILE = "tnved_dump.json"
# Output: clean data with proper Russian descriptions
OUTPUT_FILE = "tnved_alta_clean.json"

# Alta.ru base URL for individual codes
CODE_URL_TEMPLATE = "https://www.alta.ru/tnved/code/{code}/"

# Rate limiter: max concurrent requests
MAX_CONCURRENT = 3
semaphore = asyncio.Semaphore(MAX_CONCURRENT)

# Progress tracking
processed_count = 0
total_count = 0

async def fetch_page(session: aiohttp.ClientSession, url: str) -> Optional[str]:
    """Fetch a page with rate limiting and retry."""
    async with semaphore:
        for attempt in range(3):
            try:
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=30)) as response:
                    if response.status == 200:
                        return await response.text()
                    elif response.status == 404:
                        return None  # Code doesn't exist
                    else:
                        print(f"  Warning: {response.status} for {url}")
                        await asyncio.sleep(1)
            except asyncio.TimeoutError:
                print(f"  Timeout for {url}, attempt {attempt + 1}")
                await asyncio.sleep(2)
            except Exception as e:
                print(f"  Error fetching {url}: {e}")
                await asyncio.sleep(1)
        return None

def extract_code_details(html: str, code: str) -> Dict:
    """Extract details from a code page."""
    soup = BeautifulSoup(html, 'html.parser')
    
    result = {
        "code": code,
        "description": "",
        "duty_pct": 0.0,
        "vat_pct": 20.0,
    }
    
    # Find description from the page title or breadcrumbs
    # Alta.ru typically has the description in the OG description or page content
    
    # Try meta description first
    meta_desc = soup.find('meta', attrs={'name': 'description'}) or soup.find('meta', attrs={'property': 'og:description'})
    if meta_desc and meta_desc.get('content'):
        desc = meta_desc['content']
        # Extract just the product description part (before "Базовая ставка")
        if ':' in desc:
            desc = desc.split(':', 1)[1].strip()
        if '.' in desc:
            desc = desc.split('.')[0].strip()
        result["description"] = desc[:300]
    
    # Alternatively, look for the main content
    if not result["description"]:
        # Try the h1 or specific content area
        content = soup.find('div', class_='tnved-code-info') or soup.find('h1')
        if content:
            text = content.get_text(strip=True)
            # Clean up
            text = re.sub(r'^Код\s+ТН\s+ВЭД\s+\d+\s*', '', text, flags=re.IGNORECASE)
            result["description"] = text[:300]
    
    # Extract duty rate
    page_text = soup.get_text()
    
    # Look for percentage pattern
    duty_patterns = [
        r'ставка[^0-9]*?(\d+(?:[.,]\d+)?)\s*%',
        r'пошлин[^0-9]*?(\d+(?:[.,]\d+)?)\s*%',
        r'(\d+(?:[.,]\d+)?)\s*%\s*(?:пошлин|ставка)',
    ]
    
    for pattern in duty_patterns:
        match = re.search(pattern, page_text, re.IGNORECASE)
        if match:
            try:
                val = match.group(1).replace(',', '.')
                result["duty_pct"] = float(val)
                break
            except ValueError:
                pass
    
    # Look for euro/kg pattern (common for textiles)
    if result["duty_pct"] == 0:
        euro_match = re.search(r'(\d+(?:[.,]\d+)?)\s*евро/кг', page_text, re.IGNORECASE)
        if euro_match:
            try:
                val = euro_match.group(1).replace(',', '.')
                # Rough conversion: assume avg price ~10 euro/kg -> 1 euro/kg = ~10%
                result["duty_pct"] = float(val) * 5  # Approximate
            except ValueError:
                pass
    
    return result

async def scrape_code(session: aiohttp.ClientSession, code: str) -> Optional[Dict]:
    """Scrape a single code from alta.ru."""
    global processed_count
    
    url = CODE_URL_TEMPLATE.format(code=code)
    html = await fetch_page(session, url)
    
    processed_count += 1
    if processed_count % 100 == 0:
        print(f"Progress: {processed_count}/{total_count} ({100*processed_count/total_count:.1f}%)")
    
    if html:
        return extract_code_details(html, code)
    return None

async def main():
    """Main scraping function."""
    global total_count
    
    # Load existing codes
    print(f"Loading codes from {INPUT_FILE}...")
    
    if not Path(INPUT_FILE).exists():
        print(f"Error: {INPUT_FILE} not found!")
        print("Please ensure you have a file with TNVED codes to scrape.")
        return
    
    with open(INPUT_FILE, 'r', encoding='utf-8') as f:
        existing_data = json.load(f)
    
    # Extract 10-digit codes only
    codes = []
    for item in existing_data:
        code = str(item.get('code', '')).strip()
        if len(code) == 10 and code.isdigit():
            codes.append(code)
    
    codes = list(set(codes))  # Remove duplicates
    total_count = len(codes)
    
    print(f"Found {total_count} unique 10-digit codes to scrape")
    
    if total_count == 0:
        print("No valid codes found!")
        return
    
    # Scrape in batches
    results = []
    batch_size = 50
    
    async with aiohttp.ClientSession(headers={
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "ru-RU,ru;q=0.9,en;q=0.8",
    }) as session:
        
        for i in range(0, len(codes), batch_size):
            batch = codes[i:i + batch_size]
            tasks = [scrape_code(session, code) for code in batch]
            batch_results = await asyncio.gather(*tasks)
            
            for result in batch_results:
                if result and result.get("description"):
                    results.append(result)
            
            # Save intermediate results every 500 codes
            if len(results) % 500 < batch_size:
                with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
                    json.dump(results, f, ensure_ascii=False, indent=2)
                print(f"  Saved {len(results)} codes to {OUTPUT_FILE}")
            
            # Small delay between batches
            await asyncio.sleep(0.5)
    
    # Save final results
    print(f"\nTotal codes scraped successfully: {len(results)}")
    
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    
    print(f"Saved to {OUTPUT_FILE}")
    print("\nTo import into bot database, run:")
    print(f"  python import_tnved.py {OUTPUT_FILE}")

if __name__ == "__main__":
    print("Alta.ru TNVED Scraper v2")
    print("=" * 40)
    asyncio.run(main())
