# Enterprise-grade AI architecture

Reference patterns for **high availability**, **resilience**, and **operable** AI on **Red Hat OpenShift** and **OpenShift AI** (3.x): logical planes, scaling assumptions, failure containment, and how structure supports **security** (detailed controls: **`docs/enterprise-grade-ai-security.md`**).

---

## Logical planes

| Plane | Components (typical) | Design intent |
|-------|----------------------|----------------|
| **Edge** | **Route** / **Ingress**, TLS termination, optional **API gateway** | Stateless, horizontally scaled; accurate **readiness**; **timeouts** toward backends |
| **Application** | Web UI, **BFF** or **API**, **OpenAI-compatible gateway** | **Replicas** + **PodDisruptionBudget**; **bulkheads** so one slow dependency does not exhaust the whole tier |
| **Data** | **PostgreSQL** (e.g. **CloudNativePG**), object storage if used | Replication and **backup** meet **RPO**; **restore** exercises are part of architecture validation |
| **Inference** | **MaaS**, **LLMInferenceService**, GPU **MachineSet** / pools | **Capacity** planning; **node affinity**; product-defined **degraded** behavior when GPUs are saturated |
| **Platform / GitOps** | **Argo CD**, **Operators**, monitoring stack | **Git** as desired state; ordered **restore** (operators → data → inference → routes) |

**ragu-builder** maps planes to **`ragu-app`** (edge + application), **`ragu-data`** (data), **`ragu-llm`** (inference)—see **`docs/ARCHITECTURE.md`** for object-level inventory.

---

## High availability

| Concern | Approach |
|---------|----------|
| **Cluster control plane** | Platform responsibility (**etcd**, API availability). Applications assume transient API errors and use **idempotent** automation. |
| **Stateless HTTP tiers** | **≥ 2 replicas** for UI, gateway, and API **Deployments**; **PodDisruptionBudget** aligned to SLO during drains and upgrades. |
| **Placement** | **Pod anti-affinity** or **topology spread** across workers and, where available, **availability zones**. |
| **Ingress** | **Service** endpoints reflect only **ready** pods; document client **retry** policy for **5xx** and connection failures. |
| **Stateful data** | Follow **CloudNativePG** (or chosen operator) patterns for instance topology, synchronous expectations, and backup windows. |
| **Large models** | **HA** may mean **N+1 GPU capacity** or **queueing** at the gateway, not two full replicas of the same large model; define **fallback** models or UX when inference is unavailable. |

---

## Resilience

| Concern | Approach |
|---------|----------|
| **Timeouts** | Bounded waits at **edge**, **gateway**, and **upstream** HTTP clients to avoid thread exhaustion on slow LLM calls. |
| **Retries** | Retry only **idempotent** operations; for conversational **writes**, use **request IDs** and deduplication where needed. |
| **Bulkheads / circuit breaking** | Isolate **retrieval**, **embedding**, and **completion** pools so one path cannot starve the others; shed load when error budgets are exceeded. |
| **Degradation** | Explicit product behavior when inference or retrieval fails; degradation paths must **not** widen data exposure (avoid unintended “fail open” to broader corpora). |
| **GitOps recovery** | Declarative manifests under **Argo CD** limit post-incident drift; restore order matches dependency order of planes above. |

---

## Security by architecture

Structural choices reduce coupling between **identity**, **data**, and **inference**:

| Decision | Effect |
|----------|--------|
| **Namespace** boundaries (**app** / **data** / **llm**) | Smaller blast radius; clearer **RBAC** and **NetworkPolicy** attachment points |
| **Single gateway** path from browser to **MaaS** | One TLS and policy **choke point**; fewer ad-hoc egress targets |
| **Non-root**, **restricted**-friendly images | Consistent **SCC** posture across environments |
| **Dedicated GPU** pools | Cost, noisy-neighbor, and compliance isolation |
| **Private registries** + pull secrets | Supply-chain gate before **Schedule** |
| **Centralized metrics and logs** | Faster incident and abuse investigation |
| **Separate CI tracks** for app, prompts, RAG artifacts, and model promotion | Independent blast radius and approval paths |

**Zero trust (operational):** assume any pod may be compromised; **default-deny** **NetworkPolicy**, scoped credentials, and minimal **ClusterRole** use limit lateral movement.

---

## Capacity and multi-tenancy

| Concern | Approach |
|---------|----------|
| **Quotas** | **ResourceQuota** and **LimitRange** per namespace or team to protect shared workers and GPU pools. |
| **Autoscaling** | **HPA** (or custom metrics) for stateless tiers; GPU inference scaling needs **product-specific** signals, not CPU-only defaults. |
| **Shared clusters** | Combine quotas with **per-tenant** **RAG** indexes or strict **metadata** scoping to avoid cross-tenant retrieval under load. |

---

## Observability architecture

| Signal class | Examples |
|--------------|----------|
| **Golden four** | Latency, traffic, errors, saturation for gateway, API, database, inference |
| **RAG** | Retrieval hit rate, empty retrieval rate, embedding lag |
| **Tracing** | Propagate context from edge through gateway to API and data clients for performance and security correlation |
| **Logging** | Structured logs with correlation IDs; align with **`docs/enterprise-grade-ai-security.md`** on **PII** in log payloads |

---

## Backup and disaster recovery

| Asset | Note |
|-------|------|
| **Manifests** | **Git** is the source of truth for desired **YAML**; cluster **etcd** backup is a platform concern. |
| **Application data** | **Postgres** volumes and **WAL**, object storage for uploads; **RPO/RTO** per tier (data usually strictest). |
| **Secrets** | Restore via **Sealed Secrets** / vault procedures—not cleartext in Git. |
| **Multi-region** | If inference or data spans regions, design **latency**, **residency**, and **key management** explicitly; avoid blind DNS failover without health checks and consistent state. |

---

## ragu-builder alignment

The repository encodes **GitOps** **`ragu-*`** applications, **gateway-first** traffic (**`ragu-openai-gateway`**), **CloudNativePG** in **`ragu-data`**, and **LLMInferenceService** manifests in **`ragu-llm`**. Production hardening should treat **replicas**, **PDB**, **probes**, and **affinity** in those manifests as first-class, not sandbox defaults.

**Inventory and status:** **`docs/ARCHITECTURE.md`**. **Delivery checklist:** **`docs/DEVELOPMENT_PLAN.md`**.
