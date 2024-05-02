### Flask-Kafka-Odoo Integration App

#### Table of Contents
1. [Overview](#overview)
2. [Key Features](#key-features)
3. [Prerequisites](#prerequisites)
4. [Setup Instructions](#setup-instructions)
5. [Usage](#usage)
6. [Troubleshooting](#troubleshooting)
7. [Support](#support)

---

### Overview
This application automates the process of receiving, processing, and managing invoices via a web interface, Kafka messaging, and integration with the Odoo ERP system.

### Key Features
- **Web Form Submission**: Simple interface for submitting invoice data.
- **Real-Time Processing**: Integration with Kafka for real-time data handling.
- **Odoo Integration**: Automated creation of invoices in Odoo from Kafka messages.
- **Error Handling**: Robust error management and feedback.

### Prerequisites
- Docker
- Python 3.8+
- Flask
- confluent_kafka
- Access to an Odoo instance

### Setup Instructions
#### 1. Clone the Repository
   ```bash
   git clone [your-repository-url]
   cd [your-project-directory]
   ```
#### 2. Set Up Kafka and Zookeeper
   Using Docker:
   ```bash
   docker-compose up -d
   ```
#### 3. Configure Environment Variables
   Example `.env` file:
   ```plaintext
   ODOO_URL=https://your-odoo-instance.com
   ODOO_DB=your-database
   ODOO_USERNAME=your-username
   ODOO_API_KEY=your-api-key
   ```
#### 4. Install Dependencies
   ```bash
   pip install -r requirements.txt
   ```
#### 5. Run the Flask Application
   ```bash
   flask run
   ```

### Usage
Navigate to `http://localhost:5000` to submit invoices. They will be processed and appear in Odoo once handled by the Kafka consumer.

### Troubleshooting
- Ensure all components (Kafka, Zookeeper, Flask, Kafka consumer) are operational.
- Check logs for errors related to connections with Odoo or Kafka.
- Verify Kafka topic configurations and consumer subscriptions.

### Support
For assistance, please email [pcuestamorer@gmail.com] with a detailed description of your issue.
