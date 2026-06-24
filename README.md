# Nation.africa Columnist Scraper

This is a personal project built to gather and archive columns, opinion pieces, and articles written by my favorite writer, **Makau Mutua**, from [nation.africa](https://nation.africa).

It automates session authentication via cookies, pagination crawling, metadata extraction, dynamic client-side content rendering, and markdown conversion.

---

## Features

- **Authenticated Premium Scraping**: Uses merged browser cookies (including `my.nationmedia.com` authentication sessions) to bypass the paywall and download full premium articles.
- **Dynamic Content Loading Check**: Automatically polls the article body content for up to 7 seconds to wait for client-side JavaScript to inject full premium content, avoiding incomplete 2-paragraph previews.
- **Robust Markdown Conversion**: Converts article bodies to clean, read-optimized Markdown using BeautifulSoup and `markdownify`, removing ad containers, tracking scripts, and "Also Read:" links.
- **Resumable Runs**: Checks the success log to skip already successfully scraped articles on subsequent runs.
- **Detailed Logging**: Records successfully scraped articles in `success_log.json` and logs failures with exact reason messages (e.g. video page, network error, Cloudflare block) in `failed_log.json`.

---

## Codebase Structure

- **`scraper.py`**: The main scraping controller. Supports:
  - `collect`: Search and crawl all pagination pages to collect article URLs into `links.json`.
  - `scrape`: Iteratively fetch, wait, parse, format, and save each article.
- **`clean_paywalled.py`**: Utility script to clean up short/paywalled previews (< 1600 characters) and synchronize the success log.
- **`cookies.json`**: Session cookies exported from the browser for authentication.
- **`links.json`**: Catalog of crawled article URLs.
- **`success_log.json`**: JSON list of successfully scraped articles (`title`, `author`, `date`, `link`, `url`, `timestamp`).
- **`failed_log.json`**: JSON list of failed article scrapes with reasons for debugging.
- **`markdown/`**: Directory containing the final saved `.md` files.

---

## Usage

### Prerequisites
Make sure you have Python 3.10+ and the virtual environment activated:
```bash
# Activate virtual environment
.\venv\Scripts\activate
```

### 1. Collect Article Links
Crawls search results pagination for the columnist name and populates `links.json`:
```bash
python scraper.py collect --query "Makau Mutua"
```

### 2. Scrape Articles
Downloads and processes collected articles:
```bash
python scraper.py scrape
```
