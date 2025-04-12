import sys
sys.path.append('/Users/mhassan/osps/myenv/lib/python3.13/site-packages')  # Add the path to your module
# sys.path.append('/home/mohamadhassan2/Downloads/Flask-RESTful-API-Example/backpressure_code')
# sys.path.append('/home/mohamadhassan2/Downloads/Flask-RESTful-API-Example/backpressure_code/utils')
# sys.path.append('/home/mohamadhassan2/Downloads/Flask-RESTful-API-Example/sources')
#    
#print sys.path
from flask import Flask, app, request, jsonify
import flask

'''
print ("--" * 20)
app = Flask(__name__)
print(sys.executable)
print(flask.__version__)
print(f"Flask version: {flask.__version__}")
print(f"Python version: {sys.version}")
print(f"Python executable: {sys.executable}")
print(f"Python path: {sys.path}")
print(f"Flask app name: {app.name}")
print("--" * 20)
'''
app = Flask(__name__)

@app.route('/data', methods=['POST'])
def receive():
    print(f"[DESTINATION] Got: {request.json}")
    return jsonify({"status": "ok"}), 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5001)
