#------------------------------------------------------
# This is a TCP, UDP, and cloud storage proxy server that listens for multiple sources,
# processes raw socket data or cloud storage files, applies a pipeline transformation,
# and forwards the data to multiple destinations.
#------------------------------------------------------

import sys
#sys.path.append('/Users/mhassan/osps/myenv/lib/python3.13/site-packages')  #When running outside the env

import socket
import threading
import json
import os
import time
import uuid
import traceback
from venv import logger
import yaml
import pipeline
import boto3  # AWS S3
from google.cloud import storage

from azure.storage.blob import BlobServiceClient  # Azure Blob
import requests  # Splunk HEC
from flask import Flask, logging, request, jsonify, render_template_string

from colorama import Back, Style, init, Fore
init(autoreset=True)  # Automatically reset color after each print

from utils import create_ip_alias, setup_logging, print_error_details, signal_handler

#------------------  Importing my modules & Local configs -------------------
DEFAULT_DEBUG_LEVEL = 0

CONFIG_FILE = 'config.yaml'
CACHE_DIR = 'cache'
CONFIG = {}

#-------------------globally hand uncaught exceptions in threads-------------------
def handle_thread_exception(args):
    print(f"Uncaught exception in thread {args.thread.name}: {args.exc_value}")
#------------------------------------------------------
threading.excepthook = handle_thread_exception


setup_logging()  # Set up logging configuration
#------------------------------------------------------
def load_config():
    try:
        with open(CONFIG_FILE, 'r') as f:
            return yaml.safe_load(f)
    except Exception as e:
        print_error_details(f"[!] Config load error: {e}")
        return {}
# End of load_config()
#------------------------------------------------------
#------------------------------------------------------
# Ensure the cache directory exists
os.makedirs(CACHE_DIR, exist_ok=True)
#-----------------------------------------------------
#------------------------------------------------------
def write_to_cache(data, tag="unknown"):
    try:
        uid = str(uuid.uuid4())
        fname = f"{tag}_{uid}.raw"
        path = os.path.join(CACHE_DIR, fname)
        with open(path, 'wb') as f:
            f.write(data)
        print(f"[+] Cached: {fname}", flush=True)
    except Exception as e:
        print_error_details(f"[!] Cache error: {e}")
# End of write_to_cache()
#------------------------------------------------------


#            **** SOURCES HANDLERS ****

#------------------------------------------------------
def handle_raw_tcp_client(client_sock, addr, source_cfg):
    """
    Handles a single raw TCP client connection.
    """
    client_ip, client_port = addr
    print(f"[+] Connection from {client_ip}:{client_port} (Raw TCP)", flush=True)
    pipeline_steps = source_cfg.get('pipeline', [])
    destinations = source_cfg.get('destinations', [])

    try:
        while True:
            raw_data = client_sock.recv(4096)
            if not raw_data:
                break
            print(f"[<] Received raw TCP data: {Fore.LIGHTBLACK_EX}{raw_data.decode('utf-8')}", flush=True)
            # Apply pipeline transformations
            transformed = pipeline.apply_pipeline({"raw_data": raw_data.decode('utf-8')}, pipeline_steps)
            encoded = json.dumps(transformed).encode('utf-8')
            # Forward to destinations
            if not forward_to_destinations(encoded, destinations):
                print (f"xxxxxxxx destination:[{destinations}]xxxxxxxxxxxxxx", flush=True)   #DEBUG
                write_to_cache(encoded, tag=source_cfg['name'])
                print(f"{Fore.RED}[!] Failed to forward raw TCP data, cached locally.", flush=True)
    except Exception as e:
        print_error_details(f"[!] Error handling raw TCP client: {e}")
    finally:
        client_sock.close()
        print(f"[-] Disconnected from {client_ip}:{client_port}", flush=True)
