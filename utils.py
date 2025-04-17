#Module: utils.py

import os
import yaml
import logging
import socket
import signal
import traceback
from colorama import Fore, Style
from colorama import init
init(autoreset=True)  # Initialize colorama for automatic reset of colors
import sys
import uuid
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
import threading
import time
from queue import Queue

OSPP_DEAULT_LOG_FILE = 'ospp.log'

# Global debug level
DEBUG_LEVEL = 3  # Default to verbose output

# Global cache queues for each destination
cache_queues = {}

# Global configuration dictionary
CONFIG = {
    "sources": [],
    "destinations": [],
    "pipelines": [],
    "routes": []
}

#--------------------------------------------------------------
def debug_print(message, DLevel=1):
    """
    Prints debug messages based on the current debug level.
    :param message: The message to print.
    :param DLevel: The debug level required to print this message.
    """
    if DEBUG_LEVEL >= DLevel:
        print(message, file=sys.stdout, flush=True)  # Explicitly write to sys.stdout
#---------------------------------------------------------------     

#-------FOR TESTING ONLY-------------------
import subprocess

def create_ip_alias(interface_name, alias_ip_address, alias_subnet_mask):
    """
    Creates an IP alias on the specified network interface.
    """
    try:
        debug_print(f"[+] Creating IP alias: {alias_ip_address} on interface: {interface_name}", DLevel=2)
        os.system(f"ifconfig {interface_name} alias {alias_ip_address} {alias_subnet_mask}")
        debug_print(f"[+] Successfully created IP alias: {alias_ip_address}", DLevel=1)
    except Exception as e:
        debug_print(f"[!] Failed to create IP alias: {alias_ip_address} - Error: {e}", DLevel=0)

def delete_ip_alias(interface_name, alias_ip_address):
    """
    Deletes an IP alias from the specified network interface.
    """
    try:
        debug_print(f"[-] Deleting IP alias: {alias_ip_address} from interface: {interface_name}", DLevel=2)
        os.system(f"ifconfig {interface_name} -alias {alias_ip_address}")
        debug_print(f"[-] Successfully deleted IP alias: {alias_ip_address}", DLevel=1)
    except Exception as e:
        debug_print(f"[!] Failed to delete IP alias: {alias_ip_address} - Error: {e}", DLevel=0)
#-----FOR TESTING ONLY-------------------

#--------------------------------------------------------------
#Function to setup signal traps. We need to know when user hit CTRL-C
def signal_handler(sig, frame):
        print('You pressed Ctrl+C!')
        print("\nSIGINT received. Shutting down gracefully...")
        logger.info("SIGINT received. Shutting down gracefully...")
        sockets = []  # List to store all socket connections
        for s in sockets:
            try:
                s.shutdown(socket.SHUT_RDWR)  # Disable further sends and receives
                s.close()
            except OSError as e:
             print(f"Error closing socket: {e}")

        sys.exit(0)

    #singal.pause()
    #return
#end of setup_signal_handling():
#------------------------------------------------------------------------------
#--------------------------------------------------------------
# Set up logging configuration
def setup_logging():
    """
    Sets up logging for the application.
    """
    try:
        debug_print("[*] Setting up logging configuration...", DLevel=2)
        # Add logging setup logic here if needed
        debug_print("[+] Logging configuration set up successfully.", DLevel=1)
    except Exception as e:
        debug_print(f"[!] Failed to set up logging configuration - Error: {e}", DLevel=0)
#End of setup_logging()
#--------------------------------------------------------


logger = setup_logging()  # Set up logging configuration

#--------------------------------------------------------------
# Function to print error details
def print_error_details(message, exception=None):
    """
    Prints detailed error messages.
    """
    debug_print(f"{Fore.RED}{message}", DLevel=0)
    if exception:
        debug_print(f"{Fore.RED}Exception: {exception}", DLevel=0)
#End of print_error_details()
# -------------------------------------------------------------

#--------------------------------------------------------------
def DLevel(DEBUG_LEVEL=0):
    import sys
    import sys
    frame = sys._getframe(1)  # Caller frame
    func_name = frame.f_code.co_name
    line_no = frame.f_lineno
    #return f"[D:{DEBUG_LEVEL}] Function:[{func_name}] Line:[{line_no}]"
    data =[]
    """Set the debug level"""
    if DEBUG_LEVEL >= 5:
        return f'[D:{Fore.LIGHTRED_EX}{DEBUG_LEVEL}{Fore.RESET}][Func:{func_name}]' #, end=line:[{sys._getframe().f_lineno}]"
    
    if DEBUG_LEVEL >= 4:
        return f'[D:{Fore.LIGHTRED_EX}{DEBUG_LEVEL}{Fore.RESET}]'
    if DEBUG_LEVEL >= 3:
        return f'[D:{Fore.LIGHTRED_EX}{DEBUG_LEVEL}{Fore.RESET}]'
    if DEBUG_LEVEL == 2:
        return f'[D:{Fore.LIGHTRED_EX}{DEBUG_LEVEL}{Fore.RESET}]'
    if DEBUG_LEVEL == 1:
        return f'[D:{Fore.LIGHTRED_EX}{DEBUG_LEVEL}{Fore.RESET}]'
    
