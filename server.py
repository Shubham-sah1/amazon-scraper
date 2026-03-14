
from playwright.sync_api import sync_playwright
import pandas as pd
import time
from datetime import datetime
import re


def clean(text):
    if not text:
        return ""
    cleaned = re.sub(r'[\u200e\u200f\u200b\u202a\u202b\u202c\u202d\u202e\ufeff\u00ad]', '', text)
    cleaned = re.sub(r'\s+', ' ', cleaned).strip()
    return cleaned


def to_ddmmyyyy(raw):
    raw = clean(raw)
    if not raw:
        return ""
    formats = ["%B %d, %Y", "%B %Y", "%d %B %Y", "%Y-%m-%d", "%m/%d/%Y"]
    for fmt in formats:
        try:
            return datetime.strptime(raw.strip(), fmt).strftime("%d-%m-%Y")
        except ValueError:
            pass
    return raw


def get_book_details(page, url):
    data = {"Description": "", "Publisher": "", "Publication Date": ""}
    try:
        page.goto(url, wait_until="domcontentloaded", timeout=45000)
        page.wait_for_timeout(3000)

        for sel in [
            "#bookDescription_feature_div .a-expander-content",
            "#bookDescription_feature_div noscript",
            "#bookDescription_feature_div",
            "#productDescription",
        ]:
            el = page.query_selector(sel)
            if el:
                t = clean(el.inner_text())
                if len(t) > 20:
                    data["Description"] = t
                    break

        bullet_lis = page.query_selector_all(
            "#detailBullets_feature_div li, "
            "#detailBulletsWrapper_feature_div li"
        )
        for li in bullet_lis:
            raw = clean(li.inner_text())

            if not data["Publisher"] and re.search(r'\bPublisher\b', raw, re.IGNORECASE):
                if ":" in raw:
                    value = clean(raw.split(":", 1)[1])
                    m = re.match(r'^(.*?)\((.+?)\)\s*$', value)
                    if m:
                        data["Publisher"] = clean(m.group(1))
                        data["Publication Date"] = to_ddmmyyyy(m.group(2))
                    else:
                        data["Publisher"] = value

            if not data["Publication Date"] and re.search(r'Publication date', raw, re.IGNORECASE):
                if ":" in raw:
                    value = clean(raw.split(":", 1)[1])
                    data["Publication Date"] = to_ddmmyyyy(value)

            if data["Publisher"] and data["Publication Date"]:
                break

        if not data["Publisher"] or not data["Publication Date"]:
            rows = page.query_selector_all("#productDetailsTable tr")
            for row in rows:
                raw = clean(row.inner_text())
                if not data["Publisher"] and "Publisher" in raw and ":" in raw:
                    value = clean(raw.split(":", 1)[1])
                    m = re.match(r'^(.*?)\((.+?)\)\s*$', value)
                    if m:
                        data["Publisher"] = clean(m.group(1))
                        if not data["Publication Date"]:
                            data["Publication Date"] = to_ddmmyyyy(m.group(2))
                    else:
                        data["Publisher"] = value
                if not data["Publication Date"] and "Publication date" in raw and ":" in raw:
                    data["Publication Date"] = to_ddmmyyyy(raw.split(":", 1)[1])

    except Exception as e:
        print("Warning: " + url + " " + str(e))

    return data


LISTING_PAGES = [
    "https://www.amazon.com/Best-Sellers-Kindle-Store-Paranormal-Romance/zgbs/digital-text/6190484011/ref=zg_bs_pg_1?_encoding=UTF8&pg=1",
    "https://www.amazon.com/Best-Sellers-Kindle-Store-Paranormal-Romance/zgbs/digital-text/6190484011/ref=zg_bs_pg_2?_encoding=UTF8&pg=2",
]

books = []

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False)
    context = browser.new_context(
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        viewport={"width": 1366, "height": 768},
        locale="en-US",
    )
    page = context.new_page()

    counter = 1

    for page_num, pg_url in enumerate(LISTING_PAGES, 1):
        print("Listing page " + str(page_num) + "/2 ...")
        page.goto(pg_url, wait_until="domcontentloaded")
        page.wait_for_timeout(6000)

        page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        page.wait_for_timeout(2000)
        page.evaluate("window.scrollTo(0, 0)")
        page.wait_for_timeout(1000)

        items = page.query_selector_all(".zg-item-immersion, .zg-grid-general-faceout, [id^='zg-item']")
        print("Items found: " + str(len(items)))

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
                    if href.startswith("http"):
                        book_url = href.split("?")[0]
                    else:
                        book_url = "https://www.amazon.com" + href.split("?")[0]

            author = ""
            for a_sel in [".a-size-small.a-link-child", ".a-size-small.a-color-base", ".a-size-small a", ".a-row .a-size-small"]:
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
            if not reviews:
                for el in item.query_selector_all("span, a"):
                    t = clean(el.inner_text()).replace(",", "")
                    if t.isdigit() and int(t) > 0:
                        reviews = clean(el.inner_text())
                        break

            price = ""
            for p_sel in [".a-size-base.a-color-price", "._cDEzb_p13n-sc-price_3mJ9Z", ".p13n-sc-price", ".a-price .a-offscreen"]:
                el = item.query_selector(p_sel)
                if el:
                    price = clean(el.inner_text())
                    if price:
                        break

            books.append({
                "Rank": rank,
                "Title": title,
                "Author": author,
                "Rating": rating,
                "Reviews": reviews,
                "Price": price,
                "URL": book_url,
                "Description": "",
                "Publisher": "",
                "Publication Date": "",
            })

    print("Total books collected: " + str(len(books)))
    print("Now scraping individual book pages ...")

    for i, book in enumerate(books):
        if not book["URL"]:
            continue
        print("[" + str(i+1) + "/" + str(len(books)) + "] " + book["Title"][:70])
        details = get_book_details(page, book["URL"])
        book["Description"] = details["Description"]
        book["Publisher"] = details["Publisher"]
        book["Publication Date"] = details["Publication Date"]
        time.sleep(1.5)

    browser.close()

print("Scraping complete - " + str(len(books)) + " books")
df = pd.DataFrame(books, columns=["Rank", "Title", "Author", "Rating", "Reviews", "Price", "URL", "Description", "Publisher", "Publication Date"])
df.to_csv("amazon_books_dataset_100.csv", index=False, encoding="utf-8-sig")
print("Saved to amazon_books_dataset_100.csv")