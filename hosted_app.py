"""Single-port ASGI entry point for hosting the complete farmer portal.

Streamlit serves the UI at / and the existing FastAPI app is mounted at /api.
The dashboard makes server-side API calls to the same local process, so only
one public port and one persistent data volume are needed.
"""

from __future__ import annotations

import os
import base64
import hashlib
import hmac
import shutil
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from http.cookies import SimpleCookie
from pathlib import Path

import streamlit as st
from starlette.middleware import Middleware
from starlette.responses import JSONResponse, PlainTextResponse
from starlette.routing import Mount, Route


port = int(os.getenv("PORT", "8501"))
os.environ.setdefault("BACKEND_URL", f"http://127.0.0.1:{port}/api")

from soil_npk.api import app as farmer_api  # noqa: E402
from soil_npk.farmer_service import MODEL_PATH, initialise_database  # noqa: E402
from soil_npk.locations import DATABASE_PATH, initialise_locations  # noqa: E402


class DemoAccessMiddleware:
    """Gate both HTTP and Streamlit WebSocket traffic for invited testers."""

    def __init__(self, app):
        self.app = app
        self.password = os.getenv("DEMO_ACCESS_PASSWORD", "")

    def _valid_cookie(self, cookie_header: str) -> bool:
        cookies = SimpleCookie()
        try:
            cookies.load(cookie_header)
            token = cookies["mittimitra_demo"].value
            issued, signature = token.split(".", 1)
            age = datetime.now(UTC).timestamp() - int(issued)
            if not 0 <= age <= 12 * 60 * 60:
                return False
            expected = hmac.new(self.password.encode(), issued.encode(), hashlib.sha256).hexdigest()
            return hmac.compare_digest(signature, expected)
        except (KeyError, ValueError, TypeError):
            return False

    def _valid_basic(self, authorization: str) -> bool:
        expected = "Basic " + base64.b64encode(f"demo:{self.password}".encode()).decode()
        return hmac.compare_digest(authorization, expected)

    async def __call__(self, scope, receive, send):
        if scope["type"] not in {"http", "websocket"} or scope.get("path") == "/__health":
            await self.app(scope, receive, send)
            return
        headers = {key.lower(): value for key, value in scope.get("headers", [])}
        cookie = headers.get(b"cookie", b"").decode("latin-1")
        authorization = headers.get(b"authorization", b"").decode("latin-1")
        cookie_valid = self._valid_cookie(cookie)
        basic_valid = self._valid_basic(authorization)
        if not (cookie_valid or basic_valid):
            if scope["type"] == "websocket":
                await send({"type": "websocket.close", "code": 4401})
            else:
                response = PlainTextResponse(
                    "MittiMitra private demo: invite password required.",
                    status_code=401,
                    headers={"WWW-Authenticate": 'Basic realm="MittiMitra private demo"'},
                )
                await response(scope, receive, send)
            return

        async def send_with_cookie(message):
            if basic_valid and not cookie_valid and message["type"] == "http.response.start":
                issued = str(int(datetime.now(UTC).timestamp()))
                signature = hmac.new(self.password.encode(), issued.encode(), hashlib.sha256).hexdigest()
                secure = "; Secure" if os.getenv("PUBLIC_DEPLOYMENT") == "1" else ""
                value = f"mittimitra_demo={issued}.{signature}; Max-Age=43200; Path=/; HttpOnly; SameSite=Lax{secure}"
                message.setdefault("headers", []).append((b"set-cookie", value.encode()))
            await send(message)

        await self.app(scope, receive, send_with_cookie)


async def health(_request):
    return JSONResponse({"status": "ok"})


@asynccontextmanager
async def lifespan(_app):
    """Prepare an empty persistent volume before accepting farmer requests."""
    if os.getenv("PUBLIC_DEPLOYMENT", "0") == "1":
        mode = os.getenv("OTP_DELIVERY_MODE", "twilio").strip().lower()
        required = ("TWILIO_ACCOUNT_SID", "TWILIO_AUTH_TOKEN", "TWILIO_VERIFY_SERVICE_SID")
        if os.getenv("DEMO_MODE") == "1":
            if mode != "screen" or len(os.getenv("DEMO_ACCESS_PASSWORD", "")) < 16:
                raise RuntimeError("Private demo requires screen OTP and a 16+ character access password.")
        elif mode != "twilio" or any(not os.getenv(key) for key in required):
            raise RuntimeError("Public farmer login requires real SMS OTP credentials.")
        if not os.getenv("SCHEME_ADMIN_KEY"):
            raise RuntimeError("Public deployment requires SCHEME_ADMIN_KEY.")

    if not MODEL_PATH.exists():
        bootstrap = Path(os.getenv("NPK_BOOTSTRAP_MODEL_PATH", "bootstrap_artifacts/npk_baseline.npz"))
        if not bootstrap.is_file():
            raise RuntimeError(f"NPK baseline is missing: {bootstrap}")
        MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(bootstrap, MODEL_PATH)

    if not DATABASE_PATH.exists():
        bootstrap_database = Path(os.getenv("NPK_BOOTSTRAP_DATABASE_PATH", "bootstrap_artifacts/terranpk.db"))
        if bootstrap_database.is_file():
            DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(bootstrap_database, DATABASE_PATH)

    initialise_database()
    initialise_locations()
    yield


app = st.App(
    "dashboard.py",
    routes=[Route("/__health", health), Mount("/api", app=farmer_api)],
    middleware=[Middleware(DemoAccessMiddleware)] if os.getenv("DEMO_MODE") == "1" else [],
    lifespan=lifespan,
)
