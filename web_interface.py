from flask import Flask, logging, request, jsonify
import yaml
import os

CONFIG_FILE = 'config.yaml'
FLASK_PORT = 5050
OSPP_DEAULT_LOG_FILE = 'ospp.log'


from utils import setup_logging, print_error_details

# Flask app for the backend API
app = Flask(__name__)

#-------------------------------------------------------------
# --- Route to get the configuration ---
@app.route("/api/config", methods=["GET"])
def get_config():
    """
    Fetch the current configuration from the config.yaml file.
    Returns the configuration as a JSON response.
    """
    try:
        with open(CONFIG_FILE, "r") as f:
            config_content = yaml.safe_load(f)
        return jsonify(config_content), 200
    except Exception as e:
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
        new_config = request.json
        with open(CONFIG_FILE, "w") as f:
            yaml.dump(new_config, f)
        return jsonify({"message": "Configuration updated successfully"}), 200
    except Exception as e:
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
        if path != "" and os.path.exists(f"build/{path}"):
            return app.send_static_file(f"build/{path}")
        else:
            return app.send_static_file("build/index.html")
    except Exception as e:
        return f"Error serving frontend: {e}", 500
# --- End of serve_frontend ---
#-------------------------------------------------------------
#-------------------------------------------------------------
# --- Start the Flask web interface ---
def start_web_interface():
    """
    Start the Flask web interface on port 5050.
    """
    app.run(host="0.0.0.0", port=FLASK_PORT, debug=True, use_reloader=False)
# --- End of start_web_interface ---
#-------------------------------------------------------------