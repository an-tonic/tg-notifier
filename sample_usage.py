import requests


def log_to_tg(message: str):
    resp = requests.post("http://127.0.0.1:12345/notify", json={"message": message}, timeout=5)
