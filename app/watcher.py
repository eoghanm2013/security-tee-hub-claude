"""
Background JIRA watcher for TEE Hub.

Polls JIRA at a configurable interval for changes on assigned tickets:
  - New comments -> appended to investigations/SCRS-XXXX/jira-updates.md
  - New attachments -> downloaded + pre-analyzed
  - Status changes -> meta.json updated
  - New assignments -> investigation folder created from template
"""

import os
import json
import time
import base64
import shutil
import threading
import urllib.request
import urllib.error
import urllib.parse
from pathlib import Path
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parent.parent
INVESTIGATIONS_DIR = ROOT / "investigations"
STATE_FILE = ROOT / ".watcher_state.json"

# Shared event log for the UI (thread-safe via _events_lock)
_events: list[dict] = []
_events_lock = threading.Lock()
MAX_EVENTS = 50


def _push_event(event_type: str, key: str, message: str, detail: str = ""):
    with _events_lock:
        _events.append({
            "type": event_type,
            "key": key,
            "message": message,
            "detail": detail,
            "ts": datetime.now(timezone.utc).isoformat(),
        })
        if len(_events) > MAX_EVENTS:
            _events.pop(0)


def get_recent_events(since_ts: str = "") -> list[dict]:
    """Get watcher events, optionally filtered to those after since_ts."""
    with _events_lock:
        if not since_ts:
            return list(_events)
        return [e for e in _events if e["ts"] > since_ts]


# ── JIRA Helpers ─────────────────────────────────────────────────────────────

def _jira_auth_header() -> str:
    email = os.environ.get("ATLASSIAN_EMAIL", "")
    token = os.environ.get("ATLASSIAN_API_TOKEN", "")
    if not email or not token:
        return ""
    return base64.b64encode(f"{email}:{token}".encode()).decode()


def _jira_domain() -> str:
    return os.environ.get("ATLASSIAN_DOMAIN", "datadoghq.atlassian.net")


def _jira_request(url: str) -> dict | None:
    auth = _jira_auth_header()
    if not auth:
        return None
    req = urllib.request.Request(url, headers={
        "Authorization": f"Basic {auth}",
        "Accept": "application/json",
    })
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode())
    except Exception as e:
        print(f"[watcher] JIRA request failed: {e}")
        return None


def _extract_adf_text(node) -> str:
    """Extract plain text from Atlassian Document Format."""
    if not node:
        return ""
    if isinstance(node, str):
        return node
    if isinstance(node, dict):
        if node.get("type") == "text":
            return node.get("text", "")
        if "content" in node:
            return "".join(_extract_adf_text(c) for c in node["content"])
    if isinstance(node, list):
        return "".join(_extract_adf_text(c) for c in node)
    return ""


# ── State Management ─────────────────────────────────────────────────────────

def _load_state() -> dict:
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {"last_poll": "", "tickets": {}}


def _save_state(state: dict):
    STATE_FILE.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")


# ── Core Poll Logic ──────────────────────────────────────────────────────────

DONE_STATUSES = {"done", "done (zd automation)", "closed", "resolved", "won't do", "cancelled"}


def _fetch_assigned_tickets() -> list[dict]:
    """Query JIRA for tickets that have local investigation folders.

    Only watches tickets the TEE is actively working on (i.e., has a folder
    in investigations/). Includes Done tickets so we can detect the transition
    and push a ready_to_close event before we stop tracking them.
    """
    tracked_keys = []
    if INVESTIGATIONS_DIR.exists():
        for d in INVESTIGATIONS_DIR.iterdir():
            if d.is_dir() and d.name.startswith("SCRS-") and not d.name.startswith("."):
                tracked_keys.append(d.name)

    if not tracked_keys:
        return []

    keys_clause = ", ".join(tracked_keys)
    jql = f"key IN ({keys_clause}) ORDER BY updated DESC"
    encoded_jql = urllib.parse.quote(jql)

    fields = "summary,status,updated,comment,attachment,customfield_11300"
    url = f"https://{_jira_domain()}/rest/api/3/search/jql?jql={encoded_jql}&maxResults=50&fields={fields}"

    data = _jira_request(url)
    if not data:
        return []
    return data.get("issues", [])


def _ensure_investigation(key: str, summary: str = ""):
    """Create investigation folder from template if it doesn't exist."""
    inv_dir = INVESTIGATIONS_DIR / key
    if inv_dir.exists():
        return inv_dir

    template_dir = INVESTIGATIONS_DIR / ".template"
    inv_dir.mkdir(parents=True, exist_ok=True)
    (inv_dir / "assets").mkdir(exist_ok=True)

    if template_dir.exists():
        for tf in template_dir.iterdir():
            if tf.is_file() and not tf.name.startswith("."):
                dest = inv_dir / tf.name
                if not dest.exists():
                    content = tf.read_text(encoding="utf-8")
                    content = content.replace("SCRS-XXXX", key)
                    if summary and "[Title]" in content:
                        content = content.replace("[Title]", summary)
                    dest.write_text(content, encoding="utf-8")

    meta_path = inv_dir / "meta.json"
    if not meta_path.exists():
        meta_path.write_text(json.dumps({
            "status": "investigating",
            "assignee": os.environ.get("WATCHER_ASSIGNEE", "").split("@")[0],
        }, indent=2) + "\n", encoding="utf-8")

    return inv_dir


