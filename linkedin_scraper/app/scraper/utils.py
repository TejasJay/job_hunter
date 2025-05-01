# app/scraper/utils.py

import re
import os
from datetime import datetime, timedelta


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