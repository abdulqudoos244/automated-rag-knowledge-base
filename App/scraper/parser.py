import re
import requests
import json
import os
import time
from bs4 import BeautifulSoup


INPUT_FILE = "data/product_urls.json"
OUTPUT_FILE = "data/products.json"
FAILED_FILE = "data/failed_urls.json"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) "
                  "Chrome/151.0.0.0 Safari/537.36"
}

MAX_RETRIES = 3
RETRY_DELAY = 3


def extract_product(url):

    response = None

    # --------------------------------
    # Retry system
    # --------------------------------

    for attempt in range(1, MAX_RETRIES + 1):

        try:

            response = requests.get(
                url,
                headers=HEADERS,
                timeout=20
            )

            response.raise_for_status()
            break

        except requests.RequestException as e:

            print(
                f"Attempt {attempt}/{MAX_RETRIES} failed: {e}"
            )

            if attempt < MAX_RETRIES:
                print("Retrying...")
                time.sleep(RETRY_DELAY)

            else:
                raise e

    # --------------------------------
    # Parse HTML
    # --------------------------------

    soup = BeautifulSoup(
        response.text,
        "html.parser"
    )

    # --------------------------------
    # Product Name
    # --------------------------------

    title = soup.find("h1")

    product_name = (
        title.get_text(" ", strip=True)
        if title
        else None
    )

    # --------------------------------
    # Product Image
    # --------------------------------

    image = soup.select_one(
        ".woocommerce-product-gallery__image img"
    )

    image_url = None

    if image:

        image_url = (
            image.get("data-src")
            or image.get("src")
            or image.get("data-large_image")
        )

    # --------------------------------
    # Price
    # --------------------------------

    price = None

    # Try WooCommerce price first

    price_element = soup.select_one(
        ".summary .price"
    )

    if price_element:

        price_text = price_element.get_text(
            " ",
            strip=True
        )
        price_text = re.sub(r"\s+", " ", price_text)

        numbers = re.findall(
            r"[\d,]+",
            price_text
        )

        if numbers:
            price = numbers[0].replace(",", "")

    # --------------------------------
    # Price History
    # --------------------------------

    low_price = None
    high_price = None

    price_history = soup.select_one(
        ".ays-ph-summary"
    )

    if price_history:

        text = price_history.get_text(
            " ",
            strip=True
        )
        # Collapse any internal line-breaks/extra whitespace so the
        # regex patterns below match regardless of how the source
        # HTML happens to wrap this text across lines.
        text = re.sub(r"\s+", " ", text)

        # Current price

        match = re.search(
            r"current price is Rs\.?\s*([\d,]+)",
            text,
            re.IGNORECASE
        )

        if match:
            price = match.group(1).replace(
                ",",
                ""
            )

        # Lowest price

        low_match = re.search(
            r"recorded low of Rs\.?\s*([\d,]+)",
            text,
            re.IGNORECASE
        )

        if low_match:

            low_price = low_match.group(1).replace(
                ",",
                ""
            )

        # Highest price

        high_match = re.search(
            r"high of Rs\.?\s*([\d,]+)",
            text,
            re.IGNORECASE
        )

        if high_match:

            high_price = high_match.group(1).replace(
                ",",
                ""
            )

    # --------------------------------
    # Product Description
    # --------------------------------

    description_text = ""

    descriptions = soup.select(
        ".woocommerce-product-details__short-description, "
        ".woocommerce-Tabs-panel--description"
    )

    for description in descriptions:

        text = description.get_text(
            " ",
            strip=True
        )

        if text:

            description_text = text
            break

    # --------------------------------
    # Product Specifications
    # --------------------------------

    specifications = {}

    tables = soup.select(
        ".woocommerce-product-attributes"
    )

    for table in tables:

        rows = table.select("tr")

        for row in rows:

            cells = row.select(
                "th, td"
            )

            if len(cells) >= 2:

                key = cells[0].get_text(
                    " ",
                    strip=True
                )

                value = cells[1].get_text(
                    " ",
                    strip=True
                )

                if key and value:

                    specifications[key] = value

    # --------------------------------
    # Product Data
    # --------------------------------

    product = {

        "name": product_name,

        "price": price,

        "price_low": low_price,

        "price_high": high_price,

        "description": description_text,

        "specifications": specifications,

        "image": image_url,

        "url": url
    }

    return product


