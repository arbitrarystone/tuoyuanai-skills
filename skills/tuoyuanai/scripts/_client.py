"""Small, dependency-free client for TuoyuanAI's current web API."""
from __future__ import annotations

import json
import os
from pathlib import Path
import re
import subprocess
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
    if parts.scheme != "https" and not (
        parts.scheme == "http" and parts.hostname in {"localhost", "127.0.0.1", "::1"}
    ):
        raise SkillError("HTTPS is required except for local loopback acceptance.")
    return value


def origin(url):
    parts = urllib.parse.urlsplit(url)
    return parts.scheme, parts.hostname, parts.port or (443 if parts.scheme == "https" else 80)


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        # Never forward credentials or replay a write via a redirect.
        return None


def write_private_json(path, value):
    path = Path(path).expanduser().resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    # Exclusive creation: a new login cannot overwrite somebody else's token.
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        if os.name == "nt":
            identity = subprocess.check_output(["whoami"], text=True).strip()
            result = subprocess.run(
                ["icacls", str(path), "/inheritance:r", "/grant:r", identity + ":F"],
                capture_output=True,
            )
            if result.returncode:
                raise SkillError("Could not restrict token file permissions; no token was saved.")
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            fd = None
            json.dump(value, handle, ensure_ascii=False)
    except BaseException:
        if fd is not None:
            os.close(fd)
        path.unlink(missing_ok=True)
        raise
    return str(path)


class Client:
    def __init__(self, *, authenticated=True):
        self.base = os.environ.get("TUOYUANAI_BASE_URL", DEFAULT_BASE).rstrip("/")
        safe_url(self.base)
        parsed = urllib.parse.urlsplit(self.base)
        if parsed.path or parsed.query:
            raise SkillError("TUOYUANAI_BASE_URL must be an origin, without /api or a query.")
        self.token = ""
        if authenticated:
            self.token = os.environ.get("TUOYUANAI_ACCESS_TOKEN", "").strip()
            token_file = os.environ.get("TUOYUANAI_TOKEN_FILE", "")
            if self.token and token_file:
                raise SkillError("Set only one of TUOYUANAI_ACCESS_TOKEN and TUOYUANAI_TOKEN_FILE.")
            if token_file:
                saved = json.loads(Path(token_file).expanduser().read_text(encoding="utf-8"))
                if saved["base_url"] != self.base:
                    raise SkillError("Token file belongs to a different platform origin.")
                self.token = saved["access_token"]
            if not self.token:
                raise SkillError("Log in first; set TUOYUANAI_TOKEN_FILE or TUOYUANAI_ACCESS_TOKEN.")
            if not isinstance(self.token, str) or any(c.isspace() for c in self.token):
                raise SkillError("Invalid access token format.")
        self.opener = urllib.request.build_opener(NoRedirect())

    def clean_error(self, text):
        if self.token:
            text = text.replace(self.token, "[redacted]")
        # Errors may contain signed URLs or provider credentials. Do not echo them.
        text = re.sub(r'https?://[^\s<>"\']+', '[URL omitted]', text)
        text = re.sub(r'(?i)bearer\s+\S+|\bsk-[a-zA-Z0-9_-]+', '[redacted]', text)
        return text[:600]

    def open(self, method, url, *, body=None, headers=None, auth=False, timeout=60):
        safe_url(url)
        headers = dict(headers or {})
        if any(key.lower() == "authorization" for key in headers):
            raise SkillError("Authorization headers may only be created by this client.")
        if auth:
            if origin(url) != origin(self.base):
                raise SkillError("Refusing to send the platform token to another origin.")
            headers["Authorization"] = "Bearer " + self.token
        headers["User-Agent"] = "tuoyuanai-skills/0.1.0"
        request = urllib.request.Request(url, data=body, headers=headers, method=method)
        try:
            return self.opener.open(request, timeout=timeout)
        except urllib.error.HTTPError as exc:
            # Never print raw response bodies (validation errors can echo a password).
            detail = ""
            if exc.code < 500:
                try:
                    error = json.loads(exc.read(65536))
                    candidate = error.get("detail") or error.get("error")
                    if isinstance(candidate, str):
                        detail = ": " + self.clean_error(candidate)
                except (ValueError, AttributeError):
                    pass
            raise SkillError(f"HTTP {exc.code}{detail}; no automatic retry was performed.") from None
        except (urllib.error.URLError, TimeoutError, OSError):
            raise SkillError(
                "Connection failed or timed out. A submitted operation may still be running; "
                "query its session before deciding whether to submit anything else."
            ) from None

    def request(self, method, path, body=None):
        if not path.startswith("/") or path.startswith("//"):
            raise SkillError("API paths must be relative to /api/v1.")
        encoded = json.dumps(body, ensure_ascii=False).encode("utf-8") if body is not None else None
        with self.open(method, self.base + "/api/v1" + path, body=encoded,
                       headers={"Content-Type": "application/json"}, auth=bool(self.token)) as response:
            envelope = json.load(response)
        if envelope.get("success") is not True or "data" not in envelope:
            raise SkillError("Unexpected API response; no alternative endpoint was attempted.")
        return envelope["data"]

    def session(self, session_id):
        return self.request("GET", f"/assistant/sessions/{session_id}")

    def canvas(self, session):
        project = session["project"]
        if project["ref_type"] not in {"content_task", "video_project"}:
            raise SkillError("Unsupported project contract.")
        return self.request("GET", f'/canvas/{project["ref_type"]}/{int(project["ref_id"])}')

    def links(self, session):
        return {"session_id": session["id"], "project": session["project"],
                "project_url": f'{self.base}/assistant?session={session["id"]}'}