# End of handle_raw_tcp_client()
#------------------------------------------------------
#------------------------------------------------------
def handle_raw_tcp_source(source_cfg):
    """
    Handles incoming raw data over TCP as a source.
    """
    ip = source_cfg.get('listen_ip', '0.0.0.0')
    port = source_cfg['listen_port']
    pipeline_steps = source_cfg.get('pipeline', [])
    destinations = source_cfg.get('destinations', [])

    print(f"[*] Listening on {ip}:{port} for {Fore.GREEN}raw TCP {Fore.RESET}data", flush=True)
    #logger.info(f"{__name__}:Listening on {ip}:{port} for raw TCP data")
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server:
        server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server.bind((ip, port))
        server.listen(5)
        while True:
            try:
                client_sock, addr = server.accept()
                threading.Thread(target=handle_raw_tcp_client, args=(client_sock, addr, source_cfg), daemon=True).start()
            except Exception as e:
                print_error_details(f"[!] Error handling raw TCP data: {e}")
# End of handle_raw_tcp_source()
#------------------------------------------------------


#------------------------------------------------------
def handle_raw_udp_source(source_cfg):
    """
    Handles incoming raw data over UDP as a source.
    """
    ip = source_cfg.get('listen_ip', '0.0.0.0')
    port = source_cfg['listen_port']
    pipeline_steps = source_cfg.get('pipeline', [])
    destinations = source_cfg.get('destinations', [])
    print(f"[*] Listening on {ip}:{port} for {Fore.GREEN}raw UDP{Fore.RESET} data", flush=True)
    #logger.info(f"{__name__}:Listening on {ip}:{port} for raw UDP data")
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as server:
        server.bind((ip, port))
        while True:
            try:
                raw_data, addr = server.recvfrom(4096)
                client_ip, client_port = addr
                print(f"[<] Received raw UDP data from {client_ip}:{client_port}: {Fore.LIGHTBLACK_EX}{raw_data.decode('utf-8')}", flush=True)
                # Apply pipeline transformations
                transformed = pipeline.apply_pipeline({"raw_data": raw_data.decode('utf-8')}, pipeline_steps)
                encoded = json.dumps(transformed).encode('utf-8')
                # Forward to destinations
                if not forward_to_destinations(encoded, destinations):
                    write_to_cache(encoded, tag=source_cfg['name'])
                    print(f"{Fore.RED}[!] Failed to forward raw UDP data, cached locally.", flush=True)
            except Exception as e:
                print_error_details(f"[!] Error handling raw UDP data: {e}")
# End of handle_raw_udp_source()
#------------------------------------------------------


#     ***** FORWARDING (DESTINATIONS) FUNCTIONS *****
#------------------------------------------------------
def forward_to_splunk_hec(data, url, token):
    """
    Forwards data to a Splunk HEC endpoint.
    """
    headers = {
        'Authorization': f"Splunk {token}",
        'Content-Type': 'application/json'
    }
    try:
        response = requests.post(url, headers=headers, data=data)
        if response.status_code == 200:
            print(f"[-] Esablishing a socket to to Splunk HEC: {url}")
            return True
        else:
            print(f"{Fore.RED}[!] Failed to send to Splunk HEC: {url}, Status Code: {response.status_code}", flush=True)
            return False
    except Exception as e:
        print_error_details(f"[!] Error sending to Splunk HEC: {e}")
        return False
# End of forward_to_splunk_hec()
#------------------------------------------------------
#------------------------------------------------------
def forward_to_s3(data, bucket_name, region):
    """
    Forwards data to an AWS S3 bucket.
    """
    try:
        s3_client = boto3.client('s3', region_name=region)
        key = f"{uuid.uuid4()}.json"
        s3_client.put_object(Bucket=bucket_name, Key=key, Body=data)
        print(f"[+] Successfully uploaded to S3 bucket: {bucket_name}, key: {key}", flush=True)
        return True
    except Exception as e:
        print_error_details(f"[!] Failed to upload to S3 bucket {bucket_name}: {e}")
        return False
# End of forward_to_s3()
#------------------------------------------------------
#------------------------------------------------------
def forward_to_azure_blob(data, container_name, connection_string):
    """
    Forwards data to an Azure Blob Storage container.
    """
    try:
        blob_service_client = BlobServiceClient.from_connection_string(connection_string)
        blob_client = blob_service_client.get_blob_client(container=container_name, blob=f"{uuid.uuid4()}.json")
        blob_client.upload_blob(data)
        print(f"[+] Successfully uploaded to Azure Blob container: {container_name}", flush=True)
        return True
    except Exception as e:
        print_error_details(f"[!] Failed to upload to Azure Blob container {container_name}: {e}")
        return False
