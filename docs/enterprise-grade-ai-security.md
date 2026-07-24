# Enterprise-grade AI security

Security model for production **RAG** and **LLM** workloads on **Red Hat OpenShift** and **OpenShift AI** (3.x): supply chain, platform isolation, identity, data handling, and governance. Complements **`docs/enterprise-grade-ai-architecture.md`** (HA, resilience, topology).

---

## Supply chain

| Control | Practice |
|---------|----------|
| **Base images** | Prefer **Red Hat Universal Base Image (UBI)** for supportable patching and metadata; minimize packages; pin **digests** in GitOps where feasible. |
| **Operators** | Install **OpenShift GitOps**, **OpenShift AI**, **CloudNativePG**, **RHACS**, and similar capabilities from **OperatorHub** / certified channels; scope **Subscription** and **OperatorGroup** per vendor guidance. |
| **CI/CD** | Build in trusted pipelines: SAST, tests, **image scan** before promotion, **signed** artifacts or immutable tags. |
| **Registry** | Authenticated pulls; **imagePullSecrets** at namespace or **ServiceAccount** scope; no long-lived secrets baked into images. |

---

## Runtime and workload hardening

| Control | Practice |
|---------|----------|
| **SCC** | Bind workloads to **restricted**-compatible **SCC**s where possible; document **`securityContext`** (`runAsNonRoot`, `readOnlyRootFilesystem`, dropped **capabilities**, **seccomp**) in manifests. |
| **Privilege** | Avoid **root** in application containers; use **PVC** or **emptyDir** for writable paths; custom SCC only with explicit risk acceptance. |
| **Secrets** | **Sealed Secrets**, **External Secrets**, or vault integration for app keys; database credentials remain operator-managed where applicable. |

---

## Segmentation and network

| Control | Practice |
|---------|----------|
| **Namespaces** | Split **data** (`ragu-data`), **inference** (`ragu-llm`), **application** (`ragu-app`), and operator install namespaces to constrain **RBAC**, **quotas**, and blast radius. |
| **NetworkPolicy** | Default **deny** where policy allows; permit only required paths (for example UI → gateway → MaaS, API → Postgres); avoid ad-hoc wide egress from sensitive tiers. |
| **Ingress** | **Routes** / **Ingress** with **TLS** (edge or re-encrypt); redirect HTTP to HTTPS; stable hostnames for clients and documentation. |

---

## Centralized security operations (RHACS)

**Red Hat Advanced Cluster Security (RHACS)** provides cluster-wide **image and deployment risk** visibility, **Kubernetes/OpenShift configuration** checks against baselines, **runtime** signals, and optional **admission** policies. It complements—not replaces—namespace **NetworkPolicy**, **RBAC**, and application-level controls.

---

## Identity and RBAC

| Layer | Practice |
|-------|----------|
| **Cluster** | **Least-privilege** **Role** / **ClusterRole**; **RoleBinding** scoped to one namespace when sufficient; separate **cluster-admin** from GitOps and CI roles. |
| **Users** | **OpenShift OAuth** or enterprise **SSO** for console and Web UI where required. |
| **Services** | **ServiceAccount**-bound tokens, **mTLS** or TLS to internal services, short-lived credentials where the platform supports them. |
| **RAG entitlements** | Authorize **retrieval** using the same identity attributes used at login (groups, tenant, labels)—not UI checks alone. |

---

## RAG and data protection

| Topic | Practice |
|-------|----------|
| **Minimization** | Redact or tokenize **PII** and secrets before model context expansion; avoid logging raw document text where logs are broadly visible—prefer **document IDs** or hashes. |
| **Tenancy** | **Shared** (anonymous / low-trust): public or low-sensitivity corpora, strict **rate limits**, no cross-tenant indexes. **Private** (authenticated): **metadata filters** or dedicated indexes per tenant so retrieval cannot cross boundaries. |
| **Retrieval** | Enforce **classification** and **domain** filters on every query; require **citations** to internal chunks when policy demands traceable answers. |
| **Ingestion** | Versioned, **reviewed** ingestion pipelines; reversible promotion of embeddings alongside **prompt** or config versions. |

---

## Application and UI guardrails

Server-side policy is authoritative: **system prompts**, scope boundaries, and **output filters** for policy violations. Client-side checks improve experience only and must not be the sole control for regulated or sensitive use cases.

---

## OpenShift AI and model governance

| Area | Practice |
|------|----------|
| **Models** | **Model registry** / **catalog**: production only from **approved** versions; documented promotion, rollback, and ownership metadata. |
| **Prompts and tools** | Treat **prompts** and **MCP** / tool definitions as **versioned artifacts** in Git with review and automated checks (including regression suites for leakage or unsafe completions where applicable). |
| **Pipelines** | **OpenShift Pipelines** (or equivalent) as gates: scan, test, policy check before deploy to higher environments. |
| **Guardrails product** | Where the organization deploys **Gen AI guardrails** (toxicity, bias, injection-oriented probes, dashboards), wire them into the same **observability** and **change** processes as the rest of the stack. |
| **Agentic workloads** | **Tool** and **MCP server** allow lists, timeouts, scoped credentials, and **audit** of invocations—same discipline as third-party HTTP dependencies. |

---

## Audit and observability

| Stream | Content |
|--------|---------|
| **Application audit** | Correlation ID, principal (or pseudonym), query, **retrieved document IDs**, model and **template version**, outcome—sufficient to reconstruct a session for investigations and compliance. |
| **Administrative** | Changes to **Routes**, **ConfigMaps**, **Deployments**, **LLMInferenceService**, and operator-managed CRs; align with **OpenShift API audit** for control-plane actions. |
| **Retention** | Store audit evidence on storage classes and retention policies that meet legal and internal standards (**append-only** / **WORM** where required). |
| **Metrics and traces** | Latency, errors, retrieval quality, drift, and abuse-oriented signals to **Prometheus**, **OpenTelemetry**, and enterprise **SIEM** as appropriate. |

---

## Risk mapping (illustrative)

| Risk class | Primary controls |
|------------|------------------|
| Configuration drift / untracked admin change | **GitOps**, **RBAC**, API audit, **RHACS** configuration management |
| Lateral movement or wrong tenant data | **NetworkPolicy**, namespace isolation, **RAG** entitlement filters |
| Secret or **PII** exfiltration | Redaction, **TLS**, secret backends, minimal logging |
| Unsupported factual claims | Citations, approved models, evaluation gates, refusal paths |
| **Prompt injection** / tool abuse | Prompt governance, retrieval allow lists, guardrails, rate limits and anomaly signals |

---

## ragu-builder alignment

Git-managed **Argo** applications under **`openshift-bootstrap/gitops/`**, namespaces **`ragu-data`**, **`ragu-llm`**, **`ragu-app`**, **gateway-first** Web UI to **MaaS** (**`openshift-bootstrap/app/openai-gateway/`**), and install or runbooks under **`openshift-bootstrap/docs/`** implement portions of the above; inventory and status are maintained in **`docs/ARCHITECTURE.md`**. Delivery order: **`docs/DEVELOPMENT_PLAN.md`**.
