#!/usr/bin/env python3
"""Generic Hermes cron post monitor.

Monitors multiple public X handles (without X/xAI API credentials) and
multiple websites/RSS/Atom feeds from a single JSON config.

Designed for Hermes cron no-agent mode:
- Prints notifications only when new posts are detected.
- Prints nothing when there is no change, so cron stays silent.
- Exits non-zero only when all due sources fail, so broken monitoring alerts.

Default config path:
  ${HERMES_HOME:-~/.hermes}/data/monitors/post-monitor-config.json

Default state path:
  ${HERMES_HOME:-~/.hermes}/data/monitors/post-monitor-state.json
"""

from __future__ import annotations

import argparse
import email.utils
import hashlib
import html
import json
import os
import re
import sys
import tempfile
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (compatible; Hermes-Post-Monitor/1.0; "
    "+https://hermes-agent.nousresearch.com)"
)
REQUEST_TIMEOUT_SECONDS = 30
COMMON_FEED_PATHS = ("/rss.xml", "/feed.xml", "/atom.xml", "/feed", "/rss")

HERMES_HOME = Path(os.environ.get("HERMES_HOME", Path.home() / ".hermes")).expanduser()
DEFAULT_CONFIG_PATH = HERMES_HOME / "data" / "monitors" / "post-monitor-config.json"
DEFAULT_STATE_PATH = HERMES_HOME / "data" / "monitors" / "post-monitor-state.json"


@dataclass
class MonitorItem:
    source_id: str
    source_type: str
    source_name: str
    item_id: str
    title: str = ""
    text: str = ""
    url: str = ""
    mirror_url: str = ""
    author: str = ""
    category: str = ""
    published_at: str = ""
    raw_published_at: str = ""
    fetch_source: str = ""


def utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(microsecond=0)


def utc_now_iso() -> str:
    return utc_now().isoformat()


def parse_iso_datetime(value: str) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)
    except Exception:
        return None


def parse_feed_datetime(value: str) -> str:
    if not value:
        return ""
    value = value.strip()

    # RFC 2822 / RSS pubDate.
    try:
        parsed = email.utils.parsedate_to_datetime(value)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc).replace(microsecond=0).isoformat()
    except Exception:
        pass

    # ISO / Atom updated.
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc).replace(microsecond=0).isoformat()
    except Exception:
        return value


def clean_html(value: str, max_chars: int | None = None) -> str:
    value = value or ""
    value = re.sub(r"</p>|</div>|</li>|<br\s*/?>", "\n", value, flags=re.I)
    value = re.sub(r"<[^>]+>", " ", value)
    value = html.unescape(value)
    value = re.sub(r"[ \t\r\f\v]+", " ", value)
    value = re.sub(r"\n\s+", "\n", value)
    value = re.sub(r"\n{3,}", "\n\n", value)
    value = value.strip()
    if max_chars and len(value) > max_chars:
        value = value[: max_chars - 3].rstrip() + "..."
    return value


def normalize_handle(value: str) -> str:
    value = (value or "").strip()
    value = value[1:] if value.startswith("@") else value
    value = value.strip().strip("/")
    if not re.fullmatch(r"[A-Za-z0-9_]{1,20}", value):
        raise ValueError(f"Invalid X handle: {value!r}")
    return value


def sha_id(*parts: str) -> str:
    payload = "\u241f".join(part or "" for part in parts)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:32]


def fetch_url(url: str, *, user_agent: str, accept: str = "*/*", timeout: int = REQUEST_TIMEOUT_SECONDS) -> bytes:
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": user_agent,
            "Accept": accept,
            "Accept-Language": "en-US,en;q=0.9,id;q=0.8",
            "Cache-Control": "no-cache",
        },
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        status = getattr(response, "status", 200)
        if status >= 400:
            raise RuntimeError(f"HTTP {status} while fetching {url}")
        return response.read()


def load_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def atomic_write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    serialized = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=str(path.parent), delete=False) as tmp:
        tmp.write(serialized)
        tmp.write("\n")
        tmp_path = Path(tmp.name)
    tmp_path.replace(path)


