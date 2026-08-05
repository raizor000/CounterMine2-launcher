import json
import os
import threading
import time
import webbrowser
import requests
import base64
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import urlparse, parse_qs
from PyQt6.QtCore import QObject, pyqtSignal
from datetime import datetime
from pathlib import Path
import urllib

from .utilties import get_resource_path

TOKEN_URL = "https://auth.cherct/token"
CLIENT_ID = "frontend"
REDIRECT_URI = "http://localh"
GRAPHQL_URL = "https://cherry.hql"

class AuthHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass

    def do_GET(self):
        if self.path.endswith(".png") or self.path.endswith(".ico"):
            try:
                from pathlib import Path
                from datetime import datetime

                req = self.path.lstrip("/")
                icon_path = Path(os.getcwd()) / req
                print(f"Serving icon from: {icon_path}")

                def _serve(p: Path):
                    with open(p, "rb") as f:
                        content = f.read()
                    self.send_response(200)
                    self.send_header("Content-Type", "image/png")
                    self.send_header("Content-Length", str(len(content)))
                    self.end_headers()
                    self.wfile.write(content)

                if icon_path.exists():
                    _serve(icon_path)
                    threading.Thread(target=lambda: (time.sleep(0.5), self.server.shutdown()), daemon=True).start()
                    return

                month = datetime.now().month
                if month in (12, 1, 2):
                    season = 'winter'
                elif month in (3, 4, 5):
                    season = 'spring'
                elif month in (6, 7, 8):
                    season = 'summer'
                else:
                    season = 'autumn'

                base_assets = get_resource_path("assets")

                candidates = [
                    base_assets / "icons" / f"icon_{season}.png",
                    base_assets / "icons" / "icon.png",
                    get_resource_path(self.path.lstrip("/"))
              ]

                found = None
                for c in candidates:
                    print(f"Checking seasonal candidate: {c}")
                    if c.exists():
                        found = c
                        break

                if not found:
                    for fold in [base_assets / "icons", base_assets / "pixmaps"]:
                        if fold.exists():
                            for f in fold.iterdir():
                                if f.suffix.lower() == ".png":
                                    found = f
                                    break
                        if found:
                            break

                if found:
                    _serve(found)
                    threading.Thread(target=lambda: (time.sleep(0.5), self.server.shutdown()), daemon=True).start()
                    return
                else:
                    self.send_response(404)
                    self.end_headers()
                    self.wfile.write(b"Icon not found")
                    return
            except Exception as e:
                self.send_response(500)
                self.end_headers()
                self.wfile.write(f"Error loading icon: {e}".encode())
                return
        
        qs = parse_qs(urlparse(self.path).query)
        code = qs.get("code")

        if not code:
            self.send_response(400)
            self.end_headers()
            self.wfile.write(b"No code found.")
            return

        code = code[0]
        data = {
            "grant_type": "authorization_code",
            "client_id": CLIENT_ID,
            "code": code,
            "redirect_uri": REDIRECT_URI
        }

        try:
            r = requests.post(TOKEN_URL, data=data)
            if r.status_code == 200:
                tokens = r.json()
                self.server.auth_manager.on_auth_success(tokens)
                
                try:
                    with open(self.server.html_path, "rb") as f:
                        content = f.read()
                    self.send_response(200)
                    self.send_header("Content-Type", "text/html; charset=utf-8")
                    self.end_headers()
                    self.wfile.write(content)
                except Exception as e:
                    self.send_response(200)
                    self.end_headers()
                    self.wfile.write(b"Auth successful! You can close this window.")
            else:
                self.send_response(500)
                self.end_headers()
                self.wfile.write(f"Auth failed: {r.text}".encode())
                self.server.auth_manager.on_auth_failed(r.text)
        except Exception as e:
            self.send_response(500)
            self.end_headers()
            self.wfile.write(f"Error: {e}".encode())
            self.server.auth_manager.on_auth_failed(str(e))
        
     
