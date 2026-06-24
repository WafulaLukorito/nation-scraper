import os
import sys
import json
import time
import argparse
import asyncio
import re
from urllib.parse import urljoin, urlparse, parse_qs
from bs4 import BeautifulSoup
from playwright.async_api import async_playwright
import markdownify

COOKIES_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "cookies.json")
LINKS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "links.json")
OUTPUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "markdown")
SUCCESS_LOG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "success_log.json")
FAILED_LOG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "failed_log.json")

# Ensure output directory exists
os.makedirs(OUTPUT_DIR, exist_ok=True)

async def load_cookies(context):
    """Load cookies from cookies.json into the browser context."""
    if not os.path.exists(COOKIES_FILE):
        print(f"Warning: Cookies file not found at {COOKIES_FILE}. Running without authenticated cookies.")
        return False
        
    try:
        with open(COOKIES_FILE, 'r', encoding='utf-8') as f:
            cookies = json.load(f)
            
        formatted_cookies = []
        for c in cookies:
            fc = {
                "name": c.get("name"),
                "value": c.get("value"),
                "domain": c.get("domain"),
                "path": c.get("path", "/"),
                "secure": c.get("secure", True),
                "httpOnly": c.get("httpOnly", False)
            }
            if "sameSite" in c:
                ss = c["sameSite"]
                if ss in ["Lax", "None", "Strict"]:
                    fc["sameSite"] = ss
            if "expirationDate" in c:
                fc["expires"] = int(c["expirationDate"])
            elif "expires" in c:
                fc["expires"] = int(c["expires"])
            formatted_cookies.append(fc)
            
        await context.add_cookies(formatted_cookies)
        print(f"Successfully loaded {len(formatted_cookies)} cookies into browser context.")
        return True
    except Exception as e:
        print(f"Error loading cookies: {e}")
        return False

async def block_resources(route):
    """Block heavy resources for faster scraping."""
    if route.request.resource_type in ["image", "media", "font", "stylesheet"]:
        await route.abort()
    else:
        await route.continue_()

async def run_collect(query="Makau Mutua"):
    """Collect article links from search results pagination by loading pageNum query param."""
    print(f"Starting link collection for query: '{query}'")
    links = set()
    
    # Load existing links if links.json exists
    if os.path.exists(LINKS_FILE):
        try:
            with open(LINKS_FILE, 'r', encoding='utf-8') as f:
                saved = json.load(f)
                links = set(saved.get("links", []))
                print(f"Loaded {len(links)} existing links from links.json")
        except Exception:
            pass

    async with async_playwright() as p:
        # Launch Chrome with automation flags disabled to bypass Cloudflare turnstile
        browser = await p.chromium.launch(
            headless=True,
            channel="chrome",
            args=["--disable-blink-features=AutomationControlled"]
        )
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        
        await load_cookies(context)
        page = await context.new_page()
        await page.route("**/*", block_resources)
        
        # Format query for URL
        formatted_query = query.replace(" ", "%20")
        
        # 1. Fetch page 1 (pageNum=0) to parse total pages count
        base_search_url = f"https://nation.africa/service/search/kenya/290754?query={formatted_query}&sortByDate=true"
        first_page_url = f"{base_search_url}&pageNum=0"
        
        print(f"Fetching first page to discover total page count: {first_page_url}")
        await page.goto(first_page_url, wait_until="domcontentloaded", timeout=60000)
        await page.wait_for_timeout(3000)
        
        html = await page.content()
        soup = BeautifulSoup(html, 'html.parser')
        
        # Try to parse total pages from elements like:
        # <p class="search-pagination-index">Page 1 of 114</p>
        total_pages = 1
        page_index_el = soup.select_one('.search-pagination-index')
        if page_index_el:
            index_text = page_index_el.get_text().strip()
            print(f"Found pagination text: '{index_text}'")
            # Parse number after "of"
            match = re.search(r'of\s+(\d+)', index_text)
            if match:
                total_pages = int(match.group(1))
                print(f"Discovered total pages: {total_pages}")
            else:
                print("Could not parse total pages from pagination text. Defaulting to 1 page.")
        else:
            print("Could not find pagination index element. Defaulting to 1 page.")
            
        # Loop through all pages from pageNum=0 to pageNum=total_pages-1
        for page_num in range(total_pages):
            current_url = f"{base_search_url}&pageNum={page_num}"
            print(f"\n--- Loading Search Page {page_num + 1} of {total_pages} ---")
            print(f"URL: {current_url}")
            
            try:
                if page_num > 0:  # already navigated for page 0
                    await page.goto(current_url, wait_until="domcontentloaded", timeout=60000)
                    await page.wait_for_timeout(3000)
                    html = await page.content()
                    soup = BeautifulSoup(html, 'html.parser')
                
                # Check for Cloudflare/bot block page in title
                title = await page.title()
                if "Cloudflare" in title or "Attention Required" in title or "Access Denied" in title:
                    print("Warning: Cloudflare or access denied page detected. Retrying once after 5s...")
                    await page.wait_for_timeout(5000)
                    await page.goto(current_url, wait_until="domcontentloaded", timeout=60000)
                    await page.wait_for_timeout(3000)
                    html = await page.content()
                    soup = BeautifulSoup(html, 'html.parser')
                
                # Extract links inside .search-page container
                search_page_div = soup.select_one('.search-page')
                if not search_page_div:
                    print("Warning: Could not find '.search-page' results container. Skipping this page.")
                    continue
                    
                page_links = []
                for a in search_page_div.find_all('a', href=True):
                    href = a['href']
                    text = a.get_text().strip()
                    
                    # Pattern match for article IDs: ends with -digits
                    parts = href.split('/')
                    if len(parts) > 3:
                        last_part = parts[-1].split('?')[0]
                        if '-' in last_part:
                            subparts = last_part.split('-')
                            if subparts[-1].isdigit() and len(subparts[-1]) >= 4:
                                # Convert to absolute URL
                                if href.startswith('/'):
                                    abs_url = "https://nation.africa" + href
                                else:
                                    abs_url = href
                                    
                                # Strip query parameters
                                clean_url = abs_url.split('?')[0].split('#')[0]
                                if clean_url not in links:
                                    links.add(clean_url)
                                    page_links.append(clean_url)
                                    print(f"  + Found article: {clean_url} | {text[:50]}")
                                    
                print(f"Page {page_num + 1}: Found {len(page_links)} new article links. Total unique: {len(links)}")
                
                # Save progress after every page
                with open(LINKS_FILE, 'w', encoding='utf-8') as f:
                    json.dump({"links": list(links)}, f, indent=2)
                    
            except Exception as e:
                print(f"Error scraping search page {page_num + 1}: {e}")
                print("Continuing to next page...")
                
        await browser.close()
    
    print(f"\nFinished collection. Total collected links: {len(links)}")

