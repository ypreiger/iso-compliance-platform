# GCP Setup - Final Step

## ✅ Current Status

- ✅ Playground deployed and running
- ✅ Project: itpc-gcp-global-revenue-claude
- ✅ Service account: yaakov@itpc-gcp-global-revenue-claude.iam.gserviceaccount.com
- ✅ Credentials updated
- ⏳ Needs: Vertex AI User role

## Required: Grant Vertex AI User Role

The service account needs the **Vertex AI User** role to access Claude models.

### Steps:

1. **Go to IAM page**:
   ```
   https://console.cloud.google.com/iam-admin/iam?project=itpc-gcp-global-revenue-claude
   ```

2. **Find the service account**:
   - Email: `yaakov@itpc-gcp-global-revenue-claude.iam.gserviceaccount.com`

3. **Grant permission**:
   - Click **"Grant Access"** or find existing account and click **"Edit"**
   - Add role: **"Vertex AI User"** (`roles/aiplatform.user`)
   - Click **"Save"**

4. **Wait 2-3 minutes** for permissions to propagate

### Alternative: Use IAM Troubleshooter

Visit the auto-generated troubleshooter link from the error:
```
https://console.cloud.google.com/iam-admin/troubleshooter
```

This will guide you through granting the exact permission needed.

## Verification

After granting the role, test the playground:

```bash
curl -X POST https://claude-playground-iso-platform.apps.ocp.8mkwb.sandbox3159.opentlc.com/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "What is Red Hat OpenShift AI and how does it help with ISO 27001 compliance?"}'
```

**Expected**: Detailed response from Claude about RHOAI and ISO 27001

## Guardrails Verification

Test that guardrails are blocking non-allowed topics:

```bash
curl -X POST https://claude-playground-iso-platform.apps.ocp.8mkwb.sandbox3159.opentlc.com/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "What is the weather?"}'
```

**Expected**: `{"blocked":true,"response":"I can only answer questions about Red Hat technologies and ISO standards..."}`

## Web UI

Open in browser:
```
https://claude-playground-iso-platform.apps.ocp.8mkwb.sandbox3159.opentlc.com
```

Try asking:
- ✅ "What is Red Hat OpenShift?" → Should work
- ✅ "Explain ISO 27001" → Should work
- 🚫 "What's the weather?" → Should be blocked

## Summary

Once the Vertex AI User role is granted, the playground will be fully functional with:
- ✅ Claude 3.5 Sonnet responses
- ✅ Guardrails (Red Hat & ISO topics only)
- ✅ TrustyAI monitoring
- ✅ Web UI and API access
