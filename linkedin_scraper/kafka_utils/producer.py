from confluent_kafka import Producer
from confluent_kafka.admin import AdminClient, NewTopic
import logging
import json
import time

KAFKA_BROKERS = "kafka-broker-1:19092,kafka-broker-2:19092,kafka-broker-3:19092"
NUM_PARTITIONS = 5
REPLICATION_FACTOR = 3

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

producer = None
topic_created = False

def get_producer():
    global producer
    if producer is None:
        producer_conf = {
            'bootstrap.servers': KAFKA_BROKERS,
            'queue.buffering.max.messages': 10000,
            'queue.buffering.max.kbytes': 512000,
            'batch.num.messages': 1000,
            'linger.ms': 10,
            'acks': 1,
            'compression.type': 'gzip'
        }
        producer = Producer(producer_conf)
    return producer

def create_topic(topic_name):
    admin_client = AdminClient({"bootstrap.servers": KAFKA_BROKERS})
    try:
        metadata = admin_client.list_topics(timeout=10)
        if topic_name not in metadata.topics:
            topic = NewTopic(
                topic=topic_name,
                num_partitions=NUM_PARTITIONS,
                replication_factor=REPLICATION_FACTOR
            )
            fs = admin_client.create_topics([topic])
            for topic, future in fs.items():
                try:
                    future.result()
                    logger.info(f"Topic '{topic_name}' created successfully!")
                except Exception as e:
                    logger.error(f"Failed to create topic '{topic_name}': {e}")
        else:
            logger.info(f"Topic '{topic_name}' already exists")
    except Exception as e:
        logger.error(f"Error creating topic: {e}")

def delivery_report(err, msg):
    if err is not None:
        print(f'Delivery failed for record {msg.key()}: {err}')
    else:
        print(f'Record {msg.key()} successfully produced')

def produce_transaction(record, topic_name="job_records"):
    global topic_created

    if not topic_created:
        create_topic(topic_name)
        topic_created = True

    p = get_producer()

    while True:
        try:
            p.produce(
                topic=topic_name,
                key=record['job_id'],
                value=json.dumps(record).encode('utf-8'),
                on_delivery=delivery_report
            )
            print(f"Job ID: {record['job_id']}\t{record['job_title']}-{record['company_name']}")
            p.flush()
            break  # success
        except Exception as e:
            print(f'Error sending transaction: {e}, retrying in 1s...')
            time.sleep(1)
