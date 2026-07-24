#!/usr/bin/env python3
"""
Create Enterprise-Grade AI Platform Presentation
Focus: Red Hat OpenShift AI architecture, not implementation details
"""
from pptx import Presentation
from pptx.util import Inches, Pt, Cm
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR, MSO_AUTO_SIZE
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE, MSO_CONNECTOR
from pptx.oxml.xmlchemy import OxmlElement

# Red Hat brand colors
RH_RED = RGBColor(238, 0, 0)
RH_DARK = RGBColor(0, 0, 0)
RH_GRAY = RGBColor(92, 92, 92)
RH_LIGHT_GRAY = RGBColor(204, 204, 204)
RH_BLUE = RGBColor(0, 102, 204)
RH_GREEN = RGBColor(146, 208, 80)
RH_ORANGE = RGBColor(255, 192, 0)
RH_PURPLE = RGBColor(112, 48, 160)

def create_presentation():
    prs = Presentation()
    # Widescreen 16:9 like Red Hat presentations
    prs.slide_width = Inches(13.33)
    prs.slide_height = Inches(7.5)

    # Slide 1: Title
    add_title_slide(prs)

    # Slide 2: Red Hat OpenShift AI Platform
    add_rhoai_platform_slide(prs)

    # Slide 3: RHOAI 3.5 Components Architecture
    add_rhoai_components_slide(prs)

    # Slide 4: Infrastructure Overview
    add_infrastructure_slide(prs)

    # Slide 5: Model as a Service (MaaS)
    add_maas_architecture_slide(prs)

    # Slide 6: Enterprise Security & Guardrails
    add_security_slide(prs)

    # Slide 7: Observability & Monitoring
    add_observability_slide(prs)

    # Slide 8: GitOps-Driven Deployment
    add_gitops_slide(prs)

    # Slide 9: AI Application Stack
    add_application_stack_slide(prs)

    # Slide 10: Business Value
    add_business_value_slide(prs)

    return prs

def add_title_slide(prs):
    slide = prs.slides.add_slide(prs.slide_layouts[6])  # Blank

    # Red Hat red bar at top
    shape = slide.shapes.add_shape(
        MSO_SHAPE.RECTANGLE,
        0, 0, prs.slide_width, Inches(0.5)
    )
    shape.fill.solid()
    shape.fill.fore_color.rgb = RH_RED
    shape.line.fill.background()

    # Title
    title_box = slide.shapes.add_textbox(Inches(1), Inches(2.5), Inches(11.33), Inches(1.2))
    tf = title_box.text_frame
    tf.text = "Enterprise-Grade AI Platform"
    p = tf.paragraphs[0]
    p.font.size = Pt(60)
    p.font.bold = True
    p.font.color.rgb = RH_DARK
    p.alignment = PP_ALIGN.CENTER

    # Subtitle
    subtitle_box = slide.shapes.add_textbox(Inches(1), Inches(3.8), Inches(11.33), Inches(0.8))
    tf = subtitle_box.text_frame
    tf.text = "Red Hat OpenShift AI 3.5"
    p = tf.paragraphs[0]
    p.font.size = Pt(36)
    p.font.color.rgb = RH_GRAY
    p.alignment = PP_ALIGN.CENTER

    # Tags
    tags_box = slide.shapes.add_textbox(Inches(1), Inches(5), Inches(11.33), Inches(1.5))
    tf = tags_box.text_frame
    tf.text = "Model as a Service  ·  TrustyAI Guardrails  ·  Vector RAG  ·  GitOps  ·  Enterprise Security"
    p = tf.paragraphs[0]
    p.font.size = Pt(20)
    p.font.color.rgb = RH_GRAY
    p.alignment = PP_ALIGN.CENTER

