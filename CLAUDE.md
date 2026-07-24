# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project overview

ISO Compliance Platform for **ISO 9001, ISO 14001, ISO 45001, and ISO 13485** certifications. Maps audit findings to ISO clause sections using RAG and LLM assistance, enables supervisor review, and exports Excel/DOCX reports in Hebrew.

**Dual deployment flavors** (same application code):
- **openshift-rhoai** (primary): OpenShift + RHOAI MaaS gateway
- **k8s-litellm** (maintained): Generic Kubernetes + LiteLLM proxy

All application services use **OpenAI-compatible `/v1` APIs only** — no provider-specific SDKs.

## Repository structure

```
apps/
  iso-api/          # FastAPI BFF: auth, projects, findings, mapping, corpus, exports
  iso-web/          # React SPA (Vite): bilingual UI (EN/HE), RTL/LTR support
services/
  rag-iso/          # RAG ingest Job: ISO standards chunking by clause
  docgen/           # Excel/DOCX export service (Hebrew RTL)
infra/
  openshift-rhoai/  # RHOAI MaaS manifests, GitOps overlays
  k8s-litellm/      # LiteLLM gateway manifests
gitops/             # 4-layer one-click deploy (OpenShift GitOps/Argo CD)
RAG/                # Seed corpus: Standards, Samples, Templates (Git LFS for PDFs)
scripts/            # deploy-all.sh, verify-*.sh, dry-run-local.sh
docs/               # PRD, ARCHITECTURE, DEPLOYMENT, GITOPS, AUTH, UI
```

## Common development commands

### Local dry-run (no OpenShift required)
```bash
./scripts/dry-run-local.sh
# Runs: RAG verify → Postgres (docker compose) → pytest → API smoke → web build → shellcheck
```

### Run API tests
```bash
# Install dependencies
python3 -m pip install -r apps/iso-api/requirements.txt pytest

# Run tests with SQLite (no Postgres required)
export USE_SQLITE=1
export SQLITE_PATH="/tmp/iso-test.db"
export AUTH_DEV_MODE=1
export ADMIN_EMAILS="yaakovpreiger@gmail.com,valeria.preiger@gmail.com"

PYTHONPATH=apps/iso-api python3 -m pytest apps/iso-api/tests -v
```

### Run specific API test file
```bash
PYTHONPATH=apps/iso-api python3 -m pytest apps/iso-api/tests/test_health.py -v
```

### Run RAG service tests
```bash
python3 -m pip install -r services/rag-iso/requirements.txt pytest pyyaml
PYTHONPATH=services/rag-iso python3 -m pytest services/rag-iso/tests -v
```

### Web UI development
```bash
cd apps/iso-web
npm install
npm run dev      # Dev server with hot reload
npm run build    # Production build
npm run preview  # Preview production build
```

### Local stack with docker-compose
```bash
docker compose up -d          # Start postgres + iso-api + docgen
docker compose logs -f iso-api
docker compose down
```

### OpenShift deployment (one-click)
```bash
oc login ...
./scripts/deploy-all.sh
# Deploys 4 GitOps layers: platform-infra → app-infra → application → RAG population
```

### Verify deployment
```bash
./scripts/verify-all.sh              # All layers
./scripts/verify-layer-03.sh         # Application layer only
```

### RAG corpus verification
```bash
./scripts/verify-rag-local.sh        # Validate manifest.yaml + file references
python3 -m pytest services/rag-iso/tests/test_manifest.py -q
```

## Architecture essentials

### LLM gateway abstraction
Application code never imports provider-specific SDKs. All LLM calls use OpenAI-compatible client configured via:
```python
# All services read these env vars:
LLM_GATEWAY_URL=https://<gateway-host>/v1
LLM_API_KEY=<token>
LLM_MODEL_MAPPING=iso-mapper    # Task-specific model aliases
LLM_MODEL_REPORT=iso-report
LLM_MODEL_EMBED=iso-embed
```

Platform teams choose the gateway:
- **openshift-rhoai**: RHOAI MaaS `/v1` → LLMInferenceService or ExternalModel
- **k8s-litellm**: LiteLLM `/v1` → vLLM, OpenAI, Azure, etc.

