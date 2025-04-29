# app/web/views.py
from flask import Blueprint, render_template, request
from app.scraper.scraper import scrape_linkedin_jobs
from flask import Blueprint, request, jsonify
from app.scraper.driver import get_driver
from app.scraper.job_parser import parse_job_details
from kafka_utils.producer import produce_transaction

web = Blueprint("web", __name__, template_folder="templates")

@web.route("/", methods=["GET", "POST"])
def home():
    jobs = []
    if request.method == "POST":
        title = request.form.get("title", "Data Engineer")
        location = request.form.get("location", "Canada")
        max_jobs = int(request.form.get("max_jobs", 10))

        try:
            result = scrape_linkedin_jobs(max_jobs=max_jobs, title=title, location=location)
            if isinstance(result, list):
                jobs = result
            else:
                print("scrape_linkedin_jobs did not return a list")
        except Exception as e:
            print(f"Error during scraping: {e}")

    return render_template("home.html", jobs=jobs)

@web.route('/trigger_scraper', methods=['POST'])
def trigger_scraper():
    data = request.get_json()

    job_id = data.get("job_id")
    job_url = data.get("job_url")

    if not job_id or not job_url:
        return jsonify({"error": "Missing job_id or job_url"}), 400

    driver = None
    try:
        driver = get_driver()
        job_data = parse_job_details(driver, job_url)
        
        if not job_data:
            return jsonify({"error": "Failed to parse job details"}), 500

        produce_transaction(job_data)  # Produce to Kafka
        return jsonify({"message": f"Job {job_id} successfully scraped and produced."}), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500

    finally:
        if driver:
            driver.quit()