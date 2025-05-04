import argparse
import os
from app.main import create_app
from app.scraper.scraper import scrape_linkedin_jobs
from app.monitor.monitor_jobs import monitor_linkedin_jobs

def parse_arguments():
    parser = argparse.ArgumentParser(description="LinkedIn Job Scraper and Monitor")
    parser.add_argument("--title", default="Data Engineer", help="Job title to search or monitor")
    parser.add_argument("--location", default="Canada", help="Location to search or monitor")
    parser.add_argument("--max_jobs", type=int, default=10, help="Maximum number of jobs to scrape in CLI mode")
    parser.add_argument("--mode", choices=["web", "cli", "monitor"], default="web", help="Run mode: 'web', 'cli', or 'monitor'")
    parser.add_argument("--date_filter", default="any", help="Date filter: 'any', 'past_month', 'past_week', 'past_24_hours'")
    parser.add_argument("--max_posted_days", type=float, default=None, help="Max job age in days (optional, float supported). Example: 0.25 for 6 hours.")
    return parser.parse_args()

def select_dynamic_date_filter(date_filter, max_posted_days):
    if date_filter == "any" and max_posted_days is not None:
        if max_posted_days <= 1:
            return "past_24_hours"
        elif max_posted_days <= 7:
            return "past_week"
        elif max_posted_days <= 30:
            return "past_month"
        else:
            return "any"
    return date_filter  # Use user-specified filter if provided

def estimate_max_scrolls(max_jobs):
    """
    Estimate the number of scrolls based on desired max_jobs.
    You can tweak thresholds as needed.
    """
    if max_jobs <= 25:
        return 5
    elif max_jobs <= 75:
        return 8
    elif max_jobs <= 150:
        return 12
    elif max_jobs <= 300:
        return 15
    else:
        return 20  # Cap at 20 scrolls for very large jobs

def main():
    args = parse_arguments()

    if args.mode == "cli":
        dynamic_scrolls = estimate_max_scrolls(args.max_jobs)
        print(f"Running in CLI mode: scraping '{args.title}' jobs in '{args.location}' (max {args.max_jobs}) using {dynamic_scrolls} scrolls")
        
        scrape_linkedin_jobs(
            max_jobs=args.max_jobs,
            title=args.title,
            location=args.location,
            max_scrolls=dynamic_scrolls  # 👈 pass it dynamically!
        )

    elif args.mode == "monitor":
        selected_date_filter = select_dynamic_date_filter(args.date_filter, args.max_posted_days)

        print(f"Running in MONITOR mode: watching '{args.title}' jobs in '{args.location}'")
        print(f"Using date filter: {selected_date_filter} | Max posted days: {args.max_posted_days if args.max_posted_days is not None else 'any'}")

        monitor_linkedin_jobs(
            title=args.title,
            location=args.location,
            date_filter=selected_date_filter,
            max_posted_days=args.max_posted_days
        )

    else:
        print("Starting Flask Web Server...")
        app = create_app()
        debug_mode = os.environ.get("FLASK_DEBUG", "true").lower() == "true"
        app.run(host="0.0.0.0", port=5000, debug=debug_mode)

if __name__ == "__main__":
    main()
