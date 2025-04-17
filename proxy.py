#------------------------------------------------------
# This is a TCP, UDP, and cloud storage proxy server that listens for multiple sources,
# processes raw socket data or cloud storage files, applies a pipeline transformation,
# and forwards the data to multiple destinations.
#------------------------------------------------------

# Import necessary modules
import sys
import socket
import threading
import json
import os
import time
import uuid
import traceback
import yaml
import pipeline
import boto3  # AWS S3
from google.cloud import storage
from azure.storage.blob import BlobServiceClient  # Azure Blob
import requests  # Splunk HEC
from flask import Flask, request, jsonify
from colorama import Fore, Style, init
from utils import create_ip_alias, setup_logging, print_error_details, signal_handler, start_monitoring_thread, validate_config, debug_print
from web_interface import start_web_interface  # Flask app for web interface
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

init(autoreset=True)  # Automatically reset color after each print

#------------------  Importing my modules & Local configs -------------------
DEFAULT_DEBUG_LEVEL = 3
CONFIG_FILE = 'config.yaml'
CACHE_DIR = 'cache'
CONFIG = {
    "sources": [],
    "destinations": [],
    "pipelines": [],
    "routes": []
}

# Global debug level
DEBUG_LEVEL = 3  # Default to verbose output

# Parse command-line arguments
import argparse

parser = argparse.ArgumentParser(description="Run the proxy server.")
parser.add_argument(
    "--debug", "-d", 
    type=int, 
    default=3, 
    help=(
        "Set the debug level:\n"
        "  0 = Errors only\n"
        "  1 = Basic information\n"
        "  2 = Detailed information\n"
        "  3 = Verbose/debug logs"
    )
)
parser.add_argument(
    "--assign-null-route",
    action="store_true",
    help="Automatically assign a null route to sources with no routes configured."
)

args = parser.parse_args()

# Set the global debug level
DEBUG_LEVEL = args.debug

# Display the debug level as the first output
debug_print(f"[DEBUG] Debug level set to: {DEBUG_LEVEL}", DLevel=3)

# Assign the null route flag
ASSIGN_NULL_ROUTE = args.assign_null_route

# Check if the help argument (-h/--help) was triggered
if '-h' in sys.argv or '--help' in sys.argv:
    print("\n")
    sys.exit(0)  # Exit the program after displaying the help message

#-------------------globally hand uncaught exceptions in threads-------------------
def handle_thread_exception(args):
    debug_print(f"[!] Uncaught exception in thread {args.thread.name}: {args.exc_value}:", DLevel=0)
threading.excepthook = handle_thread_exception

setup_logging()  # Set up logging configuration

#------------------------------------------------------
def load_config():
    """
    Loads and merges configurations from sources.yaml, destinations.yaml, and pipelines.yaml.
    """
    try:
        with open("sources.yaml", "r") as f:
            sources = yaml.safe_load(f)

        with open("destinations.yaml", "r") as f:
            destinations = yaml.safe_load(f)

        with open("pipelines.yaml", "r") as f:
            pipelines = yaml.safe_load(f)

        with open("routes.yaml", "r") as f:
            routes = yaml.safe_load(f)

        # Merge the configurations into a single dictionary
        config = {
            "sources": sources.get("sources", []),
            "destinations": destinations.get("destinations", []),
            "pipelines": pipelines.get("pipelines", []),
            "routes": routes.get("routes", []),
        }
        return config
    except Exception as e:
        debug_print(f"[!] Config load error: {e}", DLevel=0)
        return {}
# End of load_config()
#------------------------------------------------------
#------------------------------------------------------
# Ensure the cache directory exists
os.makedirs(CACHE_DIR, exist_ok=True)

#------------------------------------------------------
def write_to_cache(data, tag="unknown"):
    """
    Writes data to a local cache file.
    """
    try:
        uid = str(uuid.uuid4())
        fname = f"{tag}_{uid}.raw"
        path = os.path.join(CACHE_DIR, fname)
        with open(path, 'wb') as f:
            f.write(data)
        debug_print(f"{Fore.YELLOW}[+] Cache filename: {fname}", DLevel=3)
    except Exception as e:
        debug_print(f"[!] Cache error: {e}", DLevel=0)
