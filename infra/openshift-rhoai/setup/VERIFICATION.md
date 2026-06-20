# End-to-End Verification Guide

## ✅ Complete Setup Deployed

### Infrastructure
- ✅ RHOAI 3.5.0-ea.1 (upgraded from 3.2.0)
- ✅ iso-platform project
- ✅ Model connections with GCP Vertex AI credentials
- ✅ TrustyAI enabled
- ✅ Guardrails configured (Red Hat & ISO only)
- ✅ MaaS playground running

### Playground URL
**https://claude-playground-iso-platform.apps.ocp.8mkwb.sandbox3159.opentlc.com**

---

## 🧪 Verification Steps

### 1. Check Playground is Running

```bash
# Check pod status
oc get pods -n iso-platform

# Expected output:
# claude-playground-xxxxx   1/1     Running   0          Xm
# claude-test-client        1/1     Running   0          Xm
```

### 2. Test Health Endpoint

```bash
curl https://claude-playground-iso-platform.apps.ocp.8mkwb.sandbox3159.opentlc.com/health
```

**Expected Response:**
```json
{
  "status": "healthy",
  "model": "claude-3-5-sonnet@20240620",
  "project": "iso-compliance-platform",
  "guardrails": "enabled"
}
```

### 3. Test Guardrails - Allowed Topic (Red Hat)

```bash
curl -X POST https://claude-playground-iso-platform.apps.ocp.8mkwb.sandbox3159.opentlc.com/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "What is Red Hat OpenShift?"}'
```

**Expected:** Response with information about Red Hat OpenShift

### 4. Test Guardrails - Allowed Topic (ISO)

```bash
curl -X POST https://claude-playground-iso-platform.apps.ocp.8mkwb.sandbox3159.opentlc.com/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "What is ISO 27001?"}'
```

**Expected:** Response with information about ISO 27001

### 5. Test Guardrails - Blocked Topic

```bash
curl -X POST https://claude-playground-iso-platform.apps.ocp.8mkwb.sandbox3159.opentlc.com/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "What is the weather today?"}'
```

**Expected Response:**
```json
{
  "blocked": true,
  "response": "I can only answer questions about Red Hat technologies and ISO standards. Please ask a question related to these topics."
}
```

### 6. Test Guardrails - Another Blocked Topic

```bash
curl -X POST https://claude-playground-iso-platform.apps.ocp.8mkwb.sandbox3159.opentlc.com/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "Tell me a joke"}'
```

**Expected:** Blocked with guardrails message

### 7. Access Web UI

Open in browser:
```
https://claude-playground-iso-platform.apps.ocp.8mkwb.sandbox3159.opentlc.com
```

**Verify:**
- ✅ Page loads with Red Hat themed UI
- ✅ Shows project info (iso-compliance-platform)
- ✅ Shows region (us-east5)
- ✅ Shows "Guardrails: ✅ Enabled"
- ✅ Has guardrails warning notice
- ✅ Pre-filled with Red Hat/ISO question
- ✅ Can send messages
- ✅ Blocked topics show red error message
- ✅ Allowed topics show green success message

### 8. Check TrustyAI

```bash
oc get pods -n redhat-ods-applications | grep trustyai
```

**Expected:**
```
trustyai-service-operator-controller-manager-xxxxx   1/1     Running   0   XXm
```

### 9. Check DataScienceCluster

```bash
oc get datasciencecluster default-dsc -o jsonpath='{.status.conditions[?(@.type=="TrustyAIReady")].status}'
```

**Expected:** `True`

### 10. Verify Model Connections

```bash
oc get secrets -n iso-platform -l opendatahub.io/dashboard=true
```

**Expected:**
```
anthropic-claude-vertex        Opaque   5      XXm
anthropic-vertex-credentials   Opaque   6      XXm
```

---

## 🎯 Test Scenarios

### Scenario 1: Valid Red Hat Question
**Input:** "How do I install Red Hat OpenShift AI?"
**Expected:** Detailed response about RHOAI installation

### Scenario 2: Valid ISO Question
**Input:** "What are the requirements for ISO 27001 certification?"
**Expected:** Detailed response about ISO 27001 requirements

### Scenario 3: Combined Question
**Input:** "How does Red Hat OpenShift help with ISO 27001 compliance?"
**Expected:** Response connecting Red Hat and ISO topics

### Scenario 4: Blocked General Topic
**Input:** "What is Python programming?"
**Expected:** Blocked by guardrails

### Scenario 5: Blocked Other Vendor
**Input:** "Tell me about AWS Lambda"
**Expected:** Blocked by guardrails

### Scenario 6: Edge Case (close but not allowed)
**Input:** "What is Kubernetes?"
**Expected:** May be blocked (not Red Hat specific)

---

## 🔍 Troubleshooting

### Issue: Vertex AI API Not Enabled

