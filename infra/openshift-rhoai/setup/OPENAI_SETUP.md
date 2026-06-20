# OpenAI Setup - Complete

## ✅ Deployment Complete

The playground has been switched from Anthropic Claude (Vertex AI) to OpenAI.

### Configuration

- **Provider**: OpenAI
- **API Key**: Configured
- **Models**: 3 available
  - GPT-4 (Most capable)
  - GPT-4 Turbo (Fast & capable, default)
  - GPT-3.5 Turbo (Fast & economical)
- **Guardrails**: ✅ Active (Red Hat & ISO topics only)

## Access

**Playground URL**: https://claude-playground-iso-platform.apps.ocp.8mkwb.sandbox3159.opentlc.com

## Features

1. **Model Selection**: Choose between 3 OpenAI models via dropdown
2. **Guardrails**: Only answers Red Hat & ISO questions
3. **Web UI**: Interactive chat interface
4. **API**: REST endpoints for integration

## Testing

### Test Allowed Topic
```bash
curl -X POST https://claude-playground-iso-platform.apps.ocp.8mkwb.sandbox3159.opentlc.com/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "What is Red Hat OpenShift AI?", "model": "gpt-4-turbo"}'
```

### Test Blocked Topic```bash
curl -X POST https://claude-playground-iso-platform.apps.ocp.8mkwb.sandbox3159.opentlc.com/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "What is the weather?", "model": "gpt-3.5-turbo"}'
```

**Expected**: `{"blocked":true,"response":"I can only answer questions about Red Hat technologies and ISO standards..."}`

## Test All 3 Models

### GPT-4 (Most capable)
```bash
curl -X POST https://claude-playground-iso-platform.apps.ocp.8mkwb.sandbox3159.opentlc.com/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "Explain ISO 27001 certification process", "model": "gpt-4"}'
```

### GPT-4 Turbo (Fast & capable - default)
```bash
curl -X POST https://claude-playground-iso-platform.apps.ocp.8mkwb.sandbox3159.opentlc.com/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "What is Red Hat OpenShift?", "model": "gpt-4-turbo"}'
```

### GPT-3.5 Turbo (Fast & economical)
```bash
curl -X POST https://claude-playground-iso-platform.apps.ocp.8mkwb.sandbox3159.opentlc.com/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "What is RHEL?", "model": "gpt-3.5-turbo"}'
```

## Architecture

- **Backend**: Flask app with OpenAI Python SDK
- **Models**: GPT-4, GPT-4 Turbo, GPT-3.5 Turbo
- **Guardrails**: Dual-layer protection
  - Pre-filter: Keyword check before API call
  - System prompt: Enforced topic restrictions
- **Security**: UBI9 base, non-root, restricted capabilities
- **Monitoring**: TrustyAI enabled

## Files

- `app-openai.py` - Flask application
- `10-openai-deployment.yaml` - Deployment manifest
- Secret: `openai-api-key` (namespace: iso-platform)
