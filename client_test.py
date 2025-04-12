# test_client.py

import sys
sys.path.append('/Users/mhassan/osps/myenv/lib/python3.13/site-packages')  # Add the path to your module

import socket
import json

#--------------------------------------------------------
# Function to send data to the worker
def send_to_worker(data):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.connect(("localhost", 9000))
        json_data = json.dumps(data).encode('utf-8')
        sock.sendall(json_data)
#--------------------------------------------------------
#=======================================================
if __name__ == "__main__":
    
    for i in range(5):
        sample_data = {
            "message_id": i,
            "payload": f"Hello #{i}"
        }
        send_to_worker(sample_data)
        print(f"[CLIENT] Sent: {sample_data} to the worker on localhost:8000")
#========================================================
