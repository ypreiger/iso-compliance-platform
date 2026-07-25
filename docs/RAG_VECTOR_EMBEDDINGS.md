# RAG with Vector Embeddings

## Overview

The ISO Compliance Platform uses advanced RAG (Retrieval Augmented Generation) with multilingual vector embeddings for semantic search across ISO standards in English and Hebrew.

## Architecture

```
Document Upload (Hebrew/English ISO Standards)
        │
        ▼
┌─────────────────────────────────────────────┐
│  LLM-based Clause Extraction                │
│  (GPT-oss-20b: 21B MoE, 128K context)       │
│  → Handles RTL Hebrew text correctly        │
│  → Identifies clause boundaries (1, 2, 4.1) │
│  → Extracts 94 clauses vs 21 with regex     │
└────────┬────────────────────────────────────┘
         │ Structured clauses (94 total)
         ▼
┌─────────────────────────────────────────────┐
│  Text Chunking                              │
│  - Size: 1000 characters                    │
│  - Overlap: 100 characters                  │
│  - Result: 123 chunks from 94 clauses       │
└────────┬────────────────────────────────────┘
         │ Text chunks
         ▼
┌─────────────────────────────────────────────┐
│  BGE-M3 Embedding Generation                │
│  - Model: BAAI/bge-m3                       │
│  - Batch size: 32 chunks                    │
│  - Output: 1024-dimensional vectors         │
│  - Multilingual: EN/HE/100+ languages       │
└────────┬────────────────────────────────────┘
         │ Vector embeddings (1024-dim)
         ▼
┌─────────────────────────────────────────────┐
│  PostgreSQL + pgvector Storage              │
│  - Extension: pgvector 0.6.2                │
│  - Index: IVFFlat with 100 lists            │
│  - Distance: Cosine similarity              │
│  - Table: rag_documents                     │
└─────────────────────────────────────────────┘
```

## Components

### 1. BGE-M3 Embedding Model

**Model Details:**
- **Full Name**: BAAI/bge-m3
- **Size**: 568M parameters
- **Embedding Dimension**: 1024
- **Languages**: 100+ (including English and Hebrew)
- **License**: MIT
- **Deployment**: sentence-transformers on CPU (no GPU needed for embeddings)
- **MaaS routing**: `HTTPRoute/bge-m3-maas-route` → Kuadrant Auth/RateLimit → Limitador `authorized_hits`

### When BGE-M3 is needed

BGE-M3 produces **1024-dim multilingual embeddings** so RAG can match Hebrew and English by meaning (not only keywords). It is required when:

1. **Indexing** ISO uploads into `rag_documents.embedding` (Admin upload / translate re-index)
2. **Querying** semantic RAG (project **Auto mapping**, and any future vector search UI)

It is **not** used for chat/parse/translate — those use GPT-oss (or other chat models).

### Why it looked unused before

Until the wiring below, upload only stored text chunks (keyword RAG). `vector_search.py` existed but no route called it, so UI actions never hit BGE-M3 and MaaS token panels stayed empty for `bge-m3`.

### Endpoints
```
# App / RAG (in-cluster — volume; app metrics iso_app_model_* + bge_m3_*)
http://bge-m3.llm.svc.cluster.local:8080/v1/embeddings

# MaaS (Kuadrant authorized_hits{model="bge-m3"}) — demos / gateway monitoring
https://maas.apps.ocp.7hrxw.sandbox880.opentlc.com/llm/bge-m3/v1/embeddings
```

Monitor **application** use in Grafana dashboard `ISO App Model Calls` (`embed_index` / `embed_query` / `bge-m3`).

**Why BGE-M3?**
- Best multilingual performance for Hebrew/English
- Higher quality than OpenAI text-embedding-ada-002
- Open weights (no vendor lock-in)
- Optimized for semantic search tasks

### 2. GPT-oss-20b Document Parser