#End of DLevel()
#--------------------------------------------------------------

   

#--------------------------------------------------------------
# Function to load YAML configuration files
#import json    #if there is a neeed to dump dict to json

def load_yaml(file_path=""):
    try:
        with open(file_path, "r") as f:
            return yaml.safe_load(f)
    except Exception as e:
        print(f"{Fore.RED}[!] Error loading {file_path}: {e}")
        return None
#End of load_yaml()
#--------------------------------------------------------------
#--------------------------------------------------------------
def handle_invalid_config(message):
    """
    Handles invalid configuration by prompting the user to decide whether to continue or terminate.
    CONTINUE: Allows the program to proceed without exiting.
    TERMINATE: Forcefully terminates the entire program using os._exit().
    """
    debug_print(f"{Fore.RED}[!] {message}", DLevel=0)
    while True:
        user_input = input(f"{Fore.YELLOW}[?] Invalid configuration detected. Do you want to CONTINUE or TERMINATE the program? (continue/terminate): ").strip().lower()
        if user_input in ["continue", "c"]:
            debug_print(f"{Fore.YELLOW}[!] Continuing execution despite invalid configuration.", DLevel=0)
            return  # Allow the program to proceed
        elif user_input in ["terminate", "t"]:
            debug_print(f"{Fore.RED}[!] Terminating the program as per user request.", DLevel=0)
            print("\n")
            os._exit(1)  # Forcefully terminate the entire program
        else:
            print(f"{Fore.RED}[!] Invalid input. Please enter 'continue' or 'terminate'.")
#End of handle_invalid_config()
#--------------------------------------------------------------
#--------------------------------------------------------------
def validate_config():
    """
    Validates the configuration files (sources.yaml, destinations.yaml, etc.).
    Prompts the user to decide whether to terminate or continue if invalid configurations are encountered.
    """
    debug_print("[*] Starting configuration validation...", DLevel=1)
    try:
        sources = load_yaml("sources.yaml")
        destinations = load_yaml("destinations.yaml")
        pipelines = load_yaml("pipelines.yaml")
        routes = load_yaml("routes.yaml")

        if not sources or not destinations or not pipelines or not routes:
            debug_print(f"{Fore.RED}[!] Failed to load one or more configuration files.", DLevel=0)
            handle_invalid_config("Configuration files are missing or invalid.")

        # Validate sources.yaml
        source_ids = set()
        line = 0
        for source in sources.get("sources", []):
            line += 1
            if "source_id" not in source:
                debug_print(f"{Fore.RED}[!] Missing 'source_id' in sources.yaml: {line}:{source}", DLevel=0)
                handle_invalid_config("Invalid 'sources.yaml' configuration.")
            else:
                source_ids.add(source["source_id"])

        # Validate destinations.yaml
        destination_ids = set()
        line = 0
        for dest in destinations.get("destinations", []):
            line += 1
            if "destination_id" not in dest:
                debug_print(f"{Fore.RED}[!] Missing 'destination_id' in destinations.yaml: {line}:{dest}", DLevel=0)
                handle_invalid_config("Invalid 'destinations.yaml' configuration.")
            else:
                destination_ids.add(dest["destination_id"])

        # Validate pipelines.yaml
        pipeline_ids = set()
        line = 0
        for pipeline in pipelines.get("pipelines", []):
            line += 1
            if "pipeline_id" not in pipeline:
                debug_print(f"{Fore.RED}[!] Missing 'pipeline_id' in pipelines.yaml: {line}:{pipeline}", DLevel=0)
                handle_invalid_config("Invalid 'pipelines.yaml' configuration.")
            else:
                pipeline_ids.add(pipeline["pipeline_id"])

        # Validate routes.yaml
        line = 0
        for route in routes.get("routes", []):
            line += 1
            if "source_id" not in route:
                debug_print(f"{Fore.RED}[!] Missing 'source_id' in routes.yaml: {line}:{route}", DLevel=0)
                handle_invalid_config("Invalid 'routes.yaml' configuration.")
            elif route["source_id"] not in source_ids:
                debug_print(f"{Fore.RED}[!] Invalid 'source_id' in routes.yaml: {line}:{route['source_id']}", DLevel=0)
                handle_invalid_config("Invalid 'routes.yaml' configuration.")

            if "pipeline_id" not in route:
                debug_print(f"{Fore.RED}[!] Missing 'pipeline_id' in routes.yaml: {line}:{route}", DLevel=0)
                handle_invalid_config("Invalid 'routes.yaml' configuration.")
            elif route["pipeline_id"] not in pipeline_ids:
                debug_print(f"{Fore.RED}[!] Invalid 'pipeline_id' in routes.yaml: {line}:{route['pipeline_id']}", DLevel=0)
                handle_invalid_config("Invalid 'routes.yaml' configuration.")

            if "destination_ids" not in route:
                debug_print(f"{Fore.RED}[!] Missing 'destination_ids' in routes.yaml: {line}:{route}", DLevel=0)
                handle_invalid_config("Invalid 'routes.yaml' configuration.")
            else:
                for dest_id in route["destination_ids"]:
                    if dest_id not in destination_ids:
                        debug_print(f"{Fore.RED}[!] Invalid 'destination_id' in routes.yaml: {line}:{dest_id}", DLevel=0)
                        handle_invalid_config("Invalid 'routes.yaml' configuration.")

        debug_print("[+] Configuration validation completed successfully.", DLevel=1)
    except Exception as e:
        debug_print(f"[!] Configuration validation failed - Error: {e}", DLevel=0)
        handle_invalid_config("Unexpected error during configuration validation.")
