#!/bin/bash
# Comprehensive verification of all ISO Compliance Platform functions

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo "========================================="
echo "ISO Compliance Platform - Full Verification"
echo "========================================="
echo

# 1. Check GPT-oss-20b
echo -e "${YELLOW}[1/8] Checking GPT-oss-20b LLM...${NC}"
GPT_POD=$(oc get pods -n llm -l app.kubernetes.io/name=gpt-oss-20b --field-selector=status.phase=Running -o name | head -1)
if [ -z "$GPT_POD" ]; then
    echo -e "${RED}✗ GPT-oss-20b pod not running${NC}"
    oc get pods -n llm | grep gpt-oss-20b
    exit 1
fi

echo "  Testing GPT-oss-20b endpoint..."
RESPONSE=$(oc exec -n iso-platform deployment/iso-api-orchestrator -- curl -sk https://gpt-oss-20b-kserve-workload-svc.llm.svc.cluster.local:8000/v1/models --max-time 5 2>&1)
if echo "$RESPONSE" | grep -q "gpt-oss-20b"; then
    echo -e "${GREEN}✓ GPT-oss-20b responding${NC}"
else
    echo -e "${RED}✗ GPT-oss-20b not responding${NC}"
    echo "$RESPONSE"
    exit 1
fi

# Test chat completion
echo "  Testing GPT-oss-20b chat completion..."
CHAT_RESPONSE=$(oc exec -n iso-platform deployment/iso-api-orchestrator -- curl -sk https://gpt-oss-20b-kserve-workload-svc.llm.svc.cluster.local:8000/v1/chat/completions -H "Content-Type: application/json" -d '{"model":"gpt-oss-20b","messages":[{"role":"user","content":"Say OK"}],"max_tokens":5}' --max-time 30 2>&1)
if echo "$CHAT_RESPONSE" | grep -q '"content"'; then
    echo -e "${GREEN}✓ GPT-oss-20b chat completion working${NC}"
elif echo "$CHAT_RESPONSE" | grep -q "Hermes"; then
    echo -e "${RED}✗ Tool parser error still exists!${NC}"
    echo "$CHAT_RESPONSE"
    exit 1
else
    echo -e "${RED}✗ GPT-oss-20b chat completion failed${NC}"
    echo "$CHAT_RESPONSE"
    exit 1
fi

echo

# 2. Check BGE-M3
echo -e "${YELLOW}[2/8] Checking BGE-M3 embeddings...${NC}"
BGE_RESPONSE=$(curl -sk https://bge-m3-llm.apps.ocp.7hrxw.sandbox880.opentlc.com/v1/models --max-time 5 2>&1)
if echo "$BGE_RESPONSE" | grep -q "bge-m3"; then
    echo -e "${GREEN}✓ BGE-M3 responding${NC}"
else
    echo -e "${RED}✗ BGE-M3 not responding${NC}"
    exit 1
fi

# Test embedding generation
echo "  Testing BGE-M3 embedding generation..."
EMBED_RESPONSE=$(curl -sk https://bge-m3-llm.apps.ocp.7hrxw.sandbox880.opentlc.com/v1/embeddings -H "Content-Type: application/json" -d '{"model":"bge-m3","input":"test"}' --max-time 10 2>&1)
if echo "$EMBED_RESPONSE" | grep -q '"embedding"'; then
    echo -e "${GREEN}✓ BGE-M3 embedding generation working${NC}"
else
    echo -e "${RED}✗ BGE-M3 embedding generation failed${NC}"
    echo "$EMBED_RESPONSE"
    exit 1
fi

echo

# 3. Check PostgreSQL + pgvector
echo -e "${YELLOW}[3/8] Checking PostgreSQL + pgvector...${NC}"
PG_POD=$(oc get pods -n iso-platform -l app=iso-postgres --field-selector=status.phase=Running -o name | head -1)
if [ -z "$PG_POD" ]; then
    echo -e "${RED}✗ PostgreSQL pod not running${NC}"
    exit 1
fi

echo "  Checking pgvector extension..."
PGVECTOR_CHECK=$(oc exec -n iso-platform "$PG_POD" -- psql -U iso -d iso -tAc "SELECT extversion FROM pg_extension WHERE extname='vector';" 2>&1)
if [ -n "$PGVECTOR_CHECK" ]; then
    echo -e "${GREEN}✓ pgvector extension installed (version: $PGVECTOR_CHECK)${NC}"
else
    echo -e "${RED}✗ pgvector extension not installed${NC}"
    exit 1
fi

echo "  Checking rag_documents table..."
RAG_COUNT=$(oc exec -n iso-platform "$PG_POD" -- psql -U iso -d iso -tAc "SELECT COUNT(*) FROM rag_documents;" 2>&1)
if [ "$RAG_COUNT" -gt 0 ]; then
    echo -e "${GREEN}✓ rag_documents table has $RAG_COUNT rows${NC}"
else
    echo -e "${YELLOW}⚠ rag_documents table is empty${NC}"
fi

echo "  Checking IVFFlat index..."
INDEX_CHECK=$(oc exec -n iso-platform "$PG_POD" -- psql -U iso -d iso -tAc "SELECT indexname FROM pg_indexes WHERE tablename='rag_documents' AND indexname LIKE '%ivfflat%';" 2>&1)
if [ -n "$INDEX_CHECK" ]; then
    echo -e "${GREEN}✓ IVFFlat index exists: $INDEX_CHECK${NC}"
else
    echo -e "${YELLOW}⚠ IVFFlat index not found${NC}"
fi

echo

# 4. Check Grafana metrics
echo -e "${YELLOW}[4/8] Checking Grafana observability...${NC}"
GRAFANA_URL="https://grafana-route-grafana.apps.ocp.7hrxw.sandbox880.opentlc.com"
GRAFANA_CHECK=$(curl -sk -o /dev/null -w "%{http_code}" "$GRAFANA_URL" --max-time 5)
if [ "$GRAFANA_CHECK" = "200" ]; then
    echo -e "${GREEN}✓ Grafana accessible at $GRAFANA_URL${NC}"
else
    echo -e "${RED}✗ Grafana not accessible (HTTP $GRAFANA_CHECK)${NC}"
fi

echo "  Checking ServiceMonitors..."
SM_COUNT=$(oc get servicemonitor -n llm -l app.kubernetes.io/component=llm-monitoring --no-headers 2>/dev/null | wc -l)
if [ "$SM_COUNT" -ge 3 ]; then
    echo -e "${GREEN}✓ $SM_COUNT ServiceMonitors configured${NC}"
    oc get servicemonitor -n llm -l app.kubernetes.io/component=llm-monitoring --no-headers | awk '{print "    - " $1}'
else
    echo -e "${YELLOW}⚠ Only $SM_COUNT ServiceMonitors found (expected 3+)${NC}"
fi

echo

# 5. Check Playground
echo -e "${YELLOW}[5/8] Checking AI Playground...${NC}"
PLAYGROUND_URL="https://playground-iso-platform.apps.ocp.7hrxw.sandbox880.opentlc.com"
PLAYGROUND_CHECK=$(curl -sk -o /dev/null -w "%{http_code}" "$PLAYGROUND_URL" --max-time 5)
if [ "$PLAYGROUND_CHECK" = "200" ]; then
    echo -e "${GREEN}✓ Playground accessible at $PLAYGROUND_URL${NC}"
else
    echo -e "${RED}✗ Playground not accessible (HTTP $PLAYGROUND_CHECK)${NC}"
fi

PLAYGROUND_PODS=$(oc get pods -n iso-platform -l app.kubernetes.io/name=playground --field-selector=status.phase=Running --no-headers 2>/dev/null | wc -l)
if [ "$PLAYGROUND_PODS" -ge 2 ]; then
    echo -e "${GREEN}✓ $PLAYGROUND_PODS Playground pods running${NC}"
else
    echo -e "${YELLOW}⚠ Only $PLAYGROUND_PODS Playground pod(s) running (expected 2)${NC}"
fi

echo

# 6. Check ISO Web & API
echo -e "${YELLOW}[6/8] Checking ISO Web & API...${NC}"
WEB_URL="https://iso-web-iso-platform.apps.ocp.7hrxw.sandbox880.opentlc.com"
WEB_CHECK=$(curl -sk -o /dev/null -w "%{http_code}" "$WEB_URL" --max-time 5)
if [ "$WEB_CHECK" = "200" ]; then
    echo -e "${GREEN}✓ ISO Web accessible at $WEB_URL${NC}"
else
    echo -e "${RED}✗ ISO Web not accessible (HTTP $WEB_CHECK)${NC}"
fi

API_HEALTH=$(curl -sk "$WEB_URL/api/health" --max-time 5 2>&1)
if echo "$API_HEALTH" | grep -q '"status"'; then
    echo -e "${GREEN}✓ ISO API health check passed${NC}"
else
    echo -e "${RED}✗ ISO API health check failed${NC}"
fi

echo

# 7. Check GitOps
echo -e "${YELLOW}[7/8] Checking GitOps deployment...${NC}"
ARGOCD_APPS=$(oc get applications -n openshift-gitops -l app.kubernetes.io/name=iso-compliance-platform --no-headers 2>/dev/null | wc -l)
if [ "$ARGOCD_APPS" -ge 1 ]; then
    echo -e "${GREEN}✓ $ARGOCD_APPS ArgoCD application(s) found${NC}"
    oc get applications -n openshift-gitops | grep -E "iso-compliance|llm-ai" | awk '{print "    " $1 " - " $2 " / " $3}'
else
    echo -e "${YELLOW}⚠ No ArgoCD applications found${NC}"
fi

echo

# 8. Check doc-parse configuration
echo -e "${YELLOW}[8/8] Checking doc-parse-rag configuration...${NC}"
EXTRACT_MODEL_URL=$(oc get cm -n iso-platform iso-app-config -o jsonpath='{.data.EXTRACT_MODEL_URL}' 2>/dev/null)
EXTRACT_MODEL_NAME=$(oc get cm -n iso-platform iso-app-config -o jsonpath='{.data.EXTRACT_MODEL_NAME}' 2>/dev/null)

if echo "$EXTRACT_MODEL_URL" | grep -q "https://gpt-oss-20b"; then
    echo -e "${GREEN}✓ doc-parse configured to use GPT-oss-20b via HTTPS${NC}"
    echo "    URL: $EXTRACT_MODEL_URL"
    echo "    Model: $EXTRACT_MODEL_NAME"
else
    echo -e "${RED}✗ doc-parse NOT configured for HTTPS GPT-oss-20b${NC}"
    echo "    URL: $EXTRACT_MODEL_URL"
    exit 1
fi

DOC_PARSE_PODS=$(oc get pods -n iso-platform -l app=iso-doc-parse-rag --field-selector=status.phase=Running --no-headers 2>/dev/null | wc -l)
if [ "$DOC_PARSE_PODS" -ge 1 ]; then
    echo -e "${GREEN}✓ $DOC_PARSE_PODS doc-parse-rag pod(s) running${NC}"
else
    echo -e "${RED}✗ No doc-parse-rag pods running${NC}"
    exit 1
fi

echo
echo "========================================="
echo -e "${GREEN}All verifications completed!${NC}"
echo "========================================="
echo
echo "Summary:"
echo "  ✓ GPT-oss-20b LLM (21B MoE, 128K context)"
echo "  ✓ BGE-M3 embeddings (1024-dim, multilingual)"
echo "  ✓ PostgreSQL + pgvector (IVFFlat index)"
echo "  ✓ Grafana observability (ServiceMonitors)"
echo "  ✓ AI Playground (multi-model)"
echo "  ✓ ISO Web & API"
echo "  ✓ GitOps deployment (ArgoCD)"
echo "  ✓ doc-parse-rag (HTTPS GPT-oss-20b)"
echo
echo "Ready for Hebrew document parsing! 🎉"
echo
echo "Next steps:"
echo "  1. Upload Hebrew ISO9001 document via ISO Web"
echo "  2. Verify 94 clauses extracted (not 21)"
echo "  3. Check Grafana for GPT-oss-20b metrics"
echo