# End of write_to_cache()
#------------------------------------------------------
#------------------------------------------------------
def handle_raw_tcp_client_connection(client_sock, addr, pipeline_cfg, destinations):
    """
    Handles a single raw TCP client connection.
    Receives data from the client, applies pipeline transformations, and forwards the data to destinations.
    """
    client_ip, client_port = addr
    pipeline_steps = pipeline_cfg.get('pipeline', [])

    try:
        client_sock.settimeout(30)  # 30 seconds timeout
        while True:
            try:
                raw_data = client_sock.recv(4096)
                if not raw_data:
                    debug_print(f"[-] Connection closed by client [{client_ip}:{client_port}]", DLevel=1)
                    break

                debug_print(f"[<] Received raw TCP data from {client_ip}:{client_port}: {Fore.LIGHTBLACK_EX}{raw_data.decode('utf-8')}", DLevel=3)

                # Apply pipeline transformations
                try:
                    transformed = pipeline.apply_pipeline({"raw_data": raw_data.decode('utf-8')}, pipeline_steps)
                    encoded = json.dumps(transformed).encode('utf-8')
                except Exception as e:
                    debug_print(f"[!] Pipeline transformation failed for data from {client_ip}:{client_port} - Error: {e}", DLevel=0)
                    write_to_cache(raw_data, tag=pipeline_cfg['name'])
                    continue

                # Forward to destinations
                if not forward_to_destinations(encoded, destinations):
                    write_to_cache(encoded, tag=pipeline_cfg['name'])
                    debug_print(f"{Fore.RED}[!] Failed to forward raw TCP data from {client_ip}:{client_port}, cached locally.", DLevel=0)

            except socket.timeout:
                debug_print(f"[!] Connection timed out for client [{client_ip}:{client_port}]", DLevel=1)
                break
            except Exception as e:
                debug_print(f"[!] Error receiving data from client [{client_ip}:{client_port}] - Error: {e}", DLevel=0)
                break

    except Exception as e:
        debug_print(f"[!] Unexpected error handling raw TCP client [{client_ip}:{client_port}] - Error: {e}", DLevel=0)
    finally:
        client_sock.close()
        debug_print(f"[-] Connection closed for client [{client_ip}:{client_port}]", DLevel=1)
# End of handle_raw_tcp_client_connection()
#------------------------------------------------------
#------------------------------------------------------
def handle_raw_tcp_client(source_cfg, routes, all_destinations, all_pipelines):
    """
    Handles incoming raw TCP connections as a source.
    Listens for raw TCP connections, processes incoming data, and forwards it to destinations.
    """
    ip = source_cfg.get('listen_ip', '0.0.0.0')
    port = source_cfg['listen_port']
    route_count = len(routes)  # Count the number of configured routes

    debug_print(f"[*] {Fore.LIGHTBLUE_EX}Listening on {ip}:{port} for Raw TCP data.\t{Fore.BLUE}[{route_count} Route(s)]", DLevel=1)
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server:
        server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server.bind((ip, port))
        server.listen(5)
        while True:
            client_sock, addr = server.accept()
            client_ip, client_port = addr
            debug_print(f"[+] Connection established from {client_ip}:{client_port} (Raw TCP)", DLevel=1)

            for route in routes:
                pipeline_cfg = resolve_pipeline(route["pipeline_id"], all_pipelines)
                destinations = resolve_destinations(route["destination_ids"], all_destinations)
                threading.Thread(
                    target=handle_raw_tcp_client_connection,
                    args=(client_sock, addr, pipeline_cfg, destinations),
                    daemon=True,
                ).start()