### iso-api modular structure
Single FastAPI app with route modules:
```
app/
  auth/         # Google OAuth, JWT, dev-mode login
  routes/       # projects, findings, mapping, coverage, exports, admin
  iso/          # Bilingual clause search & text viewer (EN/HE)
  db.py         # PostgreSQL or SQLite (USE_SQLITE=1)
  config.py     # Env vars via pydantic-settings
  main.py       # FastAPI app assembly
```

### Key data entities
- `Project` → `Finding` → `FindingClauseMapping` (relevance ≥50%, severity: minor/major/critical)
- `IsoStandardEdition` → `IsoClause` (chunk-indexed per clause ID)
- `ClauseCoverageStatus`: compliant | NC | N/A | not_checked
- `SupervisorReview`: human-approved edits feed supervised learning
- `CorpusDocument`: typed as `iso_standard` | `sample_report` | `template`

### Authentication
- **Production**: Google Sign-In (any Gmail account); bootstrap admins: `yaakovpreiger@gmail.com`, `valeria.preiger@gmail.com`
- **Dry-run**: `AUTH_DEV_MODE=1` enables `POST /auth/dev-login`
- Roles: `admin`, `consultant`, `supervisor`, `viewer` (default)

### Bilingual support
- UI and code: **English**
- ISO clause text: **EN + HE** (stored separately, toggled in `/iso` viewer with RTL/LTR layout switch)
- Customer exports: **Hebrew** (RTL DOCX/XLSX via `docgen` service)

## GitOps deployment model

Four sequential layers under `gitops/layers/`:
1. **01-platform-infra**: Namespaces, RBAC, RHOAI endpoint placeholders
2. **02-app-infra**: PostgreSQL, Redis, PVCs, ConfigMaps/Secrets examples
3. **03-application**: iso-api, iso-web, Services, Routes
4. **04-rag-population**: Job clones repo → ingests `RAG/` per `manifest.yaml`

Each layer has `scripts/verify-layer-NN.sh`. Root Application `iso-compliance-platform` in `openshift-gitops` syncs all with sync waves.

**Sandbox overlay**: Single Application at `gitops/overlays/ocp-sandbox3159/` bundles catalog PostgreSQL + OpenAI/MaaS routing.

## RAG corpus management