def parse_article_html(html, url):
    """Parse article HTML and extract Title, Author, Date, and Content."""
    soup = BeautifulSoup(html, 'html.parser')
    
    title = ""
    author = "Unknown Author"
    date_str = "Unknown Date"
    content_html = ""
    
    # 1. Try parsing JSON-LD (highly robust for schema metadata)
    json_ld_scripts = soup.find_all('script', type='application/ld+json')
    for script in json_ld_scripts:
        try:
            data = json.loads(script.string)
            if isinstance(data, list):
                items = data
            elif isinstance(data, dict):
                if '@graph' in data:
                    items = data['@graph']
                else:
                    items = [data]
            else:
                items = []
                
            for item in items:
                if item.get('@type') in ['NewsArticle', 'Article', 'BlogPosting']:
                    if not title:
                        title = item.get('headline', '')
                    
                    # Parse author
                    auth_data = item.get('author')
                    if auth_data:
                        if isinstance(auth_data, list):
                            author = ", ".join([a.get('name', '') for a in auth_data if isinstance(a, dict)])
                        elif isinstance(auth_data, dict):
                            author = auth_data.get('name', 'Unknown Author')
                        elif isinstance(auth_data, str):
                            author = auth_data
                            
                    # Parse date
                    if item.get('datePublished'):
                        date_str = item.get('datePublished')
                    elif item.get('dateCreated'):
                        date_str = item.get('dateCreated')
        except Exception:
            continue
            
    # 2. Fallbacks for Title
    if not title:
        h1 = soup.find('h1')
        if h1:
            title = h1.get_text().strip()
        else:
            title = soup.title.get_text().replace("- Nation", "").strip() if soup.title else "Untitled"
            
    # 3. Fallbacks for Author
    if author == "Unknown Author":
        author_el = (soup.find(class_=lambda c: c and 'author' in c.lower()) or 
                     soup.find(class_=lambda c: c and 'writer' in c.lower()) or
                     soup.find(class_=lambda c: c and 'byline' in c.lower()))
        if author_el:
            author = author_el.get_text().strip()
            
    # 4. Fallbacks for Date
    if date_str == "Unknown Date":
        time_el = soup.find('time')
        if time_el:
            date_str = time_el.get('datetime') or time_el.get_text().strip()
        else:
            date_el = soup.find(class_=lambda c: c and ('publish' in c.lower() or 'date' in c.lower()))
            if date_el:
                date_str = date_el.get_text().strip()
                
    # 5. Extract Article Content HTML
    body_container = None
    body_selectors = [
        '.article-body', '.article__body', '.entry-content', '.post-content', 
        '.article-content', '.article-copy', 'article .content', 'article'
    ]
    
    for selector in body_selectors:
        body_container = soup.select_one(selector)
        if body_container:
            break
            
    if not body_container:
        body_container = soup
        
    # Clean up standard non-content elements inside body container
    for tag in body_container.find_all(['script', 'style', 'iframe', 'noscript', 'header', 'footer', 'nav']):
        tag.decompose()
    for class_keyword in ['promo', 'share', 'social', 'ad-', 'advertisement', 'related', 'newsletter', 'comment', 'widget']:
        for tag in body_container.find_all(class_=lambda c: c and any(kw in c.lower() for kw in class_keyword.split())):
            tag.decompose()
            
    content_html = str(body_container)
    
    # Convert HTML to markdown, keeping only basic structures
    md_converter = markdownify.MarkdownConverter(
        strip=['img', 'script', 'style', 'iframe', 'button', 'svg'],
        heading_style="ATX"
    )
    content_markdown = md_converter.convert(content_html).strip()
    
    # Strip paywall/subscription artifacts from the end of the markdown content
    paywall_patterns = [
        r"## Register to continue reading this premium article[\s\S]*",
        r"## To continue reading, please subscribe[\s\S]*"
    ]
    for pattern in paywall_patterns:
        content_markdown = re.sub(pattern, "", content_markdown)
        
    # Strip "Also Read:" links (e.g. **Also Read: ...**)
    content_markdown = re.sub(r"\*\*Also Read:[\s\S]*?\*\*\n?", "", content_markdown)
    content_markdown = re.sub(r"(?i)\*?\*?Also Read:.*?\n?", "", content_markdown)
        
    content_markdown = content_markdown.strip()
    
    return {
        "title": title,
        "author": author,
        "date": date_str,
        "content": content_markdown,
        "url": url
    }

