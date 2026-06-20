# Optional OpenAI-compatible passthrough (OpenShift)

Thin nginx (or app) Route that proxies to the cluster **MaaS origin**, so application ConfigMaps only reference one stable in-namespace URL.

Set `MAAS_ORIGIN` to the RHOAI MaaS HTTPS base (no trailing slash). Application uses:

```text
LLM_GATEWAY_URL=https://<iso-openai-gateway-route>/v1
```

See ragu-builder `openshift-bootstrap/app/openai-gateway/` for a working reference.

## Status

Placeholder — implement in Phase 1 alongside `iso-api` deployment.