**Model Details:**
- **Full Name**: openai/gpt-oss-20b
- **Size**: 21B parameters (3.6B active via Mixture-of-Experts)
- **Context Length**: 128K tokens
- **License**: Apache 2.0
- **Performance**: Matches o3-mini on reasoning tasks
- **Deployment**: vLLM on NVIDIA L40 GPU (48GB VRAM)

**Endpoint:**
```
https://gpt-oss-20b-kserve-workload-svc.llm.svc.cluster.local:8000/v1
```

**Key Capabilities:**
- Handles RTL (right-to-left) Hebrew text
- Identifies clause boundaries in complex documents
- Extracts structured metadata (clause ID, title, body)
- Superior to regex parsing for multilingual documents

**Performance:**
- **Before (regex parser)**: 21 clauses extracted, garbled Hebrew text
- **After (GPT-oss-20b)**: 94 clauses extracted correctly ✅

### 3. pgvector for Vector Search

**PostgreSQL Extension:**
```sql
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE rag_documents (
    id SERIAL PRIMARY KEY,
    collection_id TEXT NOT NULL,
    chunk_index INT NOT NULL,
    content TEXT NOT NULL,
    embedding vector(1024),  -- BGE-M3 embeddings
    metadata JSONB,
    created_at TIMESTAMP DEFAULT NOW()
);

-- IVFFlat index for fast cosine similarity search
CREATE INDEX rag_embeddings_ivfflat_idx 
ON rag_documents 
USING ivfflat (embedding vector_cosine_ops) 
WITH (lists = 100);
```

**Index Type**: IVFFlat (Inverted File with Flat quantization)
- **Lists**: 100 (partitions for faster search)
- **Distance Metric**: Cosine similarity
- **Query Time**: <100ms for top-10 results
- **Recall**: ~98% with 100 lists

## Ingestion Pipeline

**RAG Job** (`rag-iso` service):

```python
# services/rag-iso/rag_iso/ingest.py

1. Clone repository: git clone + git lfs pull
2. Read manifest: RAG/manifest.yaml
3. For each document:
   a. Extract text (PDF/DOCX)
   b. Call GPT-oss-20b for clause extraction
   c. Chunk extracted text (1000 chars, 100 overlap)
   d. Generate embeddings in batches (32 chunks)
   e. Store in rag_documents with pgvector
4. Create IVFFlat index
5. Report statistics (clauses, chunks, embeddings)
```

**Configuration:**
- Batch size for embeddings: 32 chunks
- Max retries for LLM calls: 3
- Fallback: regex parser (if LLM unavailable)

## Semantic Search

**Query Flow:**

```python
# apps/iso-api/app/iso/vector_search.py

def search_similar_chunks(
    query: str,
    collection_id: str = "iso-standards",
    language: Optional[str] = None,
    top_k: int = 10,
    min_similarity: float = 0.5
) -> List[Dict]:
    # 1. Generate query embedding
    query_embedding = generate_embedding(query)  # BGE-M3: 1024-dim
    
    # 2. Search with cosine similarity
    sql = """
        SELECT 
            content,
            metadata,
            1 - (embedding <=> %s::vector) as similarity
        FROM rag_documents
        WHERE collection_id = %s
        AND (%s IS NULL OR metadata->>'language' = %s)
        AND (1 - (embedding <=> %s::vector)) >= %s
        ORDER BY embedding <=> %s::vector
        LIMIT %s
    """
    
    # 3. Return ranked results
    return results  # [{content, metadata, similarity}]
```

**Performance:**
- Query embedding generation: ~45ms (BGE-M3)
- Vector search (IVFFlat): <50ms for 10K documents
- Total query time: <100ms

## Multilingual Support

**Language Handling:**

| Language | ISO Clause Text | Embeddings | Search Quality |
|----------|----------------|------------|----------------|
| English | Stored in `iso_clause_text.body` | BGE-M3 (1024-dim) | Excellent |
| Hebrew | Stored in `iso_clause_text.body` (RTL) | BGE-M3 (1024-dim) | Excellent |

