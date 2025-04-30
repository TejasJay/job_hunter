import time
import argparse
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

from app.scraper.driver import get_driver
from app.scraper.utils import extract_job_id
from app.scraper.redis_store import redis_store

SCROLL_PAUSE_TIME = 2

DATE_FILTERS = {
    "any": "",
    "past_month": "r2592000",
    "past_week": "r604800",
    "past_24_hours": "r86400"
}


def parse_posted_days(posted_text):
    text = posted_text.lower()

    if "today" in text or "just now" in text:
        return 0
    if "minute" in text:
        return round(1 / 24, 2)
    if "hour" in text:
        digits = ''.join(filter(str.isdigit, text))
        return round(int(digits) / 24, 2) if digits else 999
    if "day" in text:
        digits = ''.join(filter(str.isdigit, text))
        return int(digits) if digits else 999
    if "week" in text:
        digits = ''.join(filter(str.isdigit, text))
        return int(digits) * 7 if digits else 999
    if "month" in text:
        digits = ''.join(filter(str.isdigit, text))
        return int(digits) * 30 if digits else 999

    return 999


def scroll_and_click_see_more(driver, n_jobs_estimate):
    scroll_iteration = 2
    no_button_attempts = 0
    max_iterations = int((n_jobs_estimate + 200) / 25) + 1

    while scroll_iteration <= max_iterations:
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(SCROLL_PAUSE_TIME)

        try:
            see_more_button = driver.find_element(By.XPATH, "//button[@aria-label='See more jobs']")
            if see_more_button.is_displayed():
                driver.execute_script("arguments[0].click();", see_more_button)
                time.sleep(3)
                no_button_attempts = 0
        except:
            no_button_attempts += 1
            time.sleep(2)
            if no_button_attempts >= 2:
                break
        scroll_iteration += 1

    print("[Monitor] Finished scrolling and loading all jobs.")


def process_job_item(job_item, max_posted_days):
    try:
        job_div = job_item.find_element(By.CLASS_NAME, "base-card")
        data_entity_urn = job_div.get_attribute("data-entity-urn")
        if not data_entity_urn or "jobPosting:" not in data_entity_urn:
            return None, "no_job_id"

        job_id = data_entity_urn.split("jobPosting:")[-1].strip()

        try:
            job_url_element = job_div.find_element(By.XPATH, ".//a[contains(@href, '/jobs/view/')]")
            job_url = job_url_element.get_attribute("href")
        except:
            return None, "no_url"

        try:
            posted_time_element = job_div.find_element(By.XPATH, ".//*[contains(@class, 'listdate') or contains(text(), 'ago')]")
            posted_text = posted_time_element.text.strip()
            posted_days = parse_posted_days(posted_text)
        except:
            posted_days = 999

        if max_posted_days is not None and posted_days > max_posted_days:
            return None, "too_old"

        return {
            "job_id": job_id,
            "job_url": job_url
        }, None

    except Exception as e:
        print(f"[Monitor] Error processing job item: {e}")
        return None, "exception"


def monitor_linkedin_jobs(title="Data Engineer", location="Canada", date_filter="past_week", max_posted_days=None):
    if date_filter not in DATE_FILTERS:
        raise ValueError(f"Invalid date_filter '{date_filter}'. Valid options are: {list(DATE_FILTERS.keys())}")

    print(f"\n[Monitor] Monitoring '{title}' jobs in '{location}' | Filter: '{date_filter}' | Max Days: {max_posted_days or 'Any'}")

    driver = get_driver()
    wait = WebDriverWait(driver, 10)

    try:
        base_url = f"https://www.linkedin.com/jobs/search?keywords={title}&location={location}"
        date_code = DATE_FILTERS[date_filter]
        if date_code:
            base_url += f"&f_TPR={date_code}"

        driver.get(base_url)
        wait.until(EC.presence_of_element_located((By.CLASS_NAME, 'results-context-header__job-count')))
        time.sleep(2)

        try:
            job_count_element = driver.find_element(By.CLASS_NAME, 'results-context-header__job-count')
            job_count_text = job_count_element.text
            n_jobs_estimate = int(''.join(filter(str.isdigit, job_count_text)))
            print(f"[Monitor] Found {n_jobs_estimate} total jobs listed.")
        except Exception as e:
            print(f"[Monitor] Could not determine total job count: {e}")
            n_jobs_estimate = 300

        scroll_and_click_see_more(driver, n_jobs_estimate)

        try:
            container = driver.find_element(By.XPATH, "//ul[contains(@class, 'jobs-search__results-list') or @role='list']")
            job_items = container.find_elements(By.TAG_NAME, "li")
        except Exception as e:
            print(f"[Monitor] Failed to find job container: {e}")
            return

        print(f"[Monitor] Found {len(job_items)} jobs after scrolling.")

        total_jobs = len(job_items)
        skipped = {
            "no_job_id": 0,
            "no_url": 0,
            "too_old": 0,
            "exception": 0
        }
        accepted_jobs = 0

        for job_item in job_items:
            result, skip_reason = process_job_item(job_item, max_posted_days)

            if skip_reason:
                skipped[skip_reason] += 1
                continue

            job_id = result["job_id"]
            job_url = result["job_url"]

            if redis_store.is_job_id_scraped(job_id):
                print(f"[Monitor] Already scraped {job_id}, skipping...")
                continue
            elif redis_store.is_job_id_seen(job_id):
                print(f"[Monitor] Seen before but not scraped, adding to update queue: {job_id}")
                redis_store.add_to_pending_update_jobs(job_id, job_url)
            else:
                print(f"[Monitor] New job detected, adding to new scrape queue: {job_id}")
                redis_store.add_to_pending_new_jobs(job_id, job_url)
                redis_store.add_job_id(job_id)

            accepted_jobs += 1

        # Summary
        print("\n[Summary] --------------------------------------------------")
        print(f"Total Jobs Found           : {total_jobs}")
        print(f"Jobs Accepted              : {accepted_jobs}")
        for k, v in skipped.items():
            print(f"Skipped - {k.replace('_', ' ').title():<22}: {v}")
        print("-----------------------------------------------------------\n")

    except Exception as e:
        print(f"[Monitor] Error during monitoring: {e}")

    finally:
        driver.quit()
        print("[Monitor] Done scraping. Exiting process.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--title", type=str, required=True)
    parser.add_argument("--location", type=str, required=True)
    parser.add_argument("--max_posted_days", type=float, default=None)
    parser.add_argument("--date_filter", type=str, default="past_week")
    args = parser.parse_args()

    monitor_linkedin_jobs(
        title=args.title,
        location=args.location,
        date_filter=args.date_filter,
        max_posted_days=args.max_posted_days
    )