Seed files in `RAG/` directory:
- **RAG-Standards/**: ISO PDFs (EN/HE, amendments) — **Git LFS for large files**
- **RAG-Samples/**: Hebrew sample audit reports (.docx)
- **RAG-Templates/**: Report templates (Hebrew DOCX)

Manifest `RAG/manifest.yaml` drives ingest order and metadata. The `iso-rag-populate` Job (GitOps layer 4) runs `git lfs pull` after clone.

**Note:** `audio/` directory (if present) contains temporary audio files and should not be committed to git.

## Environment configuration

### iso-api required env vars
```bash
DATABASE_HOST=postgres         # or localhost
DATABASE_PORT=5432
DATABASE_USER=iso
DATABASE_PASSWORD=iso
DATABASE_NAME=iso
# OR: USE_SQLITE=1 + SQLITE_PATH=/tmp/iso.db for dry-run

AUTH_DEV_MODE=1                # Enables /auth/dev-login (local/CI only)
JWT_SECRET=<secret>            # Session signing
ADMIN_EMAILS=yaakovpreiger@gmail.com,valeria.preiger@gmail.com

# Google OAuth (production)
GOOGLE_CLIENT_ID=<client-id>.apps.googleusercontent.com
ISO_WEB_URL=https://iso-web-...  # OAuth redirect base

# LLM gateway (flavor-agnostic)
LLM_GATEWAY_URL=https://<gateway>/v1
LLM_API_KEY=<token>
LLM_MODEL_MAPPING=iso-mapper
LLM_MODEL_REPORT=iso-report
LLM_MODEL_EMBED=iso-embed

# docgen service
DOCGEN_URL=http://iso-docgen:8080
```

## Testing conventions

- **pytest** for iso-api and rag-iso services
- Use `USE_SQLITE=1` for fast tests without Postgres
- `AUTH_DEV_MODE=1` for bypassing OAuth in tests
- TestClient from FastAPI for API smoke tests
- All tests must pass in `dry-run-local.sh` before commits

### Run docgen service tests
```bash
python3 -m pip install -r services/docgen/requirements.txt pytest
PYTHONPATH=services/docgen python3 -m pytest services/docgen/tests -v
```

## Important patterns

### Database abstraction
`app/db.py` supports both PostgreSQL (production) and SQLite (dry-run/tests) via `USE_SQLITE` env var. Schema created by `ensure_schema()` on startup.

### ISO clause bilingual lookup
`/v1/iso/clauses?standard=ISO9001&language=he` returns Hebrew clause text. The `/iso` UI route has a language toggle (EN/HE) with automatic RTL/LTR layout switching.

### Supervisor review workflow
1. LLM proposes finding→clause mappings with relevance/severity
2. Supervisor reviews in three-pane UI: findings | clauses | mapping pairs
3. Human edits (remove pairs, change severity, mark N/A) stored as labeled tuples
4. Phase 2: use labels for reranking or fine-tuning

### Pipeline stages (prompt-administrable)
All prompts versioned in DB, editable via `/admin/instructions` without code deploy:
- `context_summarize`, `finding_normalize`, `iso_map_and_score`, `clause_coverage`, `corrective_action_draft`, `ofi_instruction_draft`, `report_narrative`

### Database migrations
Migrations run automatically via GitOps PostSync hooks in layer 02-app-infra.

**sort_order scale migration (2026-06)**: ISO clause `sort_order` migrated from 3-digit (401) to 9-digit base-100 encoding (401000000) to support hierarchical sorting (4 < 4.1 < 4.2 < 5).
- Migration Job: `gitops/layers/02-app-infra/migrate-sort-order-job.yaml`
- Idempotent: Safe to re-run; only updates rows with `sort_order < 1000000`
- Rollback: Automated via GitOps revert

## Development workflow

1. Make changes to code
2. Run local tests: `PYTHONPATH=apps/iso-api python3 -m pytest apps/iso-api/tests`
3. Verify full dry-run: `./scripts/dry-run-local.sh`
4. For OpenShift changes: update manifests under `gitops/layers/` or `infra/`
5. Validate with `kubectl kustomize gitops/layers/NN-*/`
6. Commit and push; GitOps auto-syncs on OpenShift

## Key documentation files

- `docs/PRD.md` — Product requirements, inputs, results, standards
- `docs/ARCHITECTURE.md` — Logical architecture, LLM routing, data model
- `docs/MICROSERVICES.md` — Service map, modules, roles, UI routes
- `docs/DEPLOYMENT.md` — Dual-flavor bootstrap runbooks
- `docs/GITOPS.md` — Four-layer GitOps model, verification matrix
- `docs/AUTH.md` — Google Sign-In setup, SAML option, bootstrap admins
- `docs/UI.md` — Screen flows, corpus uploads, supervisor mapping UI
- `RAG/README.md` — Seed corpus structure, Git LFS, manifest

## Notes for contributors

- **Implement and test `openshift-rhoai` flavor first** — `k8s-litellm` maintained in parallel for parity
- **Never use provider-specific LLM SDKs** in application code — only OpenAI-compatible client
- **Bilingual ISO text** (EN/HE) is stored separately; UI toggles language + RTL/LTR
- **Hebrew exports** (DOCX/XLSX) generated by `docgen` service with RTL templates
- **Git LFS required** for large PDFs in `RAG/` directory
- **Bootstrap admins** (`yaakovpreiger@gmail.com`, `valeria.preiger@gmail.com`) always receive `admin` role on first login

## Code sharing and duplication

### Service isolation policy
`iso-api` and `docgen` are deployed as separate containers with zero runtime coupling.
They do NOT share Python packages or imports.

### Vendored modules (intentional duplication)
The following code is duplicated across services to preserve isolation:

| Module | iso-api | docgen | Lines | Purpose |
|--------|---------|--------|-------|---------|
| Document extraction | app/iso/document_extract.py | app/agents/parser.py | ~145 | PDF/DOC/DOCX text extraction |
| Clause normalization | app/iso/parser.py:normalize_clause_id | app/routes/parse.py:_normalize_clause_id | ~5 | Clause ID cleanup (4.01 → 4.1) |
| Text preprocessing | app/iso/parser.py:preprocess_extracted_text | app/routes/parse.py:_preprocess_extracted_text | ~15 | Fix PDF spacing artifacts |

**Maintenance rule:** Bug fixes must be applied to BOTH copies. Search for function name
before fixing to ensure consistency.

**Why not a shared package?** Services deploy independently via GitOps. A shared package
would require version pinning, coordinated releases, and dependency management complexity
not justified for ~200 LOC.