**Examples:**

```python
# English query
results = search_similar_chunks(
    query="quality management requirements",
    language="en",
    top_k=5
)

# Hebrew query
results = search_similar_chunks(
    query="דרישות ניהול איכות",  # "quality management requirements"
    language="he",
    top_k=5
)
```

Both queries return semantically similar clauses because BGE-M3 understands cross-lingual similarity.

## Current Status

**✅ Implemented:**
- BGE-M3 deployment on CPU (vLLM)
- GPT-oss-20b deployment on L40 GPU
- pgvector extension in PostgreSQL
- Embedding generation during ingestion
- IVFFlat index creation
- Vector storage in `rag_documents` table
- `vector_search.py` with semantic search function

**⏳ TODO:**
- **Wire up vector search to API routes**: `vector_search.py` exists but is not imported
  - Current: `iso_text.py` uses simple substring matching
  - Target: Replace with `search_similar_chunks()` for semantic search
- Add reranking with cross-encoder (optional enhancement)
- Hybrid search: combine dense (BGE-M3) + sparse (BM25)

## Observability

**Metrics:**
- BGE-M3 request rate: `vllm:request_success_total{model="bge-m3"}`
- Embedding generation latency: `vllm:e2e_request_latency_seconds{model="bge-m3"}`
- GPT-oss-20b parsing latency: `vllm:e2e_request_latency_seconds{model="gpt-oss-20b"}`

**Grafana Dashboard:**
- URL: https://grafana-route-grafana.apps.ocp.7hrxw.sandbox880.opentlc.com
- Dashboard: "LLM Observability - ISO Platform"
- Panels: Request rate, P95/P99 latency, GPU utilization, model health

## Deployment

**GitOps:**
```
gitops/overlays/ocp-sandbox3159/llm-ai/
├── bge-m3-simple.yaml          # CPU-based BGE-M3 deployment (+ /metrics, /v1/models)
├── bge-m3-external-model.yaml  # MaaS HTTPRoute (/llm/bge-m3/v1)
├── gpt-oss-20b.yaml            # GPU-based GPT-oss-20b
└── llm-servicemonitors.yaml    # Prometheus ServiceMonitor (bge-m3-metrics)
```

**Environment Variables:**
```bash
# iso-api, rag-iso — in-cluster for volume; MaaS path for monitored demos
LLM_EMBED_URL=http://bge-m3.llm.svc.cluster.local:8080
LLM_MODEL_EMBED=bge-m3
```

# doc-parse-rag
EXTRACT_MODEL_URL=https://gpt-oss-20b-kserve-workload-svc.llm.svc.cluster.local:8000/v1
EXTRACT_MODEL_NAME=gpt-oss-20b
```

## Next Steps

1. **Integrate vector search**:
   ```python
   # In apps/iso-api/app/routes/iso_text.py
   from app.iso.vector_search import search_similar_chunks
   
   @router.get("/v1/iso/clauses")
   def get_clauses(query: Optional[str] = None, ...):
       if query:
           # Use semantic search
           results = search_similar_chunks(query, ...)
       else:
           # List all clauses
           results = db.query(IsoClause).all()
   ```

2. **Add hybrid search** (dense + sparse):
   - BGE-M3 for semantic similarity
   - BM25 for keyword matching
   - Combine with reciprocal rank fusion

3. **Fine-tune on supervisor edits**:
   - Collect human feedback from supervisor reviews
   - Fine-tune BGE-M3 on domain-specific data
   - Improve relevance for ISO compliance queries

## References

- BGE-M3 paper: https://arxiv.org/abs/2402.03216
- pgvector documentation: https://github.com/pgvector/pgvector
- GPT-oss-20b: https://huggingface.co/openai/gpt-oss-20b
- vLLM documentation: https://docs.vllm.ai/