def add_rhoai_platform_slide(prs):
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    add_slide_header(slide, "Red Hat OpenShift AI Platform", prs)

    # Three pillars diagram
    pillar_width = Inches(3.5)
    pillar_height = Inches(4)
    y_pos = Inches(2.5)

    pillars = [
        {
            "x": Inches(1),
            "title": "Model Serving",
            "color": RH_BLUE,
            "items": ["KServe", "vLLM Runtime", "LLMInferenceService", "Auto-scaling"]
        },
        {
            "x": Inches(4.9),
            "title": "AI Governance",
            "color": RH_PURPLE,
            "items": ["TrustyAI", "Guardrails", "Bias Detection", "Audit Logs"]
        },
        {
            "x": Inches(8.8),
            "title": "Developer Tools",
            "color": RH_GREEN,
            "items": ["Jupyter", "Pipelines", "Model Registry", "GitOps"]
        }
    ]

    for pillar in pillars:
        # Pillar box
        box = slide.shapes.add_shape(
            MSO_SHAPE.ROUNDED_RECTANGLE,
            pillar["x"], y_pos, pillar_width, pillar_height
        )
        box.fill.solid()
        box.fill.fore_color.rgb = pillar["color"]
        box.line.color.rgb = pillar["color"]
        box.shadow.inherit = False

        # Title
        title_box = slide.shapes.add_textbox(
            pillar["x"], y_pos + Inches(0.3), pillar_width, Inches(0.6)
        )
        tf = title_box.text_frame
        tf.text = pillar["title"]
        p = tf.paragraphs[0]
        p.font.size = Pt(24)
        p.font.bold = True
        p.font.color.rgb = RGBColor(255, 255, 255)
        p.alignment = PP_ALIGN.CENTER

        # Items
        items_box = slide.shapes.add_textbox(
            pillar["x"] + Inches(0.3), y_pos + Inches(1.2),
            pillar_width - Inches(0.6), pillar_height - Inches(1.4)
        )
        tf = items_box.text_frame
        tf.word_wrap = True

        for i, item in enumerate(pillar["items"]):
            if i > 0:
                p = tf.add_paragraph()
            else:
                p = tf.paragraphs[0]
            p.text = f"• {item}"
            p.font.size = Pt(16)
            p.font.color.rgb = RGBColor(255, 255, 255)
            p.space_after = Pt(8)

def add_rhoai_components_slide(prs):
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    add_slide_header(slide, "RHOAI 3.5 Architecture", prs)

    # Layer diagram
    layers = [
        {"y": Inches(2), "h": Inches(0.8), "text": "Application Layer", "color": RH_BLUE,
         "detail": "iso-web  ·  iso-api  ·  AI Playground"},
        {"y": Inches(3), "h": Inches(1.2), "text": "Model as a Service", "color": RH_PURPLE,
         "detail": "GPT-oss-20b (21B MoE)  ·  BGE-M3 Embeddings  ·  Qwen3-4B"},
        {"y": Inches(4.5), "h": Inches(0.8), "text": "Inference & Serving", "color": RH_GREEN,
         "detail": "KServe  ·  vLLM  ·  LLMInferenceService CRDs"},
        {"y": Inches(5.5), "h": Inches(0.8), "text": "AI Governance", "color": RH_ORANGE,
         "detail": "TrustyAI  ·  Guardrails Orchestrator  ·  Kuadrant + Authorino"},
        {"y": Inches(6.5), "h": Inches(0.8), "text": "Platform", "color": RH_GRAY,
         "detail": "OpenShift 4.x  ·  Operators  ·  GPU Nodes (NVIDIA L40)"}
    ]

    for layer in layers:
        # Main box
        box = slide.shapes.add_shape(
            MSO_SHAPE.RECTANGLE,
            Inches(1.5), layer["y"], Inches(10), layer["h"]
        )
        box.fill.solid()
        box.fill.fore_color.rgb = layer["color"]
        box.line.color.rgb = layer["color"]

        # Title
        title_box = slide.shapes.add_textbox(
            Inches(1.7), layer["y"] + Inches(0.1), Inches(3), layer["h"] - Inches(0.2)
        )
        tf = title_box.text_frame
        tf.text = layer["text"]
        tf.vertical_anchor = MSO_ANCHOR.MIDDLE
        p = tf.paragraphs[0]
        p.font.size = Pt(20)
        p.font.bold = True
        p.font.color.rgb = RGBColor(255, 255, 255)

        # Detail
        detail_box = slide.shapes.add_textbox(
            Inches(5), layer["y"] + Inches(0.1), Inches(6), layer["h"] - Inches(0.2)
        )
        tf = detail_box.text_frame
        tf.text = layer["detail"]
        tf.vertical_anchor = MSO_ANCHOR.MIDDLE
        p = tf.paragraphs[0]
        p.font.size = Pt(14)
        p.font.color.rgb = RGBColor(255, 255, 255)