# ==========================================
# MAIN
# ==========================================

if __name__ == "__main__":

    print()
    print("======================================")
    print("AYS ONLINE PRODUCT PARSER")
    print("======================================")

    # --------------------------------
    # Load URLs
    # --------------------------------

    if not os.path.exists(INPUT_FILE):

        print(
            f"ERROR: {INPUT_FILE} not found!"
        )

        exit()

    with open(
        INPUT_FILE,
        "r",
        encoding="utf-8"
    ) as file:

        product_urls = json.load(file)

    print(
        f"Product URLs loaded: {len(product_urls)}"
    )

    # --------------------------------
    # Remove invalid URLs
    # --------------------------------

    valid_urls = []

    for url in product_urls:

        if not isinstance(url, str):
            continue

        if not url.startswith(
            "https://www.aysonline.pk/"
        ):

            print(
                f"Skipping invalid URL: {url}"
            )

            continue

        # Skip obvious non-product pages

        blocked = [
            "/alternatives",
            "/cart",
            "/checkout",
            "/my-account",
            "/wishlist",
            "/compare",
            "/blog/"
        ]

        if any(
            item in url.lower()
            for item in blocked
        ):

            print(
                f"Skipping non-product URL: {url}"
            )

            continue

        valid_urls.append(url)

    # Remove duplicates

    valid_urls = list(
        dict.fromkeys(valid_urls)
    )

    print(
        f"Valid product URLs: {len(valid_urls)}"
    )

    # --------------------------------
    # Load existing products
    # --------------------------------

    products = []

    if os.path.exists(OUTPUT_FILE):

        try:

            with open(
                OUTPUT_FILE,
                "r",
                encoding="utf-8"
            ) as file:

                products = json.load(file)

            print(
                f"Existing products loaded: {len(products)}"
            )

        except Exception:

            print(
                "Could not load existing products."
            )

    # --------------------------------
    # Existing URLs
    # --------------------------------

    existing_urls = {
        product.get("url")
        for product in products
        if isinstance(product, dict)
    }

    # --------------------------------
    # Failed URLs
    # --------------------------------

    failed_urls = []

    # --------------------------------
    # Parse products
    # --------------------------------

    total = len(valid_urls)

    for index, url in enumerate(
        valid_urls,
        start=1
    ):

        print()
        print("--------------------------------------")
        print(
            f"Product {index}/{total}"
        )
        print("--------------------------------------")

        # Skip already scraped

        if url in existing_urls:

            print(
                "Already scraped. Skipping..."
            )

            continue

        print(
            f"Loading: {url}"
        )

        try:

            product = extract_product(url)

            # Make sure this is actually a product

            if not product["name"]:

                print(
                    "No product name found."
                )

                failed_urls.append(url)

                continue

            products.append(product)

            existing_urls.add(url)

            print(
                "Product scraped successfully!"
            )

            print(
                "Name:",
                product["name"]
            )

            print(
                "Price:",
                product["price"]
            )

            print(
                "Specifications:",
                len(product["specifications"])
            )

            # --------------------------------
            # Save immediately
            # --------------------------------

            os.makedirs(
                "data",
                exist_ok=True
            )

            with open(
                OUTPUT_FILE,
                "w",
                encoding="utf-8"
            ) as file:

                json.dump(
                    products,
                    file,
                    indent=4,
                    ensure_ascii=False
                )

        except Exception as e:

            print(
                f"ERROR: {e}"
            )

            print(
                "Skipping this product..."
            )

            failed_urls.append(url)

        # Small delay

        time.sleep(1)

    # --------------------------------
    # Save failed URLs
    # --------------------------------

    with open(
        FAILED_FILE,
        "w",
        encoding="utf-8"
    ) as file:

        json.dump(
            failed_urls,
            file,
            indent=4,
            ensure_ascii=False
        )

    # --------------------------------
    # Final Result
    # --------------------------------

    print()
    print("======================================")
    print("PARSING COMPLETED")
    print("======================================")

    print(
        f"Total URLs: {total}"
    )

    print(
        f"Products saved: {len(products)}"
    )

    print(
        f"Failed URLs: {len(failed_urls)}"
    )

    print()
    print(
        f"Products file: {OUTPUT_FILE}"
    )

    print(
        f"Failed URLs file: {FAILED_FILE}"
    )

    print()
    print("======================================")