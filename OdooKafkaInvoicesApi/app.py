from flask import Flask, render_template, request, redirect, url_for
from confluent_kafka import Producer
import xmlrpc.client
import logging
import json


app = Flask(__name__)


def acked(err, msg):
    if err is not None:
        print(f"Failed to deliver message: {err}")
    else:
        print(f"Message produced: {msg.topic()} {msg.partition()} {msg.offset()}")


# Configure Kafka producer
producer = Producer({"bootstrap.servers": "localhost:9092"})


def send_to_kafka(topic, data):
    producer.produce(topic, json.dumps(data).encode("utf-8"), callback=acked)
    producer.poll(0)
    producer.flush()


# Configure logging
logging.basicConfig(
    level=logging.DEBUG, format="%(asctime)s - %(levelname)s - %(message)s"
)


@app.route("/")
def index():
    url, db, username, api_key = get_odoo_connection()
    common = xmlrpc.client.ServerProxy("{}/xmlrpc/2/common".format(url))
    uid = common.authenticate(db, username, api_key, {})

    if uid:
        models = xmlrpc.client.ServerProxy("{}/xmlrpc/2/object".format(url))

        # Fetch the invoices
        data = models.execute_kw(
            db,
            uid,
            api_key,
            "account.move",
            "search_read",
            [[["move_type", "=", "out_invoice"]]],  # Filter for customer invoices
            {
                "fields": [
                    "name",
                    "invoice_date",
                    "invoice_date_due",
                    "partner_id",
                    "amount_total",
                    "state",
                ],
                "limit": 10,
            },
        )
        return render_template("index.html", data=data)
    else:
        return "Authentication failed", 401


def get_odoo_connection():
    url = "https://universidadsanjorge.odoo.com"
    db = "universidadsanjorge"
    username = "alu.133005@usj.es"
    api_key = "fc5e2cd68ffe328eccbaee2cf36798068df4e746"
    return url, db, username, api_key


def find_partner_id(models, db, uid, api_key, partner_name):
    partner = models.execute_kw(
        db,
        uid,
        api_key,
        "res.partner",
        "search_read",
        [[["name", "ilike", partner_name]]],
        {"fields": ["id"], "limit": 1},
    )
    return partner[0]["id"] if partner else None


def find_account_id(models, db, uid, api_key, partner_id):
    # adjust depending on your accounting setup
    partner = models.execute_kw(
        db,
        uid,
        api_key,
        "res.partner",
        "read",
        [partner_id],
        {"fields": ["property_account_receivable_id"]},
    )
    return (
        partner[0]["property_account_receivable_id"][0]
        if partner and "property_account_receivable_id" in partner[0]
        else None
    )


@app.route("/add-invoice", methods=["POST"])
def add_invoice():
    logging.debug("Received POST request for /add-invoice")
    url, db, username, api_key = get_odoo_connection()
    common = xmlrpc.client.ServerProxy("{}/xmlrpc/2/common".format(url))
    uid = common.authenticate(db, username, api_key, {})

    if uid:
        models = xmlrpc.client.ServerProxy("{}/xmlrpc/2/object".format(url))
        invoice_code = request.form.get(
            "invoice_code", "Default Invoice Name"
        )  # Providing a default if not supplied
        partner_name = request.form["customer_name"]
        product_reference = request.form["product_reference"]
        quantity = float(request.form["quantity"])
        unit_price = float(request.form["unit_price"])
        invoice_date = request.form["invoice_date"]
        due_date = request.form["due_date"]

        partner_id = find_partner_id(models, db, uid, api_key, partner_name)
        if not partner_id:
            logging.error("Partner not found")
            return "Partner not found", 404

        product_id = find_product_id_by_reference(
            models, db, uid, api_key, product_reference
        )
        if not product_id:
            logging.error("Product not found")
            return "Product not found", 404

        # Create the invoice
        new_invoice = {
            "name": invoice_code,
            "partner_id": partner_id,
            "invoice_date": invoice_date,
            "invoice_date_due": due_date,
            "invoice_line_ids": [
                (
                    0,
                    0,
                    {
                        "product_id": product_id,
                        "quantity": quantity,
                        "price_unit": unit_price,
                    },
                )
            ],
            "move_type": "out_invoice",
        }

        # Publish to Kafka using Confluent Kafka
        send_to_kafka("invoices", new_invoice)

        return redirect(url_for("index"))
    else:
        return "Authentication failed", 401


def find_product_id_by_reference(models, db, uid, api_key, internal_reference):
    product_data = models.execute_kw(
        db,
        uid,
        api_key,
        "product.product",
        "search_read",
        [[["default_code", "=", internal_reference]]],
        {"fields": ["id"], "limit": 1},
    )
    if product_data:
        return product_data[0]["id"]
    else:
        logging.info(
            "Product not found for internal reference: {}".format(internal_reference)
        )
        return None


@app.route("/invoice-form")
def invoice_form():
    return render_template("invoice_form.html")


@app.route("/post-invoice/<int:invoice_id>", methods=["POST"])
def post_invoice(invoice_id):
    url, db, username, api_key = get_odoo_connection()
    common = xmlrpc.client.ServerProxy("{}/xmlrpc/2/common".format(url))
    uid = common.authenticate(db, username, api_key, {})

    if uid:
        models = xmlrpc.client.ServerProxy("{}/xmlrpc/2/object".format(url))
        try:
            invoice = models.execute_kw(
                db,
                uid,
                api_key,
                "account.move",
                "read",
                [invoice_id],
                {"fields": ["state"]},
            )
            if invoice and invoice[0]["state"] == "draft":
                models.execute_kw(
                    db, uid, api_key, "account.move", "action_post", [[invoice_id]]
                )
            elif invoice and invoice[0]["state"] == "posted":
                models.execute_kw(
                    db, uid, api_key, "account.move", "button_draft", [[invoice_id]]
                )
            return redirect(url_for("index"))
        except xmlrpc.client.Fault as e:
            if "None unless allow_none is enabled" in str(e):
                # No se porque devuelve esta excepcion pero cambia bien el estado de la factura, es algo de la respuesta de Odoo
                logging.info(
                    f"Invoice state changed but response handling failed for invoice {invoice_id}"
                )
                return redirect(url_for("index"))
            else:
                logging.error(f"Failed to change invoice state {invoice_id}: {e}")
                return f"Failed to change invoice state {invoice_id}", 400
        except Exception as e:
            logging.error(f"Unexpected error for invoice {invoice_id}: {e}")
            return "Unexpected error", 500
    else:
        logging.error("Authentication failed")
        return "Authentication failed", 401


@app.route("/fetch-fields")
def fetch_fields():
    url, db, username, api_key = get_odoo_connection()
    common = xmlrpc.client.ServerProxy("{}/xmlrpc/2/common".format(url))
    uid = common.authenticate(db, username, api_key, {})
    if uid:
        models = xmlrpc.client.ServerProxy("{}/xmlrpc/2/object".format(url))
        fields_account_move = models.execute_kw(
            db,
            uid,
            api_key,
            "account.move",
            "fields_get",
            [],
            {"attributes": ["string", "help", "type"]},
        )
        fields_account_move_line = models.execute_kw(
            db,
            uid,
            api_key,
            "account.move.line",
            "fields_get",
            [],
            {"attributes": ["string", "help", "type"]},
        )
        return {
            "Account Move Fields": fields_account_move,
            "Account Move Line Fields": fields_account_move_line,
        }
    else:
        return "Authentication failed", 401


if __name__ == "__main__":
    # app.run(host='localhost', port=8080)
    app.run(debug=True)
