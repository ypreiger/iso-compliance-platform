#!/usr/bin/env python3
"""Generate docs/architecture-overview.png (preview). Editable source: architecture-overview.drawio"""

from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch

OUT = Path(__file__).resolve().parent / "architecture-overview.png"

fig, ax = plt.subplots(figsize=(22, 13.5), dpi=220)
ax.set_xlim(0, 100)
ax.set_ylim(0, 64)
ax.axis("off")
fig.patch.set_facecolor("#F5F7FA")
ax.set_facecolor("#F5F7FA")

boxes: dict[str, tuple[float, float, float, float]] = {}

BLUE, PURPLE, GREEN, RED = "#1565C0", "#6A1B9A", "#2E7D32", "#C62828"
PVC, ORANGE, MAAS, BROWN, GRAY = "#388E3C", "#E65100", "#5E35B1", "#6D4C41", "#455A64"


def rounded(x, y, w, h, fc, ec, lw=1.5, r=0.45, z=2):
    ax.add_patch(
        FancyBboxPatch(
            (x, y), w, h,
            boxstyle=f"round,pad=0.015,rounding_size={r}",
            facecolor=fc, edgecolor=ec, linewidth=lw, zorder=z,
        )
    )


def plane(x, y, w, h, title, fc, ec):
    rounded(x, y, w, h, fc, ec, lw=2.0, r=0.7, z=1)
    ax.text(x + 1.0, y + h - 1.1, title, fontsize=12, fontweight="bold",
            color="#37474F", ha="left", va="top", zorder=3)


def box(name, x, y, w, h, title, lines, fc, ec, title_size=12, body_size=9.6):
    boxes[name] = (x, y, w, h)
    rounded(x, y, w, h, fc, ec, lw=1.45, r=0.4, z=3)
    if lines:
        ax.text(x + w / 2, y + h - 1.25, title, fontsize=title_size, fontweight="bold",
                color="#0D1B2A", ha="center", va="top", zorder=4)
        ax.text(x + w / 2, y + h * 0.40, "\n".join(lines), fontsize=body_size,
                color="#37474F", ha="center", va="center", zorder=4, linespacing=1.42)
    else:
        ax.text(x + w / 2, y + h / 2, title, fontsize=title_size, fontweight="bold",
                color="#0D1B2A", ha="center", va="center", zorder=4)


def pt(name, side, t=0.5):
    x, y, w, h = boxes[name]
    t = max(0.15, min(0.85, t))
    if side == "L":
        return (x, y + h * (1 - t))
    if side == "R":
        return (x + w, y + h * (1 - t))
    if side == "T":
        return (x + w * t, y + h)
    if side == "B":
        return (x + w * t, y)
    raise ValueError(side)


def label_at(x, y, text, color, size=9.5):
    ax.text(
        x, y, text, fontsize=size, color=color, ha="center", va="center", zorder=8,
        fontweight="bold",
        bbox=dict(boxstyle="round,pad=0.24", fc="white", ec="#90A4AE", lw=0.7, alpha=0.97),
    )


def arrow(points, color="#37474F", style="-", lw=1.85):
    clean = [points[0]]
    for p in points[1:]:
        if abs(p[0] - clean[-1][0]) > 0.01 or abs(p[1] - clean[-1][1]) > 0.01:
            clean.append(p)
    ortho = [clean[0]]
    for p in clean[1:]:
        prev = ortho[-1]
        if abs(p[0] - prev[0]) > 0.01 and abs(p[1] - prev[1]) > 0.01:
            ortho.append((p[0], prev[1]))
        ortho.append(p)
    if len(ortho) >= 3:
        ax.plot(
            [p[0] for p in ortho[:-1]], [p[1] for p in ortho[:-1]],
            color=color, lw=lw, ls=style, solid_capstyle="round",
            solid_joinstyle="miter", zorder=5,
        )
    ax.add_patch(
        FancyArrowPatch(
            ortho[-2], ortho[-1], arrowstyle="-|>", mutation_scale=17,
            lw=lw, color=color, linestyle=style, zorder=6, shrinkA=0, shrinkB=0,
        )
    )


ax.text(50, 62.2, "ISO Compliance AI Platform — Architecture (OpenShift Flavor)",
        fontsize=17, fontweight="bold", color="#0D47A1", ha="center", va="center")
ax.text(50, 60.5,
        "GPT-oss-20b · BGE-M3 embeddings · PostgreSQL 16 + pgvector · MaaS / TrustyAI · 4-layer GitOps",
        fontsize=10.5, color="#546E7A", ha="center", va="center")

# ===== APPLICATION =====
plane(1.0, 40.5, 98.0, 18.0, "Application Plane  ·  Namespace: iso-platform", "#E3F2FD", "#64B5F6")

box("users", 3.0, 48.5, 13.0, 7.5, "Users",
    ["Admin / Auditor / Viewer", "Google OAuth + JWT"],
    "#E1F5FE", "#039BE5")
box("web", 20.0, 48.5, 18.0, 7.5, "iso-web",
    ["React SPA · EN/HE · RTL", "viewer · projects · admin"],
    "#BBDEFB", "#1E88E5")
