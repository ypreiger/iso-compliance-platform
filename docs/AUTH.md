# Authentication & authorization

## Model

- **Authentication**: Google Sign-In (any Google / Gmail account) via Google Identity Services. Optional: Google Workspace SAML for Think-21 org accounts.
- **Authorization**: Internal role assignment by administrators. New users receive **`viewer`** until an admin grants additional roles.

## Google Sign-In — any Gmail user (production)

### 1. Google Cloud Console (one-time)

Project: `iso-compliance-platform` (or your own GCP project).

1. **OAuth consent screen** → User type: **External** (required for `@gmail.com` users, not only Workspace).
2. **Credentials** → **Create credentials** → **OAuth client ID** → **Web application**.
3. **Authorized JavaScript origins** (required):
   ```
   https://<iso-web-route>
   ```
   Example: `https://iso-web-iso-platform.apps.ocp.7hrxw.sandbox880.opentlc.com`
4. Copy the **Client ID** (`*.apps.googleusercontent.com`).

If the app is in **Testing** mode, add test user emails on the consent screen, or publish the app.

### 2. Cluster

```bash
export GOOGLE_CLIENT_ID="YOUR_CLIENT_ID.apps.googleusercontent.com"
./scripts/configure-google-signin.sh
```

Only `GOOGLE_CLIENT_ID` is required (no client secret for GIS ID-token flow).

## Google Workspace SAML (optional)

For Think-21 org SSO, configure SAML in Google Admin with ACS URL and Entity ID from `docs/AUTH.md` / `configure-saml-auth.sh`. SAML is used only when Google Sign-In is not configured.

## Bootstrap administrators

- `yaakov.preiger@think-21.com`
- `yaakovpreiger@gmail.com`
- `valeria.preiger@gmail.com`

Override with `ADMIN_EMAILS`.

## New users

Any verified Google account can sign in. First login → **`viewer`** → **ISO Standards** (`/iso`).

## Granting project access

Admins use **Admin → Users** to assign `consultant`, `supervisor`, or `admin`.

## Dry-run

```bash
export AUTH_DEV_MODE=1
./scripts/dry-run-local.sh
```
