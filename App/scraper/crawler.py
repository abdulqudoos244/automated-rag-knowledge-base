import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
import json
import os
import time


BASE_URL = "https://www.aysonline.pk"
START_URL = "https://www.aysonline.pk/shop/"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/151.0.0.0 Safari/537.36"
    )
}

REQUEST_DELAY = 1


# =========================================
# GET PAGE
# =========================================

def get_page(url):

    try:

        response = requests.get(
            url,
            headers=HEADERS,
            timeout=20
        )

        print(
            f"Status: {response.status_code} | {url}"
        )

        response.raise_for_status()

        return BeautifulSoup(
            response.text,
            "html.parser"
        )

    except requests.RequestException as e:

        print(
            f"ERROR loading {url}: {e}"
        )

        return None


# =========================================
# NORMALIZE URL
# =========================================

def normalize_url(url):

    parsed = urlparse(url)

    clean_url = parsed._replace(
        query="",
        fragment=""
    ).geturl()

    return clean_url.rstrip("/")


# =========================================
# SAME DOMAIN
# =========================================

def is_same_domain(url):

    domain = urlparse(url).netloc.lower()

    return domain in (
        "",
        "aysonline.pk",
        "www.aysonline.pk"
    )


# =========================================
# IGNORE URL
# =========================================

def is_ignored_url(url):

    path = urlparse(url).path.lower()

    ignored = [

        "/cart",
        "/checkout",
        "/my-account",
        "/wishlist",
        "/compare",
        "/blog",
        "/contact",
        "/about",
        "/privacy-policy",
        "/terms-and-conditions",
        "/shipping-policy",
        "/refund-policy",
        "/return-policy",
        "/wp-admin",
        "/wp-login"
    ]

    for item in ignored:

        if path == item or path.startswith(item + "/"):

            return True

    return False


# =========================================
# PRODUCT URL
# =========================================

def is_product_url(url):

    url = normalize_url(url)

    if not is_same_domain(url):
        return False

    if is_ignored_url(url):
        return False

    path = urlparse(url).path.strip("/").lower()

    if not path:
        return False

    # Known archive/category paths
    archive_words = [

        "shop",
        "category",
        "product-category",
        "tag",
        "author",
        "page",
        "air-conditioner",
        "refrigerator",
        "washing-machine",
        "led-tv",
        "home-theater",
        "freezer",
        "air-cooler"
    ]

    # Exact category/archive detection
    if path in archive_words:
        return False

    # Category pagination
    if "/page/" in "/" + path + "/":
        return False

    # Product pages on AYS generally have
    # a single slug after the domain.
    if path.count("/") != 0:
        return False

    # Avoid very short slugs
    if len(path) < 8:
        return False

    # Avoid obvious archive names
    archive_patterns = [

        "air-conditioners",
        "air-conditioner",
        "refrigerators",
        "refrigerator",
        "washing-machines",
        "washing-machine",
        "led-tvs",
        "led-tv",
        "freezers",
        "freezer",
        "air-coolers",
        "air-cooler",
        "home-theater",
        "home-theaters"
    ]

    for pattern in archive_patterns:

        if path == pattern:
            return False

    return True


# =========================================
# FIND PRODUCT LINKS
# =========================================

def find_product_urls(soup):

    products = set()

    selectors = [

        "li.product a[href]",
        ".product a[href]",
        ".woocommerce-loop-product__link[href]",
        "a.woocommerce-LoopProduct-link[href]"
    ]

    for selector in selectors:

        for link in soup.select(selector):

            href = link.get("href")

            if not href:
                continue

            full_url = normalize_url(
                urljoin(BASE_URL, href)
            )

            if is_product_url(full_url):

                products.add(full_url)

    return products


# =========================================
# FIND ALL INTERNAL LINKS
# =========================================

def find_internal_links(soup):

    links = set()

    for link in soup.find_all("a", href=True):

        href = link.get("href")

        full_url = normalize_url(
            urljoin(BASE_URL, href)
        )

        if not is_same_domain(full_url):
            continue

        if is_ignored_url(full_url):
            continue

        links.add(full_url)

    return links


# =========================================
# FIND NEXT PAGE
# =========================================

def find_next_page(soup):

    selectors = [

        "a.next",
        "a.next.page-numbers",
        ".woocommerce-pagination a.next",
        "a[rel='next']"
    ]

    for selector in selectors:

        link = soup.select_one(selector)

        if link:

            href = link.get("href")

            if href:

                return normalize_url(
                    urljoin(BASE_URL, href)
                )

    return None


# =========================================
# CRAWL WEBSITE
# =========================================

def crawl_website():

    visited = set()

    product_urls = set()

    queue = []

    start_url = normalize_url(START_URL)

    queue.append(start_url)

    print()
    print("========================================")
    print("AYS ONLINE FULL WEBSITE CRAWLER")
    print("========================================")
    print()
    print("Starting URL:")
    print(start_url)
    print()

    while queue:

        current_url = queue.pop(0)

        current_url = normalize_url(current_url)

        if current_url in visited:
            continue

        visited.add(current_url)

        print()
        print("----------------------------------------")
        print(f"Pages visited: {len(visited)}")
        print(f"Queue size: {len(queue)}")
        print(f"Products found: {len(product_urls)}")
        print("----------------------------------------")
        print(current_url)

        soup = get_page(current_url)

        if not soup:

            continue

        # ---------------------------------
        # Find product URLs
        # ---------------------------------

        page_products = find_product_urls(soup)

        if page_products:

            before = len(product_urls)

            product_urls.update(page_products)

            new_products = (
                len(product_urls) - before
            )

            print(
                f"New products found: {new_products}"
            )

        # ---------------------------------
        # Find internal links
        # ---------------------------------

        internal_links = find_internal_links(soup)

        for link in internal_links:

            if link in visited:
                continue

            # Product URL
            if is_product_url(link):

                product_urls.add(link)

            # Other internal pages
            else:

                if link not in queue:

                    queue.append(link)

        # ---------------------------------
        # Pagination
        # ---------------------------------

        next_page = find_next_page(soup)

        if next_page:

            if next_page not in visited:

                if next_page not in queue:

                    queue.append(next_page)

        time.sleep(REQUEST_DELAY)

    return product_urls


# =========================================
# SAVE PRODUCTS
# =========================================

def save_product_urls(product_urls):

    os.makedirs(
        "data",
        exist_ok=True
    )

    file_path = "data/product_urls.json"

    product_urls = sorted(
        list(product_urls)
    )

    with open(
        file_path,
        "w",
        encoding="utf-8"
    ) as file:

        json.dump(
            product_urls,
            file,
            indent=4,
            ensure_ascii=False
        )

    print()
    print("========================================")
    print("PRODUCT URLS SAVED")
    print("========================================")
    print()
    print(
        f"Total products: {len(product_urls)}"
    )
    print(
        f"File: {file_path}"
    )


# =========================================
# MAIN
# =========================================

def main():

    product_urls = crawl_website()

    save_product_urls(
        product_urls
    )

    print()
    print("========================================")
    print("CRAWLER COMPLETED")
    print("========================================")
    print()
    print(
        f"Total unique products found: "
        f"{len(product_urls)}"
    )


if __name__ == "__main__":

    main()