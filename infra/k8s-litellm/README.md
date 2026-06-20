# Kubernetes + LiteLLM (maintained flavor)

Same application containers and **same env var contract** as `openshift-rhoai`, with **LiteLLM** as the OpenAI-compatible gateway.

## Planned layout

```
k8s-litellm/
├── README.md           # this file
├── litellm/            # Deployment, Service, config ConfigMap, secrets example
├── ingress/            # Ingress or Gateway API for LiteLLM and app
├── app/                # iso-api, iso-web (Kustomize overlays)
└── secrets/            # External provider keys (examples only)
```

## LLM path

```
iso-api  →  LiteLLM :4000/v1  →  vLLM | OpenAI | Azure | …
```

Model **aliases** (`iso-mapper`, `iso-report`, `iso-embed`) must match the OpenShift flavor so the app needs no code changes.

## Parity testing

Run shared contract tests with:

```bash
export LLM_GATEWAY_URL=https://litellm.example.com/v1
export LLM_API_KEY=...
```

## Status

Placeholder — maintain manifest parity when OpenShift flavor changes.
