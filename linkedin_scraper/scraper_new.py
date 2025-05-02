import time
from playwright.sync_api import sync_playwright
import re
from bs4 import BeautifulSoup
import os
from app.scraper.job_parser import parse_job_details
from app.scraper.driver import get_driver

title = "Data Engineer"
location = "Canada"

base_url = f"https://www.linkedin.com/jobs/search?keywords={title}&location={location}"


def close_modal_if_exists(page):
    """
    Closes the LinkedIn modal popup by clicking its dismiss button (via JS or fallback force click).
    """
    dismiss_selector = "button.contextual-sign-in-modal__modal-dismiss"

    try:
        # Wait for the dismiss button to be attached in DOM.
        page.wait_for_selector(dismiss_selector, timeout=10000, state="attached")
        dismiss_button = page.locator(dismiss_selector).first

        print("[✅] Dismiss button found in DOM → trying JS click...")
        # Try JavaScript click directly (avoiding visibility restriction)
        page.evaluate("(el) => el.click()", dismiss_button)

        time.sleep(1)  # allow modal to fade
        print("[✅] Modal closed using JS click.")

    except Exception as e:
        print(f"[⚠️] Dismiss button JS click failed: {e}")
        try:
            # Fallback → try force click
            dismiss_button.click(force=True)
            print("[✅] Modal closed using force click.")
        except Exception as ex:
            print(f"[❌] Could not close modal: {ex}")


def scroll_and_load_jobs(page, max_scrolls=5):
    """
    Scrolls the page multiple times and clicks 'See more jobs' if present.
    """
    for i in range(max_scrolls):
        print(f"[Scroll] Attempt {i+1}/{max_scrolls} → scrolling to bottom...")
        page.keyboard.press('End')
        time.sleep(2)

        try:
            see_more_button = page.locator("//button[@aria-label='See more jobs']")
            if see_more_button.is_visible():
                print("[✅] 'See more jobs' button visible → clicking...")
                see_more_button.click()
                time.sleep(3)
        except:
            print("[⚠️] 'See more jobs' button not found this time.")

    print("[✅] Done scrolling.")


def extract_job_id(job_url):
    """
    Extracts a 10-digit numeric job ID from a LinkedIn job URL.
    Returns None if not found.
    """
    match = re.search(r'/view/[^/]+-(\d{10})', job_url)
    if match:
        return match.group(1)
    else:
        return None


def extract_job_links(page):
    """
    Extracts job posting links from the loaded page.
    """
    job_links = page.locator("a.base-card__full-link")
    count = job_links.count()
    print(f"[✅] Found {count} job links on the page.")

    jobs = []
    for i in range(count):
        href = job_links.nth(i).get_attribute("href")
        job_id = extract_job_id(href)
        driver = get_driver()
        job = parse_job_details(driver, href, known_job_id=job_id)
        jobs.append(job)

    return jobs


def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)  # set headless=True if you don’t want browser window
        page = browser.new_page()

        print(f"[🌐] Navigating to {base_url}")
        page.goto(base_url)
        page.wait_for_timeout(5000)  # wait for page to load

        print("[✅] Page loaded:", page.title())

        # ✅ Close modal if it shows up
        close_modal_if_exists(page)

        # ✅ Scroll and click 'See more jobs'
        scroll_and_load_jobs(page, max_scrolls=2)

        # ✅ Extract job links
        job_urls = extract_job_links(page)

        print("\n[Results] ---------------------------")
        for idx, url in enumerate(job_urls):
            print(f"{idx+1}. {url}")
        print("------------------------------------")

        browser.close()


if __name__ == "__main__":
    main()