**Error:**
```
Agent Platform API has not been used in project iso-compliance-platform
```

**Solution:**
1. Go to: https://console.developers.google.com/apis/api/aiplatform.googleapis.com/overview?project=iso-compliance-platform
2. Click "Enable"
3. Wait 2-3 minutes
4. Retry

### Issue: Permission Denied

**Error:**
```
403 PERMISSION_DENIED
```

**Solution:**
Verify service account has "Vertex AI User" role:
```bash
# Check in GCP Console
https://console.cloud.google.com/iam-admin/iam?project=iso-compliance-platform
```

### Issue: Pod Not Running

```bash
# Check pod status
oc get pods -n iso-platform

# View logs
oc logs -n iso-platform deployment/claude-playground

# Describe pod
oc describe pod -n iso-platform -l app=claude-playground
```

### Issue: Guardrails Not Working

**Symptom:** All questions work regardless of topic

**Solution:**
1. Check guardrails config:
```bash
oc get configmap claude-guardrails-config -n iso-platform
```

2. Restart deployment:
```bash
oc rollout restart deployment/claude-playground -n iso-platform
```

---

## 📊 Expected Architecture

```
┌─────────────────────────────────────────────┐
│         OpenShift Cluster                    │
│                                              │
│  ┌────────────────────────────────────────┐ │
│  │  iso-platform namespace                 │ │
│  │                                         │ │
│  │  ┌──────────────────────┐              │ │
│  │  │  claude-playground   │              │ │
│  │  │  (with guardrails)   │              │ │
│  │  │                      │              │ │
│  │  │  - Flask App         │              │ │
│  │  │  - Guardrails Filter │              │ │
│  │  │  - Anthropic SDK     │              │ │
│  │  └──────────┬───────────┘              │ │
│  │             │                           │ │
│  │             │ (uses credentials)        │ │
│  │             │                           │ │
│  │  ┌──────────▼───────────┐              │ │
│  │  │ Vertex AI Secret     │              │ │
│  │  │ (GCP credentials)    │              │ │
│  │  └──────────────────────┘              │ │
│  └────────────────────────────────────────┘ │
│                                              │
│  ┌────────────────────────────────────────┐ │
│  │  redhat-ods-applications                │ │
│  │                                         │ │
│  │  - TrustyAI Operator (✅ Running)      │ │
│  │  - MaaS API (✅ Running)               │ │
│  │  - Dashboard (✅ Running)              │ │
│  └────────────────────────────────────────┘ │
└─────────────────────────────────────────────┘
              │
              │ (HTTPS)
              ▼
┌─────────────────────────────────────────────┐
│  Google Cloud Vertex AI                     │
│  - Project: iso-compliance-platform         │
│  - Region: us-east5                         │
│  - Model: Claude 3.5 Sonnet                 │
└─────────────────────────────────────────────┘
```

---

## 🎉 Success Criteria

All of the following must be ✅:

- [x] RHOAI 3.5.0-ea.1 installed
- [x] Playground accessible via web UI
- [x] Health endpoint returns healthy status
- [x] Guardrails block non-Red Hat/ISO questions
- [x] Guardrails allow Red Hat questions
- [x] Guardrails allow ISO questions
- [x] TrustyAI operator running
- [x] MaaS API available
- [x] Model connections configured
- [x] All files committed to git

---

## 📝 Quick Verification Script

```bash
#!/bin/bash

echo "=== RHOAI Claude Playground Verification ==="
echo ""

echo "1. Checking playground pod..."
oc get pods -n iso-platform -l app=claude-playground --no-headers | grep Running && echo "✅ PASS" || echo "❌ FAIL"

echo ""
echo "2. Testing health endpoint..."
curl -s https://claude-playground-iso-platform.apps.ocp.8mkwb.sandbox3159.opentlc.com/health | jq .status | grep healthy && echo "✅ PASS" || echo "❌ FAIL"

echo ""
echo "3. Testing guardrails (should block)..."
curl -s -X POST https://claude-playground-iso-platform.apps.ocp.8mkwb.sandbox3159.opentlc.com/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "What is the weather?"}' | jq .blocked | grep true && echo "✅ PASS" || echo "❌ FAIL"

echo ""
echo "4. Checking TrustyAI..."
oc get pods -n redhat-ods-applications | grep trustyai | grep Running && echo "✅ PASS" || echo "❌ FAIL"

echo ""
echo "5. Checking model connections..."
[[ $(oc get secrets -n iso-platform -l opendatahub.io/dashboard=true --no-headers | wc -l) -eq 2 ]] && echo "✅ PASS" || echo "❌ FAIL"

echo ""
echo "=== Verification Complete ==="
```

Save this as `verify.sh`, make it executable, and run:
```bash
chmod +x verify.sh
./verify.sh
```