# End of forward_to_azure_blob()
#------------------------------------------------------
#------------------------------------------------------
def forward_to_gcs(data, bucket_name):
    """
    Forwards data to a Google Cloud Storage bucket.
    """
    try:
        client = storage.Client()
        bucket = client.get_bucket(bucket_name)
        blob = bucket.blob(f"{uuid.uuid4()}.json")
        blob.upload_from_string(data)
        print(f"[+] Successfully uploaded to GCS bucket: {bucket_name}", flush=True)
        return True
    except Exception as e:
        print_error_details(f"[!] Failed to upload to GCS bucket {bucket_name}: {e}")
        return False
# End of forward_to_gcs()
#------------------------------------------------------
#------------------------------------------------------
def forward_to_tcp_udp(data, dest):
    """
    Forwards data to a raw TCP or UDP destination.
    """
    ip = dest['ip']
    port = dest['port']
    protocol = dest.get('protocol', 'tcp').lower()

    try:
        if protocol == 'tcp':
            with socket.create_connection((ip, port), timeout=2) as sock:
                sock.sendall(data)
                print(f"[-] Esablishing a socket to data to TCP destination {ip}:{port}", flush=True)
        elif protocol == 'udp':
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
                sock.sendto(data, (ip, port))
                print(f"[-] Esablishing a socket to data to UDP destination {ip}:{port}", flush=True)
    except Exception as e:
        print_error_details(f"[!] Failed to send data to {protocol.upper()} destination {ip}:{port} - {e}")
# End of forward_to_tcp_udp()
#------------------------------------------------------
#------------------------------------------------------
def forward_to_tcp_syslog_dest(data, dest):
    """
    Forwards data to a Syslog destination over TCP.
    """
    ip = dest['ip']
    port = dest['port']

    try:
        with socket.create_connection((ip, port), timeout=2) as sock:
            sock.sendall(data)
            print(f"[-] Esablishing a socket to Syslog TCP data to {ip}:{port}", flush=True)
        return True
    except Exception as e:
        print_error_details(f"[!] Failed to send Syslog TCP data to {ip}:{port} - {e}", flush=True)
        return False
# End of forward_to_tcp_syslog_dest()
#------------------------------------------------------

#------------------------------------------------------
def forward_to_udp_syslog_dest(data, dest):
    """
    Forwards data to a Syslog destination over UDP.
    """
    ip = dest['ip']
    port = dest['port']

    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.sendto(data, (ip, port))
            print(f"[-] Esablishing a socket to Syslog UDP data to {ip}:{port}", flush=True)
        return True
    except Exception as e:
        print_error_details(f"[!] Failed to send Syslog UDP data to {ip}:{port} - {e}")
        return False
# End of forward_to_udp_syslog_dest()
#------------------------------------------------------

#------------------------------------------------------
def forward_to_destinations(data, destinations):
    """
    Forwards data to multiple destinations based on the configuration.
    """
    for dest in destinations:
        try:
            if 'ip' in dest and 'port' in dest:
                protocol = dest.get('protocol', 'tcp').lower()
                if protocol == 'syslog_udp':
                    forward_to_udp_syslog_dest(data, dest)
                elif protocol == 'syslog_tcp':
                    forward_to_tcp_syslog_dest(data, dest)
                else:
                    forward_to_tcp_udp(data, dest)

            elif 'bucket_name' in dest:
                if 'region' in dest:
                    forward_to_s3(data, dest['bucket_name'], dest['region'])
                else:
                    forward_to_gcs(data, dest['bucket_name'])
            elif 'container_name' in dest:
                forward_to_azure_blob(data, dest['container_name'], dest.get('connection_string'))
            elif 'url' in dest and 'token' in dest:
                forward_to_splunk_hec(data, dest['url'], dest['token'])

            print(f"[-] Forwarding data to destination: {dest}", flush=True)
        except Exception as e:
            print_error_details(f"[!] Failed to forward data to destination: {dest} - {e}")