# End of handle_raw_tcp_client()
#------------------------------------------------------
#------------------------------------------------------
def handle_raw_udp_source(source_cfg, all_routes, all_destinations, all_pipelines):
    """
    Handles incoming raw data over UDP as a source.
    """
    ip = source_cfg.get("listen_ip", "0.0.0.0")
    port = source_cfg["listen_port"]

    # Resolve all routes for this source
    routes = resolve_routes(source_cfg["source_id"], all_routes)
    route_count = len(routes)

    debug_print(f"[*] {Fore.LIGHTBLUE_EX}Listening on {ip}:{port} for raw UDP data.\t\t{Fore.BLUE}[{route_count} Route]", DLevel=3)
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as server:
        server.bind((ip, port))
        while True:
            try:
                raw_data, addr = server.recvfrom(4096)
                client_ip, client_port = addr
                debug_print(f"[<] Received raw UDP data from {client_ip}:{client_port}: {raw_data.decode('utf-8')}", DLevel=3)

                for route in routes:
                    pipeline_cfg = resolve_pipeline(route["pipeline_id"], all_pipelines)
                    destinations = resolve_destinations(route["destination_ids"], all_destinations)

                    # Apply pipeline transformations
                    transformed = pipeline.apply_pipeline({"raw_data": raw_data.decode('utf-8')}, pipeline_cfg.get("steps", []))
                    encoded = json.dumps(transformed).encode('utf-8')

                    # Forward to destinations
                    if not forward_to_destinations(encoded, destinations):
                        write_to_cache(encoded, tag=source_cfg['name'])
                        debug_print(f"{Fore.RED}[!] Failed to forward raw UDP data, cached locally.", DLevel=0)
            except Exception as e:
                debug_print(f"[!] Error handling raw UDP data: {e}", DLevel=0)
# End of handle_raw_udp_source()
#------------------------------------------------------
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
            debug_print(f"[-] Establishing a socket to Splunk HEC: {url}", DLevel=2)
            return True
        else:
            debug_print(f"{Fore.RED}[!] Destination DOWN! Failed to send to Splunk HEC! URL:[{url}], Status Code:[{response.status_code}]", DLevel=0)
            return False
    except Exception as e:
        debug_print(f"[!] Error sending to Splunk HEC: {e}", DLevel=0)
        return False
# End of forward_to_splunk_hec()
#-------------------------------------------------------
#------------------------------------------------------
def forward_to_s3(data, bucket_name, region):
    """
    Forwards data to an AWS S3 bucket.
    """
    try:
        s3_client = boto3.client('s3', region_name=region)
        key = f"{uuid.uuid4()}.json"
        s3_client.put_object(Bucket=bucket_name, Key=key, Body=data)
        debug_print(f"[+] Successfully uploaded to S3 bucket: {bucket_name}, key: {key}", DLevel=3)
        return True
    except Exception as e:
        debug_print(f"[!] Failed to upload to S3 bucket:[{bucket_name}] -  Error:[{e}]", DLevel=0)
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
        debug_print(f"[+] Successfully uploaded to Azure Blob container: {container_name}", DLevel=3)
        return True
    except Exception as e:
        debug_print(f"[!] Failed to upload to Azure Blob container:[{container_name}] -  Error:[{e}]", DLevel=0)
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
        debug_print(f"[+] Successfully uploaded to GCS bucket: {bucket_name}", DLevel=3)
        return True
    except Exception as e:
        debug_print(f"[!] Failed to upload to GCS bucket:[{bucket_name}] - Error:[{e}]", DLevel=0)
        return False
