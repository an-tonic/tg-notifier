import os

import requests


def log_to_tg(message):
    """Topic should be a unique string to allow identification of source of the message"""

    ip = os.popen("hostname -I").read().strip().split()[0]
    file_path = os.path.abspath(__file__)
    topic = f"{ip}/{file_path}"
    print(topic)
    requests.post("http://127.0.0.1:12345/notify",
                  json={"message": f"Message from: {ip} on this file {file_path}:\n {message}",
                        "topic": topic},
                  timeout=5)