def add_infrastructure_slide(prs):
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    add_slide_header(slide, "Infrastructure & Resource Management", prs)

    # Left: OpenShift
    left_box = slide.shapes.add_shape(
        MSO_SHAPE.ROUNDED_RECTANGLE,
        Inches(1), Inches(2), Inches(5.5), Inches(4.5)
    )
    left_box.fill.solid()
    left_box.fill.fore_color.rgb = RGBColor(230, 240, 255)
    left_box.line.color.rgb = RH_BLUE
    left_box.line.width = Pt(2)

    title_box = slide.shapes.add_textbox(Inches(1.3), Inches(2.2), Inches(5), Inches(0.5))
    tf = title_box.text_frame
    tf.text = "OpenShift Container Platform"
    p = tf.paragraphs[0]
    p.font.size = Pt(22)
    p.font.bold = True
    p.font.color.rgb = RH_BLUE

    # OpenShift components
    components = [
        "Namespace Isolation (iso-platform, llm, grafana)",
        "RBAC & ServiceAccounts",
        "Routes (TLS edge termination)",
        "GPU Node Scheduling (L40 48GB VRAM)",
        "StatefulSets (PostgreSQL + pgvector)",
        "ConfigMaps & Secrets Management"
    ]

    comp_box = slide.shapes.add_textbox(Inches(1.5), Inches(3), Inches(5), Inches(3))
    tf = comp_box.text_frame
    tf.word_wrap = True

    for i, comp in enumerate(components):
        if i > 0:
            p = tf.add_paragraph()
        else:
            p = tf.paragraphs[0]
        p.text = f"✓ {comp}"
        p.font.size = Pt(14)
        p.font.color.rgb = RH_DARK
        p.space_after = Pt(6)

    # Right: RHOAI
    right_box = slide.shapes.add_shape(
        MSO_SHAPE.ROUNDED_RECTANGLE,
        Inches(7), Inches(2), Inches(5.5), Inches(4.5)
    )
    right_box.fill.solid()
    right_box.fill.fore_color.rgb = RGBColor(255, 240, 240)
    right_box.line.color.rgb = RH_RED
    right_box.line.width = Pt(2)

    title_box = slide.shapes.add_textbox(Inches(7.3), Inches(2.2), Inches(5), Inches(0.5))
    tf = title_box.text_frame
    tf.text = "Red Hat OpenShift AI Operator"
    p = tf.paragraphs[0]
    p.font.size = Pt(22)
    p.font.bold = True
    p.font.color.rgb = RH_RED

    # RHOAI components
    rhoai_components = [
        "Model Serving (KServe, vLLM)",
        "MaaS Gateway (Kuadrant API mgmt)",
        "TrustyAI Service (Observability)",
        "Ray Operator (Distributed ML)",
        "MLflow (Experiment Tracking)",
        "Data Science Pipelines (Tekton)"
    ]

    rhoai_box = slide.shapes.add_textbox(Inches(7.5), Inches(3), Inches(5), Inches(3))
    tf = rhoai_box.text_frame
    tf.word_wrap = True

    for i, comp in enumerate(rhoai_components):
        if i > 0:
            p = tf.add_paragraph()
        else:
            p = tf.paragraphs[0]
        p.text = f"✓ {comp}"
        p.font.size = Pt(14)
        p.font.color.rgb = RH_DARK
        p.space_after = Pt(6)

