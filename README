# Welcome to the Multi-Source Data Proxy Server! 🎉

## Introduction
Welcome to the **Multi-Source Data Proxy Server**, a powerful and flexible tool designed to simplify the collection, transformation, and forwarding of data from multiple sources to various destinations. Whether you're working with **Syslog (TCP/UDP)**, **AWS S3**, **Google Cloud Storage (GCP)**, **Azure Blob Storage**, or **Splunk HEC**, this proxy server has you covered.

This project is perfect for developers, system administrators, and data engineers who need to process and route data efficiently across different systems. With its **config-driven architecture**, you can easily enable or disable sources and destinations, apply custom transformations, and handle failures gracefully.

---

## What Does This Proxy Server Do?
The **Multi-Source Data Proxy Server** acts as a bridge between data sources and destinations. Here's how it works:
1. **Listens to Data Sources**: The server listens for incoming data from various protocols like Syslog, AWS S3, GCP, Azure Blob, and Splunk HEC.
2. **Processes the Data**: It applies configurable **pipeline transformations** (e.g., regex replacements) to clean, modify, or enrich the data.
3. **Forwards the Data**: The transformed data is forwarded to one or more destinations, such as Syslog endpoints, cloud storage buckets, or Splunk HEC.

---

## Why Use This Proxy Server?
- **Centralized Data Processing**: Manage multiple data sources and destinations from a single server.
- **Customizable Pipelines**: Apply transformations to incoming data to meet your specific requirements.
- **Dynamic Configuration**: Enable or disable sources and destinations without modifying the code.
- **Error Handling**: Automatically cache failed data for retrying later.
- **Extensibility**: Add new protocols, pipelines, or destinations with minimal effort.

---

## Features
- **Multi-Source Support**:
  - Syslog (TCP/UDP)
  - AWS S3
  - Google Cloud Storage (GCP)
  - Azure Blob Storage
  - Splunk HEC
- **Pipeline Transformations**:
  - Apply regex-based transformations to incoming data.
  - Easily extendable for custom transformations.
- **Dynamic Configuration**:
  - Enable or disable sources and destinations via `config.yaml`.
- **Caching**:
  - Failed data forwarding is cached locally for retry.
- **Extensibility**:
  - Add new protocols, pipelines, or destinations with minimal changes.

---

## How It Works
1. **Sources**: The server listens to data from various sources defined in the `config.yaml` file.
2. **Pipelines**: Incoming data is processed through a series of transformations.
3. **Destinations**: The transformed data is forwarded to the configured destinations.

---

## Getting Started

### Prerequisites
- Python 3.8 or higher
- Install required dependencies:
  ```bash
  pip install -r requirements.txt

