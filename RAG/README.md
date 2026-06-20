# RAG seed corpus

Initial population for **GitOps layer 04** (`iso-rag-populate` Job).

## Folders

| Folder | Purpose | Required at first deploy |
|--------|---------|--------------------------|
| `RAG-Standards/` | ISO standard PDFs (EN/HE, amendments) | Yes |
| `RAG-Samples/` | Hebrew sample audit reports (`.docx`) | Yes |
| `RAG-Templates/` | Report templates (Hebrew DOCX) | No — add when ready |

Manifest: [`manifest.yaml`](manifest.yaml) — drives ingest order and metadata.

## Git LFS

PDFs over ~50 MB must use LFS:

```bash
git lfs install
git lfs pull
```

The populate Job runs `git lfs pull` after clone.

## Local verify (no cluster)

```bash
python -m pytest services/rag-iso/tests/test_manifest.py -q
./scripts/verify-rag-local.sh
```

## Adding templates later

1. Drop Hebrew `.docx` files into `RAG-Templates/`.
2. Commit and push; re-run layer 4 or `./scripts/deploy-all.sh --layer 4`.
