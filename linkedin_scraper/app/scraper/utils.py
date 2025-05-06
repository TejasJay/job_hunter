# app/scraper/utils.py

import re
import os
from datetime import datetime, timedelta
from selenium.common.exceptions import TimeoutException, ElementClickInterceptedException, NoSuchElementException, JavascriptException
import time
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
import random
from selenium.webdriver.support import expected_conditions as EC



LOG_PATH = os.path.join("logs", "missing_fields.log")


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


def log_missing_field(job_url, field_name):
    """Logs fields that could not be extracted during scraping."""
    os.makedirs(os.path.dirname(LOG_PATH), exist_ok=True)
    with open(LOG_PATH, "a", encoding="utf-8") as log_file:
        log_file.write(f"[MISSING] {field_name} not found at {job_url}\n")


def get_text_by_xpath(driver, xpath: str, field_name: str, job_url: str):
    """
    Attempt to extract the text from an element by XPath. If not found, logs and returns None.
    """
    try:
        return driver.find_element("xpath", xpath).text.strip()
    except Exception:
        log_missing_field(job_url, field_name)
        return None
    

def round_to_nearest_hour(dt):
    """Round a datetime object to the nearest hour."""
    # If minutes >= 30, round up by adding (60 - minutes) minutes.
    # Otherwise, subtract minutes
    if dt.minute >= 30:
        dt = dt.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)
    else:
        dt = dt.replace(minute=0, second=0, microsecond=0)
    return dt


def posted_text_to_datetime(posted_text):
    posted_text = posted_text.lower()
    now = datetime.utcnow()
    if "minute" in posted_text:
        minutes = int(re.search(r"\d+", posted_text).group())
        dt = now - timedelta(minutes=minutes)
        return round_to_nearest_hour(dt)  # <<< ROUNDING HERE
    elif "hour" in posted_text:
        hours = int(re.search(r"\d+", posted_text).group())
        dt = now - timedelta(hours=hours)
        return round_to_nearest_hour(dt)  # <<< ROUNDING HERE
    elif "day" in posted_text:
        days = int(re.search(r"\d+", posted_text).group())
        dt = now - timedelta(days=days)
        return datetime(dt.year, dt.month, dt.day)  # Already resetting time to 00:00
    elif "week" in posted_text:
        weeks = int(re.search(r"\d+", posted_text).group())
        dt = now - timedelta(weeks=weeks)
        return datetime(dt.year, dt.month, dt.day)
    elif "month" in posted_text:
        months = int(re.search(r"\d+", posted_text).group())
        dt = now - timedelta(days=months * 30)  # Approximate
        return datetime(dt.year, dt.month, dt.day)
    elif "year" in posted_text:
        years = int(re.search(r"\d+", posted_text).group())
        dt = now - timedelta(days=years * 365)  # Approximate
        return datetime(dt.year, dt.month, dt.day)
    else:
        return None
    

def compute_dynamic_scrolls(max_jobs):
    if max_jobs <= 25:
        return 5
    elif max_jobs <= 75:
        return 8
    elif max_jobs <= 150:
        return 12
    elif max_jobs <= 300:
        return 15
    else:
        return 20


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