def add_maas_architecture_slide(prs):
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    add_slide_header(slide, "Model as a Service (MaaS) Gateway", prs)

    # Flow diagram (vertical)
    boxes = [
        {"y": Inches(2), "text": "Application\n(iso-api, playground)", "color": RH_BLUE},
        {"y": Inches(3.2), "text": "MaaS Gateway\n(Kuadrant + Authorino)", "color": RH_PURPLE},
        {"y": Inches(4.4), "text": "TrustyAI\n(Observability & Guardrails)", "color": RH_ORANGE},
        {"y": Inches(5.6), "text": "Model Inference\n(vLLM on GPU)", "color": RH_GREEN}
    ]

    box_width = Inches(4)
    box_height = Inches(0.8)
    x_center = Inches(4.5)

    for i, box_info in enumerate(boxes):
        # Box
        box = slide.shapes.add_shape(
            MSO_SHAPE.ROUNDED_RECTANGLE,
            x_center, box_info["y"], box_width, box_height
        )
        box.fill.solid()
        box.fill.fore_color.rgb = box_info["color"]
        box.line.color.rgb = box_info["color"]

        # Text
        text_box = slide.shapes.add_textbox(
            x_center, box_info["y"], box_width, box_height
        )
        tf = text_box.text_frame
        tf.text = box_info["text"]
        tf.vertical_anchor = MSO_ANCHOR.MIDDLE
        p = tf.paragraphs[0]
        p.font.size = Pt(18)
        p.font.bold = True
        p.font.color.rgb = RGBColor(255, 255, 255)
        p.alignment = PP_ALIGN.CENTER

        # Arrow to next box
        if i < len(boxes) - 1:
            arrow = slide.shapes.add_connector(
                MSO_CONNECTOR.STRAIGHT,
                x_center + box_width / 2, box_info["y"] + box_height,
                x_center + box_width / 2, boxes[i + 1]["y"]
            )
            arrow.line.color.rgb = RH_GRAY
            arrow.line.width = Pt(3)

    # Right side: Features
    features_box = slide.shapes.add_textbox(Inches(9), Inches(2), Inches(3.5), Inches(4.5))
    tf = features_box.text_frame
    tf.word_wrap = True

    p = tf.paragraphs[0]
    p.text = "MaaS Benefits"
    p.font.size = Pt(22)
    p.font.bold = True
    p.font.color.rgb = RH_RED
    p.space_after = Pt(12)

    features = [
        "OpenAI-compatible API",
        "Multi-tenancy & quotas",
        "JWT authentication",
        "Rate limiting per tier",
        "Request/response logging",
        "Bias detection",
        "Content guardrails"
    ]

    for feature in features:
        p = tf.add_paragraph()
        p.text = f"✓ {feature}"
        p.font.size = Pt(16)
        p.font.color.rgb = RH_DARK
        p.space_after = Pt(6)

