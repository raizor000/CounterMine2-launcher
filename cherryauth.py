import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import urlparse, parse_qs
import requests
import json
import base64
import threading
import time

TOKEN_URL = "https://auth.cherry.pizza/realms/cherrypizza/protocol/openid-connect/token"
CLIENT_ID = "frontend"
REDIRECT_URI = "http://localhost:8080"

tokens = {}


def decode_jwt(token: str):
    try:
        payload = token.split(".")[1]
        payload += "=" * (-len(payload) % 4)
        return json.loads(base64.urlsafe_b64decode(payload))
    except Exception as e:
        return {"error": str(e)}

def refresh_token():
    global tokens
    if "refresh_token" not in tokens:
        print("Нет refresh_token")
        return

    data = {
        "grant_type": "refresh_token",
        "client_id": CLIENT_ID,
        "refresh_token": tokens["refresh_token"]
    }

    r = requests.post(TOKEN_URL, data=data)
    if r.status_code == 200:
        tokens.update(r.json())
        print("\n🔄 Access token обновлён")
    else:
        print("\n❌ Ошибка обновления:", r.text)

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        global tokens
        qs = parse_qs(urlparse(self.path).query)
        code = qs.get("code")

        if not code:
            self.send_response(400)
            self.end_headers()
            self.wfile.write(b"No code")
            return

        code = code[0]
        print("\nCODE:", code)

        data = {
            "grant_type": "authorization_code",
            "client_id": CLIENT_ID,
            "code": code,
            "redirect_uri": REDIRECT_URI
        }

        r = requests.post(TOKEN_URL, data=data)
        print("STATUS:", r.status_code)

        if r.status_code != 200:
            print("ERROR:", r.text)
            self.send_response(500)
            self.end_headers()
            self.wfile.write(b"Token error")
            return

        tokens = r.json()

        print("\n=== TOKENS ===")
        print(json.dumps(tokens, indent=2))

        print("\n=== ACCESS TOKEN PAYLOAD ===")
        print(json.dumps(decode_jwt(tokens["access_token"]), indent=2))

        print("\n=== ID TOKEN PAYLOAD ===")
        print(json.dumps(decode_jwt(tokens["id_token"]), indent=2))

        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Auth OK. Check console.")

        # авто-refresh за 10 сек до конца
        threading.Timer(tokens["expires_in"] - 10, refresh_token).start()

        GRAPHQL_URL = "https://cherry.pizza/api/graphql"  # если другой — подставь реальный
        ACCESS_TOKEN = tokens["access_token"]  # из предыдущего шага

        nick = decode_jwt(tokens["id_token"]).get("preferred_username")

        query = """
        query ($nick: String!) {
          accountByNickname(nickname: $nick) {
            id
            nickname
            displayName
            prime
            balance
            
          }
        }
        """

        payload = {
            "query": query,
            "variables": {
                "nick": nick
            }
        }

        headers = {
            "Authorization": f"Bearer {ACCESS_TOKEN}",
            "Content-Type": "application/json"
        }

        r = requests.post(
            GRAPHQL_URL,
            json=payload,
            headers=headers
        )

        print("STATUS:", r.status_code)
        try:
            print(r.json())
        except Exception as e:
            print(e)

        # сервер больше не нужен
        threading.Thread(target=shutdown_server, daemon=True).start()

def shutdown_server():
    time.sleep(1)
    print("\n🛑 HTTP server stopped")
    httpd.shutdown()

httpd = HTTPServer(("localhost", 8080), Handler)

print("🚀 Waiting for auth on http://localhost:8080")
webbrowser.open("https://auth.cherry.pizza/realms/cherrypizza/protocol/openid-connect/auth?client_id=frontend&redirect_uri=http://localhost:8080&response_type=code&scope=openid")
httpd.serve_forever()
