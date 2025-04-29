# app/scraper/job_parser.py

import os
from bs4 import BeautifulSoup
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException

from .utils import get_text_by_xpath, log_missing_field, extract_job_id, posted_text_to_datetime

def parse_job_details(driver, job_url, known_job_id=None):
    """
    Parses job details from a LinkedIn job page.
    If known_job_id is provided (from Redis), use it directly.
    Otherwise, extract from URL.
    """
    job_id = known_job_id or extract_job_id(job_url)

    try:
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CLASS_NAME, "show-more-less-html"))
        )
    except TimeoutException:
        print(f"Description never loaded for {job_url}")
        return None

    job_title = get_text_by_xpath(driver,
        "//h2[contains(@class,'top-card-layout__title') or contains(@class,'topcard__title')]",
        "job_title", job_url)

    company_name = (
        get_text_by_xpath(driver, "//a[contains(@class,'topcard__org-name-link')]", "company_name", job_url)
        or get_text_by_xpath(driver, "//span[contains(@class,'topcard__flavor')]", "company_name", job_url)
        or get_text_by_xpath(driver, "//span[contains(@class,'topcard__flavor--metadata')]", "company_name", job_url)
    )

    location_text = get_text_by_xpath(driver, "//span[contains(@class,'topcard__flavor--bullet')]", "location", job_url)
    posted_time = get_text_by_xpath(driver, "//span[contains(@class,'posted-time-ago__text')]", "posted_time", job_url)

    try:
        applicants = driver.find_element(By.XPATH, "//figcaption[contains(@class, 'num-applicants__caption')]").text.strip()
    except:
        try:
            applicants = driver.find_element(By.XPATH, "//span[contains(@class, 'num-applicants__caption')]").text.strip()
        except:
            applicants = None
            log_missing_field(job_url, "applicants")

    try:
        desc_html = driver.find_element(By.XPATH, "//div[contains(@class, 'show-more-less-html')]").get_attribute("innerHTML")
        soup = BeautifulSoup(desc_html, "html.parser")
        description = soup.get_text(separator="\n").strip()
    except:
        description = None
        log_missing_field(job_url, "description")

    required_fields = [job_title, company_name, description]
    if any(f is None or f.strip() == "" for f in required_fields):
        print(f"Skipping job due to missing required fields: {job_url}")

        os.makedirs("logs/failures", exist_ok=True)
        snapshot_path = f"logs/failures/job_{job_id}.html"
        with open(snapshot_path, "w", encoding="utf-8") as f:
            f.write(driver.page_source)
            print(f"Saved page snapshot: {snapshot_path}")

        return None

    job_data = {
        "job_id": job_id,
        "job_url": job_url,
        "job_title": job_title,
        "company_name": company_name,
        "location": location_text,
        "posted_time": posted_time,
        "posted_timestamp": str(posted_text_to_datetime(posted_time)),
        "applicants": applicants,
        "description": description
    }

    for label in ["Seniority level", "Employment type", "Job function", "Industries"]:
        try:
            value = driver.find_element(
                By.XPATH,
                f"//h3[contains(text(), '{label}')]/ancestor::li[1]//span[contains(@class, 'description__job-criteria-text')]"
            ).text.strip()
            job_data[label] = value
        except:
            job_data[label] = None
            log_missing_field(job_url, label)

    return job_data
