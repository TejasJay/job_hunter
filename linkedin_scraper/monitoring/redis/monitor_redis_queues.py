import time
import redis
import json

# Configuration (👉 correctly point to Docker service name!)
REDIS_HOST = "localhost"      # <-- Important: Not localhost inside docker!
REDIS_PORT = 6380
POLL_INTERVAL = 10        # seconds between refresh

def get_redis_connection():
    return redis.Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True)

def monitor_queues():
    client = get_redis_connection()

    while True:
        try:
            pending_new_count = client.llen("pending_new_jobs")
            pending_update_count = client.llen("pending_update_jobs")
            failed_jobs_count = client.llen("failed_jobs") if client.exists("failed_jobs") else 0
            total_seen_jobs = client.scard("linkedin_job_ids")
            total_scraped_jobs = client.scard("scraped_job_ids")

            print("\n📊  [Redis Queue Monitor] ------------------------------")
            print(f"Pending New Jobs        : {pending_new_count}")
            print(f"Pending Update Jobs     : {pending_update_count}")
            print(f"Failed Jobs              : {failed_jobs_count}")
            print(f"Total Seen Jobs (Set)    : {total_seen_jobs}")
            print(f"Total Scraped Jobs (Set) : {total_scraped_jobs}")
            print("--------------------------------------------------------\n")

        except Exception as e:
            print(f"[Monitor] Error accessing Redis: {e}")

        time.sleep(POLL_INTERVAL)

if __name__ == "__main__":
    monitor_queues()



