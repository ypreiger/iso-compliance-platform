# Product requirements — ISO Compliance Platform

## Purpose

Support ISO certification engagements by mapping audit **findings** to **ISO clause sections**, scoring **severity**, enabling **human supervisor** review, and exporting **Excel** and **DOCX** reports for regulatory bodies.

## Standards (Rag ISO corpus)

| Standard | Scope |
|----------|--------|
| ISO 9001 | Quality management |
| ISO 14001 | Environmental management |
| ISO 45001 | Occupational health & safety |
| ISO 13485 | Medical devices QMS |

The **Rag ISO** corpus holds standard text per **edition/version** and can be updated when new releases are published.

## Languages

- Application UI and internal logic: **English**
- Samples, templates, and generated customer documents: **Hebrew**

## User inputs

### Input 1 — Context questionnaire

Organization profile: industry, size, sites, departments, main processes (procurement, development, production, sales, etc.), and **certification type(s)**.

### Input 2 — Findings

Findings list via:

- Word upload
- Excel upload
- Copy/paste or direct entry in UI

### Input 3 — Supervisor review

Human supervisor may:

- Remove finding ↔ clause pairs
- Change evaluated severity
- Mark clauses **not applicable** (out of context)
- Mark clauses **not checked** (no finding coverage)

## AI / RAG behavior

### Rag ISO

Retrieve relevant ISO clause text for each finding (hybrid search: vector + keyword).

### Supervised learning

Persist supervisor edits and historical reports as labeled examples for reranking / future model improvement.

## Results

### Result 1 (intermediate)

For each finding:

- Map to **at most 3** ISO sections
- Keep pairs with **≥ 50% relevance**
- Severity per pair:
  - **Minor** — opportunity for improvement (OFI)
  - **Major** — major non-conformity
  - **Critical** — critical non-conformity

Clause coverage:

- **N/A** — out of organizational context
- **Not checked** — no finding mapped

### Result 2 — Excel

Export mapping, severity, **corrective actions** (major/critical), and **opportunity instructions** (minor/OFI).

### Result 3 — DOCX

Final regulatory report: findings, compliance status, and reasoning for non-compliance.

### Special case

**Combined report** for two ISO certifications in one engagement.

## Admin console

Versioned **prompts/instructions** per pipeline stage (configurable without code deploy). See [UI plan — Instructions edit](UI.md#4-instructions-edit-prompt-admin).

## User interface

Detailed screen-level plan (corpus uploads, supervisor mapping, exports):

- [UI.md](UI.md) — ISO / sample / template RAG uploads, instructions editor, supervisor mapping UI

## Non-functional (MVP)

- Audit trail for all supervisor and export actions
- Project pinned to ISO **edition**
- Explainability: store retrieval context + model rationale for report sections
- Supervisor approval gate before final export (configurable)
