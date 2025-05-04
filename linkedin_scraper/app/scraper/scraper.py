# app/scraper/scraper.py

import os
import time
import json
import random
import re

from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, ElementClickInterceptedException, NoSuchElementException, JavascriptException

from .driver import get_driver
from .redis_store import redis_store
from .job_parser import parse_job_details
from .utils import extract_job_id
from kafka_utils.producer import create_topic, produce_transaction

DATA_FILE = os.path.join("data", "linkedin_jobs.json")
topic = create_topic("job_records")

DATE_FILTERS = {
    "any": "",
    "past_month": "r2592000",
    "past_week": "r604800",
    "past_24_hours": "r86400"
}


def close_modal_if_exists(driver):
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
        except JavascriptException:
            dismiss_button.click()
            print("[✅] Modal closed using normal click.")
    except TimeoutException:
        print("[⚠️] Dismiss button not visible, skipping...")


def scroll_and_load_jobs(driver, max_scrolls=5):
    for i in range(max_scrolls):
        print(f"[Scroll] Attempt {i+1}/{max_scrolls} → scrolling...")
        driver.find_element(By.TAG_NAME, 'body').send_keys(Keys.END)
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


def scroll_until_target_jobs(driver, target_job_count, max_scroll_attempts=150, stagnant_threshold=3):
    scroll_attempts = 0
    stagnant_scrolls = 0
    last_count = 0
    while scroll_attempts < max_scroll_attempts:
        try:
            for _ in range(3):
                see_more_button = driver.find_element(By.XPATH, "//button[@aria-label='See more jobs']")
                if see_more_button.is_displayed():
                    driver.execute_script("arguments[0].click();", see_more_button)
                    time.sleep(3)
        except:
            pass
        driver.find_element(By.TAG_NAME, "body").send_keys(Keys.END)
        time.sleep(random.uniform(2, 3))
        job_elements = driver.find_elements(By.CLASS_NAME, "base-card__full-link")
        current_count = len(job_elements)
        print(f"[Scroll] Jobs loaded: {current_count}")
        if current_count >= target_job_count:
            print(f"[Scroll] Reached target of {target_job_count} jobs.")
            break
        stagnant_scrolls = stagnant_scrolls + 1 if current_count == last_count else 0
        if stagnant_scrolls >= stagnant_threshold:
            print("[Scroll] No new jobs after multiple scrolls. Stopping early.")
            break
        last_count = current_count
        scroll_attempts += 1
    return job_elements


def scrape_linkedin_jobs(max_jobs=10, title="Data Engineer", location="Canada", use_redis=True, max_scrolls=10, date_filter="past_week", max_posted_days=None):
    if date_filter not in DATE_FILTERS:
        raise ValueError(f"Invalid date_filter '{date_filter}'. Valid options: {list(DATE_FILTERS.keys())}")
    date_code = DATE_FILTERS[date_filter]
    url_template = f"https://www.linkedin.com/jobs/search?keywords={title}&location={location}"
    if date_code:
        url_template += f"&f_TPR={date_code}"

    print(f"\n[Scraper] Starting scrape: '{title}' in '{location}' | Date filter: '{date_filter}' | Max Days: {max_posted_days or 'Any'}")
    new_jobs = []
    existing_data = []
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            try:
                existing_data = json.load(f)
            except json.JSONDecodeError:
                existing_data = []

    driver = get_driver()
    wait = WebDriverWait(driver, 10)

    url = url_template
    driver.get(url)
    time.sleep(5)
    close_modal_if_exists(driver)
    scroll_and_load_jobs(driver, max_scrolls=max_scrolls)

    try:
        job_count_element = driver.find_element(By.CLASS_NAME, 'results-context-header__job-count')
        n_jobs_estimate = int(''.join(filter(str.isdigit, job_count_element.text)))
        print(f"[Init] Found total {n_jobs_estimate} jobs.")
    except:
        n_jobs_estimate = 300
        print(f"[Init] Could not read total job count, assuming {n_jobs_estimate}.")

    job_elements = scroll_until_target_jobs(driver, target_job_count=max_jobs)

    if not job_elements or len(job_elements) == 0:
        print("[❌] No jobs loaded after scrolling. Ending scrape.")
        driver.quit()
        return []

    print(f"✅ Parsing {len(job_elements)} jobs...")

    for idx, job in enumerate(job_elements):
        if len(new_jobs) >= max_jobs:
            break
        job_url = job.get_attribute("href")
        job_id = extract_job_id(job_url)
        if use_redis and redis_store.is_job_id_seen(job_id):
            print(f"[Skip] Already seen job ID: {job_id}")
            continue
        try:
            print(f"[Process] {idx}: {job_id}")
            driver.execute_script("arguments[0].scrollIntoView(true);", job)
            driver.execute_script("arguments[0].click();", job)
            wait.until(EC.presence_of_element_located((By.XPATH, "//h2")))
            time.sleep(random.uniform(2, 4))
            job_data = parse_job_details(driver, job_url)
            if not job_data:
                print(f"[❌] Failed to parse job {idx}")
                continue
            if use_redis:
                redis_store.add_job_id(job_id)
            new_jobs.append(job_data)
            produce_transaction(job_data)
            print(f"[✅] Captured: {job_data['job_title']} at {job_data['company_name']}")
            if use_redis:
                redis_store.mark_job_as_scraped(job_id)
        except Exception as e:
            print(f"[❌] Error job {idx} ({job_id}): {e}")
            continue

    driver.quit()
    final_jobs = existing_data + new_jobs
    os.makedirs("data", exist_ok=True)
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(final_jobs, f, ensure_ascii=False, indent=2)
    print(f"\n🎉 Done. Added {len(new_jobs)} new jobs. Total: {len(final_jobs)}.")
    return new_jobs