box("api", 46.0, 43.0, 20.0, 13.0, "iso-api-orchestrator",
    ["FastAPI workflow hub", "projects · findings · mapping",
     "corpus · bilingual ISO", "RAG retrieve / persist"],
    "#64B5F6", "#1565C0", 12.5, 9.6)
box("parse", 71.0, 50.0, 26.0, 6.5, "iso-doc-parse-rag agent",
    ["/parse · clause extract · EN/HE", "→ GPT-oss-20b (parse/extract/translate)"],
    "#E1BEE7", "#8E24AA")
box("gen", 71.0, 42.5, 26.0, 6.0, "iso-doc-gen agent",
    ["/generate · Hebrew RTL exports", "XLSX / DOCX / PDF → GPT-oss-20b"],
    "#CE93D8", "#8E24AA")

arrow([pt("users", "R"), pt("web", "L")], BLUE)
label_at(17.5, 53.5, "browser", BLUE)

arrow([pt("web", "R"), pt("api", "L", 0.35)], BLUE)
label_at(40.5, 53.5, "api", BLUE)

arrow([pt("api", "R", 0.25), pt("parse", "L", 0.5)], PURPLE)
label_at(66.5, 55.0, "parse pipeline", PURPLE)

arrow([pt("api", "R", 0.75), pt("gen", "L", 0.5)], PURPLE)
label_at(66.5, 45.0, "generate request", PURPLE)

BUS, DBUS = 38.5, 37.5

# ===== AI =====
plane(1.0, 19.0, 58.0, 17.0, "AI / MaaS Plane  ·  Namespace: llm (+ maas-api)", "#EDE7F6", "#9575CD")

box("maas", 3.0, 24.0, 16.0, 9.5, "MaaS Gateway",
    ["Kuadrant + Authorino", "JWT · RBAC · quotas",
     "OpenAI-compatible /v1", "+ GPT-4o family"],
    "#B39DDB", "#5E35B1")
box("gpt", 26.0, 29.5, 30.5, 4.5, "GPT-oss-20b",
    ["LLMInferenceService · vLLM · L40 · 21B MoE · 128K"],
    "#D1C4E9", "#6A1B9A")
box("bge", 26.0, 24.0, 30.5, 4.5, "BGE-M3",
    ["LLMInferenceService · vLLM · CPU · 568M · 1024-dim EN/HE"],
    "#D1C4E9", "#6A1B9A")
box("trust", 26.0, 20.5, 14.5, 2.8, "TrustyAI",
    ["logging · drift · fairness"],
    "#D7CCC8", "#6D4C41", 11, 9)
box("guard", 42.0, 20.5, 14.5, 2.8, "GuardrailsOrchestrator",
    ["HAP / topic policy"],
    "#D7CCC8", "#6D4C41", 10.5, 9)

# Agents → MaaS
pr, mr = pt("parse", "B", 0.35), pt("maas", "T", 0.45)
arrow([pr, (pr[0], BUS), (mr[0], BUS), mr], MAAS)
label_at(30.0, BUS + 1.0, "PARSE / EXTRACT / TRANSLATE", MAAS, 9.2)

gl, mr2 = pt("gen", "L", 0.55), pt("maas", "R", 0.85)
arrow([gl, (68.5, gl[1]), (68.5, BUS - 0.8), (mr2[0] + 1.5, BUS - 0.8),
       (mr2[0] + 1.5, mr2[1]), mr2], MAAS)
label_at(55.0, BUS - 1.7, "GENERATE", MAAS)

# Independent MaaS → model arrows (stacked; no links between models)
arrow([pt("maas", "R", 0.22), pt("gpt", "L", 0.5)], MAAS)
label_at(22.0, 32.2, "authorized", MAAS, 9.2)
arrow([pt("maas", "R", 0.65), pt("bge", "L", 0.5)], MAAS)
label_at(22.0, 26.7, "embeddings", MAAS, 9.2)

arrow([pt("bge", "B", 0.3), pt("trust", "T", 0.5)], BROWN, lw=1.5)
label_at(30.5, 23.5, "policy", BROWN, 8.8)

# ===== DATA =====
plane(61.0, 19.0, 38.0, 17.0, "Data Plane", "#E8F5E9", "#66BB6A")

box("pg", 63.0, 27.0, 34.0, 7.0, "iso-postgres (PG 16 + pgvector)",
    ["iso_clause_text · rag_documents (vector 1024)",
     "projects · findings · mappings · IVFFlat"],
    "#A5D6A7", "#2E7D32")
box("redis", 63.0, 21.0, 15.5, 4.5, "iso-redis",
    ["cache / session"], "#FFCDD2", "#C62828")
box("pvc", 81.0, 21.0, 16.0, 4.5, "iso-rag-data PVC",
    ["seed + artifacts"], "#C8E6C9", "#388E3C")

ab, pgt = pt("api", "B", 0.65), pt("pg", "T", 0.4)
arrow([ab, (ab[0], DBUS), (pgt[0], DBUS), pgt], GREEN)
label_at(70.0, DBUS + 1.0, "persist clauses + RAG", GREEN)