# End of forward_to_destinations()
#------------------------------------------------------

#           *** Collectors Sources ***
#------------------------------------------------------
def handle_splunk_hec_collector_source(source_cfg):
    """
    Handles incoming data from a Splunk HEC endpoint.
    """
    ip=source_cfg['listen_ip']
    port=source_cfg['listen_port']
    endpoint = source_cfg['endpoint']
    token = source_cfg['token']
    pipeline_steps = source_cfg.get('pipeline', [])
    destinations = source_cfg.get('destinations', [])

    from flask import Flask, request, jsonify
    app = Flask(source_cfg['name'])

    @app.route(endpoint, methods=['POST'])
    def splunk_hec_handler():
        try:
            raw_data = request.get_json()
            print(f"[<] Received data from Splunk HEC: {Fore.LIGHTBLACK_EX}{raw_data}", flush=True)

            # Apply pipeline transformations
            transformed = pipeline.apply_pipeline(raw_data, pipeline_steps)
            encoded = json.dumps(transformed).encode('utf-8')

            # Forward to destinations
            if not forward_to_destinations(encoded, destinations):
                write_to_cache(encoded, tag=source_cfg['name'])
                print(f"{Fore.RED}[!] Failed to forward data from Splunk HEC, cached locally.", flush=True)

            return jsonify({"status": "success"}), 200
        except Exception as e:
            print_error_details(f"[!] Error processing Splunk HEC data: {e}")
            return jsonify({"status": "error", "message": str(e)}), 500

    # Start the Flask app
    print (f"[*] Listenig on {ip}:{port} for {Fore.GREEN}Splunk HEC{Fore.GREEN} data (using Flask)", flush=True)
    app.run(host=source_cfg.get('listen_ip', '0.0.0.0'), port=source_cfg['listen_port'], threaded=True)

    # Keep the app running
# End of handle_splunk_hec_collector_source()
#------------------------------------------------------
#------------------------------------------------------
def handle_s3_collector_source(source_cfg):
    """
    Polls an AWS S3 bucket for new files, processes them, and forwards the data.
    """
    bucket_name = source_cfg['bucket_name']
    region = source_cfg['region']
    polling_interval = source_cfg.get('polling_interval', 60)
    pipeline_steps = source_cfg.get('pipeline', [])
    destinations = source_cfg.get('destinations', [])
    delete_after_processing = source_cfg.get('delete_after_processing', False)  # Optional: Delete files after processing

    s3_client = boto3.client('s3', region_name=region)
    processed_keys = set()

    while True:
        try:
            # List objects in the S3 bucket
            response = s3_client.list_objects_v2(Bucket=bucket_name)
            if 'Contents' not in response:
                print(f"{Fore.RED}[!] No files found in S3 bucket: {bucket_name}")
                time.sleep(polling_interval)
                continue

            for obj in response['Contents']:
                key = obj['Key']
                if key in processed_keys:
                    continue

                print(f"[+] Processing file from S3 bucket: {bucket_name}, key: {key}")
                try:
                    # Fetch the file content
                    file_obj = s3_client.get_object(Bucket=bucket_name, Key=key)
                    raw_data = file_obj['Body'].read().decode('utf-8')

                    # Apply pipeline transformations
                    transformed = pipeline.apply_pipeline({"file_content": raw_data}, pipeline_steps)
                    encoded = transformed["file_content"].encode('utf-8')

                    # Forward to destinations
                    if not forward_to_destinations(encoded, destinations):
                        write_to_cache(encoded, tag=source_cfg['name'])
                        print(f"{Fore.RED}[!] Failed to forward data from S3 key: {key}, cached locally.")

                    # Mark the file as processed
                    processed_keys.add(key)

                    # Optionally delete the file after processing
                    if delete_after_processing:
                        s3_client.delete_object(Bucket=bucket_name, Key=key)
                        print(f"[+] Deleted file from S3 bucket: {bucket_name}, key: {key}")

                except Exception as e:
                    print_error_details(f"[!] Error processing file from S3 bucket: {bucket_name}, key: {key}, error: {e}")
        except Exception as e:
            print_error_details(f"[!] Error polling S3 bucket: {bucket_name}, error: {e}")
        # Wait for the next polling interval
        time.sleep(polling_interval)