# End of validate_config()
#--------------------------------------------------------------
#--------------------------------------------------------------
def write_to_cache(data, destination_id):
    """
    Writes data to a cache queue for the specified destination.
    """
    try:
        if destination_id not in cache_queues:
            cache_queues[destination_id] = Queue()

        cache_queues[destination_id].put(data)
        debug_print(f"{Fore.YELLOW}[+] Cached data for destination: {destination_id}. Queue size: {cache_queues[destination_id].qsize()}", DLevel=3)
    except Exception as e:
        debug_print(f"{Fore.RED}[!] Failed to write data to cache for destination: {destination_id} - Error: {e}", DLevel=0)
#End of write_to_cache()        
#--------------------------------------------------------------
#--------------------------------------------------------------
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
                # Clear the old configuration
                CONFIG["sources"] = []
                CONFIG["destinations"] = []
                CONFIG["pipelines"] = []
                CONFIG["routes"] = []

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

                # Apply the updated configuration dynamically
                apply_updated_configuration()

            except Exception as e:
                debug_print(f"{Fore.RED}[!] Failed to reload configuration: {e}", DLevel=0)
#End of ConfigFileChangeHandler()
#--------------------------------------------------------------
#--------------------------------------------------------------
def start_config_watcher():
    """
    Starts a file watcher to monitor configuration files for changes.
    Runs the watcher in a separate thread to avoid blocking the main thread.
    """
    config_files = [
        os.path.abspath("sources.yaml"),
        os.path.abspath("destinations.yaml"),
        os.path.abspath("pipelines.yaml"),
        os.path.abspath("routes.yaml"),
    ]

    # Log the files being monitored based on the debug level
    debug_print(f"{Fore.CYAN}[*] Monitoring the following configuration files:", DLevel=2)
    for config_file in config_files:
        debug_print(f"{Fore.GREEN}    - {config_file}", DLevel=2)

    event_handler = ConfigFileChangeHandler(config_files)
    observer = Observer()
    for config_file in config_files:
        observer.schedule(event_handler, path=os.path.dirname(config_file), recursive=False)

    def run_observer():
        observer.start()
        debug_print(f"{Fore.CYAN}[*] Configuration file watcher started.", DLevel=1)
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            observer.stop()
            observer.join()
            debug_print(f"{Fore.RED}[!] Configuration file watcher stopped.", DLevel=1)

    # Run the observer in a separate thread
    threading.Thread(target=run_observer, daemon=True).start()
