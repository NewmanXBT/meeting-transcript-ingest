#!/usr/bin/env python3
"""Import meeting transcripts into the ZeroDrift Obsidian material library."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import textwrap
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple


ROOT = Path(__file__).resolve().parents[1]
STATE_DIR = ROOT / "state"
DEFAULT_SOURCES_DIR = (
    Path.home()
    / "Documents/Obsidian Vault/ZeroDrift Material Library/sources/meetings"
)
DEFAULT_INTERNAL_DIR = (
    Path.home() / "Documents/Obsidian Vault/ZeroDrift Wiki/raw/internal"
)
DEFAULT_GOOGLE_TOKEN = STATE_DIR / "google-meet-token.json"
DEFAULT_GOOGLE_CLIENT_SECRET = STATE_DIR / "google-oauth-client.json"

GOOGLE_MEET_SCOPES = ["https://www.googleapis.com/auth/meetings.space.readonly"]

CRYPTO_GLOSSARY = [
    "ZeroDrift",
    "Security World Model",
    "smart contract",
    "EVM",
    "Solana",
    "SVM",
    "Move",
    "Aptos",
    "Sui",
    "DeFi",
    "DEX",
    "AMM",
    "CLMM",
    "Uniswap",
    "Aave",
    "Compound",
    "Pendle",
    "EigenLayer",
    "Restaking",
    "oracle",
    "liquidation",
    "MEV",
    "sandwich",
    "front-run",
    "governance",
    "multisig",
    "timelock",
    "vault",
    "TVL",
    "fork simulation",
    "proof-of-exploit",
    "PoC",
    "bug bounty",
    "Immunefi",
    "Code4rena",
    "Cantina",
    "Sherlock",
    "Trail of Bits",
    "OpenZeppelin",
    "Certora",
    "OtterSec",
    "SlowMist",
]


class IngestError(Exception):
    pass


def now_local() -> dt.datetime:
    return dt.datetime.now().astimezone()


def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def slugify(value: str, fallback: str = "meeting") -> str:
    value = value.strip().lower()
    value = re.sub(r"https?://", "", value)
    value = re.sub(r"[^a-z0-9]+", "-", value)
    value = value.strip("-")
    return value[:80] or fallback


def load_env_file(path: Path) -> None:
    if not path.exists():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


def yaml_scalar(value: str) -> str:
    escaped = value.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


def yaml_list(values: Iterable[str]) -> str:
    items = [v for v in values if v]
    if not items:
        return "[]"
    return "[" + ", ".join(yaml_scalar(v) for v in items) + "]"


def parse_json_response(raw: bytes) -> Dict[str, Any]:
    text = raw.decode("utf-8")
    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        raise IngestError(f"Expected JSON response, got: {text[:500]}") from exc


def http_json(
    method: str,
    url: str,
    *,
    headers: Optional[Dict[str, str]] = None,
    body: Optional[Dict[str, Any]] = None,
    timeout: int = 60,
) -> Dict[str, Any]:
    data = None
    request_headers = dict(headers or {})
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        request_headers.setdefault("Content-Type", "application/json; charset=utf-8")
    req = urllib.request.Request(url, data=data, headers=request_headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return parse_json_response(resp.read())
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise IngestError(f"HTTP {exc.code} for {url}: {detail[:1200]}") from exc


def http_bytes(
    method: str,
    url: str,
    *,
    headers: Optional[Dict[str, str]] = None,
    timeout: int = 120,
) -> bytes:
    req = urllib.request.Request(url, headers=headers or {}, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.read()
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise IngestError(f"HTTP {exc.code} for {url}: {detail[:1200]}") from exc


def seconds_from_rfc3339(value: Optional[str]) -> str:
    if not value:
        return ""
    try:
        parsed = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return value
    return parsed.astimezone().strftime("%H:%M:%S")


def markdown_note(
    *,
    title: str,
    platform: str,
    transcript_text: str,
    source_url: str = "",
    source_id: str = "",
    transcript_source: str = "",
    imported_at: Optional[dt.datetime] = None,
    ai_brief: str = "",
    extra: Optional[Dict[str, str]] = None,
) -> str:
    imported_at = imported_at or now_local()
    created = imported_at.strftime("%Y-%m-%d")
    updated = created
    tags = ["content", "source", "meeting", "transcript", "crypto", "security"]
    extra = extra or {}
    frontmatter_lines = [
        "---",
        f"title: {yaml_scalar(title)}",
        f"created: {created}",
        f"updated: {updated}",
        "type: source-note",
        f"tags: {yaml_list(tags)}",
        f"platform: {yaml_scalar(platform)}",
        f"source_id: {yaml_scalar(source_id)}",
        f"source_url: {yaml_scalar(source_url)}",
        f"transcript_source: {yaml_scalar(transcript_source)}",
        f"imported_at: {yaml_scalar(imported_at.isoformat())}",
    ]
    for key, value in sorted(extra.items()):
        if value:
            frontmatter_lines.append(f"{key}: {yaml_scalar(value)}")
    frontmatter_lines.append("---")

    brief = ai_brief.strip() or (
        "Not generated yet. Run this importer again with `--summarize` after setting "
        "`OPENAI_API_KEY`, or ask Codex to summarize this source note."
    )
    glossary = ", ".join(CRYPTO_GLOSSARY)
    return "\n".join(frontmatter_lines) + f"""

