#!/bin/bash

# set -e

# cd /Users/tejasjay/job_hunter/lin || exit 1


echo "Running LinkedIn scraper..."
docker compose exec linkedin-web python run.py --mode cli --title "Software Engineer" --location "Bangalore" --max_jobs 100
