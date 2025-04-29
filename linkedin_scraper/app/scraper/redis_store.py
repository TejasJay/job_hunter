import redis
import json

class RedisStore:
    def __init__(self, host="redis", port=6379, db=0):
        self.client = redis.Redis(
            host=host,
            port=port,
            db=db,
            decode_responses=True
        )

    def add_job_id(self, job_id):
        """Track job IDs we've ever seen (global deduplication)."""
        self.client.sadd("linkedin_job_ids", job_id)

    def is_job_id_seen(self, job_id):
        """Check if job was ever seen by the monitor (not necessarily scraped)."""
        return self.client.sismember("linkedin_job_ids", job_id)

    def add_to_pending_new_jobs(self, job_id, job_url):
        """Queue a new job for first-time scraping."""
        self.client.rpush("pending_new_jobs", json.dumps({
            "job_id": job_id,
            "job_url": job_url
        }))

    def add_to_pending_update_jobs(self, job_id, job_url):
        """Queue a job for re-scraping (if already known)."""
        self.client.rpush("pending_update_jobs", json.dumps({
            "job_id": job_id,
            "job_url": job_url
        }))

    def fetch_pending_new_jobs(self, batch_size=30):
        """Pop up to batch_size jobs from pending_new_jobs list."""
        pending_jobs = []
        for _ in range(batch_size):
            job_data = self.client.lpop("pending_new_jobs")
            if not job_data:
                break
            pending_jobs.append(json.loads(job_data))
        return pending_jobs

    def fetch_pending_update_jobs(self, batch_size=30):
        """Pop up to batch_size jobs from pending_update_jobs list."""
        pending_jobs = []
        for _ in range(batch_size):
            job_data = self.client.lpop("pending_update_jobs")
            if not job_data:
                break
            pending_jobs.append(json.loads(job_data))
        return pending_jobs

    def mark_job_as_scraped(self, job_id):
        """Track job IDs we have successfully scraped."""
        self.client.sadd("scraped_job_ids", job_id)

    def is_job_id_scraped(self, job_id):
        """Check if job has already been scraped."""
        return self.client.sismember("scraped_job_ids", job_id)

# Singleton instance
redis_store = RedisStore()
