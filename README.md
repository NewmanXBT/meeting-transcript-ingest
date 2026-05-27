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

## Automation Roadmap

The first reliable layer is manual/API import. The next layer is event-driven automation:

1. Subscribe to Google Meet transcript `fileGenerated` events through Google Workspace Events API and Pub/Sub.
2. Poll or search Lark/Feishu Minutes for newly created transcript records.
3. Run this importer for each new transcript.
4. Write raw source notes into Obsidian and selected internal memos into the ZeroDrift Wiki.

## Security Notes

- This repo should never contain OAuth tokens, `.env`, transcript exports, or Obsidian vault content.
- OAuth tokens are stored under `state/` and ignored by git.
- Public examples use fake IDs and tokens.
- For sensitive meetings, prefer official platform transcripts or local MLX transcription before uploading audio to a cloud API.
