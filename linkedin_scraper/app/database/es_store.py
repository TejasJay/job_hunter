# app/Database/es_store.py

import os
import time
from elasticsearch import Elasticsearch, NotFoundError

class ESStore:
    def __init__(self, index_name="linkedin_jobs"):
        elastic_host = os.environ.get("ELASTICSEARCH_HOST", "elasticsearch")
        elastic_port = os.environ.get("ELASTICSEARCH_PORT", "9200")


        elastic_url = f"http://{elastic_host}:{elastic_port}"

        print(f"[DEBUG] Connecting to Elasticsearch at {elastic_url}")

        self.client = Elasticsearch(
            hosts=[{"host": elastic_host, "port": int(elastic_port), "scheme": "http"}],
            verify_certs=False,
            ssl_show_warn=False,
            request_timeout=30,
            retry_on_timeout=True,
        )
        self.index_name = index_name

        self.wait_for_elasticsearch()

        # Auto-create index if missing
        if not self.client.indices.exists(index=self.index_name):
            self.create_index()

    def wait_for_elasticsearch(self, retries=30, delay=5):
        for attempt in range(retries):
            try:
                if self.client.ping():
                    print(f"[DEBUG] Connected to Elasticsearch at attempt {attempt+1}")
                    return
                else:
                    print(f"[DEBUG] Ping failed at attempt {attempt+1}")
            except Exception as e:
                print(f"[DEBUG] Connection attempt {attempt+1} failed: {e}")

            time.sleep(delay)

        raise Exception(f"Could not connect to Elasticsearch after {retries} retries")

    def create_index(self):
        mapping = {
            "mappings": {
                "properties": {
                    "job_id": {"type": "keyword"},
                    "job_url": {"type": "text"},
                    "job_title": {"type": "text"},
                    "company_name": {"type": "text"},
                    "location": {"type": "text"},
                    "posted_time": {"type": "text"},
                    "applicants": {"type": "text"},
                    "description": {"type": "text"},
                    "Seniority level": {"type": "text"},
                    "Employment type": {"type": "text"},
                    "Job function": {"type": "text"},
                    "Industries": {"type": "text"},
                }
            }
        }
        self.client.indices.create(index=self.index_name, body=mapping)
        print(f"[DEBUG] Created index: {self.index_name}")

    def is_job_id_seen(self, job_id):
        try:
            self.client.get(index=self.index_name, id=job_id)
            return True
        except NotFoundError:
            return False

    def add_job_data(self, job_data):
        self.client.index(index=self.index_name, id=job_data["job_id"], body=job_data)

    def update_job_data(self, job_id, updated_fields):
        self.client.update(index=self.index_name, id=job_id, body={"doc": updated_fields})

# Instantiate a global object
es_store = ESStore()
