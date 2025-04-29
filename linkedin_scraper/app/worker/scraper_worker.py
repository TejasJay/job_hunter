# app/worker/scraper_worker.py

import time
import random
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

from app.scraper.driver import get_driver
from app.scraper.job_parser import parse_job_details
from app.scraper.redis_store import redis_store
from kafka_utils.producer import produce_transaction

BATCH_SIZE = 30
BASE_SEARCH_URL = "https://www.linkedin.com/jobs/search?trk=content-hub-home-page_guest_nav_menu_jobs&currentJobId={}"
NEW_JOBS_TOPIC = "new_job_records"
MAX_RETRIES = 3

def scrape_jobs_from_pending_queue(batch_size=BATCH_SIZE):
    driver = get_driver()
    wait = WebDriverWait(driver, 10)

    print(f"[Worker] Fetching up to {batch_size} fresh pending jobs from Redis...")

    pending_jobs = redis_store.fetch_pending_new_jobs(batch_size)

    if not pending_jobs:
        print("[Worker] No pending new jobs found. Sleeping...")
        driver.quit()
        time.sleep(60)
        return

    print(f"[Worker] Found {len(pending_jobs)} new jobs to scrape.")

    for job_info in pending_jobs:
        job_id = job_info.get('job_id')
        job_url = job_info.get('job_url')

        if not job_id or not job_url:
            print("[Worker] Skipping invalid job entry (missing job_id or job_url)")
            continue

        # Skip if already scraped
        if redis_store.is_job_id_scraped(job_id):
            print(f"[Worker] Already scraped {job_id}. Skipping...")
            continue

        attempt = 0
        success = False

        while attempt < MAX_RETRIES:
            try:
                search_url = BASE_SEARCH_URL.format(job_id)
                print(f"[Worker] Navigating to {search_url} (Attempt {attempt + 1})")

                driver.get(search_url)
                wait.until(EC.presence_of_element_located((By.XPATH, "//h2")))
                time.sleep(random.uniform(2, 4))

                job_data = parse_job_details(driver, search_url, known_job_id=job_id)

                if job_data:
                    print(f"[Worker] Successfully scraped: {job_data['job_title']} at {job_data['company_name']}")
                    produce_transaction(job_data, topic_name=NEW_JOBS_TOPIC)
                    redis_store.mark_job_as_scraped(job_id)
                    redis_store.add_job_id(job_id)  # Global "seen" set
                    success = True
                    break  # Exit retry loop
                else:
                    print(f"[Worker] Failed to parse job details for {job_id}, retrying...")

            except Exception as e:
                print(f"[Worker] Error scraping job {job_id}: {e}. Retrying...")

            attempt += 1
            time.sleep(random.uniform(2, 5))  # Small backoff before retrying

        if not success:
            print(f"[Worker] Failed to scrape job {job_id} after {MAX_RETRIES} attempts. Moving on.")

    driver.quit()
    print(f"[Worker] Finished scraping batch of {len(pending_jobs)} jobs.\n")

if __name__ == "__main__":
    while True:
        scrape_jobs_from_pending_queue()
