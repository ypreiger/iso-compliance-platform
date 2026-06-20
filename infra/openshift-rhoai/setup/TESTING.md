# Testing Anthropic Claude via Vertex AI

## Current Status

✅ **Model Connections Created** - Available in your `iso-platform` project
✅ **GCP Credentials Configured** - Service account ready
✅ **Vertex AI Access** - Project: iso-compliance-platform, Region: us-east5

⚠️ **Note**: The KServe InferenceService deployment had issues with PVC requirements. For a simpler, working solution, use one of the testing methods below.

## ✅ Working Test Methods

### Method 1: Test Client Pod (Interactive)

The test client pod is running and ready:

```bash
# Enter the test client pod
oc exec -it -n iso-platform claude-test-client -- /bin/bash

# Install dependencies (run once)
pip install --user anthropic google-cloud-aiplatform

# Run the test script
python /tmp/test_vertex.py
```

Expected output:
```
Connecting to Vertex AI...
Project: iso-compliance-platform
Region: us-east5

=== Response ===
Hello! I'm Claude, an AI assistant created by Anthropic...

=== Success! ===
```

### Method 2: RHOAI Workbench/Notebook (Recommended)

1. Go to: https://rhods-dashboard-redhat-ods-applications.apps.ocp.8mkwb.sandbox3159.opentlc.com
2. Navigate to **Data Science Projects** → **iso-platform**
3. Create a **Workbench** with Python environment
4. Use this code in a Jupyter notebook:

```python
from anthropic import AnthropicVertex

# Initialize client
client = AnthropicVertex(
    project_id="iso-compliance-platform",
    region="us-east5"
)

# Test message
message = client.messages.create(
    model="claude-3-5-sonnet@20240620",
    max_tokens=1024,
    messages=[
        {"role": "user", "content": "Hello! Please tell me about yourself."}
    ]
)

print(message.content[0].text)
```

### Method 3: Custom Python Application

Create a simple Python script:

```python
#!/usr/bin/env python3
import os
from anthropic import AnthropicVertex

# Set credentials
os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = '/path/to/your/service-account-key.json'

# Initialize
client = AnthropicVertex(
    project_id="iso-compliance-platform",
    region="us-east5"
)

# Chat
message = client.messages.create(
    model="claude-3-5-sonnet@20240620",
    max_tokens=1024,
    messages=[
        {"role": "user", "content": "What is Red Hat OpenShift AI?"}
    ]
)

print(message.content[0].text)
```

## Quick Test Command

```bash
# Test that credentials work
oc exec -n iso-platform claude-test-client -- cat /var/secrets/google/key.json | jq .project_id

# Should return: "iso-compliance-platform"
```

## Available Models

Change the model by updating the secret or passing different model IDs:

- `claude-3-5-sonnet@20240620` - Most intelligent (default)
- `claude-3-opus@20240229` - Most powerful
- `claude-3-sonnet@20240229` - Balanced
- `claude-3-haiku@20240307` - Fastest

## Access Information

- **Dashboard**: https://rhods-dashboard-redhat-ods-applications.apps.ocp.8mkwb.sandbox3159.opentlc.com
- **Project**: iso-platform
- **Data Connections**: 2 connections configured
- **GCP Project**: iso-compliance-platform
- **Region**: us-east5

## Troubleshooting

### Issue: ModuleNotFoundError: No module named 'anthropic'

**Solution:**
```bash
pip install --user anthropic google-cloud-aiplatform
```

### Issue: Authentication errors

**Solution:** Verify the service account has "Vertex AI User" role:
```
https://console.cloud.google.com/iam-admin/iam?project=iso-compliance-platform
```

### Issue: Model not found

**Solution:** Enable Anthropic in Vertex AI Model Garden:
```
https://console.cloud.google.com/vertex-ai/publishers/anthropic/model-garden/claude-3-5-sonnet?project=iso-compliance-platform
```

## Next Steps

1. **Test using the test client pod** (easiest)
2. **Create a RHOAI Workbench** for persistent development
3. **Integrate into your applications** using the Anthropic SDK
4. **Monitor usage** in GCP Console

## Production Deployment

For a production deployment, consider:
- Using RHOAI's model serving with proper container images
- Setting up authentication and rate limiting
- Implementing request logging and monitoring
- Creating a proper REST API wrapper
- Adding caching for repeated queries

