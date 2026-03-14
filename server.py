from flask import Flask, send_file, jsonify
from playwright.sync_api import sync_playwright
import pandas as pd
import threading, time, os, re
from datetime import datetime

app = Flask(__name__)

# ---- paste your clean() to_ddmmyyyy() get_book_details() here unchanged ----

LISTING_PAGES = [
    "https://www.amazon.com/Best-Sellers-Kindle-Store-Paranormal-Romance/zgbs/digital-text/6190484011/ref=zg_bs_pg_1?_encoding=UTF8&pg=1",
    "https://www.amazon.com/Best-Sellers-Kindle-Store-Paranormal-Romance/zgbs/digital-text/6190484011/ref=zg_bs_pg_2?_encoding=UTF8&pg=2",
]

@app.route("/")
def home():
    return jsonify({"status": "ok", "message": "Scraper is running. Hit /scrape to start."})

@app.route("/scrape")
def scrape():
    books = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=["--no-sandbox", "--disable-setuid-sandbox"])
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            viewport={"width": 1366, "height": 768},
            locale="en-US",
        )
        page = context.new_page()
        counter = 1

        for page_num, pg_url in enumerate(LISTING_PAGES, 1):
            page.goto(pg_url, wait_until="domcontentloaded")
            page.wait_for_timeout(6000)
            page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            page.wait_for_timeout(2000)
            page.evaluate("window.scrollTo(0, 0)")
            page.wait_for_timeout(1000)

            items = page.query_selector_all(".zg-item-immersion, .zg-grid-general-faceout, [id^='zg-item']")

            for item in items:
                rank = ""
                for r_sel in [".zg-bdg-text", ".p13n-sc-badge-label", ".zg-badge-label"]:
                    el = item.query_selector(r_sel)
                    if el:
                        rank = clean(el.inner_text()).replace("#", "")
                        if rank:
                            break
                if not rank:
                    rank = str(counter)
                counter += 1

                title = ""
                img = item.query_selector("img")
                if img:
                    title = clean(img.get_attribute("alt") or "")

                book_url = ""
                link = item.query_selector("a[href]")
                if link:
                    href = clean(link.get_attribute("href") or "")
                    if href:
                        book_url = ("https://www.amazon.com" + href.split("?")[0]) if not href.startswith("http") else href.split("?")[0]

                author = ""
                for a_sel in [".a-size-small.a-link-child", ".a-size-small.a-color-base", ".a-size-small a"]:
                    el = item.query_selector(a_sel)
                    if el:
                        author = clean(el.inner_text())
                        if author:
                            break

                rating = ""
                el = item.query_selector(".a-icon-alt")
                if el:
                    rating = clean(el.inner_text()).split(" ")[0]

                reviews = ""
                for a in item.query_selector_all("a"):
                    href_val = a.get_attribute("href") or ""
                    text_val = clean(a.inner_text())
                    if "customerReview" in href_val and text_val:
                        reviews = text_val
                        break

                price = ""
                for p_sel in [".a-size-base.a-color-price", ".p13n-sc-price", ".a-price .a-offscreen"]:
                    el = item.query_selector(p_sel)
                    if el:
                        price = clean(el.inner_text())
                        if price:
                            break

                books.append({"Rank": rank, "Title": title, "Author": author, "Rating": rating,
                               "Reviews": reviews, "Price": price, "URL": book_url,
                               "Description": "", "Publisher": "", "Publication Date": ""})

        for i, book in enumerate(books):
            if not book["URL"]:
                continue
            details = get_book_details(page, book["URL"])
            book.update(details)
            time.sleep(1.5)

        browser.close()

    df = pd.DataFrame(books, columns=["Rank","Title","Author","Rating","Reviews","Price","URL","Description","Publisher","Publication Date"])
    path = "/tmp/amazon_books_dataset_100.csv"
    df.to_csv(path, index=False, encoding="utf-8-sig")
    return send_file(path, as_attachment=True, download_name="amazon_books_dataset_100.csv")

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)
```

Also make sure `flask` is in your **`requirements.txt`**:
```
flask
playwright
pandas