def add_security_slide(prs):
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    add_slide_header(slide, "Enterprise Security & Compliance", prs)

    # Security layers (concentric boxes)
    layers = [
        {"size": 9, "text": "Network & Access\nGoogle OAuth · JWT · TLS Routes", "color": RGBColor(200, 220, 255)},
        {"size": 7, "text": "API Gateway\nKuadrant · Rate Limiting · RBAC", "color": RGBColor(150, 180, 255)},
        {"size": 5, "text": "Content Guardrails\nTrustyAI · HAP Detection", "color": RGBColor(100, 140, 255)},
        {"size": 3, "text": "Data Protection\nRow-level Security · Audit Logs", "color": RGBColor(50, 100, 200)}
    ]

    center_x = Inches(6.66)
    center_y = Inches(4.25)

    for layer in reversed(layers):
        size = Inches(layer["size"])
        box = slide.shapes.add_shape(
            MSO_SHAPE.OVAL,
            center_x - size / 2, center_y - size / 2,
            size, size
        )
        box.fill.solid()
        box.fill.fore_color.rgb = layer["color"]
        box.line.color.rgb = RH_BLUE
        box.line.width = Pt(2)

    # Center text
    text_box = slide.shapes.add_textbox(
        center_x - Inches(1.5), center_y - Inches(0.5),
        Inches(3), Inches(1)
    )
    tf = text_box.text_frame
    tf.text = layers[-1]["text"]
    tf.vertical_anchor = MSO_ANCHOR.MIDDLE
    p = tf.paragraphs[0]
    p.font.size = Pt(14)
    p.font.bold = True
    p.font.color.rgb = RGBColor(255, 255, 255)
    p.alignment = PP_ALIGN.CENTER

def add_observability_slide(prs):
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    add_slide_header(slide, "Observability & Monitoring", prs)

    # Three monitoring areas
    areas = [
        {
            "x": Inches(1), "title": "Prometheus Metrics",
            "items": ["vLLM request rate", "P95/P99 latency", "GPU utilization", "Cache hit rate", "Queue depth"]
        },
        {
            "x": Inches(5), "title": "Grafana Dashboards",
            "items": ["LLM Observability", "Model health status", "Request tracing", "Resource usage", "SLO tracking"]
        },
        {
            "x": Inches(9), "title": "TrustyAI Audit",
            "items": ["Request logging", "Bias detection", "Drift analysis", "Fairness metrics", "Compliance reports"]
        }
    ]

    for area in areas:
        # Box
        box = slide.shapes.add_shape(
            MSO_SHAPE.ROUNDED_RECTANGLE,
            area["x"], Inches(2.5), Inches(3.5), Inches(3.5)
        )
        box.fill.solid()
        box.fill.fore_color.rgb = RGBColor(240, 248, 255)
        box.line.color.rgb = RH_BLUE
        box.line.width = Pt(2)

        # Title
        title_box = slide.shapes.add_textbox(
            area["x"] + Inches(0.2), Inches(2.7), Inches(3.1), Inches(0.5)
        )
        tf = title_box.text_frame
        tf.text = area["title"]
        p = tf.paragraphs[0]
        p.font.size = Pt(20)
        p.font.bold = True
        p.font.color.rgb = RH_BLUE

        # Items
        items_box = slide.shapes.add_textbox(
            area["x"] + Inches(0.3), Inches(3.3), Inches(3), Inches(2.5)
        )
        tf = items_box.text_frame
        tf.word_wrap = True

        for i, item in enumerate(area["items"]):
            if i > 0:
                p = tf.add_paragraph()
            else:
                p = tf.paragraphs[0]
            p.text = f"• {item}"
            p.font.size = Pt(14)
            p.font.color.rgb = RH_DARK
            p.space_after = Pt(6)

