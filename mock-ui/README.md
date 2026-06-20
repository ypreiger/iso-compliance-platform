# Mock UI — static browser preview

Open **`index.html`** directly in Chrome, Firefox, or Safari — no server, build, or `oc login` required.

## Quick start

```bash
open mock-ui/index.html
# or double-click mock-ui/index.html in Finder
```

## What you can click

| Screen | Hash route |
|--------|------------|
| Login (Google mock) | `#/login` |
| Projects dashboard | `#/projects` |
| Project workspace (context, findings, **3-pane mapping**, coverage, exports) | `#/project/p1` |
| ISO bilingual viewer (EN/HE, RTL/LTR) | `#/iso` |
| Admin → Users | `#/admin/users` |
| Admin → ISO / Samples / Templates corpus | `#/admin/iso` etc. |
| Admin → Instructions | `#/admin/instructions` |

Use **EN / HE** buttons in the top bar to switch UI language and document direction (LTR ↔ RTL).

Click **Sign in with Google** or **Continue as admin** on the login page to enter the mock app.

## Files

```
mock-ui/
├── index.html      # Entry point
├── styles.css      # Dark theme layout
├── mock-data.js    # Sample projects, findings, ISO clauses, users
├── app.js          # Hash routing + screens
└── README.md
```

This is a **visual prototype** only. The real app is `apps/iso-web` (React) + `apps/iso-api` (FastAPI).
