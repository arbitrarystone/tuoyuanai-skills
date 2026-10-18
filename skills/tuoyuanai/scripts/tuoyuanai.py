#!/usr/bin/env python3
"""TuoyuanAI skill CLI. Python 3.10+, standard library only."""
from __future__ import annotations

import argparse
from copy import deepcopy
import getpass
import http.client
import json
import mimetypes
import os
from pathlib import Path
import sys
import time
import urllib.parse
import uuid

from _client import Client, SkillError, emit, safe_url, write_private_json

ACTIVE = {"running", "waiting", "queued"}


def positive(value):
    number = int(value)
    if number <= 0:
        raise argparse.ArgumentTypeError("Must be positive.")
    return number


def save_turn(client, session, turn):
    messages = deepcopy(session["messages"])
    messages.setdefault("turns", []).append(turn)
    messages.setdefault("history", []).append({"role": turn["role"], "content": turn["content"]})
    return client.request("PUT", f'/assistant/sessions/{session["id"]}', {
        "expected_updated_at": session["updated_at"], "messages": messages,
    })


def login(args):
    client = Client(authenticated=False)
    password = os.environ.get("TUOYUANAI_PASSWORD") or getpass.getpass("TuoyuanAI password: ")
    data = client.request("POST", "/auth/login", {
        "phone": args.phone, "password": password, "remember": False,
    })
    del password
    path = write_private_json(args.token_file, {
        "base_url": client.base, "access_token": data["access_token"],
    })
    emit({"authenticated": True, "token_file": path, "base_url": client.base,
          "must_change_password": data["user"]["must_change_password"]})


def send(client, args):
    message = Path(args.message_file).read_text(encoding="utf-8-sig") if args.message_file else args.message
    if not message or not message.strip():
        raise SkillError("A nonempty message is required.")
    session = client.session(args.session_id)
    if any(item["status"] in ACTIVE for item in session["executions"]):
        raise SkillError("This session has active work. Query it or explicitly stop it before sending.")
    attachments = []
    if args.attachment_id:
        available = client.request("GET", f"/assistant/attachments?session_id={args.session_id}")
        by_id = {item["id"]: item for item in available}
        for attachment_id in dict.fromkeys(args.attachment_id):
            item = by_id.get(attachment_id)
            if not item or item["status"] != "ready":
                raise SkillError(f"Attachment {attachment_id} is not ready in this session.")
            attachments.append({key: item[key] for key in ("id", "filename", "kind", "mime_type")})
    body = {"message": message, "session_id": args.session_id,
            "stream_id": str(uuid.uuid4()), "attachment_ids": [a["id"] for a in attachments],
            "auto_generate_media": args.generate_media}
    if args.creation_type:
        body["creation_type"] = args.creation_type
        body["creation_type_source"] = "explicit"
    if args.settings_file:
        settings = json.loads(Path(args.settings_file).read_text(encoding="utf-8-sig"))
        if not isinstance(settings, dict):
            raise SkillError("Settings must be a JSON object matching CreationSettings.")
        body["settings"] = settings
    turn = {"role": "user", "content": message, "cards": [], "attachments": attachments}
    session = save_turn(client, session, turn)
    # Output durable identity before sending any chargeable request.
    emit({"type": "submission", **client.links(session), "stream_id": body["stream_id"],
          "auto_generate_media": args.generate_media})
    cards = []
    execution_id = None
    done = None
    with client.open("POST", client.base + "/api/v1/assistant/chat/stream",
                     body=json.dumps(body, ensure_ascii=False).encode("utf-8"),
                     headers={"Content-Type": "application/json", "Accept": "text/event-stream"},
                     auth=True, timeout=600) as response:
        if response.headers.get_content_type() != "text/event-stream":
            raise SkillError("Expected an event stream; inspect the session before submitting again.")
        lines = []
        for raw in response:
            line = raw.decode("utf-8").rstrip("\r\n")
            if line.startswith("data:"):
                lines.append(line[5:].lstrip(" "))
            elif line == "" and lines:
                event = json.loads("\n".join(lines))
                lines.clear()
                kind = event.get("type")
                if kind == "execution":
                    execution_id = event["execution_id"]
                if kind == "card":
                    cards.append(event["card"])
                if kind == "error":
                    raise SkillError(client.clean_error(event.get("message", "Assistant error")))
                if kind == "done":
                    done = event
                    break
                # Do not dump reasoning, internal diagnostics or arbitrary provider payloads.
                if kind == "delta":
                    emit({"type": "delta", "text": event.get("text", "")})
    if done is None:
        raise SkillError("The stream ended without a final result. Query the session; do not resend automatically.")
    latest = client.session(args.session_id)
    turn = {"role": "assistant", "content": done["reply"], "cards": cards}
    if execution_id is not None:
        turn["execution_id"] = execution_id
    # UI-only turn fields (e.g. confirmation display state) are not conversation edits.
    # Preserve the latest display state; stop if semantic message history changed.
    if latest["messages"].get("history") != session["messages"].get("history"):
        emit({"type": "unsaved_reply", "reply": done["reply"], "cards": cards, **client.links(latest)})
        raise SkillError("Session was edited during this request. Reply is returned but the cloud copy was not overwritten.")
    # The normal web-client persistence contract uses an optimistic version.
    # A 409 is surfaced, never resolved by overwriting or resending a model request.
    saved = save_turn(client, latest, turn)
    emit({"type": "done", **client.links(saved), "reply": done["reply"],
          "cards": cards, "agent": saved["agent"]})


