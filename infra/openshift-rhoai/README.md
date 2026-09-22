# OpenShift + RHOAI (primary flavor)

GitOps manifests for deploying the ISO Compliance Platform on OpenShift with **RHOAI MaaS** as the OpenAI-compatible LLM gateway.

## Planned layout

```
openshift-rhoai/
├── README.md           # this file
├── argocd/             # Argo CD Application(s)
├── namespace/          # iso-platform namespace, quotas, network policies
├── rhoai/              # MaaS tokens, ExternalModel refs, model alias notes
├── gateway/            # optional passthrough to MaaS (openai-compatible Route)
├── app/                # iso-api, iso-web, workers (Phase 1)
└── secrets/            # SealedSecret examples (no real secrets in git)
```

## LLM path

```
iso-api / iso-web  →  [iso-openai-gateway]  →  RHOAI MaaS /v1  →  LLMInferenceService | ExternalModel
```

Implement and test this flavor **first**.

## References

- [OpenShift AI 3.5 GA on this cluster](../../docs/OPENSHIFT_AI.md)
- [RHOAI 3.5 demo project (`rhoai-demo`)](../../docs/RHOAI_35_DEMO.md)
- [RHOAI MaaS governance (3.5)](https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/govern_llm_access_with_models-as-a-service/index)
- ragu-builder `openshift-bootstrap/app/openai-gateway/` (passthrough pattern)
