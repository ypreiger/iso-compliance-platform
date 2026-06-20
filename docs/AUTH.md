# Authentication & local dry-run

## Google OAuth (production)

1. Create OAuth client in [Google Cloud Console](https://console.cloud.google.com/apis/credentials).
2. Authorized redirect URI: `https://<iso-web-route>/login` (or `/auth/callback`).
3. Set on cluster:
   - ConfigMap `iso-app-config`: `GOOGLE_CLIENT_ID`
   - Secret `iso-secrets`: `GOOGLE_CLIENT_SECRET`, `JWT_SECRET`

## Bootstrap administrators

These Google accounts receive **admin** on first login (also seeded in DB):

- `yaakovpreiger@gmail.com`
- `valeria.preiger@gmail.com`

Override with env `ADMIN_EMAILS` (comma-separated).

## User invite flow

1. Admin signs in → **Admin → Users**.
2. Enter email + roles (`consultant`, `supervisor`, `admin`).
3. Invited user signs in with Google using that email.

Non-invited emails are rejected unless listed in `ADMIN_EMAILS`.

## Dry-run (no Google credentials)

```bash
export AUTH_DEV_MODE=1
./scripts/dry-run-local.sh
```

Dev login accepts bootstrap admin emails only unless user was pre-invited.

## UI language vs ISO text

| Layer | Languages | Direction |
|-------|-----------|-----------|
| Application chrome | EN / HE (toggle) | LTR / RTL via `document.dir` |
| ISO clause viewer | EN + HE side-by-side | Per-locale `dir` on content panels |
| Generated exports | Hebrew default | RTL in DOCX (docgen phase 2) |

See [UI.md](UI.md) and `/iso` route in iso-web.
