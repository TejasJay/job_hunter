import time
import re
import argparse
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from app.scraper.driver import get_driver
from app.scraper.utils import extract_job_id
from app.scraper.redis_store import redis_store

# Constants
SCROLL_PAUSE_TIME = 2
MAX_SCROLL_ITERATIONS = 100

DATE_FILTERS = {
    "any": "",
    "past_month": "r2592000",
    "past_week": "r604800",
    "past_24_hours": "r86400"
}

def parse_posted_days(posted_text):
    text = posted_text.lower()
    if "hour" in text:
        hours = int(''.join(filter(str.isdigit, text)))
        return round(hours / 24, 2)
    if "day" in text:
        return int(''.join(filter(str.isdigit, text)))
    if "week" in text:
        return int(''.join(filter(str.isdigit, text))) * 7
    if "month" in text:
        return int(''.join(filter(str.isdigit, text))) * 30
    return 999

def scroll_and_click_see_more(driver, n_jobs_estimate):
    i = 2
    no_button_attempts = 0
    while i <= int((n_jobs_estimate + 200) / 25) + 1:
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
        i += 1

    print("[Monitor] Finished scrolling and loading all jobs.")

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
        time.sleep(5)

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
            driver.quit()
            return

        print(f"[Monitor] Found {len(job_items)} jobs after scrolling.")

        total_jobs = len(job_items)
        skipped_no_jobid = 0
        skipped_no_url = 0
        skipped_too_old = 0
        accepted_jobs = 0

        for job_item in job_items:
            try:
                try:
                    job_div = job_item.find_element(By.CLASS_NAME, "base-card")
                except:
                    skipped_no_jobid += 1
                    continue

                data_entity_urn = job_div.get_attribute("data-entity-urn")
                if not data_entity_urn or "jobPosting:" not in data_entity_urn:
                    skipped_no_jobid += 1
                    continue

                job_id = data_entity_urn.split("jobPosting:")[-1].strip()

                try:
                    job_url_element = job_div.find_element(By.XPATH, ".//a[contains(@href, '/jobs/view/')]")
                    job_url = job_url_element.get_attribute("href")
                except:
                    skipped_no_url += 1
                    continue

                try:
                    posted_time_element = job_div.find_element(By.XPATH, ".//*[contains(@class, 'listdate')]")
                    posted_text = posted_time_element.text.strip()
                    posted_days = parse_posted_days(posted_text)
                except:
                    posted_days = 999

                if max_posted_days is not None and posted_days > max_posted_days:
                    skipped_too_old += 1
                    continue

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

            except Exception as e:
                print(f"[Monitor] Error parsing job item: {e}")
                continue

        print("\n[Summary] --------------------------------------------------")
        print(f"[Monitor] Monitoring '{title}' jobs in '{location}'")
        print(f"Total Jobs Found                       : {len(job_items)}")
        print(f"Jobs Accepted                          : {accepted_jobs}")
        print(f"Skipped - No Job ID                    : {skipped_no_jobid}")
        print(f"Skipped - No URL                       : {skipped_no_url}")
        print(f"Skipped - Too Old                      : {skipped_too_old}")
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
