#!/bin/bash
set -e

echo "========================================"
echo "Anthropic Claude RHOAI Deployment"
echo "========================================"
echo ""

# Check if logged into OpenShift
if ! oc whoami &> /dev/null; then
    echo "❌ Not logged into OpenShift. Please run 'oc login' first."
    exit 1
fi

echo "✅ Logged in as: $(oc whoami)"
echo ""

# Deploy in order
echo "📦 Deploying namespace..."
oc apply -f 01-namespace.yaml

echo "📦 Deploying service account..."
oc apply -f 02-service-account.yaml

echo "📦 Deploying model connections..."
oc apply -f 03-model-connection.yaml

echo "📦 Deploying serving runtime..."
oc apply -f 04-serving-runtime.yaml

echo "📦 Deploying inference service..."
oc apply -f 05-inference-service.yaml

echo "📦 Deploying test client..."
oc apply -f 06-test-client.yaml

echo "📦 Deploying playground..."
oc apply -f 07-playground-deployment.yaml

echo ""
echo "========================================"
echo "✅ Deployment Complete!"
echo "========================================"
echo ""
echo "Waiting for playground to be ready..."
oc wait --for=condition=available deployment/claude-playground -n iso-platform --timeout=300s || true

echo ""
echo "🌐 Access URLs:"
echo "  Playground: https://$(oc get route claude-playground -n iso-platform -o jsonpath='{.spec.host}')"
echo "  Dashboard:  https://rhods-dashboard-redhat-ods-applications.apps.ocp.8mkwb.sandbox3159.opentlc.com"
echo ""
echo "🧪 To test the connection:"
echo "  oc exec -n iso-platform claude-test-client -- python /tmp/test_vertex.py"
echo ""
echo "📊 To check status:"
echo "  oc get all -n iso-platform"
echo ""