ab2, rl = pt("api", "B", 0.25), pt("redis", "L", 0.5)
arrow([ab2, (ab2[0], DBUS), (60.0, DBUS), (60.0, rl[1]), rl], RED)
label_at(60.0, 30.0, "cache / session", RED, 9.0)

gb, pvt = pt("gen", "B", 0.7), pt("pvc", "T", 0.55)
arrow([gb, (gb[0], DBUS), (pvt[0], DBUS), pvt], PVC)
label_at(90.5, DBUS + 1.0, "seed / artifacts", PVC, 9.0)

# ===== OBS =====
plane(1.0, 7.5, 58.0, 9.5, "Observability & Policy Plane", "#FFF3E0", "#FFA726")

box("prom", 3.0, 9.2, 25.5, 5.5, "Prometheus",
    ["ServiceMonitors: GPT-oss-20b · BGE-M3", "+ MaaS / application scrapes"],
    "#FFE0B2", "#EF6C00")
box("graf", 31.5, 9.2, 25.5, 5.5, "Grafana",
    ["LLM Observability dashboard", "req/s · P95/P99 · GPU · health"],
    "#FFCC80", "#EF6C00")

mb, pmt = pt("maas", "B", 0.4), pt("prom", "T", 0.3)
arrow([mb, (mb[0], pmt[1] + 1.2), (pmt[0], pmt[1] + 1.2), pmt], ORANGE, style="--", lw=1.65)
label_at(8.5, 17.8, "metrics", ORANGE, 9.0)

tb, gft = pt("trust", "B", 0.5), pt("graf", "T", 0.35)
# trust is short — signals from guard area instead if needed; keep from trust
arrow([tb, (tb[0], gft[1] + 1.2), (gft[0], gft[1] + 1.2), gft], ORANGE, style="--", lw=1.65)
label_at(22.0, 17.8, "signals", ORANGE, 9.0)

arrow([pt("prom", "R"), pt("graf", "L")], "#EF6C00")
label_at(29.5, 12.0, "dashboards", "#EF6C00", 9.0)

# ===== DELIVERY =====
plane(61.0, 1.0, 38.0, 16.0, "Delivery / Control Plane", "#ECEFF1", "#90A4AE")

box("gh", 63.0, 12.0, 15.5, 3.8, "GitHub",
    ["manifests source of truth"], "#CFD8DC", "#546E7A")
box("argo", 81.0, 12.0, 16.0, 3.8, "ArgoCD",
    ["4 layers + llm-ai app"], "#B0BEC5", "#455A64")
box("layers", 63.0, 7.0, 34.0, 4.0, "GitOps layers",
    ["01 platform → 02 app-infra (+pgvector)", "→ 03 apps → 04 RAG populate (BGE-M3)"],
    "#CFD8DC", "#546E7A", 11, 9.2)
box("ci", 63.0, 2.2, 15.5, 3.8, "External CI",
    ["build / push images"], "#B0BEC5", "#455A64")
box("ocp", 81.0, 2.2, 16.0, 3.8, "OpenShift",
    ["iso-platform + llm"], "#90A4AE", "#37474F")

arrow([pt("gh", "R"), pt("argo", "L")], GRAY)
label_at(79.0, 14.8, "manifests", GRAY, 9.0)

arb, oct_ = pt("argo", "R", 0.5), pt("ocp", "R", 0.5)
arrow([arb, (98.2, arb[1]), (98.2, oct_[1]), oct_], GRAY)
label_at(96.5, 8.5, "deploy", GRAY, 9.0)

arrow([pt("ci", "R"), pt("ocp", "L")], GRAY)
label_at(79.0, 4.1, "images", GRAY, 9.0)

ax.text(1.5, 6.0, "Notes", fontsize=11.5, fontweight="bold", color="#37474F")
ax.text(
    1.5, 4.5,
    "• All app LLM traffic uses OpenAI-compatible /v1 via MaaS (no provider SDKs).\n"
    "• Default models: PARSE/EXTRACT/TRANSLATE/GENERATE → GPT-oss-20b; embeddings → BGE-M3.\n"
    "• rag_documents stores BGE-M3 vector(1024); IVFFlat cosine for semantic EN/HE search.\n"
    "• Dual flavor: OpenShift + RHOAI (shown) and Kubernetes + LiteLLM / Ollama.\n"
    "• Editable source: docs/architecture-overview.drawio (diagrams.net)",
    fontsize=9.4, color="#37474F", va="top", ha="left", linespacing=1.4,
)

ax.text(50, 0.35,
        "Updated 2026-07 — GPT-oss-20b, BGE-M3 + pgvector, TrustyAI/Guardrails, Grafana LLM Observability, 4-layer GitOps.",
        fontsize=8.5, color="#78909C", ha="center", va="center", style="italic")

fig.tight_layout(pad=0.2)
fig.savefig(OUT, dpi=220, bbox_inches="tight", facecolor=fig.get_facecolor())
plt.close(fig)
print(f"Wrote {OUT} ({OUT.stat().st_size:,} bytes)")
