import os
import time
import json
import random
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

from .driver import get_driver
from .redis_store import redis_store
from .job_parser import parse_job_details
from .utils import extract_job_id
from kafka_utils.producer import create_topic, produce_transaction

topic = create_topic("job_records")

DATA_FILE = os.path.join("data", "linkedin_jobs.json")


def scroll_and_click_see_more(driver):
    """
    Scrolls down the LinkedIn jobs page and clicks the 'See more jobs' button if present.
    """
    try:
        see_more_button = driver.find_element(By.XPATH, "//button[@aria-label='See more jobs']")
        if see_more_button.is_displayed():
            driver.execute_script("arguments[0].click();", see_more_button)
            time.sleep(3)
            return True
    except:
        pass

    driver.find_element(By.TAG_NAME, "body").send_keys(Keys.END)
    time.sleep(random.uniform(2, 3))
    return False


def scrape_linkedin_jobs(max_jobs=10, title="Data Engineer", location="Canada", use_redis=True):
    new_jobs = []

    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            try:
                existing_data = json.load(f)
            except json.JSONDecodeError:
                existing_data = []
    else:
        existing_data = []

    driver = get_driver()
    wait = WebDriverWait(driver, 10)

    url = f"https://www.linkedin.com/jobs/search?keywords={title}&location={location}&position=1&pageNum=0"
    driver.get(url)
    time.sleep(5)

    scroll_attempts = 0
    max_scroll_attempts = 150
    last_seen_count = 0
    stagnant_scrolls = 0

    while len(new_jobs) < max_jobs and scroll_attempts < max_scroll_attempts:
        job_elements = driver.find_elements(By.CLASS_NAME, "base-card__full-link")
        print(f"🔍 Found {len(job_elements)} job elements")

        if not job_elements:
            print("No job cards found. Dumping HTML to debug...")
            with open("debug_linkedin_jobs.html", "w", encoding="utf-8") as f:
                f.write(driver.page_source)
            break

        for idx, job in enumerate(job_elements):
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
                driver.execute_script("arguments[0].click();", job)
                wait.until(EC.presence_of_element_located((By.XPATH, "//h2")))
                time.sleep(random.uniform(2, 4))

                job_data = parse_job_details(driver, job_url)
                if not job_data:
                    print(f"Failed to parse job index {idx}")
                    continue

                if use_redis:
                    redis_store.add_job_id(job_id)

                new_jobs.append(job_data)
                produce_transaction(job_data)
                print("------------------------------------------------")
                print(f"Captured: {job_data['job_title']} at {job_data['company_name']}")
                print("------------------------------------------------")

                if use_redis:
                    redis_store.mark_job_as_scraped(job_id)

                if len(new_jobs) >= max_jobs:
                    break

            except Exception as e:
                print(f"Failed to process job index {idx}: {e}")
                continue

        if len(new_jobs) >= max_jobs:
            break

        scroll_and_click_see_more(driver)
        scroll_attempts += 1

        # Optional: detect stagnation in job discovery
        current_count = len(job_elements)
        if current_count == last_seen_count:
            stagnant_scrolls += 1
        else:
            stagnant_scrolls = 0
        last_seen_count = current_count

        if stagnant_scrolls >= 3:
            print("[Scroll] No new jobs loaded after multiple attempts. Exiting scroll loop early.")
            break

    driver.quit()

    final_jobs = existing_data + new_jobs
    os.makedirs("data", exist_ok=True)
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(final_jobs, f, ensure_ascii=False, indent=2)

    print(f"\nScraping complete. Added {len(new_jobs)} new job(s). Total now: {len(final_jobs)}.")
    return new_jobs



#