async def log_success(url, title, author, date, log_lock):
    """Append a success log entry to success_log.json."""
    async with log_lock:
        logs = []
        if os.path.exists(SUCCESS_LOG_FILE):
            try:
                with open(SUCCESS_LOG_FILE, 'r', encoding='utf-8') as f:
                    logs = json.load(f)
            except Exception:
                pass
        
        # Check if already logged to prevent duplicates
        if not any(log.get("url") == url for log in logs):
            logs.append({
                "url": url,
                "link": url,
                "title": title,
                "author": author,
                "date": date,
                "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
            })
            with open(SUCCESS_LOG_FILE, 'w', encoding='utf-8') as f:
                json.dump(logs, f, indent=2)

async def log_failure(url, reason, log_lock, title=None, author=None, date=None):
    """Append a failure log entry to failed_log.json."""
    async with log_lock:
        logs = []
        if os.path.exists(FAILED_LOG_FILE):
            try:
                with open(FAILED_LOG_FILE, 'r', encoding='utf-8') as f:
                    logs = json.load(f)
            except Exception:
                pass
                
        # Remove previous failure for the same URL if retrying
        logs = [log for log in logs if log.get("url") != url]
        
        logs.append({
            "url": url,
            "link": url,
            "title": title or "Unknown Title",
            "author": author or "Unknown Author",
            "date": date or "Unknown Date",
            "reason": str(reason),
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        })
        with open(FAILED_LOG_FILE, 'w', encoding='utf-8') as f:
            json.dump(logs, f, indent=2)

