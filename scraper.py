# scraping_legale_con_playwright.py - Scraper responsabile con Playwright

from playwright.sync_api import sync_playwright
import time
import random
import re
import json
from pathlib import Path
from urllib.robotparser import RobotFileParser
import logging
import math

# Configura il logging per vedere cosa succede
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class WebScraper:
    def __init__(self, book_url: str, start_chapter: int, end_chapter: int):
        self.book_url = book_url.strip()
        self.start_chapter = start_chapter
        self.end_chapter = end_chapter
        self.text_selector = "#dle-content > article > div.block.story.shortstory"
        self.headers = {
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "it-IT,it;q=0.9,en-US;q=0.8,en;q=0.7",
            "Accept-Encoding": "gzip, deflate",
            "Connection": "keep-alive"
        }

    def check_robots_txt(self) -> bool:
        """Check if scraping is permitted by robots.txt"""
        try:
            rp = RobotFileParser()
            rp.set_url(f"{self.book_url.rstrip('/')}/robots.txt")
            rp.read()
            user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            can_fetch = rp.can_fetch(user_agent, self.book_url)
            if not can_fetch:
                logger.warning("Scraping prohibited by robots.txt")
            return True
        except Exception as e:
            logger.warning(f"Failed to read robots.txt: {e}")
            return True

    def get_targeted_chapter_info(self) -> list[dict]:
        """
        Efficiently gets chapter info by calculating which pages to visit
        based on the start and end chapter numbers.
        """
        targeted_chapters = []
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=False, slow_mo=500)
            page = browser.new_page()
            try:
                # 1. Fetch metadata from the first page
                logger.info(f"🔄 Fetching metadata from initial page: {self.book_url}")
                page.goto(self.book_url, wait_until="networkidle", timeout=30_000)
                data_content = page.evaluate("() => window.__DATA__")

                if not data_content:
                    logger.error("Could not extract metadata from the page.")
                    return []

                total_chapters = data_content.get('count_all')
                chapters_per_page = data_content.get('limit', 25)
                book_id = data_content.get('book_id')

                if not all([total_chapters, chapters_per_page, book_id]):
                    logger.error("Essential metadata (total_chapters, chapters_per_page, book_id) is missing.")
                    return []

                logger.info(f"✅ Metadata found: {total_chapters} total chapters, {chapters_per_page} per page.")

                # 2. Calculate target pages
                # Chapters are in descending order, so we calculate page numbers based on offset from the total.
                start_page = math.floor((total_chapters - self.end_chapter) / chapters_per_page) + 1
                end_page = math.floor((total_chapters - self.start_chapter) / chapters_per_page) + 1
                
                pages_to_visit = set(range(start_page, end_page + 1))
                logger.info(f"Calculated pages to visit: {sorted(list(pages_to_visit))}")

                # 3. Scrape only the necessary pages
                for page_num in sorted(list(pages_to_visit)):
                    # The first page is already loaded
                    if page_num == 1:
                         page_chapters = data_content.get('chapters', [])
                    else:
                        page_url = f"https://ranobes.top/chapters/{book_id}/page/{page_num}/"
                        logger.info(f"🔄 Loading targeted chapter page: {page_url}")
                        page.goto(page_url, wait_until="networkidle", timeout=30_000)
                        page_data = page.evaluate("() => window.__DATA__")
                        page_chapters = page_data.get('chapters', []) if page_data else []

                    if page_chapters:
                        targeted_chapters.extend(page_chapters)

                logger.info(f"✅ Found {len(targeted_chapters)} chapters on targeted pages.")
                return targeted_chapters

            except Exception as e:
                logger.error(f"❌ Error getting targeted chapter info: {e}")
                return []
            finally:
                browser.close()

    def scrape_selected(self, url: str) -> list[str]:
        """Extract data with Playwright (simulate real browser)"""
        if not self.check_robots_txt():
            logger.error("Scraping prohibited by robots.txt")
            return []

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=False, slow_mo=500)
            page = browser.new_page()
            try:
                logger.info(f"🔄 Load page: {url}")
                page.set_extra_http_headers(self.headers)
                response = page.goto(url, wait_until="networkidle", timeout=20_000)

                if response.status != 200:
                    logger.error(f"HTTP error: {response.status}")
                    return []

                page.wait_for_load_state("networkidle")
                time.sleep(random.uniform(3, 6))

                results = []
                elements = page.query_selector_all(self.text_selector)
                for el in elements:
                    text = el.inner_text().strip()
                    if text:
                        results.append(text)
                
                if not results:
                    logger.warning("⚠️ No element found with given selector.")
                return results
            except Exception as e:
                logger.error(f"❌ Error during scraping: {e}")
                return []
            finally:
                browser.close()

    def scrape(self):
        temp_dir = Path("temp")
        temp_dir.mkdir(exist_ok=True)

        chapter_info_from_pages = self.get_targeted_chapter_info()
        if not chapter_info_from_pages:
            logger.error("No chapter information found. Exiting.")
            return None

        chapters_to_scrape = []
        for chapter in chapter_info_from_pages:
            title = chapter.get('title', '')
            # Use regex to robustly find the chapter number
            match = re.search(r'Chapter\s+(\d+)', title, re.IGNORECASE)
            if match:
                chapter_num = int(match.group(1))
                if self.start_chapter <= chapter_num <= self.end_chapter:
                    chapters_to_scrape.append(chapter)
        
        logger.info(f"Filtered down to {len(chapters_to_scrape)} chapters to scrape between chapter {self.start_chapter} and {self.end_chapter}.")

        # Sort chapters to scrape them in ascending order
        chapters_to_scrape.sort(key=lambda x: int(re.search(r'Chapter\s+(\d+)', x['title'], re.IGNORECASE).group(1)))

        for chapter in chapters_to_scrape:
            url = chapter['link']
            results = self.scrape_selected(url)
            
            if not results:
                logger.error(f"❌ No results to save for {url}, skipping.")
                continue
            
            content = results[0]
            first_line = content.split('\n')[0].strip()
            
            safe_filename = re.sub(r'[<>:"/\\|?*]', '', first_line)
            safe_filename = safe_filename[:100].strip().replace(' ', '_')
            
            if not safe_filename:
                safe_filename = f"chapter_{chapter.get('id', 'unknown')}"
            
            filepath = temp_dir / f"{safe_filename}.txt"
            filepath.write_text(content, encoding='utf-8')
            
            logger.info(f"💾 Saved to: {filepath}")
            print(f"Content saved to: {filepath}")

        return temp_dir


if __name__ == "__main__":
    # Example of use
    book_url = "https://ranobes.top/chapters/1205249/"
    start_chapter = 3060
    end_chapter = 3062
    
    scraper = WebScraper(book_url, start_chapter, end_chapter)
    scraper.scrape()