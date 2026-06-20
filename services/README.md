# Backend services (Phase 1)

| Service | Role |
|---------|------|
| `rag-iso` | ISO standards ingest, chunk, embed, retrieve |
| `docgen` | Excel + Hebrew DOCX templates |

Both call the LLM via `LLM_GATEWAY_URL` only (OpenAI-compatible).

## Status

Not implemented — see `docs/ARCHITECTURE.md`.