def add_gitops_slide(prs):
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    add_slide_header(slide, "GitOps-Driven Deployment", prs)

    # 4 layers with sync waves
    layers = [
        {"wave": "0-10", "name": "Platform Infrastructure", "content": "Namespaces · RBAC · Operators", "color": RH_BLUE},
        {"wave": "10-20", "name": "Application Infrastructure", "content": "PostgreSQL · Redis · Secrets", "color": RH_PURPLE},
        {"wave": "20-30", "name": "Application Services", "content": "iso-api · iso-web · Playground", "color": RH_GREEN},
        {"wave": "40+", "name": "Data Population", "content": "RAG ingestion · Embeddings", "color": RH_ORANGE}
    ]

    y_start = Inches(2.5)
    layer_height = Inches(0.9)
    spacing = Inches(0.15)

    for i, layer in enumerate(layers):
        y_pos = y_start + i * (layer_height + spacing)

        # Wave number box
        wave_box = slide.shapes.add_shape(
            MSO_SHAPE.RECTANGLE,
            Inches(1), y_pos, Inches(1.5), layer_height
        )
        wave_box.fill.solid()
        wave_box.fill.fore_color.rgb = layer["color"]
        wave_box.line.color.rgb = layer["color"]

        wave_text = slide.shapes.add_textbox(Inches(1), y_pos, Inches(1.5), layer_height)
        tf = wave_text.text_frame
        tf.text = f"Wave\n{layer['wave']}"
        tf.vertical_anchor = MSO_ANCHOR.MIDDLE
        p = tf.paragraphs[0]
        p.font.size = Pt(16)
        p.font.bold = True
        p.font.color.rgb = RGBColor(255, 255, 255)
        p.alignment = PP_ALIGN.CENTER

        # Layer name
        name_box = slide.shapes.add_shape(
            MSO_SHAPE.RECTANGLE,
            Inches(2.7), y_pos, Inches(3.5), layer_height
        )
        name_box.fill.solid()
        name_box.fill.fore_color.rgb = RGBColor(245, 245, 245)
        name_box.line.color.rgb = RH_GRAY

        name_text = slide.shapes.add_textbox(Inches(2.9), y_pos, Inches(3.1), layer_height)
        tf = name_text.text_frame
        tf.text = layer["name"]
        tf.vertical_anchor = MSO_ANCHOR.MIDDLE
        p = tf.paragraphs[0]
        p.font.size = Pt(18)
        p.font.bold = True
        p.font.color.rgb = RH_DARK

        # Content
        content_text = slide.shapes.add_textbox(Inches(6.5), y_pos, Inches(5.5), layer_height)
        tf = content_text.text_frame
        tf.text = layer["content"]
        tf.vertical_anchor = MSO_ANCHOR.MIDDLE
        p = tf.paragraphs[0]
        p.font.size = Pt(14)
        p.font.color.rgb = RH_GRAY

    # ArgoCD logo/text
    argocd_box = slide.shapes.add_textbox(Inches(1), Inches(6.5), Inches(11), Inches(0.5))
    tf = argocd_box.text_frame
    tf.text = "OpenShift GitOps (ArgoCD) · Declarative · Auditable · Auto-sync · Rollback"
    p = tf.paragraphs[0]
    p.font.size = Pt(16)
    p.font.bold = True
    p.font.color.rgb = RH_BLUE
    p.alignment = PP_ALIGN.CENTER

def add_application_stack_slide(prs):
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    add_slide_header(slide, "AI Application Stack", prs)

    # Stack layers (bottom to top)
    stack = [
        {"text": "OpenShift + RHOAI 3.5", "color": RGBColor(100, 100, 100)},
        {"text": "PostgreSQL 16 + pgvector · Redis", "color": RGBColor(60, 120, 180)},
        {"text": "LLM Models (GPT-oss-20b · BGE-M3 · Qwen3)", "color": RGBColor(160, 80, 200)},
        {"text": "FastAPI Orchestrator · Document Services", "color": RGBColor(80, 160, 100)},
        {"text": "React SPA · AI Playground", "color": RGBColor(200, 80, 80)}
    ]

    layer_height = Inches(0.8)
    y_base = Inches(6)

    for i, layer in enumerate(reversed(stack)):
        y_pos = y_base - i * layer_height

        box = slide.shapes.add_shape(
            MSO_SHAPE.RECTANGLE,
            Inches(3), y_pos, Inches(7.5), layer_height
        )
        box.fill.solid()
        box.fill.fore_color.rgb = layer["color"]
        box.line.color.rgb = RH_GRAY

        text_box = slide.shapes.add_textbox(Inches(3), y_pos, Inches(7.5), layer_height)
        tf = text_box.text_frame
        tf.text = layer["text"]
        tf.vertical_anchor = MSO_ANCHOR.MIDDLE
        p = tf.paragraphs[0]
        p.font.size = Pt(18)
        p.font.bold = True
        p.font.color.rgb = RGBColor(255, 255, 255)
        p.alignment = PP_ALIGN.CENTER