def source_id_for(source: dict[str, Any]) -> str:
    if source.get("id"):
        return str(source["id"])
    source_type = source.get("type")
    if source_type == "x":
        return "x-" + normalize_handle(str(source.get("handle", ""))).lower()
    if source_type in {"website", "rss"}:
        raw = source.get("url") or source.get("feed_url") or source.get("feed_urls") or source.get("name")
        return "web-" + sha_id(json.dumps(raw, sort_keys=True))[:12]
    return "source-" + sha_id(json.dumps(source, sort_keys=True))[:12]


def should_check_source(source: dict[str, Any], source_state: dict[str, Any], *, force: bool) -> bool:
    if force:
        return True
    interval = source.get("min_interval_seconds")
    if interval is None:
        return True
    try:
        interval_seconds = int(interval)
    except Exception:
        return True
    if interval_seconds <= 0:
        return True

    last_checked_at = parse_iso_datetime(str(source_state.get("last_checked_at", "")))
    if not last_checked_at:
        return True
    return (utc_now() - last_checked_at).total_seconds() >= interval_seconds


def feed_text(element: ET.Element, child_name: str) -> str:
    value = element.findtext(child_name)
    if value is not None:
        return html.unescape(value.strip())
    for child in element:
        if child.tag.rsplit("}", 1)[-1] == child_name:
            return html.unescape((child.text or "").strip())
    return ""


def parse_feed_items(
    *,
    source_id: str,
    source_type: str,
    source_name: str,
    feed_url: str,
    xml_bytes: bytes,
    item_url_transform=None,
    author_default: str = "",
    category_default: str = "",
) -> list[MonitorItem]:
    root = ET.fromstring(xml_bytes)
    items: list[MonitorItem] = []

    channel = root.find("channel")
    channel_element = channel if channel is not None else root
    channel_title = feed_text(channel_element, "title")
    channel_description = feed_text(channel_element, "description")
    if "RSS reader not yet whitelisted" in channel_title or "RSS reader not yet whitelist" in channel_description:
        raise RuntimeError("feed returned whitelist placeholder, not real feed")

    # RSS 2.0.
    dc_creator_tag = "{http://purl.org/dc/elements/1.1/}creator"
    for item in root.findall("./channel/item"):
        title = feed_text(item, "title")
        link = feed_text(item, "link")
        guid = feed_text(item, "guid") or link
        creator = feed_text(item, dc_creator_tag) or author_default
        description = clean_html(item.findtext("description") or "")
        raw_date = feed_text(item, "pubDate")
        published_at = parse_feed_datetime(raw_date)
        category = feed_text(item, "category") or category_default or channel_title
        item_id = guid or link or sha_id(feed_url, title, raw_date, description)
        final_url = item_url_transform(link, guid) if item_url_transform else link

        items.append(
            MonitorItem(
                source_id=source_id,
                source_type=source_type,
                source_name=source_name,
                item_id=str(item_id),
                title=title,
                text=description or title,
                url=final_url or link,
                mirror_url=link if final_url and final_url != link else "",
                author=creator,
                category=category,
                published_at=published_at,
                raw_published_at=raw_date,
                fetch_source=feed_url,
            )
        )

    if items:
        return items

    # Atom.
    ns = {"atom": "http://www.w3.org/2005/Atom"}
    feed_title = root.findtext("atom:title", namespaces=ns) or source_name
    for entry in root.findall(".//atom:entry", ns):
        title = feed_text(entry, "title")
        link = ""
        for link_el in entry.findall("atom:link", ns):
            href = html.unescape(link_el.attrib.get("href", "").strip())
            rel = link_el.attrib.get("rel", "alternate")
            if href and rel in ("alternate", ""):
                link = urllib.parse.urljoin(feed_url, href)
                break
        entry_id = feed_text(entry, "id") or link
        summary = clean_html(feed_text(entry, "summary") or feed_text(entry, "content"))
        raw_date = feed_text(entry, "updated") or feed_text(entry, "published")
        published_at = parse_feed_datetime(raw_date)
        item_id = entry_id or link or sha_id(feed_url, title, raw_date, summary)
        final_url = item_url_transform(link, item_id) if item_url_transform else link

        items.append(
            MonitorItem(
                source_id=source_id,
                source_type=source_type,
                source_name=source_name,
                item_id=str(item_id),
                title=title,
                text=summary or title,
                url=final_url or link,
                mirror_url=link if final_url and final_url != link else "",
                author=author_default,
                category=category_default or feed_title,
                published_at=published_at,
                raw_published_at=raw_date,
                fetch_source=feed_url,
            )
        )

    return items


