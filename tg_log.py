import os
import inspect
import requests


def log_to_tg(message):
    caller_file = os.path.abspath(inspect.stack()[1].filename)
    ip = os.popen("hostname -I").read().strip().split()[0]
    topic = f"{ip}/{caller_file}"
    requests.post("http://127.0.0.1:12345/notify",
                  json={"message": f"[{ip}] {caller_file}:\n\n{message}",
                        "topic": topic},
                  timeout=5)