# End of handle_s3_collector_source()
#------------------------------------------------------
#------------------------------------------------------
def handle_gcp_collector_source(source_cfg):
    """
    Polls a Google Cloud Storage bucket for new files, processes them, and forwards the data.
    """
    bucket_name = source_cfg['bucket_name']
    polling_interval = source_cfg.get('polling_interval', 60)
    pipeline_steps = source_cfg.get('pipeline', [])
    destinations = source_cfg.get('destinations', [])

    client = storage.Client()
    bucket = client.get_bucket(bucket_name)
    processed_blobs = set()

    while True:
        try:
            # List blobs in the GCP bucket
            blobs = bucket.list_blobs()
            for blob in blobs:
                if blob.name in processed_blobs:
                    continue

                print(f"[+] Processing file from GCP bucket: {bucket_name}, blob: {blob.name}")
                try:
                    # Fetch the file content
                    raw_data = blob.download_as_text()

                    # Apply pipeline transformations
                    transformed = pipeline.apply_pipeline({"file_content": raw_data}, pipeline_steps)
                    encoded = transformed["file_content"].encode('utf-8')

                    # Forward to destinations
                    if not forward_to_destinations(encoded, destinations):
                        write_to_cache(encoded, tag=source_cfg['name'])
                        print(f"{Fore.RED}[!] Failed to forward data from GCP blob: {blob.name}, cached locally.")

                    # Mark the blob as processed
                    processed_blobs.add(blob.name)

                except Exception as e:
                    print_error_details(f"[!] Error processing blob from GCP bucket: {bucket_name}, blob: {blob.name}, error: {e}")
        except Exception as e:
            print_error_details(f"[!] Error polling GCP bucket: {bucket_name}, error: {e}")
        # Wait for the next polling interval
        time.sleep(polling_interval)
# End of handle_gcp_collector_source()
#------------------------------------------------------
#------------------------------------------------------
def handle_azure_blob_collector_source(source_cfg):
    """
    Polls an Azure Blob Storage container for new files, processes them, and forwards the data.
    """
    container_name = source_cfg['container_name']
    connection_string = source_cfg['connection_string']
    polling_interval = source_cfg.get('polling_interval', 60)
    pipeline_steps = source_cfg.get('pipeline', [])
    destinations = source_cfg.get('destinations', [])

    blob_service_client = BlobServiceClient.from_connection_string(connection_string)
    container_client = blob_service_client.get_container_client(container_name)
    processed_blobs = set()

    while True:
        try:
            # List blobs in the Azure Blob container
            blobs = container_client.list_blobs()
            for blob in blobs:
                if blob.name in processed_blobs:
                    continue

                print(f"[+] Processing file from Azure Blob container: {container_name}, blob: {blob.name}")
                try:
                    # Fetch the blob content
                    blob_client = container_client.get_blob_client(blob)
                    raw_data = blob_client.download_blob().readall().decode('utf-8')

                    # Apply pipeline transformations
                    transformed = pipeline.apply_pipeline({"blob_content": raw_data}, pipeline_steps)
                    encoded = transformed["blob_content"].encode('utf-8')

                    # Forward to destinations
                    if not forward_to_destinations(encoded, destinations):
                        write_to_cache(encoded, tag=source_cfg['name'])
                        print(f"{Fore.RED}[!] Failed to forward data from Azure blob: {blob.name}, cached locally.")

                    # Mark the blob as processed
                    processed_blobs.add(blob.name)

                except Exception as e:
                    print(f"{Fore.RED}[!] Error processing blob from Azure Blob container: {container_name}, blob: {blob.name}, error: {e}")
                    print_error_details(e)
        except Exception as e:
            print_error_details(f"[!] Error polling Azure Blob container: {container_name}, error: {e}")

        # Wait for the next polling interval
        time.sleep(polling_interval)
# End of handle_azure_blob_collector_source()
#------------------------------------------------------

