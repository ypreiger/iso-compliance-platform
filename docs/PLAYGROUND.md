# ISO Playground (Canonical)

This is the single source of truth for Playground behavior, guardrails, speech/file capabilities, and model wiring.

If another document mentions Playground, it should link here instead of duplicating operational details.

## Scope

- Chat with selectable reasoning models (MaaS/OpenAI-compatible).
- Speech-to-text tab with:
  - microphone capture,
  - audio-file upload,
  - Whisper transcription.
- File Prompt tab:
  - upload file,
  - apply custom system prompt + criteria,
  - run analysis with selected reasoning model.

## GitOps Ownership

All Playground resources are Git-managed.

- App layer:
  - `gitops/layers/03-application/playground.yaml`
  - `gitops/layers/03-application/playground-stt.yaml`
  - `gitops/layers/03-application/kustomization.yaml`
- Cluster overlay config:
  - `gitops/overlays/ocp-sandbox3159/playground-models-config.yaml`
- Whisper in `llm` namespace (MaaS-exposed route):
  - `gitops/overlays/ocp-sandbox3159/llm-ai/whisper-maas.yaml`
  - `gitops/overlays/ocp-sandbox3159/llm-ai/kustomization.yaml`

## Model Separation (Expected UX)

- **Reasoning models** (chat/summarization/file analysis): dropdown in main Playground controls these.
- **Transcription model** (speech-to-text): separate STT selector in Speech tab.

This split is intentional:
- Whisper handles speech recognition.
- LLM models handle reasoning/summarization.

## STT/Whisper Behavior

- STT supports: `en`, `he`, `ar` (+ auto for upload flow).
- Playground discovers MaaS Whisper models through `/v1/models`.
- If MaaS Whisper exists, it is shown in STT selector.
- Local STT fallback is hidden by default and only used when MaaS Whisper is unavailable (or explicitly enabled).

Relevant config keys in `playground-models-config`:

- `STT_SERVICE_URL`
- `STT_TIMEOUT_SEC`
- `STT_DEFAULT_MODEL_ID`
- `STT_DISCOVER_MAAS_WHISPER`
- `STT_MAAS_MODEL_IDS`
- `STT_EXPOSE_LOCAL_MODEL`
- `STT_MODEL_NAME`, `STT_MODEL_DEVICE`, `STT_MODEL_COMPUTE_TYPE`

## Guardrail Modes

Configured in UI and backend:

- `iso_only`
- `cv_analysis`
- `speech_any_subject`

Default is controlled by `GUARDRAIL_DEFAULT_MODE`.

## Verification Commands

```bash
# Playground health/status
curl -sk https://playground-iso-platform.apps.ocp.7hrxw.sandbox880.opentlc.com/health
curl -sk https://playground-iso-platform.apps.ocp.7hrxw.sandbox880.opentlc.com/status

# STT models visible to playground
curl -sk https://playground-iso-platform.apps.ocp.7hrxw.sandbox880.opentlc.com/speech/models

# Whisper route through MaaS (from cluster context with token)
TOKEN=$(oc create token default -n iso-platform)
curl -sk -H "Authorization: Bearer $TOKEN" \
  https://maas.apps.ocp.7hrxw.sandbox880.opentlc.com/llm/whisper-small/v1/models
```

## Notes

- Keep one playground deployment unless explicit A/B isolation is requested.
- Do not duplicate playground runbooks in multiple docs; link to this file.