def add_business_value_slide(prs):
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    add_slide_header(slide, "Enterprise Value Delivered", prs)

    # Value propositions in boxes
    values = [
        {
            "title": "Production-Ready AI",
            "items": ["Enterprise security", "High availability", "Auto-scaling", "Disaster recovery"]
        },
        {
            "title": "Operational Excellence",
            "items": ["Full observability", "GitOps automation", "Zero downtime updates", "Compliance ready"]
        },
        {
            "title": "Developer Productivity",
            "items": ["OpenAI-compatible API", "Multi-model support", "Self-service platform", "Fast iteration"]
        },
        {
            "title": "Cost Optimization",
            "items": ["GPU efficiency", "Resource pooling", "Usage tracking", "On-prem + cloud hybrid"]
        }
    ]

    positions = [
        {"x": Inches(1), "y": Inches(2.5)},
        {"x": Inches(7), "y": Inches(2.5)},
        {"x": Inches(1), "y": Inches(4.8)},
        {"x": Inches(7), "y": Inches(4.8)}
    ]

    for value, pos in zip(values, positions):
        box = slide.shapes.add_shape(
            MSO_SHAPE.ROUNDED_RECTANGLE,
            pos["x"], pos["y"], Inches(5.5), Inches(2)
        )
        box.fill.solid()
        box.fill.fore_color.rgb = RGBColor(240, 248, 255)
        box.line.color.rgb = RH_BLUE
        box.line.width = Pt(2)

        # Title
        title_box = slide.shapes.add_textbox(
            pos["x"] + Inches(0.3), pos["y"] + Inches(0.2),
            Inches(5), Inches(0.4)
        )
        tf = title_box.text_frame
        tf.text = value["title"]
        p = tf.paragraphs[0]
        p.font.size = Pt(20)
        p.font.bold = True
        p.font.color.rgb = RH_RED

        # Items
        items_box = slide.shapes.add_textbox(
            pos["x"] + Inches(0.4), pos["y"] + Inches(0.7),
            Inches(5), Inches(1.2)
        )
        tf = items_box.text_frame
        tf.word_wrap = True

        for i, item in enumerate(value["items"]):
            if i > 0:
                p = tf.add_paragraph()
            else:
                p = tf.paragraphs[0]
            p.text = f"✓ {item}"
            p.font.size = Pt(14)
            p.font.color.rgb = RH_DARK
            p.space_after = Pt(4)

def add_slide_header(slide, title, prs):
    # Red bar
    bar = slide.shapes.add_shape(
        MSO_SHAPE.RECTANGLE,
        0, 0, prs.slide_width, Inches(0.4)
    )
    bar.fill.solid()
    bar.fill.fore_color.rgb = RH_RED
    bar.line.fill.background()

    # Title
    title_box = slide.shapes.add_textbox(Inches(0.5), Inches(0.05), Inches(12), Inches(0.3))
    tf = title_box.text_frame
    tf.text = title
    p = tf.paragraphs[0]
    p.font.size = Pt(28)
    p.font.bold = True
    p.font.color.rgb = RGBColor(255, 255, 255)

if __name__ == "__main__":
    import os

    output_dir = "/Users/ypreiger/Downloads/sources/iso-compliance-platform/docs/ppts"
    os.makedirs(output_dir, exist_ok=True)

    prs = create_presentation()
    output_file = os.path.join(output_dir, "Enterprise_AI_Platform_RHOAI.pptx")
    prs.save(output_file)
    print(f"✅ Enterprise presentation created: {output_file}")
    print(f"   Widescreen 16:9 ({prs.slide_width/914400:.1f}\" x {prs.slide_height/914400:.1f}\")")
    print(f"   {len(prs.slides)} slides with visual diagrams")