#------------------------------------------------------
def handle_syslog_udp_source(source_cfg):
    """
    ** Doesn't client routine() like syslog_tcp_source() **
    Handles incoming Syslog messages over UDP as a source.
    Listens for Syslog messages over UDP and processes them.
    Logs incoming messages and forwards them to destinations.
    """
    ip = source_cfg.get('listen_ip', '0.0.0.0')
    port = source_cfg['listen_port']
    pipeline_steps = source_cfg.get('pipeline', [])
    destinations = source_cfg.get('destinations', [])

    print(f"[*] Listening on {ip}:{port} for {Fore.GREEN}Syslog UDP{Fore.GREEN} messages", flush=True)
    #logger.info(f"{__name__}:Listening on {ip}:{port} for Syslog UDP messages")
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as server:
        server.bind((ip, port))
        while True:
            try:
                raw_data, addr = server.recvfrom(4096)
                client_ip, client_port = addr
                print(f"[<] Received Syslog UDP message from {client_ip}:{client_port}: {Fore.LIGHTBLACK_EX}{raw_data.decode('utf-8')}")

                # Apply pipeline transformations
                transformed = pipeline.apply_pipeline({"raw_data": raw_data.decode('utf-8')}, pipeline_steps)
                encoded = json.dumps(transformed).encode('utf-8')

                # Forward to destinations
                if not forward_to_destinations(encoded, destinations):
                    write_to_cache(encoded, tag=source_cfg['name'])
                    print(f"{Fore.RED}[!] Failed to forward Syslog UDP message, cached locally.")
            except Exception as e:
                print_error_details(f"[!] Error handling Syslog UDP message: {e}")
# End of handle_syslog_udp_source()
#------------------------------------------------------
#------------------------------------------------------
def handle_syslog_tcp_source(source_cfg):
    """
    Handles incoming Syslog messages over TCP as a source.
    Listens for Syslog messages over TCP and spawns a thread for each client connection.
    """
    ip = source_cfg.get('listen_ip', '0.0.0.0')
    port = source_cfg['listen_port']
    pipeline_steps = source_cfg.get('pipeline', [])
    destinations = source_cfg.get('destinations', [])

    print(f"[*] Listening on {ip}:{port} for {Fore.GREEN}Syslog TCP{Fore.RESET} messages", flush=True)
    #logger.info(f"{__name__}:Listening on {ip}:{port} for Syslog TCP messages")
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server:
        server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server.bind((ip, port))
        server.listen(5)
        while True:
            client_sock, addr = server.accept()
            threading.Thread(target=handle_syslog_tcp_client, args=(client_sock, addr, source_cfg), daemon=True).start()
# End of handle_syslog_tcp_source()
#------------------------------------------------------
#------------------------------------------------------
def handle_syslog_tcp_client(client_sock, addr, source_cfg):
    """
    Handles a single Syslog TCP client connection.
    Handles individual TCP client connections, processes messages, and forwards them to destinations.
    """
    client_ip, client_port = addr
    print(f"[+] Connection from {client_ip}:{client_port} (Syslog TCP)", flush=True)
    pipeline_steps = source_cfg.get('pipeline', [])
    destinations = source_cfg.get('destinations', [])

    try:
        while True:
            raw_data = client_sock.recv(4096)
            if not raw_data:
                break
            print(f"[<] Received Syslog TCP message: {Fore.LIGHTBLACK_EX}{raw_data.decode('utf-8')}", flush=True)

            # Apply pipeline transformations
            transformed = pipeline.apply_pipeline({"raw_data": raw_data.decode('utf-8')}, pipeline_steps)
            encoded = json.dumps(transformed).encode('utf-8')

            # Forward to destinations
            if not forward_to_destinations(encoded, destinations):
                write_to_cache(encoded, tag=source_cfg['name'])
                print(f"{Fore.RED}[!] Failed to forward Syslog TCP message, cached locally., flush=True")
    except Exception as e:
        print_error_details(f"[!] Error handling Syslog TCP client: {e}")
    finally:
        client_sock.close()
        print(f"[-] Disconnected from {client_ip}:{client_port}",flush=True)
