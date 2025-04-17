# Fully Modular Pipeline Engine
# This script provides a RESTful API for managing and monitoring a data pipeline.
# It includes endpoints for configuration, cache status, health checks, and more.
# The API is built using Flask and serves JSON responses.
# The script also includes functions for loading configuration files, checking cache status,
# and performing health checks on the source and destination systems.

import re
import json
import os
from flask import Flask, request, jsonify
from utils import debug_print  # Import debug_print from utils.py

app = Flask(__name__)

def apply_pipeline(data: dict, steps: list) -> dict:
    for step in steps:
        t = step.get('type')
        if t == 'regex_replace':
            data = regex_replace(data, step)
        elif t == 'uppercase_field':
            data = uppercase_field(data, step)
        elif t == 'parse_json_string_field':
            data = parse_json_string_field(data, step)
    return data

def regex_replace(data, step):
    field = step.get("field")
    pattern = step.get("pattern")
    replacement = step.get("replacement", "")
    value = data.get(field, "")
    if isinstance(value, str):
        try:
            data[field] = re.sub(pattern, replacement, value, flags=re.IGNORECASE)
        except re.error as e:
            debug_print(f"[!] Regex error: {e}", DLevel=0)
    return data

def uppercase_field(data, step):
    field = step.get("field")
    if field in data and isinstance(data[field], str):
        data[field] = data[field].upper()
    return data

def parse_json_string_field(data, step):
    field = step.get("field")
    if field in data and isinstance(data[field], str):
        try:
            data[field] = json.loads(data[field])
        except Exception as e:
            debug_print(f"[!] Failed to parse JSON string in field '{field}': {e}", DLevel=0)
    return data

#------------------------------------------------------
@app.route('/api/config', methods=['GET'])
def api_config():
    try:
        with open('config.yaml', 'r') as f:
            config = json.load(f)
        return jsonify(config), 200
    except Exception as e:
        debug_print(f"[!] Error loading config.yaml: {e}", DLevel=0)
        return jsonify({"error": str(e)}), 500
# End of api_config()
#------------------------------------------------------

#------------------------------------------------------
@app.route('/api/cache', methods=['GET'])
def api_cache():
    try:
        cache_files = os.listdir('cache')
        debug_print(f"[+] Retrieved cache files: {cache_files}", DLevel=2)
        return jsonify({"cache_files": cache_files}), 200
    except Exception as e:
        debug_print(f"[!] Error retrieving cache files: {e}", DLevel=0)
        return jsonify({"error": str(e)}), 500
# End of api_cache()
#------------------------------------------------------

#------------------------------------------------------
@app.route('/api/health', methods=['GET'])
def api_health():
    debug_print("[+] Health check endpoint accessed.", DLevel=2)
    return jsonify({"status": "healthy"}), 200
# End of api_health()
#------------------------------------------------------

@app.route('/process', methods=['POST'])
def process_data():
    """
    API endpoint to process incoming data.
    """
    debug_print("[>] Received request at /process", DLevel=2)
    try:
        data = request.json
        debug_print(f"[>] Processing data: {data}", DLevel=3)
        # Process the data (e.g., apply a pipeline)
        result = {"status": "success", "processed_data": data}
        debug_print(f"[<] Successfully processed data: {result}", DLevel=2)
        return jsonify(result), 200
    except Exception as e:
        debug_print(f"[!] Error processing data: {e}", DLevel=0)
        return jsonify({"status": "error", "message": str(e)}), 500

if __name__ == '__main__':
    debug_print("[*] Starting API server...", DLevel=1)
    app.run(host='0.0.0.0', port=5000)
# End of api.py