def query(client, args):
    deadline = time.monotonic() + args.wait
    while True:
        session = client.session(args.session_id)
        active = any(item["status"] in ACTIVE for item in session["executions"])
        if not active or time.monotonic() >= deadline:
            emit({**client.links(session), "title": session["title"],
                  "updated_at": session["updated_at"], "messages": session["messages"],
                  "agent": session["agent"], "executions": session["executions"],
                  "still_running": active})
            return
        time.sleep(min(8, max(0, deadline - time.monotonic())))


def upload(client, args):
    path = Path(args.path).expanduser().resolve()
    if not path.is_file():
        raise SkillError("Upload path must be a regular file.")
    size = path.stat().st_size
    if not 0 < size <= 100 * 1024 * 1024:
        raise SkillError("Files must be nonempty and at most 100 MiB; server purpose limits also apply.")
    content_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
    client.session(args.session_id)
    prepared = client.request("POST", "/uploads", {
        "purpose": "assistant_attachment", "filename": path.name,
        "content_type": content_type, "size_bytes": size,
        "context": {"session_id": args.session_id},
    })
    emit({"type": "upload_prepared", "upload_id": prepared["upload_id"]})
    if prepared["method"] != "PUT":
        raise SkillError("Unsupported upload method.")
    if prepared["transport"] == "api":
        relative = prepared["url"]
        if not relative.startswith("/uploads/"):
            raise SkillError("Unexpected API upload path.")
        url, auth = client.base + "/api/v1" + relative, True
    elif prepared["transport"] == "direct":
        url, auth = prepared["url"], False
    else:
        raise SkillError("Unsupported upload transport.")
    with client.open("PUT", url, body=path.read_bytes(), headers=prepared["headers"],
                     auth=auth, timeout=120):
        pass
    result = client.request("POST", "/assistant/attachments", {
        "session_id": args.session_id, "upload_id": prepared["upload_id"],
    })
    emit({"type": "attachment", **result})


def results(client, session):
    graph = client.canvas(session)
    # Current canvas content, not links extracted from chat or stale previews.
    # Imported materials can also be image/audio/text nodes: callers select IDs.
    items = [{key: node.get(key) for key in
              ("id", "node_key", "node_type", "generation_kind", "knowledge_doc_id", "asset_role",
               "label", "status", "error", "url", "mime_type", "body")}
             for node in graph["nodes"] if node["node_type"] in {"image", "video", "audio", "text"}]
    return {**client.links(session), "nodes": items, "generation_runs": graph["generation_runs"]}


def exportable(node):
    if node["node_type"] == "text":
        return bool(node["body"]) and node["status"] in {None, "idle", "done"}
    return node["status"] == "done"


def download(client, args):
    session = client.session(args.session_id)
    items = results(client, session)["nodes"]
    if args.node_id:
        requested = set(args.node_id)
        items = [node for node in items if node["id"] in requested]
        if {node["id"] for node in items} != requested:
            raise SkillError("One or more requested nodes do not belong to this canvas.")
        if any(not exportable(node) for node in items):
            raise SkillError("Requested nodes are not complete; no files were downloaded.")
    else:
        items = [node for node in items if exportable(node)]
    if not items:
        raise SkillError("No completed output nodes in this canvas.")
    directory = Path(args.output_dir).expanduser().resolve()
    directory.mkdir(parents=True, exist_ok=True)
    downloaded = []
    for node in items:
        if node["node_type"] == "text":
            if not node["body"]:
                continue
            destination = directory / f'node-{node["id"]}.txt'
            with destination.open("x", encoding="utf-8") as handle:
                handle.write(node["body"])
        else:
            suffix = {"image": "download", "audio": "audio-download", "video": "media"}[node["node_type"]]
            media = client.request("GET", f'/canvas/nodes/{node["id"]}/{suffix}')
            url = media["url"]
            if not url:
                raise SkillError(f'Node {node["id"]} has no current media URL.')
            url = safe_url(urllib.parse.urljoin(client.base + "/", url))
            # No platform Authorization header, including for external signed object URLs.
            with client.open("GET", url, timeout=120) as response:
                content_type = response.headers.get_content_type()
                expected = node["node_type"] + "/"
                if not content_type.startswith(expected) and content_type != "application/octet-stream":
                    raise SkillError("Download did not return the expected media type.")
                extension = mimetypes.guess_extension(node["mime_type"] or content_type) or ".bin"
                destination = directory / f'node-{node["id"]}{extension}'
                try:
                    handle = destination.open("xb")
                except FileExistsError:
                    raise SkillError(f"Output already exists: {destination}; choose another directory.") from None
                try:
                    with handle:
                        total = 0
                        while chunk := response.read(1024 * 1024):
                            total += len(chunk)
                            if total > args.max_mb * 1024 * 1024:
                                raise SkillError("Download exceeded --max-mb.")
                            handle.write(chunk)
                        expected_length = response.headers.get("Content-Length")
                        if total == 0 or (expected_length is not None and total != int(expected_length)):
                            raise SkillError("Download was empty or incomplete.")
                except BaseException:
                    destination.unlink(missing_ok=True)
                    raise
        downloaded.append(str(destination))
        emit({"type": "downloaded", "node_id": node["id"], "path": str(destination)})
    emit({"type": "complete", "downloaded": downloaded, **client.links(session)})