# End of forward_to_gcs()
#------------------------------------------------------
#------------------------------------------------------
class PersistentTCPConnection:
    def __init__(self, ip, port):
        self.ip = ip
        self.port = port
        self.sock = None

    def connect(self):
        if self.sock is None:
            self.sock = socket.create_connection((self.ip, self.port), timeout=2)
            debug_print(f"[-] Established persistent connection to [{self.ip}:{self.port}]", DLevel=3)

    def send(self, data):
        try:
            self.connect()
            self.sock.sendall(data)
            debug_print(f"[-] Successfully sent data to TCP destination:[{self.ip}:{self.port}]", DLevel=3)
            return True  # Indicate success
        except Exception as e:
            debug_print(f"[!] Failed to send data to TCP destination:[{self.ip}:{self.port}] - Error:[{e}]", DLevel=0)
            self.close()
            return False  # Indicate failure

    def close(self):
        if self.sock:
            self.sock.close()
            self.sock = None
            debug_print(f"[-] Closed connection to {self.ip}:{self.port}", DLevel=3)
# End of PersistentTCPConnection()
#------------------------------------------------------
#------------------------------------------------------
def forward_to_tcp_udp(data, dest):
    """
    Forwards data to a raw TCP or UDP destination.
    """
    ip = dest['ip']
    port = dest['port']
    protocol = dest.get('protocol', 'tcp').lower()
    debug_print(f"[-] Forwarding data to destination: {ip}:{port} using protocol: {protocol}", DLevel=2)
    try:
        if protocol == 'tcp':
            tcp_connection = PersistentTCPConnection(dest['ip'], dest['port'])
            result = tcp_connection.send(data)
            return result  # Return the result of the send operation
        elif protocol == 'udp':
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
                sock.sendto(data, (ip, port))
                debug_print(f"[-] Successfully sent data to UDP destination {ip}:{port}", DLevel=1)
                return True  # Ensure success is returned
    except Exception as e:
        debug_print(f"[!] Destination DOWN! Failed to send data to protocol:[{protocol.upper()}] destination:[{ip}:{port}] - Error:[{e}]", DLevel=0)
        return False  # Return failure if an exception occurs
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
            debug_print(f"[-] Establishing a socket to Syslog TCP data to {ip}:{port}", DLevel=3)
        return True
    except Exception as e:
        debug_print(f"[!] Destination DOWN! Failed to send Syslog TCP data to [{ip}:{port}] - Error:[{e}]", DLevel=0)
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
            debug_print(f"[-] Establishing a socket to Syslog UDP data to {ip}:{port}", DLevel=3)
        return True
    except Exception as e:
        debug_print(f"[!] Destination DOWN! Failed to send Syslog UDP data to [{ip}:{port}] - Error:[{e}]", DLevel=0)
        return False
# End of forward_to_udp_syslog_dest()
#------------------------------------------------------
#------------------------------------------------------
def forward_to_destinations(data, destinations):
    """
    Forwards data to multiple destinations based on the configuration.
    """
    success = False  # Track if at least one forwarding attempt succeeds
    for dest in destinations:
        try:
            if 'ip' in dest and 'port' in dest:
                protocol = dest.get('protocol', 'tcp').lower()
                if protocol == 'syslog_udp':
                    result = forward_to_udp_syslog_dest(data, dest)
                elif protocol == 'syslog_tcp':
                    result = forward_to_tcp_syslog_dest(data, dest)
                else:
                    result = forward_to_tcp_udp(data, dest)
            elif 'bucket_name' in dest:
                if 'region' in dest:
                    result = forward_to_s3(data, dest['bucket_name'], dest['region'])
                else:
                    result = forward_to_gcs(data, dest['bucket_name'])
            elif 'container_name' in dest:
                result = forward_to_azure_blob(data, dest['container_name'], dest.get('connection_string'))
            elif 'url' in dest and 'token' in dest:
                result = forward_to_splunk_hec(data, dest['url'], dest['token'])
            else:
                result = False  # Unknown destination type

            success = result or success
            #debug_print(f"[-]XXXForwarding to destination {dest}: {'Success' if result else 'Failed'}", DLevel=1)
        except Exception as e:
            debug_print(f"{Fore.RED}[!] Failed to forward data to destination:[{dest}] - Error:[{e}]", DLevel=0)
    return success  # Return True if at least one forwarding attempt succeeded