class CherryAuth(QObject):
    auth_finished = pyqtSignal(dict) 
    auth_failed = pyqtSignal(str)    
    logged_out = pyqtSignal()

    def __init__(self, config_path, html_path):
        super().__init__()
        self.config_path = config_path
        self.html_path = html_path
        self.tokens = {}
        self.user_data = {}
        self.refresh_timer = None
        
    def load_token(self):
        try:
            if self.config_path.exists():
                with open(self.config_path, "r", encoding="utf-8") as f:
                    self.tokens = json.load(f)
                return True
            return False
        except Exception:
            return False

    def save_token(self):
        try:
            with open(self.config_path, "w", encoding="utf-8") as f:
                json.dump(self.tokens, f)
        except Exception as e:
            print(f"Failed to save token: {e}")

    def start_login(self):
        threading.Thread(target=self._run_server, daemon=True).start()

    def _run_server(self):
        try:
            server = HTTPServer(("127.0.0.1", 8080), AuthHandler)
            server.auth_manager = self
            server.html_path = self.html_path
            
            encoded_redirect = urllib.parse.quote(REDIRECT_URI)
            auth_url = f"https://auth.cherry.pizza/realms/cher_id={CLIENT_ID}&redirect_uri={encoded_redirect}&response_type=code&scope=openid"
            webbrowser.open(auth_url)
            
            server.serve_forever()
        except OSError:
             self.auth_failed.emit("Port 8080 is explicitly required but busy.")
        except Exception as e:
             self.auth_failed.emit(str(e))

    def on_auth_success(self, tokens):
        self.tokens = tokens
        self.save_token()
        self._schedule_refresh()
        self.fetch_user_profile()

    def on_auth_failed(self, error):
        self.auth_failed.emit(error)

    def decode_jwt(self, token):
        try:
            payload = token.split(".")[1]
            payload += "=" * (-len(payload) % 4)
            return json.loads(base64.urlsafe_b64decode(payload))
        except:
            return {}

    def fetch_user_profile(self):
        access_token = self.tokens.get("access_token")
        if not access_token:
            return

        nick = self.decode_jwt(self.tokens.get("id_token", "")).get("preferred_username")
        if not nick:
            self.auth_failed.emit("Could not extract nickname from token")
            return

        query = """
        query LoadAccountProfile($username: String!) {
          accountByNickname(nickname: $username) {
            ...AccountProfile
          }
        }
        fragment AccountProfile on Account {
          ...MinimalAccount
          prime
          displayName
          type
          balance
          createdAt
          accountBans {
            edges {
              node {
                ...FrontAccountBan
              }
            }
          }
          gameStats(first: 100, order: [{type: ASC}]) {
            edges {
              node {
                type
                total
              }
            }
          }
        }
        fragment MinimalAccount on Account {
          id
          nickname
          displayName
          mailSha256
          createdAt
        }
        fragment FrontAccountBan on AccountBan {
          id
          reason
          staffReason
          account {
            id
          }
          type
          by {
            ...MinimalAccount
          }
          expireAt
          createdAt
        }
        """

        payload = {
            "query": query,
            "variables": {"username": nick}
        }

        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json"
        }

        try:
            r = requests.post(GRAPHQL_URL, json=payload, headers=headers)
            if r.status_code == 200:
                data = r.json()


                if "data" in data and data["data"] and data["data"].get("accountByNickname"):
                    self.user_data = data["data"]["accountByNickname"]
                    self.auth_finished.emit(self.user_data)
                else:
                    self.auth_failed.emit(f"User not found in API. Response: {data}")
            else:
                self.auth_failed.emit(f"API Error: {r.status_code} {r.text}")
        except Exception as e:
            self.auth_failed.emit(f"Fetch profile failed: {e}")

    def refresh_token(self):
        refresh_token = self.tokens.get("refresh_token")
        if not refresh_token:
            return False

        data = {
            "grant_type": "refresh_token",
            "client_id": CLIENT_ID,
            "refresh_token": refresh_token
        }

        try:
            r = requests.post(TOKEN_URL, data=data)
            if r.status_code == 200:
                new_tokens = r.json()
                self.tokens.update(new_tokens)
                self.save_token()
                self._schedule_refresh()
                return True
            else:
                print("Refresh failed:", r.text)
                return False
        except Exception as e:
            print("Refresh exception:", e)
            return False

    def _schedule_refresh(self):
        if self.refresh_timer:
            self.refresh_timer.cancel()
        
        expires_in = self.tokens.get("expires_in", 300)
        interval = max(10, expires_in - 30)
        
        self.refresh_timer = threading.Timer(interval, self.refresh_token)
        self.refresh_timer.daemon = True
        self.refresh_timer.start()

    def check_auth_status(self):
        if self.load_token():
            if self.refresh_token(): 
                self.fetch_user_profile()
            else:
                 self.logged_out.emit()
        else:
            self.logged_out.emit()
    
    def logout(self):
        self.tokens = {}
        self.user_data = {}
        if self.refresh_timer:
            self.refresh_timer.cancel()
        try:
            if self.config_path.exists():
                import os
                os.remove(self.config_path)
        except:
            pass
        self.logged_out.emit()
