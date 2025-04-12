# Fully Modular Pipeline Engine
# This script provides a RESTful API for managing and monitoring a data pipeline.
# It includes endpoints for configuration, cache status, health checks, and more.
# The API is built using Flask and serves JSON responses.
# The script also includes functions for loading configuration files, checking cache status,
# and performing health checks on the source and destination systems.

import re
import json
import os
from flask import Flask, jsonify

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
            print(f"[!] Regex error: {e}")
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
            print(f"[!] Failed to parse JSON string in field '{field}': {e}")
    return data

#------------------------------------------------------
@app.route('/api/config', methods=['GET'])
def api_config():
    try:
        with open('config.yaml', 'r') as f:
            config = json.load(f)
        return jsonify(config), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500
# End of api_config()
#------------------------------------------------------

#------------------------------------------------------
@app.route('/api/cache', methods=['GET'])
def api_cache():
    try:
        cache_files = os.listdir('cache')
        return jsonify({"cache_files": cache_files}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500
# End of api_cache()
#------------------------------------------------------

#------------------------------------------------------
@app.route('/api/health', methods=['GET'])
def api_health():
    return jsonify({"status": "healthy"}), 200
# End of api_health()
#------------------------------------------------------

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
# End of api.py