# {title}

## Why this belongs in the material library

This is a meeting transcript source note. It preserves the raw transcript and enough provenance for later ZeroDrift strategy, customer-delivery, security research, and company-memory work.

## Source facts

- Platform: {platform}
- Source URL: {source_url or "not provided"}
- Source ID: {source_id or "not provided"}
- Transcript source: {transcript_source or "not provided"}
- Imported at: {imported_at.isoformat()}

## AI / operator summary

{brief}

## Crypto/domain vocabulary to preserve

{glossary}

## Raw transcript

```text
{transcript_text.strip()}
```
"""


def write_note(
    *,
    title: str,
    platform: str,
    transcript_text: str,
    source_url: str = "",
    source_id: str = "",
    transcript_source: str = "",
    sources_dir: Path = DEFAULT_SOURCES_DIR,
    internal_dir: Optional[Path] = None,
    summarize: bool = False,
    ai_brief: str = "",
    extra: Optional[Dict[str, str]] = None,
) -> Path:
    ensure_dir(sources_dir)
    date_prefix = now_local().strftime("%Y-%m-%d")
    filename = f"source-{date_prefix}-{platform}-{slugify(title)}.md"
    note = markdown_note(
        title=title,
        platform=platform,
        transcript_text=transcript_text,
        source_url=source_url,
        source_id=source_id,
        transcript_source=transcript_source,
        ai_brief=ai_brief,
        extra=extra,
    )
    out_path = sources_dir / filename
    out_path.write_text(note, encoding="utf-8")

    if internal_dir:
        ensure_dir(internal_dir)
        internal_path = internal_dir / f"{date_prefix}-{platform}-{slugify(title)}.md"
        internal_path.write_text(note, encoding="utf-8")

    return out_path


def generate_openai_brief(transcript_text: str, *, model: str, title: str) -> str:
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise IngestError("OPENAI_API_KEY is not set; cannot generate AI summary.")

    trimmed = transcript_text.strip()
    max_chars = int(os.environ.get("MEETING_SUMMARY_MAX_CHARS", "120000"))
    if len(trimmed) > max_chars:
        trimmed = trimmed[:max_chars] + "\n\n[Transcript truncated for summary generation.]"

    system = (
        "You turn meeting transcripts into ZeroDrift company-memory notes. "
        "Write in Chinese by default, preserve English technical terms, normalize obvious "
        "crypto/security vocabulary, and do not invent facts not supported by the transcript."
    )
    user = f"""
Meeting title: {title}

Crypto/security vocabulary to preserve:
{", ".join(CRYPTO_GLOSSARY)}

Produce a concise but useful note with these sections:
1. Core summary
2. Decisions
3. Action items with owners if stated
4. Security/product/customer signals
5. Open questions
6. Terms or names that may need human correction