# End of forward_to_destinations()
#------------------------------------------------------
#------------------------------------------------------
def resolve_routes(source_id, all_routes):
    """
    Resolves all route configurations for a given source ID.
    """
    return [route for route in all_routes if route["source_id"] == source_id]

def resolve_destinations(destination_ids, all_destinations):
    """
    Resolves destination configurations by their IDs.
    """
    return [dest for dest in all_destinations if dest["destination_id"] in destination_ids]

def resolve_pipeline(pipeline_id, all_pipelines):
    """
    Resolves a pipeline configuration by its ID.
    """
    for pipeline in all_pipelines:
        if pipeline["pipeline_id"] == pipeline_id: 
            return pipeline
    debug_print(f"{Fore.RED}[!] No pipeline found for pipeline ID: {pipeline_id}", DLevel=0)
    return None
# End of resolve_pipeline()
#------------------------------------------------------
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
            debug_print(f"[<] Received data from Splunk HEC: {Fore.LIGHTBLACK_EX}{raw_data}", DLevel=3)

            # Apply pipeline transformations
            transformed = pipeline.apply_pipeline(raw_data, pipeline_steps)
            encoded = json.dumps(transformed).encode('utf-8')

            # Forward to destinations
            if not forward_to_destinations(encoded, destinations):
                write_to_cache(encoded, tag=source_cfg['name'])
                debug_print(f"{Fore.RED}[!] Failed to forward data from Splunk HEC, cached locally.", DLevel=0)

            return jsonify({"status": "success"}), 200
        except Exception as e:
            debug_print(f"[!] Error processing Splunk HEC data: {e}", DLevel=0)
            return jsonify({"status": "error", "message": str(e)}), 500

    # Start the Flask app
    debug_print(f"[*] Listenig on {ip}:{port} for {Fore.GREEN}Splunk HEC{Fore.GREEN} data (using Flask)", DLevel=1)
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
                debug_print(f"{Fore.RED}[!] No files found in S3 bucket: {bucket_name}", DLevel=0)
                debug_print(f"[*] Waiting for {polling_interval} seconds before next polling attempt.", DLevel=2)
                time.sleep(polling_interval)
                continue

            for obj in response['Contents']:
                key = obj['Key']
                if key in processed_keys:
                    continue

                debug_print(f"[+] Processing file from S3 bucket: {bucket_name}, key: {key}", DLevel=3)
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
                        debug_print(f"{Fore.RED}[!] Failed to forward data from S3 key:[{key}], cached locally.", DLevel=0)

                    # Mark the file as processed
                    processed_keys.add(key)

                    # Optionally delete the file after processing
                    if delete_after_processing:
                        s3_client.delete_object(Bucket=bucket_name, Key=key)
                        debug_print(f"[+] Deleted file from S3 bucket:[{bucket_name}], key:[{key}]", DLevel=3)

                except Exception as e:
                    debug_print(f"[!] Error processing file from S3 bucket:[{bucket_name}], key:[{key}], Error:[{e}]", DLevel=0)
        except Exception as e:
            debug_print(f"[!] Error polling S3 bucket:[{bucket_name}] - Error:[{e}]", DLevel=0)
        # Wait for the next polling interval
        debug_print(f"[*] Waiting for {polling_interval} seconds before next polling attempt.", DLevel=2)
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

                debug_print(f"[+] Processing file from GCP bucket: {bucket_name}, blob: {blob.name}", DLevel=3)
                try:
                    # Fetch the file content
                    raw_data = blob.download_as_text()

                    # Apply pipeline transformations
                    transformed = pipeline.apply_pipeline({"file_content": raw_data}, pipeline_steps)
                    encoded = transformed["file_content"].encode('utf-8')

                    # Forward to destinations
                    if not forward_to_destinations(encoded, destinations):
                        write_to_cache(encoded, tag=source_cfg['name'])
                        debug_print(f"{Fore.RED}[!] Failed to forward data from GCP blob:[{blob.name}], cached locally.", DLevel=0)

                    # Mark the blob as processed
                    processed_blobs.add(blob.name)

                except Exception as e:
                    debug_print(f"[!] Error processing blob from GCP bucket:[{bucket_name}], Blob:[{blob.name}], Error:[{e}]", DLevel=0)
        except Exception as e:
            debug_print(f"[!] Error polling GCP bucket:[{bucket_name}] - Error:[{e}]", DLevel=0)
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

                debug_print(f"[+] Processing file from Azure Blob container: {container_name}, blob: {blob.name}", DLevel=3)
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
                        debug_print(f"{Fore.RED}[!] Failed to forward data from Azure blob:[{blob.name}], cached locally.", DLevel=0)

                    # Mark the blob as processed
                    processed_blobs.add(blob.name)

                except Exception as e:
                    debug_print(f"{Fore.RED}[!] Error processing blob from Azure Blob container:[{container_name}], Blob:[{blob.name}] , Error:[{e}]", DLevel=0)
                    debug_print(f"[!] Error processing blob from Azure Blob container:[{container_name}], Blob:[{blob.name}] , Error:[{e}]", DLevel=0)
        except Exception as e:
            debug_print(f"[!] Error polling Azure Blob container:[{container_name}] - Error:[{e}]", DLevel=0)

        # Wait for the next polling interval
        time.sleep(polling_interval)