def discover_feed_urls(homepage_url: str, *, user_agent: str) -> list[str]:
    html_bytes = fetch_url(homepage_url, user_agent=user_agent, accept="text/html,application/xhtml+xml,*/*")
    html_text = html_bytes.decode("utf-8", "replace")
    feeds: list[str] = []
    seen: set[str] = set()

    link_pattern = re.compile(r"<link\b[^>]*>", re.I)
    href_pattern = re.compile(r"\bhref\s*=\s*(['\"])(.*?)\1", re.I | re.S)
    type_pattern = re.compile(r"\btype\s*=\s*(['\"])(.*?)\1", re.I | re.S)
    rel_pattern = re.compile(r"\brel\s*=\s*(['\"])(.*?)\1", re.I | re.S)

    for tag_match in link_pattern.finditer(html_text):
        tag = tag_match.group(0)
        href_match = href_pattern.search(tag)
        if not href_match:
            continue
        rel = rel_pattern.search(tag)
        typ = type_pattern.search(tag)
        rel_value = (rel.group(2) if rel else "").lower()
        type_value = (typ.group(2) if typ else "").lower()
        if "alternate" not in rel_value and "rss" not in type_value and "atom" not in type_value:
            continue
        if "rss" not in type_value and "atom" not in type_value and "feed" not in tag.lower():
            continue
        feed_url = urllib.parse.urljoin(homepage_url, html.unescape(href_match.group(2)))
        if feed_url not in seen:
            feeds.append(feed_url)
            seen.add(feed_url)

    if feeds:
        return feeds

    # Conservative common-path fallback. Only include paths that parse as feeds.
    for path in COMMON_FEED_PATHS:
        candidate = urllib.parse.urljoin(homepage_url.rstrip("/") + "/", path.lstrip("/"))
        try:
            xml_bytes = fetch_url(candidate, user_agent=user_agent, accept="application/rss+xml,application/xml,text/xml,*/*")
            parse_feed_items(
                source_id="discovery",
                source_type="rss",
                source_name="discovery",
                feed_url=candidate,
                xml_bytes=xml_bytes,
            )
            if candidate not in seen:
                feeds.append(candidate)
                seen.add(candidate)
        except Exception:
            continue

    return feeds


def x_status_url(handle: str, tweet_id: str) -> str:
    return f"https://x.com/{handle}/status/{tweet_id}"


def nitter_url_to_x(handle: str, link: str, guid: str = "") -> str:
    tweet_id = guid or ""
    if not tweet_id:
        match = re.search(r"/status/(\d+)", link or "")
        if match:
            tweet_id = match.group(1)
    return x_status_url(handle, tweet_id) if tweet_id else f"https://x.com/{handle}"


def parse_x_rss_items(source: dict[str, Any], source_id: str, source_name: str, feed_url: str, xml_bytes: bytes) -> list[MonitorItem]:
    handle = normalize_handle(str(source.get("handle", "")))
    display_handle = "@" + handle

    def transform(link: str, guid: str) -> str:
        return nitter_url_to_x(handle, link, guid)

    items = parse_feed_items(
        source_id=source_id,
        source_type="x",
        source_name=source_name,
        feed_url=feed_url,
        xml_bytes=xml_bytes,
        item_url_transform=transform,
        author_default=display_handle,
    )

    filtered: list[MonitorItem] = []
    include_replies = bool(source.get("include_replies", True))
    include_reposts = bool(source.get("include_reposts", True))
    for item in items:
        if item.author and item.author.lower().lstrip("@") != handle.lower():
            continue
        item.author = display_handle
        # Nitter RSS GUID is usually the tweet ID. If not, extract one.
        match = re.search(r"/status/(\d+)", item.url or item.mirror_url)
        if match:
            item.item_id = match.group(1)
            item.url = x_status_url(handle, item.item_id)
        if not include_reposts and item.text.strip().startswith("RT @"):
            continue
        if not include_replies and item.title.lower().startswith("replying to"):
            continue
        filtered.append(item)
    return filtered