Transcript:
{trimmed}
"""
    payload = {
        "model": model,
        "input": [
            {"role": "system", "content": [{"type": "input_text", "text": system}]},
            {"role": "user", "content": [{"type": "input_text", "text": user}]},
        ],
        "max_output_tokens": int(os.environ.get("MEETING_SUMMARY_MAX_OUTPUT_TOKENS", "2400")),
    }
    req = urllib.request.Request(
        "https://api.openai.com/v1/responses",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=240) as resp:
            data = parse_json_response(resp.read())
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise IngestError(f"OpenAI summary failed: HTTP {exc.code}: {detail[:1200]}") from exc

    if data.get("output_text"):
        return str(data["output_text"]).strip()

    pieces: List[str] = []
    for item in data.get("output", []):
        for content in item.get("content", []):
            text = content.get("text")
            if text:
                pieces.append(text)
    if pieces:
        return "\n".join(pieces).strip()
    raise IngestError(f"Could not parse OpenAI summary response: {json.dumps(data)[:1000]}")


def get_google_creds(token_path: Path, client_secret_path: Path):
    try:
        from google.auth.transport.requests import Request
        from google.oauth2.credentials import Credentials
        from google_auth_oauthlib.flow import InstalledAppFlow
    except ImportError as exc:
        raise IngestError(
            "Missing Google client libraries. Install requirements first: "
            "uv pip install -r requirements.txt --python .venv/bin/python"
        ) from exc

    creds = None
    if token_path.exists():
        creds = Credentials.from_authorized_user_file(str(token_path), GOOGLE_MEET_SCOPES)
    if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())
    if not creds or not creds.valid:
        if not client_secret_path.exists():
            raise IngestError(
                f"Missing Google OAuth client secret at {client_secret_path}. "
                "Create an OAuth desktop client in Google Cloud and save it there."
            )
        flow = InstalledAppFlow.from_client_secrets_file(
            str(client_secret_path), GOOGLE_MEET_SCOPES
        )
        creds = flow.run_local_server(port=0)
    ensure_dir(token_path.parent)
    token_path.write_text(creds.to_json(), encoding="utf-8")
    return creds


def list_google_entries(service: Any, transcript_name: str) -> List[Dict[str, Any]]:
    entries: List[Dict[str, Any]] = []
    page_token = None
    while True:
        kwargs = {"parent": transcript_name, "pageSize": 100}
        if page_token:
            kwargs["pageToken"] = page_token
        response = (
            service.conferenceRecords()
            .transcripts()
            .entries()
            .list(**kwargs)
            .execute()
        )
        entries.extend(response.get("transcriptEntries", []))
        page_token = response.get("nextPageToken")
        if not page_token:
            break
    return entries


def google_entries_to_text(entries: List[Dict[str, Any]]) -> str:
    lines = []
    for entry in entries:
        start = seconds_from_rfc3339(entry.get("startTime"))
        end = seconds_from_rfc3339(entry.get("endTime"))
        span = f"{start}-{end}" if start or end else ""
        speaker = entry.get("participant", "speaker")
        text = entry.get("text", "").strip()
        if span:
            lines.append(f"[{span}] {speaker}: {text}")
        else:
            lines.append(f"{speaker}: {text}")
    return "\n".join(lines)


def import_google(args: argparse.Namespace) -> Path:
    try:
        from googleapiclient.discovery import build
    except ImportError as exc:
        raise IngestError(
            "Missing google-api-python-client. Install requirements first."
        ) from exc

    creds = get_google_creds(args.token_path, args.client_secret)
    service = build("meet", "v2", credentials=creds)

    transcript_name = args.transcript_name
    transcript_meta: Dict[str, Any] = {}
    if not transcript_name:
        if not args.conference_record:
            raise IngestError("Provide --transcript-name or --conference-record.")
        response = (
            service.conferenceRecords()
            .transcripts()
            .list(parent=args.conference_record, pageSize=100)
            .execute()
        )
        transcripts = response.get("transcripts", [])
        if not transcripts:
            raise IngestError(f"No transcripts found for {args.conference_record}.")
        transcript_meta = transcripts[-1]
        transcript_name = transcript_meta["name"]

    entries = list_google_entries(service, transcript_name)
    if not entries:
        raise IngestError(f"No transcript entries found for {transcript_name}.")
    transcript_text = google_entries_to_text(entries)
    title = args.title or f"Google Meet transcript {transcript_name.split('/')[-1]}"
    brief = ""
    if args.summarize:
        brief = generate_openai_brief(
            transcript_text, model=args.summary_model, title=title
        )
    return write_note(
        title=title,
        platform="google-meet",
        transcript_text=transcript_text,
        source_url=args.source_url,
        source_id=transcript_name,
        transcript_source="google-meet-api",
        sources_dir=args.sources_dir,
        internal_dir=args.internal_dir if args.write_internal else None,
        ai_brief=brief,
        extra={"google_conference_record": args.conference_record or ""},
    )


def lark_base(region: str) -> str:
    if region == "feishu":
        return "https://open.feishu.cn"
    if region == "lark":
        return "https://open.larksuite.com"
    custom = os.environ.get("LARK_API_BASE") or os.environ.get("FEISHU_API_BASE")
    if custom:
        return custom.rstrip("/")
    raise IngestError("Unknown Lark region; use --region feishu or --region lark.")


def lark_access_token(region: str, explicit_token: str = "") -> str:
    if explicit_token:
        return explicit_token
    env_token = (
        os.environ.get("LARK_ACCESS_TOKEN")
        or os.environ.get("FEISHU_ACCESS_TOKEN")
        or os.environ.get("LARK_USER_ACCESS_TOKEN")
        or os.environ.get("FEISHU_USER_ACCESS_TOKEN")
    )
    if env_token:
        return env_token
    app_id = os.environ.get("LARK_APP_ID") or os.environ.get("FEISHU_APP_ID")
    app_secret = os.environ.get("LARK_APP_SECRET") or os.environ.get("FEISHU_APP_SECRET")
    if not app_id or not app_secret:
        raise IngestError(
            "Set LARK_ACCESS_TOKEN/FEISHU_ACCESS_TOKEN, or set LARK_APP_ID and "
            "LARK_APP_SECRET for tenant_access_token."
        )
    url = f"{lark_base(region)}/open-apis/auth/v3/tenant_access_token/internal"
    data = http_json("POST", url, body={"app_id": app_id, "app_secret": app_secret})
    if data.get("code") not in (0, None):
        raise IngestError(f"Lark token request failed: {data}")
    token = data.get("tenant_access_token")
    if not token:
        raise IngestError(f"Lark token response did not include tenant_access_token: {data}")
    return token


def parse_minute_token(value: str) -> str:
    value = value.strip()
    match = re.search(r"/minutes/([A-Za-z0-9_-]{24})", value)
    if match:
        return match.group(1)
    if re.fullmatch(r"[A-Za-z0-9_-]{24}", value):
        return value
    raise IngestError(f"Could not parse Lark/Feishu minute token from: {value}")


def lark_get_minute_info(region: str, token: str, bearer: str) -> Dict[str, Any]:
    url = f"{lark_base(region)}/open-apis/minutes/v1/minutes/{token}"
    try:
        data = http_json(
            "GET",
            url,
            headers={"Authorization": f"Bearer {bearer}"},
        )
    except IngestError:
        return {}
    if data.get("code") not in (0, None):
        return {}
    return data.get("data", {}).get("minute", {}) or data.get("data", {}) or {}


def import_lark(args: argparse.Namespace) -> Path:
    token = parse_minute_token(args.minute)
    bearer = lark_access_token(args.region, args.access_token)
    params = urllib.parse.urlencode(
        {
            "need_speaker": "true" if args.need_speaker else "false",
            "need_timestamp": "true" if args.need_timestamp else "false",
            "file_format": args.file_format,
        }
    )
    url = (
        f"{lark_base(args.region)}/open-apis/minutes/v1/minutes/"
        f"{token}/transcript?{params}"
    )
    raw = http_bytes(
        "GET",
        url,
        headers={
            "Authorization": f"Bearer {bearer}",
            "Content-Type": "application/json; charset=utf-8",
        },
    )
    transcript_text = raw.decode("utf-8", errors="replace")
    info = lark_get_minute_info(args.region, token, bearer)
    title = (
        args.title
        or info.get("title")
        or info.get("topic")
        or f"Lark Minutes transcript {token}"
    )
    source_url = args.source_url or info.get("url") or args.minute
    brief = ""
    if args.summarize:
        brief = generate_openai_brief(
            transcript_text, model=args.summary_model, title=title
        )
    return write_note(
        title=title,
        platform=args.region,
        transcript_text=transcript_text,
        source_url=source_url,
        source_id=token,
        transcript_source="lark-minutes-api",
        sources_dir=args.sources_dir,
        internal_dir=args.internal_dir if args.write_internal else None,
        ai_brief=brief,
        extra={"minute_token": token},
    )


def search_lark(args: argparse.Namespace) -> None:
    bearer = lark_access_token(args.region, args.access_token)
    query = {"query": args.query, "sorter": "create_time_desc"}
    if args.start_time or args.end_time:
        create_time: Dict[str, str] = {}
        if args.start_time:
            create_time["start_time"] = args.start_time
        if args.end_time:
            create_time["end_time"] = args.end_time
        query["filter"] = {"create_time": create_time}
    params = urllib.parse.urlencode({"page_size": args.page_size, "user_id_type": "open_id"})
    url = f"{lark_base(args.region)}/open-apis/minutes/v1/minutes/search?{params}"
    data = http_json(
        "POST",
        url,
        headers={"Authorization": f"Bearer {bearer}"},
        body=query,
    )
    print(json.dumps(data, ensure_ascii=False, indent=2))


def import_file(args: argparse.Namespace) -> Path:
    transcript_text = args.input.read_text(encoding="utf-8")
    title = args.title or args.input.stem
    brief = ""
    if args.summarize:
        brief = generate_openai_brief(
            transcript_text, model=args.summary_model, title=title
        )
    return write_note(
        title=title,
        platform=args.platform,
        transcript_text=transcript_text,
        source_url=args.source_url,
        source_id=args.source_id or str(args.input),
        transcript_source=args.transcript_source,
        sources_dir=args.sources_dir,
        internal_dir=args.internal_dir if args.write_internal else None,
        ai_brief=brief,
    )


def transcribe_audio(args: argparse.Namespace) -> Path:
    ensure_dir(args.out_dir)
    title = args.title or args.audio.stem
    if args.engine == "mlx":
        exe = shutil.which("mlx_whisper")
        if not exe:
            raise IngestError("mlx_whisper is not installed or not in PATH.")
        cmd = [
            exe,
            str(args.audio),
            "--model",
            args.mlx_model,
            "--output-dir",
            str(args.out_dir),
            "--output-name",
            slugify(title),
        ]
        if args.language:
            cmd.extend(["--language", args.language])
        subprocess.run(cmd, check=True)
        transcript_path = args.out_dir / f"{slugify(title)}.txt"
        if not transcript_path.exists():
            candidates = sorted(args.out_dir.glob(f"{slugify(title)}*.txt"))
            if not candidates:
                raise IngestError(f"mlx_whisper did not produce a txt file in {args.out_dir}")
            transcript_path = candidates[0]
        args.input = transcript_path
        args.platform = "local-audio"
        args.source_id = str(args.audio)
        args.transcript_source = f"mlx-whisper:{args.mlx_model}"
        return import_file(args)

    if args.engine == "openai":
        transcribe_cli = Path(
            os.environ.get(
                "TRANSCRIBE_CLI",
                str(Path.home() / ".codex/skills/transcribe/scripts/transcribe_diarize.py"),
            )
        )
        if not transcribe_cli.exists():
            raise IngestError(f"OpenAI transcribe CLI not found: {transcribe_cli}")
        transcript_path = args.out_dir / f"{slugify(title)}.txt"
        cmd = [
            sys.executable,
            str(transcribe_cli),
            str(args.audio),
            "--model",
            args.openai_transcribe_model,
            "--response-format",
            "text",
            "--out",
            str(transcript_path),
        ]
        if args.language:
            cmd.extend(["--language", args.language])
        if args.openai_prompt:
            cmd.extend(["--prompt", args.openai_prompt])
        subprocess.run(cmd, check=True)
        args.input = transcript_path
        args.platform = "local-audio"
        args.source_id = str(args.audio)
        args.transcript_source = f"openai:{args.openai_transcribe_model}"
        return import_file(args)

    raise IngestError(f"Unknown engine: {args.engine}")


def add_common_note_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--title", default="")
    parser.add_argument("--source-url", default="")
    parser.add_argument("--sources-dir", type=Path, default=DEFAULT_SOURCES_DIR)
    parser.add_argument("--internal-dir", type=Path, default=DEFAULT_INTERNAL_DIR)
    parser.add_argument("--write-internal", action="store_true")
    parser.add_argument("--summarize", action="store_true")
    parser.add_argument(
        "--summary-model",
        default=os.environ.get("MEETING_NOTES_MODEL", "gpt-4o"),
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Import Google Meet, Lark/Feishu, or audio transcripts into Obsidian."
    )
    parser.add_argument(
        "--env-file",
        type=Path,
        default=ROOT / ".env",
        help="Optional env file. Defaults to ./env in the tool directory.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    google = sub.add_parser("google-import", help="Import a Google Meet transcript.")
    add_common_note_args(google)
    google.add_argument("--conference-record", default="")
    google.add_argument("--transcript-name", default="")
    google.add_argument("--client-secret", type=Path, default=DEFAULT_GOOGLE_CLIENT_SECRET)
    google.add_argument("--token-path", type=Path, default=DEFAULT_GOOGLE_TOKEN)
    google.set_defaults(func=import_google)

    lark = sub.add_parser("lark-import", help="Import a Lark/Feishu Minutes transcript.")
    add_common_note_args(lark)
    lark.add_argument("minute", help="Minutes URL or 24-character minute token.")
    lark.add_argument("--region", choices=["feishu", "lark"], default="feishu")
    lark.add_argument("--access-token", default="")
    lark.add_argument("--need-speaker", action="store_true", default=True)
    lark.add_argument("--no-speaker", dest="need_speaker", action="store_false")
    lark.add_argument("--need-timestamp", action="store_true", default=True)
    lark.add_argument("--no-timestamp", dest="need_timestamp", action="store_false")
    lark.add_argument("--file-format", default="txt")
    lark.set_defaults(func=import_lark)

    lark_search = sub.add_parser("lark-search", help="Search Lark/Feishu Minutes.")
    lark_search.add_argument("--region", choices=["feishu", "lark"], default="feishu")
    lark_search.add_argument("--access-token", default="")
    lark_search.add_argument("--query", default="")
    lark_search.add_argument("--start-time", default="", help="RFC3339, e.g. 2026-05-27T00:00:00+08:00")
    lark_search.add_argument("--end-time", default="", help="RFC3339, e.g. 2026-05-27T23:59:59+08:00")
    lark_search.add_argument("--page-size", type=int, default=10)
    lark_search.set_defaults(func=search_lark)

    file_import = sub.add_parser("file-import", help="Import an existing transcript file.")
    add_common_note_args(file_import)
    file_import.add_argument("input", type=Path)
    file_import.add_argument("--platform", default="manual")
    file_import.add_argument("--source-id", default="")
    file_import.add_argument("--transcript-source", default="local-file")
    file_import.set_defaults(func=import_file)

    audio = sub.add_parser("transcribe-audio", help="Transcribe audio and write an Obsidian note.")
    add_common_note_args(audio)
    audio.add_argument("audio", type=Path)
    audio.add_argument("--engine", choices=["mlx", "openai"], default="mlx")
    audio.add_argument("--out-dir", type=Path, default=ROOT / "output")
    audio.add_argument("--language", default="")
    audio.add_argument("--mlx-model", default="mlx-community/whisper-large-v3-turbo")
    audio.add_argument("--openai-transcribe-model", default="gpt-4o-transcribe")
    audio.add_argument(
        "--openai-prompt",
        default=(
            "This is a crypto security meeting. Preserve names like ZeroDrift, "
            "Security World Model, EVM, Solana, Move, Sui, DeFi, CLMM, oracle, "
            "MEV, governance, multisig, timelock, vault, TVL, proof-of-exploit, "
            "Cantina, Immunefi, Code4rena, Trail of Bits, Certora, OtterSec."
        ),
    )
    audio.add_argument("--platform", default="local-audio")
    audio.add_argument("--source-id", default="")
    audio.add_argument("--transcript-source", default="")
    audio.set_defaults(func=transcribe_audio)

    return parser


def main(argv: Optional[List[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    load_env_file(args.env_file)
    if hasattr(args, "sources_dir") and args.sources_dir == DEFAULT_SOURCES_DIR:
        env_sources = os.environ.get("OBSIDIAN_SOURCES_DIR")
        if env_sources:
            args.sources_dir = Path(env_sources).expanduser()
    if hasattr(args, "internal_dir") and args.internal_dir == DEFAULT_INTERNAL_DIR:
        env_internal = os.environ.get("OBSIDIAN_INTERNAL_DIR")
        if env_internal:
            args.internal_dir = Path(env_internal).expanduser()
    if hasattr(args, "summary_model") and args.summary_model == "gpt-4o":
        args.summary_model = os.environ.get("MEETING_NOTES_MODEL", args.summary_model)
    try:
        result = args.func(args)
    except subprocess.CalledProcessError as exc:
        print(f"Command failed with exit code {exc.returncode}: {exc.cmd}", file=sys.stderr)
        return exc.returncode
    except IngestError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    if isinstance(result, Path):
        print(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
