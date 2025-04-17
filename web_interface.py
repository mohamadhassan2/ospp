#Module: web_interface.py

from flask import Flask, logging, request, jsonify
import yaml
import os

CONFIG_FILE = 'config.yaml'
FLASK_PORT = 5050
OSPP_DEAULT_LOG_FILE = 'ospp.log'


from utils import setup_logging, print_error_details, debug_print  # Import debug_print from utils.py

# Flask app for the backend API
app = Flask(__name__)


# --- Route to get the configuration ---
@app.route("/api/config", methods=["GET"])
def get_config():
    """
    Fetch the current configuration from the config.yaml file.
    Returns the configuration as a JSON response.
    """
    try:
        debug_print("[>] Fetching configuration from config.yaml", DLevel=2)
        with open(CONFIG_FILE, "r") as f:
            config_content = yaml.safe_load(f)
        debug_print("[+] Successfully fetched configuration", DLevel=2)
        return jsonify(config_content), 200
    except Exception as e:
        debug_print(f"[!] Error loading configuration: {e}", DLevel=0)
        return jsonify({"error": f"Error loading configuration: {e}"}), 500
# --- End of get_config ---
#-------------------------------------------------------------
#--------------------------------------------------------------
# --- Route to update the configuration ---
@app.route("/api/config", methods=["POST"])
def update_config():
    """
    Update the configuration in the config.yaml file.
    Accepts a JSON payload and writes it to the file.
    """
    try:
        debug_print("[>] Updating configuration in config.yaml", DLevel=2)
        new_config = request.json
        with open(CONFIG_FILE, "w") as f:
            yaml.dump(new_config, f)
        debug_print("[+] Configuration updated successfully", DLevel=2)
        return jsonify({"message": "Configuration updated successfully"}), 200
    except Exception as e:
        debug_print(f"[!] Error saving configuration: {e}", DLevel=0)
        return jsonify({"error": f"Error saving configuration: {e}"}), 500
# --- End of update_config ---
#-------------------------------------------------------------
#--------------------------------------------------------------
# --- Serve the React frontend ---
@app.route("/", defaults={"path": ""})
@app.route("/<path:path>")
def serve_frontend(path):
    """
    Serve the React frontend from the build directory.
    If the requested path exists, serve the corresponding file.
    Otherwise, serve the index.html file for React routing.
    """
    try:
        debug_print(f"[>] Serving frontend for path: {path}", DLevel=2)
        if path != "" and os.path.exists(f"build/{path}"):
            debug_print(f"[+] Serving file: build/{path}", DLevel=3)
            return app.send_static_file(f"build/{path}")
        else:
            debug_print("[+] Serving index.html for React routing", DLevel=3)
            return app.send_static_file("build/index.html")
    except Exception as e:
        debug_print(f"[!] Error serving frontend: {e}", DLevel=0)
        return f"Error serving frontend: {e}", 500
# --- End of serve_frontend ---
#-------------------------------------------------------------
#-------------------------------------------------------------
# --- Start the Flask web interface ---
def start_web_interface():
    """
    Start the Flask web interface on port 5050.
    """
    debug_print("[*] Starting Flask web interface...", DLevel=1)
    app.run(host="0.0.0.0", port=FLASK_PORT, debug=False, use_reloader=False)
# --- End of start_web_interface ---
#-------------------------------------------------------------

@app.route('/')
def index():
    """
    Web interface home page.
    """
    debug_print("[>] Web interface accessed: /", DLevel=2)
    return jsonify({"status": "running", "message": "Welcome to the Proxy Server Web Interface"})

@app.route('/status')
def status():
    """
    Web interface status page.
    """
    debug_print("[>] Web interface accessed: /status", DLevel=2)
    # Example: Return the status of the proxy server
    return jsonify({"status": "running", "sources": 5, "destinations": 3})

if __name__ == "__main__":
    debug_print("[*] Starting web interface...", DLevel=1)
    app.run(host='0.0.0.0', port=8080)