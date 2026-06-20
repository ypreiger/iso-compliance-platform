# GCP Setup Required for Anthropic Claude via Vertex AI

## Current Status

✅ Playground deployed and running
✅ Project configured: itpc-gcp-global-revenue-claude
❌ Service account needs permissions

## Required GCP Configuration

### 1. Enable Vertex AI API

Visit:
```
https://console.developers.google.com/apis/api/aiplatform.googleapis.com/overview?project=itpc-gcp-global-revenue-claude
```

Click **"Enable"** and wait 2-3 minutes.

### 2. Grant Service Account Permissions

The service account `REPLACE_WITH_SA@PROJECT.iam.gserviceaccount.com` needs the **Vertex AI User** role.

**Steps:**

1. Go to IAM page:
   ```
   https://console.cloud.google.com/iam-admin/iam?project=itpc-gcp-global-revenue-claude
   ```

2. Find the service account:
   - Email: `REPLACE_WITH_SA@PROJECT.iam.gserviceaccount.com`

3. Click **"Edit"** (pencil icon)

4. Click **"Add Another Role"**

5. Select: **Vertex AI User** (roles/aiplatform.user)

6. Click **"Save"**

### 3. Enable Anthropic Models

Visit Vertex AI Model Garden:
```
https://console.cloud.google.com/vertex-ai/publishers/anthropic/model-garden/claude-3-5-sonnet?project=itpc-gcp-global-revenue-claude
```

Ensure Anthropic Claude models are enabled for your project.

## Verification

After completing the above steps, test the playground:

```bash
curl -X POST https://claude-playground-iso-platform.apps.ocp.8mkwb.sandbox3159.opentlc.com/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "What is Red Hat OpenShift AI?"}'
```

**Expected:** JSON response with information about Red Hat OpenShift AI

**If you see 403 error:** Wait 2-3 minutes for permissions to propagate, then retry.

## Current Error

```
Permission 'aiplatform.endpoints.predict' denied
```

This confirms the service account exists but lacks the Vertex AI User role.

## Troubleshooter URL

If issues persist, use the GCP IAM Troubleshooter:
```
https://console.cloud.google.com/iam-admin/troubleshooter;errorId=CiQwMTllZTYyNy00NjFlLTcyYWQtYmE0YS01NDVmYWYyMzc5NmY
```

## Summary

✅ Playground: Running
✅ Guardrails: Working  
✅ Project: Configured correctly (itpc-gcp-global-revenue-claude)
⏳ Waiting for: Vertex AI User role on service account

Once permissions are granted, the playground will be fully functional.