# End of handle_azure_blob_collector_source()
#-------------------------------------------------------
#------------------------------------------------------
def handle_syslog_udp_source(source_cfg, routes, all_destinations, all_pipelines):
    """
    Handles incoming Syslog messages over UDP as a source.
    Listens for Syslog messages over UDP and processes them.
    Logs incoming messages and forwards them to destinations.
    """
    ip = source_cfg.get('listen_ip', '0.0.0.0')
    port = source_cfg['listen_port']
    route_count = len(routes)  # Count the number of configured routes

    debug_print(f"[*] {Fore.LIGHTBLUE_EX}Listening on {ip}:{port} for Syslog UDP messages.\t{Fore.BLUE}[{route_count} Route]", DLevel=1)
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as server:
        server.bind((ip, port))
        while True:
            try:
                raw_data, addr = server.recvfrom(4096)
                client_ip, client_port = addr
                debug_print(f"[<] Received Syslog UDP message from {client_ip}:{client_port}: {Fore.LIGHTBLACK_EX}{raw_data.decode('utf-8')}", DLevel=3)

                for route in routes:
                    pipeline_cfg = resolve_pipeline(route["pipeline_id"], all_pipelines)
                    destinations = resolve_destinations(route["destination_ids"], all_destinations)

                    # Apply pipeline transformations
                    transformed = pipeline.apply_pipeline({"raw_data": raw_data.decode('utf-8')}, pipeline_cfg.get("steps", []))
                    encoded = json.dumps(transformed).encode('utf-8')

                    # Forward to destinations
                    if not forward_to_destinations(encoded, destinations):
                        write_to_cache(encoded, tag=source_cfg['name'])
                        debug_print(f"{Fore.RED}[!] Failed to forward Syslog UDP message, cached locally.", DLevel=0)
            except Exception as e:
                debug_print(f"[!] Error handling Syslog UDP message:[{e}]", DLevel=0)
# End of handle_syslog_udp_source()

#------------------------------------------------------
def handle_syslog_tcp_source(source_cfg, routes, all_destinations, all_pipelines):
    """
    Handles incoming Syslog messages over TCP as a source.
    Listens for Syslog messages over TCP and spawns a thread for each client connection.
    """
    ip = source_cfg.get('listen_ip', '0.0.0.0')
    port = source_cfg['listen_port']
    route_count = len(routes)  # Count the number of configured routes

    debug_print(f"[*] {Fore.LIGHTBLUE_EX}Listening on {ip}:{port} for {Fore.GREEN}Syslog TCP messages.\t{Fore.BLUE}[{route_count} Route]", DLevel=1)
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server:
        server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server.bind((ip, port))
        server.listen(5)
        while True:
            client_sock, addr = server.accept()
            for route in routes:
                pipeline_cfg = resolve_pipeline(route["pipeline_id"], all_pipelines)
                destinations = resolve_destinations(route["destination_ids"], all_destinations)
                threading.Thread(
                    target=handle_syslog_tcp_client,
                    args=(client_sock, addr, pipeline_cfg, destinations),
                    daemon=True,
                ).start()
