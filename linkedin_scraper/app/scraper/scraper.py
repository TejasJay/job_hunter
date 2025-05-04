import os
import time
import json
import random

from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, ElementClickInterceptedException, NoSuchElementException, JavascriptException
import re
from .driver import get_driver
from .redis_store import redis_store
from .job_parser import parse_job_details
from .utils import extract_job_id
from kafka_utils.producer import create_topic, produce_transaction

# -- Constants --
DATA_FILE = os.path.join("data", "linkedin_jobs.json")
topic = create_topic("job_records")



def close_modal_if_exists(driver):
    """
    Closes the LinkedIn modal popup by clicking its dismiss button via JS or fallback force click.
    """
    dismiss_selector = "button.contextual-sign-in-modal__modal-dismiss"
    try:
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, dismiss_selector))
        )
        dismiss_button = driver.find_element(By.CSS_SELECTOR, dismiss_selector)

        print("[✅] Dismiss button found → trying JS click...")
        try:
            driver.execute_script("arguments[0].click();", dismiss_button)
            time.sleep(1)
            print("[✅] Modal closed using JS click.")
        except JavascriptException as e:
            print(f"[⚠️] JS click failed: {e}")
            try:
                dismiss_button.click()
                print("[✅] Modal closed using normal click.")
            except ElementClickInterceptedException as ex:
                print(f"[❌] Could not close modal: {ex}")

    except TimeoutException:
        print("[⚠️] Dismiss button not visible, skipping...")

def scroll_and_load_jobs(driver, max_scrolls=5):
    """
    Scrolls the page and clicks 'See more jobs' if present.
    """
    for i in range(max_scrolls):
        print(f"[Scroll] Attempt {i+1}/{max_scrolls} → scrolling...")
        body = driver.find_element(By.TAG_NAME, 'body')
        body.send_keys(Keys.END)
        time.sleep(2)

        try:
            see_more_button = driver.find_element(By.XPATH, "//button[@aria-label='See more jobs']")
            if see_more_button.is_displayed():
                print("[✅] 'See more jobs' button visible → clicking...")
                driver.execute_script("arguments[0].click();", see_more_button)
                time.sleep(3)
        except NoSuchElementException:
            print("[⚠️] 'See more jobs' button not found this time.")

    print("[✅] Done scrolling.")


def extract_job_id(job_url):
    """
    Extracts a 10-digit job ID from LinkedIn URL.
    """
    match = re.search(r'/view/[^/]+-(\d{10})', job_url)
    return match.group(1) if match else None


def extract_job_links(driver):
    """
    Collects job posting links and scrapes details from each full job page.
    """
    job_elements = driver.find_elements(By.CSS_SELECTOR, "a.base-card__full-link")
    print(f"[✅] Found {len(job_elements)} job links on the page.")

    job_links = [elem.get_attribute("href") for elem in job_elements]

    jobs = []
    for idx, href in enumerate(job_links):
        print(f"[{idx+1}/{len(job_links)}] Visiting job URL: {href}")

        try:
            driver.get(href)
            WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.TAG_NAME, "h1"))
            )
            time.sleep(2)  # let page stabilize

            job_id = extract_job_id(href)
            job = parse_job_details(driver, href, known_job_id=job_id)
            jobs.append(job)

        except Exception as e:
            print(f"[⚠️] Failed to scrape {href}: {e}")

    return jobs


def scroll_until_target_jobs(driver, target_job_count, max_scroll_attempts=150, stagnant_threshold=3):
    """
    Scrolls the LinkedIn jobs page until at least `target_job_count` jobs are loaded,
    or scrolling stagnates, or max scroll attempts reached.

    Args:
        driver: Selenium WebDriver instance
        target_job_count: number of job cards we want loaded
        max_scroll_attempts: maximum scroll actions
        stagnant_threshold: stop if no new jobs for N scrolls

    Returns:
        list of job element WebElements
    """
    scroll_attempts = 0
    stagnant_scrolls = 0
    last_count = 0

    while scroll_attempts < max_scroll_attempts:
        # Try clicking 'See more jobs' if visible
        try:
            for i in range(3):
                see_more_button = driver.find_element(By.XPATH, "//button[@aria-label='See more jobs']")
                if see_more_button.is_displayed():
                    driver.execute_script("arguments[0].click();", see_more_button)
                    time.sleep(3)
        except:
            pass

        # Scroll to bottom
        driver.find_element(By.TAG_NAME, "body").send_keys(Keys.END)
        time.sleep(random.uniform(2, 3))

        # Count loaded job elements
        job_elements = driver.find_elements(By.CLASS_NAME, "base-card__full-link")
        current_count = len(job_elements)
        print(f"[Scroll] Jobs loaded: {current_count}")

        # Stop if enough jobs loaded
        if current_count >= target_job_count:
            print(f"[Scroll] Reached target of {target_job_count} jobs.")
            break

        # Stop if no new jobs after several scrolls
        if current_count == last_count:
            stagnant_scrolls += 1
        else:
            stagnant_scrolls = 0

        if stagnant_scrolls >= stagnant_threshold:
            print("[Scroll] No new jobs after multiple scrolls. Stopping early.")
            break

        last_count = current_count
        scroll_attempts += 1

    return job_elements


