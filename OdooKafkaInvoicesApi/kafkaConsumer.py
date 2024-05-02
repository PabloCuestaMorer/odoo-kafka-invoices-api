import xmlrpc.client
import json
from confluent_kafka import Consumer, KafkaError, KafkaException

# docker run -d --name zookeeper --network kafka-net -e ZOOKEEPER_CLIENT_PORT=2181 confluentinc/cp-zookeeper:latest
# docker run -d --name kafka --network kafka-net -p 9092:9092 -e KAFKA_BROKER_ID=1 -e KAFKA_ZOOKEEPER_CONNECT=zookeeper:2181 -e KAFKA_LISTENER_SECURITY_PROTOCOL_MAP=PLAINTEXT:PLAINTEXT,PLAINTEXT_HOST:PLAINTEXT -e KAFKA_ADVERTISED_LISTENERS=PLAINTEXT://kafka:29092,PLAINTEXT_HOST://localhost:9092 -e KAFKA_OFFSETS_TOPIC_REPLICATION_FACTOR=1 -e KAFKA_TRANSACTION_STATE_LOG_MIN_ISR=1 -e KAFKA_TRANSACTION_STATE_LOG_REPLICATION_FACTOR=1 confluentinc/cp-kafka:latest

# View logs
# docker logs kafka
# Create the topic
# docker exec -it kafka kafka-topics --create --topic invoices --partitions 1 --replication-factor 1 --if-not-exists --bootstrap-server localhost:9092

def get_odoo_connection():
    url = "https://universidadsanjorge.odoo.com"
    db = "universidadsanjorge"
    username = "alu.133005@usj.es"
    api_key = "fc5e2cd68ffe328eccbaee2cf36798068df4e746"
    common = xmlrpc.client.ServerProxy(f"{url}/xmlrpc/2/common", allow_none=True)
    uid = common.authenticate(db, username, api_key, {})
    models = xmlrpc.client.ServerProxy(f"{url}/xmlrpc/2/object", allow_none=True)
    return models, db, uid, api_key


def create_odoo_invoice(models, db, uid, api_key, invoice_data):
    response = models.execute_kw(
        db, uid, api_key, "account.move", "create", [invoice_data]
    )
    return response


# Kafka Consumer Setup
conf = {
    "bootstrap.servers": "localhost:9092",
    "group.id": "invoice-group",
    "auto.offset.reset": "earliest",
}
consumer = Consumer(conf)
consumer.subscribe(["invoices"])

try:
    while True:
        msg = consumer.poll(timeout=1.0)
        if msg is None:
            continue
        if msg.error():
            if msg.error().code() == KafkaError._PARTITION_EOF:
                print(
                    "%% %s [%d] reached end at offset %d\n"
                    % (msg.topic(), msg.partition(), msg.offset())
                )
            else:
                raise KafkaException(msg.error())
        else:
            invoice_data = json.loads(msg.value().decode("utf-8"))
            print(f"Received invoice data: {invoice_data}")

            models, db, uid, api_key = get_odoo_connection()

            # Creating the invoice in Odoo
            invoice_id = create_odoo_invoice(models, db, uid, api_key, invoice_data)
            print(f"Invoice created with ID: {invoice_id}")
except KeyboardInterrupt:
    pass
finally:
    consumer.close()
