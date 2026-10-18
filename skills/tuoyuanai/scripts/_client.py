"""Dependency-free OpenAPI transport. Credentials are environment-only."""
from __future__ import annotations
import json
import os
import urllib.error
import urllib.parse
import urllib.request

DEFAULT_BASE = "https://tuoyuanai.com"


class SkillError(Exception):
    pass


def emit(value, *, stream=None):
    import sys
    print(json.dumps(value, ensure_ascii=False), file=stream or sys.stdout, flush=True)


def safe_url(value):
    parts = urllib.parse.urlsplit(value)
    if parts.username or parts.password or not parts.hostname or parts.fragment:
        raise SkillError("URL must not contain credentials or a fragment.")
    if parts.scheme != "https" and not (parts.scheme == "http" and parts.hostname in {"localhost", "127.0.0.1", "::1"}):
        raise SkillError("HTTPS is required except for local loopback acceptance.")
    return value


def origin(url):
    p = urllib.parse.urlsplit(url)
    return p.scheme, p.hostname, p.port or (443 if p.scheme == "https" else 80)


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class Client:
    def __init__(self):
        self.base = safe_url(os.environ.get("TUOYUANAI_BASE_URL", DEFAULT_BASE).rstrip("/"))
        p = urllib.parse.urlsplit(self.base)
        if p.query or p.path not in {"", "/"}:
            raise SkillError("TUOYUANAI_BASE_URL must be an origin without a path or query.")
        self.token = os.environ.get("TUOYUANAI_ACCESS_KEY", "").strip()
        if not self.token.startswith("ty_sk_"):
            raise SkillError("Set TUOYUANAI_ACCESS_KEY to an independent Access Key from your personal center.")
        self.opener = urllib.request.build_opener(NoRedirect)

    def open(self, method, url, *, body=None, headers=None, auth=False, timeout=60):
        safe_url(url)
        headers = dict(headers or {})
        if auth:
            if origin(url) != origin(self.base):
                raise SkillError("Refusing to send credentials to another origin.")
            headers["Authorization"] = "Bearer " + self.token
        req = urllib.request.Request(url, data=body, headers=headers, method=method)
        try:
            return self.opener.open(req, timeout=timeout)
        except urllib.error.HTTPError as exc:
            try:
                error = json.loads(exc.read(8192))
                detail = error.get("error") or error.get("detail") or "Request rejected."
                if not isinstance(detail, str):
                    detail = "Request fields are invalid."
            except (ValueError, AttributeError):
                detail = "OpenAPI unavailable or unexpected response; no alternative endpoint was attempted."
            raise SkillError(f"HTTP {exc.code}: {detail.replace(self.token, '[redacted]')[:800]}") from None
        except (urllib.error.URLError, TimeoutError, OSError):
            raise SkillError("Connection failed. A submitted request may still run. Query the session or reuse the same request ID and body; do not create a new generation request blindly.") from None

    def request(self, method, path, body=None):
        if not path.startswith("/") or path.startswith("//"):
            raise SkillError("API paths must be relative to /openapi.")
        encoded = json.dumps(body, ensure_ascii=False).encode() if body is not None else None
        with self.open(method, self.base + "/openapi" + path, body=encoded,
                       headers={"Content-Type": "application/json"}, auth=True) as response:
            try:
                envelope = json.load(response)
            except ValueError:
                raise SkillError("OpenAPI returned a non-JSON response. This server needs the OpenAPI platform release.") from None
        if not isinstance(envelope, dict) or envelope.get("success") is not True or "data" not in envelope:
            raise SkillError("Unexpected OpenAPI response; no alternative endpoint was attempted.")
        return envelope["data"]

    def session(self, session_id, *, after_seq=0, limit=100):
        return self.request("GET", f"/session/{session_id}?afterSeq={after_seq}&limit={limit}")

    def canvas(self, session):
        return self.request("GET", f'/session/{session["sessionId"]}/results')

    def links(self, session):
        return {"session_id": session["sessionId"], "project": session["project"],
                "project_url": self.base + session["projectUrl"]}