# End of handle_syslog_tcp_client()
#------------------------------------------------------



#------------------------------------------------------
def start_sources_listeners(source_cfg):
    """
    Starts a listener for the specified source configuration.
    """
    protocol = source_cfg.get('protocol', 'tcp').lower()
    name = source_cfg['name']
    ''''
    if protocol == 'tcp':
        threading.Thread(target=handle_raw_tcp_source, args=(source_cfg,), daemon=True).start()
    elif protocol == 'udp':
        threading.Thread(target=handle_raw_udp_source, args=(source_cfg,), daemon=True).start()
    elif protocol == 's3':
        threading.Thread(target=handle_s3_collector_source, args=(source_cfg,), daemon=True).start()
    elif protocol == 'gcp':
        threading.Thread(target=handle_gcp_collector_source, args=(source_cfg,), daemon=True).start()
    elif protocol == 'azure_blob':
        threading.Thread(target=handle_azure_blob_collector_source, args=(source_cfg,), daemon=True).start()
    elif protocol == 'splunk_hec':
        threading.Thread(target=handle_splunk_hec_collector_source, args=(source_cfg,), daemon=True).start()
    '''
    if name == '_s_syslog_udp_source':
        threading.Thread(target=handle_syslog_udp_source, args=(source_cfg,), daemon=True).start()
    elif name == '_s_syslog_tcp':
        threading.Thread(target=handle_syslog_tcp_source, args=(source_cfg,), daemon=True).start()

    elif name == '_s_raw_tcp':
        threading.Thread(target=handle_raw_tcp_source, args=(source_cfg,), daemon=True).start()
    elif name == '_s_raw_udp':   
        threading.Thread(target=handle_raw_udp_source, args=(source_cfg,), daemon=True).start()

    elif name == '_s_s3_collector':
        threading.Thread(target=handle_s3_collector_source, args=(source_cfg,), daemon=True).start()
    elif name == '_s_gcp_collector':
        threading.Thread(target=handle_gcp_collector_source, args=(source_cfg,), daemon=True).start()
    elif name == '_s_azure_blob_collector':
        threading.Thread(target=handle_azure_blob_collector_source, args=(source_cfg,), daemon=True).start()
    elif name == '_s_splunk_hec_collector':
        threading.Thread(target=handle_splunk_hec_collector_source, args=(source_cfg,), daemon=True).start()
    else:
        print(f"{Fore.RED}[!] {Fore.RED}Unknown source name in configuration: {name}. Skipping.", flush=True)
        return
    
# End of start_sources_listeners()
#------------------------------------------------------

# Flask app for web interface
####### moved to web_interface.py ########
from web_interface import start_web_interface    #Placement matters


#------------------------------------------------------
# Main function
def main():
    global CONFIG
    CONFIG = load_config()
    if not CONFIG:
        print(f"{Fore.RED}[!] Failed to load configuration.", flush=True)
        return

    for source in CONFIG.get("sources", []):
        # Check if the source is enabled
        if not source.get("enabled", True):
            print(f"[-] {Fore.LIGHTBLACK_EX}Skipping disabled source: {source['name']}", flush=True)
            continue

        # Start the listener for the enabled source
        print(f"[+] {Fore.LIGHTBLUE_EX}Enabled source: {source['name']}", flush=True)
        threading.Thread(target=start_sources_listeners, args=(source,), daemon=True).start()
        time.sleep(1)
    # ----End of for loop-------

    print("[*] Proxy is running. Press Ctrl+C to exit.")
    # Start the web interface in a separate thread
    threading.Thread(target=start_web_interface, daemon=True).start()
    while True:
        time.sleep(1)
# End of main()
#------------------------------------------------------        

#===================================================
if __name__ == "__main__":

    #---For testing only ---
    interface_name = "en0"  # Replace with your actual interface name
    alias_ip_address = "192.168.1.100"
    alias_subnet_mask = "255.255.255.0"

    #create_ip_alias(interface_name, alias_ip_address, alias_subnet_mask)
    #ifc Example of deleting the created alias
    # delete_ip_alias(interface_name, alias_ip_address)


    main()
# End of proxy.py
#===================================================