def _update_meta_status(key: str, jira_status: str):
    """Update meta.json with the current JIRA status mapped to local statuses."""
    inv_dir = INVESTIGATIONS_DIR / key
    meta_path = inv_dir / "meta.json"
    if not meta_path.exists():
        return

    status_map = {
        "open": "investigating",
        "in progress": "investigating",
        "investigating": "investigating",
        "waiting for customer": "waiting",
        "waiting": "waiting",
        "escalated": "escalated",
        "escalated to engineering": "escalated",
        "done": "done",
        "done (zd automation)": "done",
        "closed": "done",
        "resolved": "done",
        "won't do": "done",
        "cancelled": "done",
    }
    local_status = status_map.get(jira_status.lower().strip(), None)
    if not local_status:
        return

    try:
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        if meta.get("status") != local_status:
            meta["status"] = local_status
            meta_path.write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")
    except Exception:
        pass


def _append_new_comments(key: str, comments: list, last_known_count: int):
    """Append new comments to jira-updates.md."""
    new_comments = comments[last_known_count:]
    if not new_comments:
        return

    inv_dir = INVESTIGATIONS_DIR / key
    updates_path = inv_dir / "jira-updates.md"

    lines = []
    if not updates_path.exists():
        lines.append(f"# JIRA Updates: {key}\n")
        lines.append("*Auto-synced comments from JIRA.*\n")
        lines.append("---\n")

    for c in new_comments:
        author = c.get("author", {}).get("displayName", "Unknown")
        created = c.get("created", "")[:16].replace("T", " ")
        body = _extract_adf_text(c.get("body", {}))
        if body.strip():
            lines.append(f"\n### {author} ({created})\n")
            lines.append(body.strip())
            lines.append("\n---\n")

    if lines:
        with open(updates_path, "a", encoding="utf-8") as f:
            f.write("\n".join(lines))


def _download_new_attachments(key: str, attachments: list, known_ids: set) -> list[str]:
    """Download new attachments, returns list of new attachment IDs."""
    new_ids = []
    try:
        import asset_handler
    except ImportError:
        return new_ids

    for att in attachments:
        att_id = str(att.get("id", ""))
        if att_id in known_ids:
            continue
        filename = att.get("filename", "unknown")
        content_url = att.get("content", "")
        if not content_url:
            continue
        try:
            att_dict = {
                "id": att_id,
                "filename": filename,
                "content_url": content_url,
                "size": att.get("size", 0),
            }
            dest = asset_handler.download_attachment(key, att_dict)
            if dest.suffix.lower() in asset_handler.ARCHIVE_EXTENSIONS:
                asset_handler.extract_archive(dest)
            new_ids.append(att_id)
            _push_event("attachment", key, f"Downloaded: {filename}", str(dest))
        except Exception as e:
            print(f"[watcher] Failed to download {filename} for {key}: {e}")

    # Run pre-analysis if we downloaded anything
    if new_ids:
        try:
            import analyzer
            analyzer.analyze_investigation(key)
            _push_event("analysis", key, "Pre-analysis report generated")
        except Exception as e:
            print(f"[watcher] Analysis failed for {key}: {e}")

    return new_ids