async def scrape_single_url(context, url, idx, total_urls, sem, log_lock, success_urls):
    """Scrape a single article URL with semaphore locking, skip if already in success log."""
    async with sem:
        parsed_url = urlparse(url)
        path_parts = [p for p in parsed_url.path.split('/') if p]
        file_slug = path_parts[-1] if path_parts else f"article_{idx}"
        file_slug = "".join([c for c in file_slug if c.isalnum() or c in ['-', '_']]).strip()
        filename = f"{file_slug}.md"
        filepath = os.path.join(OUTPUT_DIR, filename)
        
        # Resumable check using success log and file existence
        if url in success_urls and os.path.exists(filepath):
            print(f"[{idx}/{total_urls}] Already scraped: {filename} (Skipping)")
            return
            
        print(f"[{idx}/{total_urls}] Scraping: {url}")
        page = await context.new_page()
        try:
            await page.route("**/*", block_resources)
            # Fetch with a generous timeout to handle temporary network issues
            await page.goto(url, wait_until="domcontentloaded", timeout=45000)
            
            # Wait up to 7 seconds for dynamic client-side premium content to load
            start_wait = time.time()
            article = None
            while time.time() - start_wait < 7.0:
                html = await page.content()
                article = parse_article_html(html, url)
                # Break early if we successfully loaded the full content
                if article and article["content"] and len(article["content"]) >= 1600:
                    break
                await page.wait_for_timeout(500)
                
            # Fallback one final parse check
            if not article or not article["content"] or len(article["content"]) < 1600:
                html = await page.content()
                article = parse_article_html(html, url)
            
            # Paywall check: length of parsed content < 1600 characters is considered paywalled
            if not article["content"] or len(article["content"]) < 1600:
                reason = "Paywall triggered or incomplete content (less than 1600 characters)"
                print(f"Warning: {reason} for {url}")
                await log_failure(url, reason, log_lock, article.get('title'), article.get('author'), article.get('date'))
            else:
                markdown_content = f"""# {article['title']}

**Author:** {article['author']}  
**Date:** {article['date']}  
**Source URL:** {article['url']}  

---

{article['content']}
"""
                with open(filepath, 'w', encoding='utf-8') as out_f:
                    out_f.write(markdown_content)
                print(f"[{idx}/{total_urls}] Saved to: markdown/{filename}")
                await log_success(url, article['title'], article['author'], article['date'], log_lock)
            
            # Throttle a bit to prevent server overload
            await asyncio.sleep(1)
        except Exception as e:
            print(f"[{idx}/{total_urls}] Error scraping {url}: {e}")
            # Try to extract whatever meta we can
            title, author, date = None, None, None
            try:
                html = await page.content()
                article = parse_article_html(html, url)
                title = article.get('title')
                author = article.get('author')
                date = article.get('date')
            except Exception:
                pass
            await log_failure(url, str(e), log_lock, title, author, date)
        finally:
            await page.close()

async def run_scrape(limit=None):
    """Scrape articles from links.json and save them as markdown files in parallel."""
    if not os.path.exists(LINKS_FILE):
        print(f"Error: No link file found at {LINKS_FILE}. Please run collect first.")
        return
        
    with open(LINKS_FILE, 'r', encoding='utf-8') as f:
        data = json.load(f)
        urls = data.get("links", [])
        
    if not urls:
        print("No URLs found to scrape.")
        return
        
    if limit:
        urls = urls[:limit]
        print(f"Scraping limit set: Only scraping first {limit} articles.")
    else:
        print(f"Starting scraping of all {len(urls)} articles.")
        
    # Load existing success URLs
    success_urls = set()
    if os.path.exists(SUCCESS_LOG_FILE):
        try:
            with open(SUCCESS_LOG_FILE, 'r', encoding='utf-8') as f:
                success_data = json.load(f)
                success_urls = {entry.get("url") for entry in success_data}
        except Exception:
            pass
    print(f"Found {len(success_urls)} already successfully scraped articles in success log.")
        
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            channel="chrome",
            args=["--disable-blink-features=AutomationControlled"]
        )
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        
        await load_cookies(context)
        
        # Concurrency limit: 4 pages in parallel
        sem = asyncio.Semaphore(4)
        log_lock = asyncio.Lock()
        tasks = []
        for idx, url in enumerate(urls):
            tasks.append(scrape_single_url(context, url, idx + 1, len(urls), sem, log_lock, success_urls))
            
        await asyncio.gather(*tasks)
        await browser.close()
    print("Scraping completed.")

def main():
    parser = argparse.ArgumentParser(description="Nation.africa Article Scraper")
    subparsers = parser.add_subparsers(dest="command", help="Command to run")
    
    # Collect links command
    collect_parser = subparsers.add_parser("collect", help="Collect article links from search pagination")
    collect_parser.add_argument("--query", default="Makau Mutua", help="Search query (default: 'Makau Mutua')")
    
    # Scrape command
    scrape_parser = subparsers.add_parser("scrape", help="Scrape content for collected URLs")
    scrape_parser.add_argument("--limit", type=int, help="Limit number of articles to scrape (for testing)")
    
    args = parser.parse_args()
    
    if args.command == "collect":
        asyncio.run(run_collect(args.query))
    elif args.command == "scrape":
        asyncio.run(run_scrape(args.limit))
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