def parse_direct_x_html(source: dict[str, Any], source_id: str, source_name: str, html_text: str) -> list[MonitorItem]:
    handle = normalize_handle(str(source.get("handle", "")))
    display_handle = "@" + handle
    ids: list[str] = []
    seen: set[str] = set()
    pattern = re.compile(rf"(?:https?://(?:twitter|x)\.com)?/{re.escape(handle)}/status/(\d+)", re.I)
    for match in pattern.finditer(html_text):
        tweet_id = match.group(1)
        if tweet_id not in seen:
            ids.append(tweet_id)
            seen.add(tweet_id)
    return [
        MonitorItem(
            source_id=source_id,
            source_type="x",
            source_name=source_name,
            item_id=tweet_id,
            url=x_status_url(handle, tweet_id),
            author=display_handle,
            fetch_source=f"https://x.com/{handle}",
        )
        for tweet_id in ids
    ]


def fetch_x_source(source: dict[str, Any], *, config: dict[str, Any], source_id: str) -> tuple[list[MonitorItem], list[str]]:
    handle = normalize_handle(str(source.get("handle", "")))
    display_handle = "@" + handle
    source_name = str(source.get("name") or display_handle)
    user_agent = str(source.get("user_agent") or config.get("user_agent") or DEFAULT_USER_AGENT)
    timeout = int(source.get("timeout_seconds") or config.get("timeout_seconds") or REQUEST_TIMEOUT_SECONDS)
    errors: list[str] = []

    rss_urls = list(source.get("rss_urls") or [])
    if not rss_urls:
        instances = source.get("nitter_instances") or config.get("nitter_instances") or ["https://nitter.net"]
        for instance in instances:
            base = str(instance).rstrip("/")
            rss_urls.append(f"{base}/{handle}/rss")

    for rss_url in rss_urls:
        try:
            xml_bytes = fetch_url(rss_url, user_agent=user_agent, accept="application/rss+xml,application/xml,text/xml,*/*", timeout=timeout)
            items = parse_x_rss_items(source, source_id, source_name, rss_url, xml_bytes)
            if items:
                return items, errors
            errors.append(f"{rss_url}: no items")
        except Exception as exc:
            errors.append(f"{rss_url}: {exc}")

    if bool(source.get("direct_x_fallback", config.get("direct_x_fallback", True))):
        profile_url = f"https://x.com/{handle}"
        try:
            html_bytes = fetch_url(profile_url, user_agent=user_agent, accept="text/html,application/xhtml+xml,*/*", timeout=timeout)
            items = parse_direct_x_html(source, source_id, source_name, html_bytes.decode("utf-8", "replace"))
            if items:
                return items, errors
            errors.append(f"{profile_url}: no logged-out status links found")
        except Exception as exc:
            errors.append(f"{profile_url}: {exc}")

    return [], errors