def poll_once() -> dict:
    """Run a single poll cycle. Returns summary of what changed.

    Can be called manually (force poll) or by the background loop.
    """
    state = _load_state()
    tickets_state = state.get("tickets", {})

    issues = _fetch_assigned_tickets()
    if not issues:
        state["last_poll"] = datetime.now(timezone.utc).isoformat()
        _save_state(state)
        return {"checked": 0, "changes": []}

    changes = []

    seen_keys = set()
    for issue in issues:
        key = issue.get("key", "")
        if not key:
            continue
        seen_keys.add(key)
        fields = issue.get("fields", {})
        summary = fields.get("summary", "")
        updated = fields.get("updated", "")
        jira_status = fields.get("status", {}).get("name", "Unknown")
        comments = fields.get("comment", {}).get("comments", [])
        attachments = fields.get("attachment", []) or []

        prev = tickets_state.get(key, {})
        is_new = not prev

        if is_new:
            _ensure_investigation(key, summary)
            _push_event("new_ticket", key, f"New ticket assigned: {summary}")
            changes.append({"key": key, "type": "new_ticket", "summary": summary})

        # Check for status changes
        prev_status = prev.get("status", "")
        is_done = jira_status.lower().strip() in DONE_STATUSES
        if prev_status and jira_status != prev_status:
            _update_meta_status(key, jira_status)
            if is_done:
                _push_event("ready_to_close", key, f"Ticket is Done in JIRA. Ready to extract patterns and close out.", f"{prev_status} -> {jira_status}")
                changes.append({"key": key, "type": "ready_to_close", "from": prev_status, "to": jira_status})
            else:
                _push_event("status_change", key, f"Status: {prev_status} -> {jira_status}")
                changes.append({"key": key, "type": "status_change", "from": prev_status, "to": jira_status})

        # Skip comment/attachment processing for done tickets
        if is_done:
            tickets_state[key] = {
                "updated": updated,
                "status": jira_status,
                "summary": summary,
                "comment_count": len(comments),
                "attachment_ids": sorted({str(a.get("id", "")) for a in attachments}),
                "done": True,
            }
            continue

        # Check for new comments
        prev_comment_count = prev.get("comment_count", 0)
        current_comment_count = len(comments)
        if current_comment_count > prev_comment_count:
            new_count = current_comment_count - prev_comment_count
            _ensure_investigation(key, summary)
            _append_new_comments(key, comments, prev_comment_count)
            last_author = comments[-1].get("author", {}).get("displayName", "Unknown") if comments else "Unknown"
            _push_event("new_comment", key, f"{new_count} new comment(s) from {last_author}")
            changes.append({"key": key, "type": "new_comment", "count": new_count, "author": last_author})

        # Check for new attachments
        prev_att_ids = set(prev.get("attachment_ids", []))
        current_att_ids = {str(a.get("id", "")) for a in attachments}
        new_att_ids_set = current_att_ids - prev_att_ids
        if new_att_ids_set:
            _ensure_investigation(key, summary)
            downloaded_ids = _download_new_attachments(key, attachments, prev_att_ids)
            new_filenames = [a.get("filename", "?") for a in attachments if str(a.get("id", "")) in new_att_ids_set]
            _push_event("new_attachment", key, f"{len(new_att_ids_set)} new attachment(s): {', '.join(new_filenames)}")
            changes.append({"key": key, "type": "new_attachment", "filenames": new_filenames})

        # Update state for this ticket
        tickets_state[key] = {
            "updated": updated,
            "status": jira_status,
            "summary": summary,
            "comment_count": current_comment_count,
            "attachment_ids": sorted(current_att_ids),
        }

    # Remove tickets no longer in results or already marked done (no need to keep polling)
    stale_keys = set(tickets_state.keys()) - seen_keys
    for sk in stale_keys:
        del tickets_state[sk]
    done_keys = [k for k, v in tickets_state.items() if v.get("done")]
    for dk in done_keys:
        del tickets_state[dk]

    state["last_poll"] = datetime.now(timezone.utc).isoformat()
    state["tickets"] = tickets_state
    _save_state(state)

    return {"checked": len(issues), "changes": changes}


# ── Background Thread ────────────────────────────────────────────────────────

class JiraWatcher:
    """Background thread that polls JIRA at a fixed interval."""

    def __init__(self):
        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()
        self._interval = int(os.environ.get("WATCHER_INTERVAL_SECONDS", "180"))
        self._enabled = os.environ.get("WATCHER_ENABLED", "false").lower() in ("true", "1", "yes")
        self._running = False
        self._last_poll_result: dict = {}

    @property
    def is_running(self) -> bool:
        return self._running and self._thread is not None and self._thread.is_alive()

    @property
    def interval(self) -> int:
        return self._interval

    @property
    def last_poll_result(self) -> dict:
        return self._last_poll_result

    def status(self) -> dict:
        state = _load_state()
        return {
            "enabled": self._enabled,
            "running": self.is_running,
            "interval_seconds": self._interval,
            "last_poll": state.get("last_poll", ""),
            "watching_count": len(state.get("tickets", {})),
            "tickets": list(state.get("tickets", {}).keys()),
            "last_result": self._last_poll_result,
        }

    def start(self):
        if self.is_running:
            return
        self._stop_event.clear()
        self._running = True
        self._thread = threading.Thread(target=self._run, daemon=True, name="jira-watcher")
        self._thread.start()
        _push_event("watcher", "", f"Watcher started (interval: {self._interval}s)")
        print(f"[watcher] Started, polling every {self._interval}s")

    def stop(self):
        self._stop_event.set()
        self._running = False
        _push_event("watcher", "", "Watcher stopped")
        print("[watcher] Stopped")

    def force_poll(self) -> dict:
        """Run a poll cycle immediately (called from API route)."""
        result = poll_once()
        self._last_poll_result = result
        return result

    def _run(self):
        # Initial delay to let the app start up
        self._stop_event.wait(5)

        while not self._stop_event.is_set():
            try:
                result = poll_once()
                self._last_poll_result = result
                if result.get("changes"):
                    print(f"[watcher] Poll found {len(result['changes'])} change(s)")
            except Exception as e:
                print(f"[watcher] Poll error: {e}")
                _push_event("error", "", f"Poll error: {e}")

            self._stop_event.wait(self._interval)

    def auto_start(self):
        """Start if WATCHER_ENABLED is set."""
        if self._enabled:
            self.start()


# Global singleton
watcher = JiraWatcher()
