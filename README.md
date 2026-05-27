# Meeting Transcript Ingest

Meeting Transcript Ingest imports Google Meet transcripts, Lark/Feishu Minutes transcripts, and local audio transcriptions into an Obsidian material library. It is designed for crypto security teams that need meeting transcripts to become durable source notes, not forgotten chat artifacts.

The default output target is a ZeroDrift-style Obsidian vault:

```text
~/Documents/Obsidian Vault/ZeroDrift Material Library/sources/meetings
```

## What It Does

- Imports Google Meet transcript entries through the Google Meet REST API.
- Imports Lark/Feishu Minutes transcripts through the Minutes OpenAPI.
- Searches Lark/Feishu Minutes when a user token with search permission is available.
- Transcribes local audio with `mlx_whisper` on Apple Silicon.
- Falls back to OpenAI `gpt-4o-transcribe` through a bundled transcribe CLI.
- Optionally generates a Chinese-first ZeroDrift meeting brief with OpenAI.
- Preserves crypto/security vocabulary such as EVM, Solana, CLMM, oracle, MEV, governance, multisig, TVL, and proof-of-exploit.

## Install

```bash
cd ~/meeting-transcript-ingest
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
```

Install the local Apple Silicon transcription fallback:

```bash
pip install mlx-whisper
```

`ffmpeg` must also be installed for most audio workflows:

```bash
brew install ffmpeg
```

## Configure

Copy the example env file and fill only the credentials you need:

```bash
cp .env.example .env
```

Do not commit `.env` or files under `state/*.json`; they are ignored by git.

### Google Meet

Create a Google OAuth desktop client, save it as:

```text
state/google-oauth-client.json
```

The importer requests:

```text
https://www.googleapis.com/auth/meetings.space.readonly
```

Import by conference record:

```bash
python scripts/meeting_ingest.py google-import \
  --conference-record "conferenceRecords/CONFERENCE_RECORD_ID" \
  --title "Customer security review sync"
```

Or import a known transcript resource:

```bash
python scripts/meeting_ingest.py google-import \
  --transcript-name "conferenceRecords/CONFERENCE_RECORD_ID/transcripts/TRANSCRIPT_ID" \
  --title "Customer security review sync"
```

### Lark / Feishu

For a single Minutes transcript:

```bash
python scripts/meeting_ingest.py lark-import \
  "https://example.feishu.cn/minutes/obcnq3b9jl72l83w4f149w9c" \
  --region feishu \
  --title "Weekly security sync"
```

For global Lark:

```bash
python scripts/meeting_ingest.py lark-import \
  "https://example.larksuite.com/minutes/obcnq3b9jl72l83w4f149w9c" \
  --region lark
```

Search Minutes:

```bash
python scripts/meeting_ingest.py lark-search \
  --region feishu \
  --query "周会" \
  --start-time "2026-05-27T00:00:00+08:00" \
  --end-time "2026-05-27T23:59:59+08:00"
```

Search requires a Lark/Feishu user access token with the Minutes search scope. Export can use a user or tenant token if the app has access to the Minutes file.

## Local Audio Fallback

Use MLX Whisper locally:

```bash
python scripts/meeting_ingest.py transcribe-audio meeting.m4a \
  --engine mlx \
  --title "Crypto customer call"
```

Use OpenAI for higher accuracy with a crypto vocabulary prompt:

```bash
python scripts/meeting_ingest.py transcribe-audio meeting.m4a \
  --engine openai \
  --openai-transcribe-model gpt-4o-transcribe \
  --title "Crypto customer call"
```

Add `--summarize` when `OPENAI_API_KEY` is available:

```bash
python scripts/meeting_ingest.py lark-import "MINUTES_URL_OR_TOKEN" \
  --region feishu \
  --summarize \
  --write-internal
```

`--write-internal` also writes the same note into:

```text
~/Documents/Obsidian Vault/ZeroDrift Wiki/raw/internal
```

## Automatic Execution

The tool can run automatically on macOS through `launchd`. The installed job runs one import cycle every five minutes.

Install the automatic job:

```bash
cd ~/meeting-transcript-ingest
./scripts/install_launchd.sh
```

Check status:

```bash
./scripts/launchd_status.sh
```

Uninstall:

```bash
./scripts/uninstall_launchd.sh
```

Logs are written to:

```text
logs/daemon.out.log
logs/daemon.err.log
```

The automatic runner executes:

```bash
python scripts/meeting_ingest.py --env-file .env daemon-run --once
```

Each cycle does three things:

1. Searches Lark/Feishu Minutes for recent transcript records and imports unseen transcripts.
2. Best-effort checks Google Meet transcripts when an existing Google OAuth token is present.
3. Processes files under `inbox/`.

The daemon deduplicates imported items through:

```text
state/daemon-state.json
```

### Inbox Automation

Drop transcript or audio files into:

```text
inbox/
```

Supported transcript files:

```text
.txt .md .vtt .srt .tsv
```

Supported audio files:

```text
.mp3 .mp4 .mpeg .mpga .m4a .wav .webm
```

Audio files are transcribed with `mlx_whisper` by default. Set `AUDIO_ENGINE=openai` in `.env` to use `gpt-4o-transcribe`.

### One-Shot Daemon Test

Run one cycle without writing anything:

```bash
python scripts/meeting_ingest.py daemon-run --once --dry-run
```

Run one real cycle:

```bash
python scripts/meeting_ingest.py daemon-run --once
```

Useful `.env` settings:

```bash
LARK_REGION=feishu
LARK_QUERY=
LOOKBACK_HOURS=72
LARK_PAGE_SIZE=20
GOOGLE_AUTO=1
GOOGLE_PAGE_SIZE=20
MEETING_INBOX_DIR="./inbox"
AUDIO_ENGINE=mlx
MLX_WHISPER_MODEL="mlx-community/whisper-large-v3-turbo"
OPENAI_TRANSCRIBE_MODEL=gpt-4o-transcribe
```

## Automation Roadmap

The current automatic layer is a local poller/scheduler. The next layer is event-driven automation:

1. Subscribe to Google Meet transcript `fileGenerated` events through Google Workspace Events API and Pub/Sub.
2. Replace Lark/Feishu polling with webhooks when the deployed app has the required permissions.
3. Trigger `google-import` or `lark-import` directly from each platform event.
4. Keep the local inbox fallback for manually exported transcripts and audio recordings.

## Security Notes

- This repo should never contain OAuth tokens, `.env`, transcript exports, or Obsidian vault content.
- OAuth tokens are stored under `state/` and ignored by git.
- Public examples use fake IDs and tokens.
- For sensitive meetings, prefer official platform transcripts or local MLX transcription before uploading audio to a cloud API.