def fetch_website_source(source: dict[str, Any], *, config: dict[str, Any], source_id: str) -> tuple[list[MonitorItem], list[str]]:
    source_type = str(source.get("type") or "website")
    source_name = str(source.get("name") or source.get("url") or source.get("feed_url") or source_id)
    user_agent = str(source.get("user_agent") or config.get("user_agent") or DEFAULT_USER_AGENT)
    timeout = int(source.get("timeout_seconds") or config.get("timeout_seconds") or REQUEST_TIMEOUT_SECONDS)
    errors: list[str] = []
    feed_urls: list[str] = []

    if source_type == "rss" and source.get("url"):
        feed_urls.append(str(source["url"]))
    if source.get("feed_url"):
        feed_urls.append(str(source["feed_url"]))
    feed_urls.extend(str(url) for url in source.get("feed_urls") or [])

    if not feed_urls and source.get("url"):
        try:
            feed_urls = discover_feed_urls(str(source["url"]), user_agent=user_agent)
        except Exception as exc:
            errors.append(f"feed discovery failed for {source.get('url')}: {exc}")

    # De-duplicate while keeping order.
    unique_feed_urls: list[str] = []
    seen_urls: set[str] = set()
    for url in feed_urls:
        if url not in seen_urls:
            unique_feed_urls.append(url)
            seen_urls.add(url)

    items: list[MonitorItem] = []
    for feed_url in unique_feed_urls:
        try:
            xml_bytes = fetch_url(feed_url, user_agent=user_agent, accept="application/rss+xml,application/atom+xml,application/xml,text/xml,*/*", timeout=timeout)
            feed_items = parse_feed_items(
                source_id=source_id,
                source_type="website",
                source_name=source_name,
                feed_url=feed_url,
                xml_bytes=xml_bytes,
                category_default=str(source.get("category") or ""),
            )
            items.extend(feed_items)
        except Exception as exc:
            errors.append(f"{feed_url}: {exc}")

    return items, errors


def fetch_source(source: dict[str, Any], *, config: dict[str, Any], source_id: str) -> tuple[list[MonitorItem], list[str]]:
    source_type = str(source.get("type") or "").lower()
    if source_type == "x":
        return fetch_x_source(source, config=config, source_id=source_id)
    if source_type in {"website", "rss"}:
        return fetch_website_source(source, config=config, source_id=source_id)
    return [], [f"unsupported source type {source_type!r}"]


def item_sort_key(item: MonitorItem) -> tuple[str, int, str]:
    published = item.published_at or ""
    try:
        numeric_id = int(re.sub(r"\D", "", item.item_id) or "0")
    except Exception:
        numeric_id = 0
    return (published, numeric_id, item.item_id)


def format_item(item: MonitorItem, *, max_text_chars: int) -> str:
    text = clean_html(item.text or item.title or "", max_text_chars)
    detected_at = utc_now_iso()

    if item.source_type == "x":
        header = f"🐦 Post X baru dari {item.author or item.source_name}"
        lines = [header, f"URL: {item.url or '-'}"]
    else:
        header = f"📝 Post website baru: {item.source_name}"
        lines = [header]
        if item.category:
            lines.append(f"Kategori: {item.category}")
        if item.title:
            lines.append(f"Judul: {item.title}")
        lines.append(f"URL: {item.url or '-'}")

    if item.published_at:
        lines.append(f"Published: {item.published_at}")
    lines.append(f"Detected: {detected_at}")
    if item.fetch_source:
        lines.append(f"Source: {item.fetch_source}")
    if text:
        label = "Text" if item.source_type == "x" else "Ringkasan"
        lines.append(f"{label}: {text}")
    if item.mirror_url:
        lines.append(f"Mirror: {item.mirror_url}")
    return "\n".join(lines)


def format_notifications(items: Iterable[MonitorItem], *, config: dict[str, Any]) -> str:
    notification_config = config.get("notification") or {}
    max_text_chars = int(notification_config.get("max_text_chars") or 700)
    max_items = int(notification_config.get("max_items_per_run") or 20)
    sorted_items = sorted(items, key=item_sort_key)
    rendered = [format_item(item, max_text_chars=max_text_chars) for item in sorted_items[:max_items]]
    if len(sorted_items) > max_items:
        rendered.append(f"…dan {len(sorted_items) - max_items} item baru lainnya.")
    return "\n\n".join(rendered)