# End of handle_syslog_tcp_source()

#------------------------------------------------------
def handle_syslog_tcp_client(client_sock, addr, pipeline_cfg, destinations):
    """
    Handles a single Syslog TCP client connection.
    Handles individual TCP client connections, processes messages, and forwards them to destinations.
    """
    client_ip, client_port = addr
    debug_print(f"[+] Connection from {client_ip}:{client_port} (Syslog TCP)", DLevel=1)
    pipeline_steps = pipeline_cfg.get('pipeline', [])

    try:
        while True:
            raw_data = client_sock.recv(4096)
            if not raw_data:
                break
            debug_print(f"[<] Received Syslog TCP message: {Fore.LIGHTBLACK_EX}{raw_data.decode('utf-8')}", DLevel=3)

            # Apply pipeline transformations
            transformed = pipeline.apply_pipeline({"raw_data": raw_data.decode('utf-8')}, pipeline_steps)
            encoded = json.dumps(transformed).encode('utf-8')

            # Forward to destinations
            if not forward_to_destinations(encoded, destinations):
                write_to_cache(encoded, tag=pipeline_cfg['name'])
                debug_print(f"{Fore.RED}[!] Failed to forward Syslog TCP message, cached locally.", DLevel=0)
    except Exception as e:
        debug_print(f"[!] Error handling Syslog TCP client:[{e}]", DLevel=0)
    finally:
        client_sock.close()
        debug_print(f"[-] Disconnected from [{client_ip}:{client_port}]", DLevel=1)
# End of handle_syslog_tcp_client()

#------------------------------------------------------
def handle_null_route(data, source_id):
    """
    Handles data for sources with no configured routes.
    Acts as a sink (similar to /dev/null) and discards the data.
    """
    debug_print(f"{Fore.YELLOW}[!] Data from source ID: {source_id} discarded (null route).", DLevel=1)
# End of handle_null_route()

#------------------------------------------------------
def start_sources_listeners(source_cfg, all_routes, all_destinations, all_pipelines):
    """
    Starts a listener for the specified source configuration.
    """
    source_id = source_cfg['source_id']  # Use 'source_id' from sources.yaml
    protocol = source_cfg.get('protocol', '').lower()  # Dynamically determine the protocol

    # Resolve all routes for this source
    routes = [route for route in all_routes if route["source_id"] == source_id]
    route_count = len(routes)

    if route_count == 0:
        debug_print(f"{Fore.RED}[!] Source ID: {source_id} has no configured routes.", DLevel=0)
        return  # Skip this source if no routes are assigned

    # Dynamically determine the appropriate handler based on the protocol
    if protocol == 'udp' and 'raw' in source_id.lower():
        debug_print(f"[*] Starting Raw UDP handler for source ID: {source_id}", DLevel=2)
        threading.Thread(target=handle_raw_udp_source, args=(source_cfg, routes, all_destinations, all_pipelines), daemon=True).start()
    elif protocol == 'tcp' and 'raw' in source_id.lower():
        debug_print(f"[*] Starting Raw TCP handler for source ID: {source_id}", DLevel=2)
        threading.Thread(target=handle_raw_tcp_client, args=(source_cfg, routes, all_destinations, all_pipelines), daemon=True).start()
    else:
        debug_print(f"{Fore.RED}[!] Unknown protocol '{protocol}' for source ID: {source_id}. Skipping.", DLevel=0)
# End of start_sources_listeners()

