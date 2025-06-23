import requests

BOT_TOKEN = '8164774178:AAGF0nTcw-Qp04qe9WxK7rZzqTmhnojS1qQ'

def get_updates():
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/getUpdates"
    r = requests.get(url)
    print(r.json())

get_updates()