def scrape_linkedin_jobs(max_jobs=10, title="Data Engineer", location="Canada", use_redis=True, max_scrolls=10):
    """
    Scrapes LinkedIn job postings, scrolls until enough jobs loaded.

    Args:
        max_jobs: number of jobs to scrape
        title: job title keyword
        location: job location
        use_redis: deduplicate using Redis

    Returns:
        list of scraped job dictionaries
    """
    new_jobs = []
    existing_data = []

    # Load existing jobs from JSON
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            try:
                existing_data = json.load(f)
            except json.JSONDecodeError:
                existing_data = []

    driver = get_driver()
    wait = WebDriverWait(driver, 10)

    url_template = f"https://www.linkedin.com/jobs/search?keywords={title}&location={location}&start={{}}"
    start_offset = 0
    jobs_loaded = 0

    while len(new_jobs) < max_jobs:
        url = url_template.format(start_offset)
        driver.get(url)
        time.sleep(5)
        close_modal_if_exists(driver)
        scroll_and_load_jobs(driver, max_scrolls=max_scrolls)

        # Get estimated total jobs
        try:
            job_count_element = driver.find_element(By.CLASS_NAME, 'results-context-header__job-count')
            n_jobs_estimate = int(''.join(filter(str.isdigit, job_count_element.text)))
            print(f"[Init] Found total {n_jobs_estimate} jobs according to page.")
        except:
            n_jobs_estimate = 300
            print(f"[Init] Could not read total job count, assuming {n_jobs_estimate}.")

        job_elements = scroll_until_target_jobs(driver, target_job_count=max_jobs)

        if not job_elements or len(job_elements) == 0:
            print("[Page] No jobs loaded on this page, trying next page...")
            start_offset += 25
            continue

        print(f"✅ Starting parse of {len(job_elements)} jobs...")

        for idx, job in enumerate(job_elements):
            if len(new_jobs) >= max_jobs:
                break

            job_url = job.get_attribute("href")
            job_id = extract_job_id(job_url)

            if use_redis and redis_store.is_job_id_seen(job_id):
                print("************************************************")
                print(f"Skipping already seen job ID: {job_id}")
                print("************************************************")
                continue

            try:
                print("------------------------------------------------")
                print(f"Processing job index {idx}: {job_id}")
                print("------------------------------------------------")

                driver.execute_script("arguments[0].scrollIntoView(true);", job)
                driver.execute_script("arguments[0].click();", job)

                wait.until(EC.presence_of_element_located((By.XPATH, "//h2")))
                time.sleep(random.uniform(2, 4))

                job_data = parse_job_details(driver, job_url)
                if not job_data:
                    print(f"❌ Failed to parse job index {idx}")
                    continue

                if use_redis:
                    redis_store.add_job_id(job_id)

                new_jobs.append(job_data)
                produce_transaction(job_data)
                print(f"✅ Captured: {job_data['job_title']} at {job_data['company_name']}")

                if use_redis:
                    redis_store.mark_job_as_scraped(job_id)

            except Exception as e:
                print(f"❌ Error processing job {idx} ({job_id}): {e}")
                continue

        # If not enough jobs scraped yet → go to next page
        if len(new_jobs) < max_jobs:
            start_offset += 25
            print(f"[Page] Moving to next page (start={start_offset}) to load more jobs...")

    driver.quit()

    final_jobs = existing_data + new_jobs
    os.makedirs("data", exist_ok=True)
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(final_jobs, f, ensure_ascii=False, indent=2)

    print(f"\n🎉 Scraping complete. Added {len(new_jobs)} new jobs. Total: {len(final_jobs)}.")
    return new_jobs
