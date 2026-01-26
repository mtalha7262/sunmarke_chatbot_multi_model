import os
import re
import time
from typing import List

from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium_stealth import stealth

# from scraping.urls import URLS

from scraping.urls import URLS

RAW_DIR = "data/raw_content"
PARSED_DIR = "data/parsed_content"
os.makedirs(RAW_DIR, exist_ok=True)
os.makedirs(PARSED_DIR, exist_ok=True)


def slugify(url: str) -> str:
    base = url.replace("https://www.sunmarke.com/", "").strip("/")
    return re.sub(r"[^a-zA-Z0-9]+", "_", base) or "home"


def extract_content(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")

    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()

    texts = []

    # Prefer main content
    main = soup.find("main") or soup.body or soup

    # Headings
    for h in main.find_all(["h1", "h2", "h3", "h4"]):
        t = h.get_text(" ", strip=True)
        if t:
            texts.append(t)

    # Paragraphs
    for p in main.find_all("p"):
        t = p.get_text(" ", strip=True)
        if len(t) >= 30:
            texts.append(t)

    # Lists often contain key info (fees, steps, etc.)
    for li in main.find_all("li"):
        t = li.get_text(" ", strip=True)
        if 20 <= len(t) <= 250:
            texts.append(t)

    # De-duplicate in order
    deduped = list(dict.fromkeys(texts))
    return "\n\n".join(deduped)


def clean_text(text: str) -> str:
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r"[ \t]{2,}", " ", text)
    return text.strip()


def build_driver() -> webdriver.Chrome:
    options = Options()
    options.add_argument("--start-maximized")
    options.add_argument("--disable-blink-features=AutomationControlled")
    # For server environments, you may need:
    # options.add_argument("--headless=new")
    # options.add_argument("--no-sandbox")
    # options.add_argument("--disable-dev-shm-usage")

    driver = webdriver.Chrome(options=options)
    stealth(
        driver,
        languages=["en-US", "en"],
        vendor="Google Inc.",
        platform="Win32",
        webgl_vendor="Intel Inc.",
        renderer="Intel Iris OpenGL Engine",
        fix_hairline=True,
    )
    return driver


def scrape(urls: List[str]) -> None:
    driver = build_driver()
    try:
        for url in urls:
            print(f"Scraping: {url}")
            driver.get(url)
            time.sleep(6)

            html = driver.page_source
            extracted = extract_content(html)
            cleaned = clean_text(extracted)

            name = slugify(url)
            raw_path = os.path.join(RAW_DIR, f"{name}.txt")
            parsed_path = os.path.join(PARSED_DIR, f"{name}_clean.txt")

            with open(raw_path, "w", encoding="utf-8") as f:
                f.write(extracted)

            with open(parsed_path, "w", encoding="utf-8") as f:
                f.write(cleaned)

            print(f"Saved → {name}.txt")
    finally:
        driver.quit()
        print("\n✅ ALL PAGES SCRAPED SUCCESSFULLY")


if __name__ == "__main__":
    scrape(URLS)