def parser():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--version", action="version", version="0.1.0")
    subs = p.add_subparsers(dest="command", required=True)
    s = subs.add_parser("login", help="Interactive password login; token never printed")
    s.add_argument("--phone", required=True)
    s.add_argument("--token-file", required=True, help="New private file outside the repository")
    subs.add_parser("me")
    subs.add_parser("capabilities")
    subs.add_parser("list")
    subs.add_parser("create", help="Create a separate blank canvas/session; no generation")
    s = subs.add_parser("send", help="Send one creative request; stream JSON Lines")
    s.add_argument("session_id", type=positive)
    group = s.add_mutually_exclusive_group(required=True)
    group.add_argument("--message")
    group.add_argument("--message-file")
    s.add_argument("--attachment-id", action="append", type=positive, default=[])
    s.add_argument("--creation-type", choices=("graphic", "storyboard"), help="Only when the user explicitly chose the deliverable type")
    s.add_argument("--settings-file", help="Current CreationSettings JSON; consult capabilities first")
    s.add_argument("--generate-media", action="store_true", help="Authorize requested paid media; off by default")
    s = subs.add_parser("query")
    s.add_argument("session_id", type=positive)
    s.add_argument("--wait", type=int, default=0, choices=range(0, 1801), metavar="0..1800")
    s = subs.add_parser("upload")
    s.add_argument("session_id", type=positive)
    s.add_argument("path")
    for command in ("attachments", "results", "stop"):
        s = subs.add_parser(command)
        s.add_argument("session_id", type=positive)
    s = subs.add_parser("cancel-upload")
    s.add_argument("upload_id", type=uuid.UUID)
    s = subs.add_parser("download")
    s.add_argument("session_id", type=positive)
    s.add_argument("--node-id", action="append", type=positive)
    s.add_argument("--output-dir", required=True)
    s.add_argument("--max-mb", type=positive, default=512)
    return p


def main():
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    args = parser().parse_args()
    try:
        if args.command == "login":
            login(args)
            return
        client = Client()
        if args.command in {"send", "query", "upload", "download"}:
            {"send": send, "query": query, "upload": upload, "download": download}[args.command](client, args)
        elif args.command == "create":
            session = client.request("POST", "/assistant/sessions?force=true")
            emit({**client.links(session), "title": session["title"]})
        elif args.command == "results":
            emit(results(client, client.session(args.session_id)))
        else:
            method, path = {
                "me": ("GET", "/auth/me"),
                "capabilities": ("GET", "/assistant/capabilities"),
                "list": ("GET", "/assistant/sessions"),
                "attachments": ("GET", f'/assistant/attachments?session_id={getattr(args, "session_id", "")}'),
                "stop": ("POST", f'/assistant/sessions/{getattr(args, "session_id", "")}/agent/stop'),
                "cancel-upload": ("DELETE", f'/uploads/{getattr(args, "upload_id", "")}'),
            }[args.command]
            emit(client.request(method, path))
    except KeyboardInterrupt:
        emit({"error": "Client interrupted; server tasks may continue. Query or explicitly stop the session."}, stream=sys.stderr)
        sys.exit(130)
    except SkillError as exc:
        emit({"error": str(exc)}, stream=sys.stderr)
        sys.exit(1)
    except (OSError, ValueError, KeyError, TypeError, http.client.HTTPException) as exc:
        # Tracebacks and response bodies can contain secrets. Keep a closed error surface.
        emit({"error": f"Local file, transport or API contract error ({type(exc).__name__}); no retry performed."}, stream=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
