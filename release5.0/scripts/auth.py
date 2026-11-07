import base64
import hashlib
import json
import secrets
import threading
import time
import webbrowser
from datetime import datetime
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs, urlencode, urlsplit

import requests
from PyQt6.QtCore import QObject, pyqtSignal

from .constants import CLIENT_ID, GRAPHQL_URL, REDIRECT_URI, TOKEN_URL
from .storage import write_json
from .utilties import get_resource_path


class AuthHandler(BaseHTTPRequestHandler):
    def setup(self):
        self.request.settimeout(5)
        super().setup()

    def log_message(self, format, *args):
        pass

    def _reply(self, status, content, content_type="text/plain; charset=utf-8"):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(content)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("Referrer-Policy", "no-referrer")
        self.end_headers()
        self.wfile.write(content)

    def do_GET(self):
        url = urlsplit(self.path)
        if url.path != "/":
            self._reply(404, b"Not found")
            return
        query = parse_qs(url.query)
        states = query.get("state", [])
        if (len(states) != 1 or not secrets.compare_digest(states[0].encode(), self.server.state.encode())
                or self.server.completed):
            self._reply(400, b"Invalid login state")
            return

        self.server.completed = True
        manager = self.server.auth_manager
        generation = self.server.generation
        try:
            if "error" in query or len(query.get("code", [])) != 1:
                raise ValueError("Login was cancelled or rejected.")
            response = requests.post(TOKEN_URL, data={
                "grant_type": "authorization_code",
                "client_id": CLIENT_ID,
                "code": query["code"][0],
                "redirect_uri": REDIRECT_URI,
                "code_verifier": self.server.verifier,
            }, timeout=10)
            response.raise_for_status()
            manager.complete_login(response.json(), generation)
        except Exception as exc:
            manager.fail_login(generation, str(exc))
            self._reply(400, b"Login failed. Return to the launcher to retry.")
            return

        try:
            content = manager.html_path.read_text(encoding="utf-8")
            month = datetime.now().month
            season = ("winter", "spring", "summer", "autumn")[(month % 12) // 3]
            with open(get_resource_path(f"assets/icons/icon_{season}.png"), "rb") as icon:
                data = base64.b64encode(icon.read()).decode("ascii")
            content = content.replace('src="icon_winter.png"', f'src="data:image/png;base64,{data}"')
        except OSError:
            content = "Login successful. You may close this window."
        self._reply(200, content.encode("utf-8"), "text/html; charset=utf-8")


class CherryAuth(QObject):
    auth_finished = pyqtSignal(dict)
    auth_failed = pyqtSignal(str)
    logged_out = pyqtSignal()
    token_refreshed = pyqtSignal(str)

    def __init__(self, config_path, html_path):
        super().__init__()
        self.config_path = config_path
        self.html_path = html_path
        self.tokens = {}
        self.user_data = {}
        self.refresh_timer = None
        self._lock = threading.Lock()
        self._generation = 0
        self._login_in_progress = False
        self._stopped = False

    def _save_token(self):
        try:
            write_json(self.config_path, self.tokens)
        except OSError as exc:
            print(f"[Auth] Could not save token: {exc}")

    def start_login(self):
        with self._lock:
            if self._stopped or self._login_in_progress:
                return
            self._login_in_progress = True
            generation = self._generation
        threading.Thread(target=self._run_server, args=(generation,), daemon=True).start()

    def _run_server(self, generation):
        try:
            with HTTPServer(("127.0.0.1", urlsplit(REDIRECT_URI).port), AuthHandler) as server:
                server.auth_manager = self
                server.generation = generation
                server.state = secrets.token_urlsafe(32)
                server.verifier = secrets.token_urlsafe(48)
                server.completed = False
                server.timeout = 0.25
                challenge = base64.urlsafe_b64encode(
                    hashlib.sha256(server.verifier.encode("ascii")).digest()
                ).rstrip(b"=").decode("ascii")
                params = urlencode({
                    "client_id": CLIENT_ID, "redirect_uri": REDIRECT_URI,
                    "response_type": "code", "scope": "openid", "state": server.state,
                    "code_challenge": challenge, "code_challenge_method": "S256",
                })
                auth_url = TOKEN_URL.rsplit("/", 1)[0] + "/auth"
                if not webbrowser.open(f"{auth_url}?{params}"):
                    raise RuntimeError("Could not open a web browser.")

                deadline = time.monotonic() + 180
                while generation == self._generation and not server.completed and time.monotonic() < deadline:
                    server.handle_request()
                if not server.completed:
                    self.fail_login(generation, "Login timed out.")
        except Exception as exc:
            self.fail_login(generation, f"Could not complete login: {exc}")
        finally:
            with self._lock:
                self._login_in_progress = False

    def complete_login(self, tokens, generation):
        profile = self.fetch_user_profile(tokens)
        with self._lock:
            if generation != self._generation:
                raise ValueError("Login is no longer active.")
            self._generation += 1
            self.tokens = tokens
            self.user_data = profile
            self._save_token()
            self._schedule_refresh()
            self.auth_finished.emit(profile)

    def fail_login(self, generation, message):
        with self._lock:
            if generation == self._generation:
                self.auth_failed.emit(message)

    @staticmethod
    def decode_jwt(token):
        try:
            payload = token.split(".")[1]
            return json.loads(base64.urlsafe_b64decode(payload + "=" * (-len(payload) % 4)))
        except (ValueError, IndexError, AttributeError):
            return {}

    def fetch_user_profile(self, tokens):
        access_token = tokens["access_token"]
        claims = self.decode_jwt(tokens.get("id_token", ""))
        nick = claims.get("preferred_username") if isinstance(claims, dict) else None
        if not access_token or not nick:
            raise ValueError("Could not read the Cherry account from the login response.")

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

        response = requests.post(
            GRAPHQL_URL,
            json={"query": query, "variables": {"username": nick}},
            headers={"Authorization": f"Bearer {access_token}"},
            timeout=10,
        )
        response.raise_for_status()
        profile = (response.json().get("data") or {}).get("accountByNickname")
        if not isinstance(profile, dict) or not profile.get("nickname") or not profile.get("id"):
            raise ValueError("Cherry account was not found.")
        return profile

    def _refresh(self, generation, tokens, *, restore=False):
        try:
            response = requests.post(TOKEN_URL, data={
                "grant_type": "refresh_token",
                "client_id": CLIENT_ID,
                "refresh_token": tokens["refresh_token"],
            }, timeout=10)
            response.raise_for_status()
            updated = dict(tokens, **response.json())
            if not updated.get("access_token"):
                raise ValueError("No access token in the refresh response.")
        except Exception as exc:
            with self._lock:
                if generation != self._generation:
                    return
                if restore:
                    self.logged_out.emit()
                elif isinstance(exc, requests.HTTPError) and exc.response.status_code in (400, 401):
                    self._clear_session()
                else:
                    self._schedule_refresh(delay=30)
            print(f"[Auth] Refresh failed: {exc}")
            return

        with self._lock:
            if generation != self._generation:
                return
            self.tokens = updated
            self._save_token()

        if restore:
            try:
                profile = self.fetch_user_profile(updated)
            except Exception as exc:
                self.fail_login(generation, str(exc))
                return

        with self._lock:
            if generation != self._generation:
                return
            self._schedule_refresh()
            if restore:
                self.user_data = profile
                self.auth_finished.emit(profile)
            else:
                self.token_refreshed.emit(updated["access_token"])

    def _schedule_refresh(self, delay=None):
        if self.refresh_timer:
            self.refresh_timer.cancel()
        if not self.tokens.get("refresh_token"):
            return
        if delay is None:
            expires = self.tokens.get("expires_in", 300)
            expires = expires if isinstance(expires, (int, float)) else 300
            delay = max(1, expires - 30 if expires > 30 else expires / 2)
        self.refresh_timer = threading.Timer(delay, self._refresh, args=(self._generation, self.tokens))
        self.refresh_timer.daemon = True
        self.refresh_timer.start()

    def check_auth_status(self):
        with self._lock:
            generation = self._generation
        try:
            tokens = json.loads(self.config_path.read_text(encoding="utf-8"))
            if not isinstance(tokens, dict) or not tokens.get("refresh_token"):
                raise ValueError("No saved refresh token")
        except (OSError, ValueError):
            with self._lock:
                if generation == self._generation:
                    self.logged_out.emit()
            return
        self._refresh(generation, tokens, restore=True)

    def _clear_session(self):
        self._generation += 1
        self.tokens = {}
        self.user_data = {}
        if self.refresh_timer:
            self.refresh_timer.cancel()
        try:
            self.config_path.unlink(missing_ok=True)
        except OSError as exc:
            print(f"[Auth] Could not remove saved session: {exc}")
        self.logged_out.emit()

    def logout(self):
        with self._lock:
            self._clear_session()

    def stop(self):
        with self._lock:
            self._stopped = True
            self._generation += 1
            if self.refresh_timer:
                self.refresh_timer.cancel()
