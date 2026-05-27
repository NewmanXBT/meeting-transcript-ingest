# Third-Party Review: mlx-whisper

Date: 2026-05-27

## Package

- Name: `mlx-whisper`
- Source reviewed: PyPI metadata and public project description
- Version observed: `0.4.3`
- Purpose: Run OpenAI Whisper-style speech recognition locally on Apple Silicon through Apple MLX and Hugging Face MLX checkpoints.
- License: MIT

## Security Review Outcome

No material risk identified for local installation as an optional transcription fallback.

## Notes

- This is not a Codex skill; it is a Python package/CLI used for local speech-to-text.
- It avoids uploading meeting audio to a cloud API when local transcription quality is sufficient.
- First use can download model weights from Hugging Face, so model provenance should be kept explicit in transcript metadata.
- This repo pins no credentials and stores no model cache inside the git tree.

## Operational Controls

- Keep `.env`, OAuth tokens, transcript exports, and generated output out of git.
- Prefer official Google Meet or Lark/Feishu transcripts when available.
- Use OpenAI `gpt-4o-transcribe` only when higher transcription quality is needed and cloud processing is acceptable.
