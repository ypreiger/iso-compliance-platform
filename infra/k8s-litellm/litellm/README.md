# LiteLLM

Deploy LiteLLM with a ConfigMap-backed `config.yaml` defining model aliases used by the ISO platform.

## Model aliases (must match OpenShift MaaS names)

| Alias | Use |
|-------|-----|
| `iso-mapper` | Finding → ISO clause mapping + severity |
| `iso-report` | DOCX regulatory narrative |
| `iso-embed` | Rag ISO embeddings |

## Status

Add Deployment/Service/Ingress in Phase 1 after OpenShift smoke test passes.