# End of start_config_watcher()
# --------------------------------------------------------------
#--------------------------------------------------------------
def is_destination_available(destination_id, destinations):
    """
    Checks if the specified destination is available by attempting to open a socket connection.
    """
    for destination in destinations:
        if destination["destination_id"] == destination_id:
            ip = destination.get("ip")
            port = destination.get("port")

            # Ensure both IP and port are provided
            if not ip or not port:
                debug_print(f"{Fore.RED}[!] Destination {destination_id} is missing 'ip' or 'port' in configuration.", DLevel=0)
                return False

            try:
                debug_print(f"{Fore.CYAN}[*] Checking availability of destination: {destination_id} ({ip}:{port})", DLevel=2)
                with socket.create_connection((ip, port), timeout=5) as sock:
                    debug_print(f"{Fore.GREEN}[+] Destination {destination_id} is available.", DLevel=2)
                    return True
            except (socket.timeout, socket.error) as e:
                debug_print(f"{Fore.RED}[!] Destination {destination_id} is unavailable: {e}", DLevel=1)
                return False

    debug_print(f"{Fore.RED}[!] Destination {destination_id} not found in configuration.", DLevel=0)
    return False
# End of is_destination_available()
#--------------------------------------------------------------
#--------------------------------------------------------------
def forward_to_destination(data, destination_id):
    """
    Forwards data to the specified destination.
    """
    try:
        # Implement the logic to forward data to the destination
        debug_print(f"{Fore.CYAN}[*] Forwarding data to destination: {destination_id}", DLevel=2)
        return True  # Replace with actual forwarding logic
    except Exception as e:
        debug_print(f"{Fore.RED}[!] Failed to forward data to destination: {destination_id} - Error: {e}", DLevel=0)
        return False
#End of forward_to_destination()
#--------------------------------------------------------------
#--------------------------------------------------------------    
def monitor_and_forward_cache(destinations):
    """
    Monitors the status of destinations and forwards cached data when they become available.
    """
    while True:
        try:
            for destination_id, queue in list(cache_queues.items()):
                if queue.empty():
                    continue

                # Check if the destination is available
                if is_destination_available(destination_id, destinations):
                    debug_print(f"{Fore.GREEN}[+] Destination {destination_id} is available. Forwarding cached data...", DLevel=2)

                    while not queue.empty():
                        data = queue.get()
                        if not forward_to_destination(data, destination_id):
                            # If forwarding fails, re-add the data to the queue
                            queue.put(data)
                            debug_print(f"{Fore.RED}[!] Failed to forward data to destination: {destination_id}. Re-queued data.", DLevel=0)
                            break
                        else:
                            debug_print(f"{Fore.GREEN}[+] Successfully forwarded cached data to destination: {destination_id}.", DLevel=2)
        except Exception as e:
            debug_print(f"{Fore.RED}[!] Error while monitoring destinations: {e}", DLevel=0)

        time.sleep(10)  # Check every 10 seconds
#End of monitor_and_forward_cache()
#--------------------------------------------------------------
#--------------------------------------------------------------
def start_monitoring_thread(destinations):
    """
    Starts a background thread to monitor destinations and forward cached data.
    """
    threading.Thread(target=monitor_and_forward_cache, args=(destinations,), daemon=True).start()
    debug_print(f"{Fore.CYAN}[*] Started monitoring thread for cached data forwarding.", DLevel=1)
#End of start_monitoring_thread()
#--------------------------------------------------------------
def apply_updated_configuration():
    """
    Applies the updated configuration dynamically.
    Reconnects to down destinations and updates routes and pipelines.
    """
    debug_print(f"{Fore.CYAN}[*] Applying updated configuration...", DLevel=1)

    # Reconnect to down destinations
    destinations = CONFIG.get("destinations", [])
    for destination in destinations:
        destination_id = destination.get("destination_id")
        if not is_destination_available(destination_id, destinations):
            debug_print(f"{Fore.YELLOW}[!] Attempting to reconnect to destination: {destination_id}", DLevel=1)
            # Attempt to reconnect (e.g., open a socket or reinitialize connection)
            # This logic can be implemented in `is_destination_available` or elsewhere

    # Update routes and pipelines
    routes = CONFIG.get("routes", [])
    pipelines = CONFIG.get("pipelines", [])
    debug_print(f"{Fore.GREEN}[+] Updated routes and pipelines applied successfully.", DLevel=1)

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
# End of apply_updated_configuration()

def apply_updated_routes():
    """
    Applies the updated routes dynamically to the running system.
    """
    debug_print(f"{Fore.CYAN}[*] Applying updated routes...", DLevel=1)

    # Get the updated routes and destinations
    routes = CONFIG.get("routes", [])
    destinations = CONFIG.get("destinations", [])
    pipelines = CONFIG.get("pipelines", [])

    # Restart listeners for sources with updated routes
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

    debug_print(f"{Fore.GREEN}[+] Updated routes applied successfully.", DLevel=1)
# End of apply_updated_routes()
