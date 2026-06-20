# Anthropic Claude on RHOAI - Setup Guide

This directory contains all the manifests needed to deploy Anthropic Claude models via Google Cloud Vertex AI on Red Hat OpenShift AI (RHOAI).

## Architecture

- **RHOAI Version**: 3.5.0-ea.1
- **Provider**: Anthropic via Google Cloud Vertex AI
- **Region**: us-east5
- **Model**: Claude 3.5 Sonnet (claude-3-5-sonnet@20240620)
- **Project**: iso-compliance-platform

## Files Overview

1. **01-namespace.yaml** - Creates the `iso-platform` namespace/project
2. **02-service-account.yaml** - Service account and RBAC for model serving
3. **03-model-connection.yaml** - Secrets containing GCP credentials and Vertex AI config
4. **04-serving-runtime.yaml** - KServe serving runtime for Anthropic models
5. **05-inference-service.yaml** - InferenceService deployment
6. **06-test-client.yaml** - Test client pod for validation
7. **07-playground-deployment.yaml** - Web-based playground UI

## Prerequisites

✅ RHOAI 3.5.0-ea.1 installed
✅ GCP project with Vertex AI API enabled
✅ Anthropic models enabled in Vertex AI Model Garden
✅ GCP service account with Vertex AI User role
✅ Service account JSON key downloaded

## Quick Start

### 1. Deploy All Resources

```bash
# From the repository root
cd iso-compliance-platform/infra/openshift-rhoai/setup

# Apply all manifests in order
oc apply -f 01-namespace.yaml
oc apply -f 02-service-account.yaml
oc apply -f 03-model-connection.yaml
oc apply -f 04-serving-runtime.yaml
oc apply -f 05-inference-service.yaml
oc apply -f 06-test-client.yaml
oc apply -f 07-playground-deployment.yaml
```

### 2. Verify Deployment

```bash
# Check all resources
oc get all -n iso-platform

# Check secrets
oc get secrets -n iso-platform

# Check serving runtime
oc get servingruntimes -n iso-platform

# Check inference service
oc get inferenceservices -n iso-platform
```

### 3. Test the Connection

#### Option A: Using Test Client Pod

```bash
# Wait for test client to be running
oc wait --for=condition=Ready pod/claude-test-client -n iso-platform --timeout=300s

# Run the test
oc exec -n iso-platform claude-test-client -- python /tmp/test_vertex.py
```

Expected output:
```
Connecting to Vertex AI...
Project: iso-compliance-platform
Region: us-east5

=== Response ===
Hello! I'm Claude, an AI assistant created by Anthropic. I'm working correctly and ready to help you...

=== Success! ===
```

#### Option B: Using Playground Web UI

```bash
# Get the playground URL
oc get route claude-playground -n iso-platform -o jsonpath='https://{.spec.host}'
```

Open the URL in your browser to access the interactive playground.

### 4. Access from RHOAI Dashboard

1. Navigate to: https://rhods-dashboard-redhat-ods-applications.apps.ocp.8mkwb.sandbox3159.opentlc.com
2. Go to **Data Science Projects** → **iso-platform**
3. You should see:
   - **Data Connections**: 2 connections listed
   - **Models**: Claude model deployment
   - **Playground**: Interactive testing interface

## Available Models

Update `MODEL_NAME` in `03-model-connection.yaml` to use different models:

- `claude-3-5-sonnet@20240620` - Most intelligent (default)
- `claude-3-opus@20240229` - Most powerful for complex tasks
- `claude-3-sonnet@20240229` - Balanced performance
- `claude-3-haiku@20240307` - Fastest

After changing, restart the playground:
```bash
oc rollout restart deployment/claude-playground -n iso-platform
```

## Troubleshooting

### Check Pod Logs

```bash
# Playground logs
oc logs -n iso-platform deployment/claude-playground

# Test client logs
oc logs -n iso-platform claude-test-client
```

### Verify GCP Credentials

```bash
oc exec -n iso-platform claude-test-client -- cat /var/secrets/google/key.json | jq .project_id
```

### Check Vertex AI Access

```bash
oc exec -n iso-platform claude-test-client -- bash -c '
  gcloud auth activate-service-account --key-file=/var/secrets/google/key.json
  gcloud config set project iso-compliance-platform
  gcloud ai models list --region=us-east5 --limit=5
'
```

### Common Issues

1. **"Permission denied" errors**
   - Verify service account has "Vertex AI User" role in GCP
   - Check that Anthropic models are enabled in Vertex AI

2. **"Model not found" errors**
   - Ensure Anthropic is enabled in Vertex AI Model Garden
   - Verify the model ID matches what's available in your region

3. **Connection timeouts**
   - Check network policies allow egress to Google APIs
   - Verify firewall rules permit HTTPS traffic

## Clean Up

```bash
# Delete all resources
oc delete -f 07-playground-deployment.yaml
oc delete -f 06-test-client.yaml
oc delete -f 05-inference-service.yaml
oc delete -f 04-serving-runtime.yaml
oc delete -f 03-model-connection.yaml
oc delete -f 02-service-account.yaml

# Optional: Delete the entire project
oc delete project iso-platform
```

## Security Notes

⚠️ **Important**: The `03-model-connection.yaml` file contains GCP credentials. 

- Do NOT commit this file with real credentials to version control
- Use a secret management solution (Vault, Sealed Secrets, etc.) for production
- Rotate credentials regularly
- Limit service account permissions to minimum required

## Next Steps

- Configure rate limiting and quotas
- Set up monitoring and alerting
- Implement request logging
- Add authentication/authorization
- Scale deployment based on load

## Support

For issues related to:
- **RHOAI**: Red Hat support or documentation
- **Vertex AI**: Google Cloud support
- **Anthropic Claude**: Anthropic documentation

## Links

- [RHOAI Documentation](https://access.redhat.com/documentation/en-us/red_hat_openshift_ai_self-managed)
- [Vertex AI - Anthropic](https://cloud.google.com/vertex-ai/generative-ai/docs/partner-models/use-claude)
- [Anthropic Documentation](https://docs.anthropic.com/)
