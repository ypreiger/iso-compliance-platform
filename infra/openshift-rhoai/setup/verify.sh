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