def run(config_path: Path, state_path: Path, *, force: bool = False, dry_run: bool = False) -> tuple[str, dict[str, Any], int]:
    config = load_json(config_path, None)
    if not isinstance(config, dict):
        raise RuntimeError(f"Config not found or invalid: {config_path}")

    sources = config.get("sources") or []
    if not isinstance(sources, list) or not sources:
        raise RuntimeError("Config must contain a non-empty sources array")

    state = load_json(state_path, {"version": 1, "created_at": utc_now_iso(), "sources": {}})
    if not isinstance(state, dict):
        raise RuntimeError(f"State file has invalid format: {state_path}")
    state.setdefault("version", 1)
    state.setdefault("created_at", utc_now_iso())
    state.setdefault("sources", {})

    new_items: list[MonitorItem] = []
    due_count = 0
    ok_count = 0
    failed_due_sources: list[str] = []
    skipped_sources: list[str] = []

    for source in sources:
        if not isinstance(source, dict):
            continue
        if not bool(source.get("enabled", True)):
            continue
        source_id = source_id_for(source)
        source_state = state["sources"].setdefault(source_id, {})
        source_state.setdefault("seen_ids", [])
        source_state.setdefault("created_at", utc_now_iso())

        if not should_check_source(source, source_state, force=force):
            skipped_sources.append(source_id)
            continue

        due_count += 1
        source_state["last_checked_at"] = utc_now_iso()
        try:
            items, errors = fetch_source(source, config=config, source_id=source_id)
            if not items:
                raise RuntimeError("no items returned" + (": " + " | ".join(errors) if errors else ""))

            seen_ids = set(str(x) for x in source_state.get("seen_ids", []) if x)
            current_ids = {item.item_id for item in items if item.item_id}
            source_new_items = [item for item in items if item.item_id and item.item_id not in seen_ids]

            # First time a source appears in state: seed silently, unless the user
            # pre-populated seen_ids from a legacy monitor.
            if not source_state.get("seeded_at") and not seen_ids:
                source_state["seeded_at"] = utc_now_iso()
                source_new_items = []

            source_state["seen_ids"] = sorted(seen_ids | current_ids)
            source_state["last_status"] = "ok"
            source_state["last_item_count"] = len(items)
            source_state["last_new_count"] = len(source_new_items)
            source_state["last_errors"] = errors[-5:]
            source_state["last_source_type"] = str(source.get("type") or "")
            source_state["last_source_name"] = str(source.get("name") or source.get("handle") or source.get("url") or source_id)
            ok_count += 1
            new_items.extend(source_new_items)
        except Exception as exc:
            source_state["last_status"] = "error"
            source_state["last_error"] = str(exc)
            source_state["last_error_at"] = utc_now_iso()
            failed_due_sources.append(f"{source_id}: {exc}")

    state["last_run_at"] = utc_now_iso()
    state["last_due_count"] = due_count
    state["last_ok_count"] = ok_count
    state["last_failed_due_sources"] = failed_due_sources[-10:]
    state["last_skipped_sources"] = skipped_sources[-20:]
    state["last_new_count"] = len(new_items)

    if not dry_run:
        atomic_write_json(state_path, state)

    output = format_notifications(new_items, config=config) if new_items else ""

    if due_count > 0 and ok_count == 0:
        error_summary = " | ".join(failed_due_sources) if failed_due_sources else "all due sources failed"
        raise RuntimeError(error_summary)

    return output, state, len(new_items)


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Generic Hermes cron monitor for X handles and website feeds")
    parser.add_argument("--config", default=os.environ.get("POST_MONITOR_CONFIG") or str(DEFAULT_CONFIG_PATH))
    parser.add_argument("--state", default=os.environ.get("POST_MONITOR_STATE") or "")
    parser.add_argument("--force", action="store_true", help="Check all sources even if min_interval_seconds says to skip")
    parser.add_argument("--dry-run", action="store_true", help="Do not write state")
    parser.add_argument("--summary", action="store_true", help="Print a human-readable summary even when no new posts")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_arg_parser()
    args = parser.parse_args(argv)
    config_path = Path(args.config).expanduser()
    config = load_json(config_path, {}) if config_path.exists() else {}
    configured_state = args.state or (config.get("state_path") if isinstance(config, dict) else "")
    state_path = Path(configured_state).expanduser() if configured_state else DEFAULT_STATE_PATH

    try:
        output, state, new_count = run(config_path, state_path, force=args.force, dry_run=args.dry_run)
        if output:
            print(output)
        elif args.summary:
            print(
                "post-monitor ok: "
                f"due={state.get('last_due_count')} "
                f"ok={state.get('last_ok_count')} "
                f"new={new_count} "
                f"skipped={len(state.get('last_skipped_sources') or [])}"
            )
        return 0
    except Exception as exc:
        print(f"post-monitor failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