#------------------------------------------------------
class ConfigFileChangeHandler(FileSystemEventHandler):
    """
    Handles file system events for configuration files.
    """
    def __init__(self, config_files):
        self.config_files = config_files

    def on_modified(self, event):
        # Check if the modified file is in the list of monitored files
        if event.src_path in self.config_files:
            debug_print(f"{Fore.YELLOW}[!] Configuration file updated: {event.src_path}", DLevel=1)
            try:
                # Reload the updated configuration file
                if "sources.yaml" in event.src_path:
                    CONFIG["sources"] = load_yaml("sources.yaml").get("sources", [])
                    debug_print(f"{Fore.GREEN}[+] Reloaded sources.yaml successfully.", DLevel=1)
                elif "destinations.yaml" in event.src_path:
                    CONFIG["destinations"] = load_yaml("destinations.yaml").get("destinations", [])
                    debug_print(f"{Fore.GREEN}[+] Reloaded destinations.yaml successfully.", DLevel=1)
                elif "pipelines.yaml" in event.src_path:
                    CONFIG["pipelines"] = load_yaml("pipelines.yaml").get("pipelines", [])
                    debug_print(f"{Fore.GREEN}[+] Reloaded pipelines.yaml successfully.", DLevel=1)
                elif "routes.yaml" in event.src_path:
                    CONFIG["routes"] = load_yaml("routes.yaml").get("routes", [])
                    debug_print(f"{Fore.GREEN}[+] Reloaded routes.yaml successfully.", DLevel=1)

                # Notify the system to apply the updated configuration
                apply_updated_configuration()

            except Exception as e:
                debug_print(f"{Fore.RED}[!] Failed to reload configuration: {e}", DLevel=0)

def apply_updated_configuration():
    """
    Applies the updated configuration dynamically.
    Updates routes, pipelines, and destinations in the running system.
    """
    debug_print(f"{Fore.CYAN}[*] Applying updated configuration...", DLevel=1)

    # Update routes and pipelines
    routes = CONFIG.get("routes", [])
    pipelines = CONFIG.get("pipelines", [])
    destinations = CONFIG.get("destinations", [])

    # Restart listeners for sources if necessary
    sources = CONFIG.get("sources", [])
    for source in sources:
        if not source.get("enabled", True):
            debug_print(f"{Fore.LIGHTBLACK_EX}[-] Skipping disabled source: {source['name']}", DLevel=1)
            continue

        threading.Thread(
            target=start_sources_listeners,
            args=(source, routes, destinations, pipelines),
            daemon=True,
        ).start()

    debug_print(f"{Fore.GREEN}[+] Updated configuration applied successfully.", DLevel=1)
# End of apply_updated_configuration()
#------------------------------------------------------
def main():
    global CONFIG
    CONFIG = load_config()
    if not CONFIG:
        debug_print(f"{Fore.RED}[!] Failed to load configuration. Exiting.", DLevel=0)
        sys.exit(1)

    validate_config()
    debug_print(f"{Fore.GREEN}[+] Configuration loaded successfully with no errors.", DLevel=1)

    # Start the monitoring thread for cached data forwarding
    destinations = CONFIG.get("destinations", [])
    start_monitoring_thread(destinations)

    # Start listeners for sources
    sources = CONFIG.get("sources", [])
    routes = CONFIG.get("routes", [])
    pipelines = CONFIG.get("pipelines", [])
    for source in sources:
        if not source.get("enabled", True):
            debug_print(f"{Fore.LIGHTBLACK_EX}[-] Skipping disabled source: {source['name']}", DLevel=1)
            continue

        threading.Thread(
            target=start_sources_listeners,
            args=(source, routes, destinations, pipelines),
            daemon=True,
        ).start()

    debug_print("[*] Proxy is running. Press Ctrl+C to exit.", DLevel=1)
    threading.Thread(target=start_web_interface, daemon=True).start()
    while True:
        time.sleep(1)
# End of main()

#===================================================
from utils import start_config_watcher

if __name__ == "__main__":
    # Start the configuration file watcher
    start_config_watcher()

    # Start the main application logic
    main()
#===================================================