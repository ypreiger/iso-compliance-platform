#!/usr/bin/env python3
"""Add business case slide to enterprise presentation"""
from pptx import Presentation
from pptx.util import Inches, Pt
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
from pptx.enum.shapes import MSO_SHAPE
from pptx.dml.color import RGBColor

RH_RED = RGBColor(238, 0, 0)
RH_DARK = RGBColor(0, 0, 0)
RH_GRAY = RGBColor(92, 92, 92)
RH_BLUE = RGBColor(0, 102, 204)
RH_GREEN = RGBColor(146, 208, 80)
RH_ORANGE = RGBColor(255, 192, 0)
RH_PURPLE = RGBColor(112, 48, 160)

def add_slide_header(slide, title, prs):
    bar = slide.shapes.add_shape(
        MSO_SHAPE.RECTANGLE,
        0, 0, prs.slide_width, Inches(0.4)
    )
    bar.fill.solid()
    bar.fill.fore_color.rgb = RH_RED
    bar.line.fill.background()

    title_box = slide.shapes.add_textbox(Inches(0.5), Inches(0.05), Inches(12), Inches(0.3))
    tf = title_box.text_frame
    tf.text = title
    p = tf.paragraphs[0]
    p.font.size = Pt(28)
    p.font.bold = True
    p.font.color.rgb = RGBColor(255, 255, 255)

def add_business_case_slide(prs):
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    add_slide_header(slide, "AI-Powered ISO Compliance Management", prs)

    # Main workflow diagram
    steps = [
        {
            "num": "1",
            "title": "Upload ISO Standards",
            "desc": "Upload ISO standard documents\n(ISO 9001, 14001, 45001, 13485)",
            "color": RH_BLUE,
            "x": Inches(1.5),
            "y": Inches(2)
        },
        {
            "num": "2",
            "title": "Populate RAG",
            "desc": "AI extracts clauses\nGenerates semantic embeddings\nBuilds knowledge base",
            "color": RH_PURPLE,
            "x": Inches(5.5),
            "y": Inches(2)
        },
        {
            "num": "3",
            "title": "Assessment Findings",
            "desc": "Document audit findings\nduring organization assessment",
            "color": RH_ORANGE,
            "x": Inches(9.5),
            "y": Inches(2)
        }
    ]

    # Draw workflow boxes
    for i, step in enumerate(steps):
        # Circle number
        circle = slide.shapes.add_shape(
            MSO_SHAPE.OVAL,
            step["x"], step["y"], Inches(0.6), Inches(0.6)
        )
        circle.fill.solid()
        circle.fill.fore_color.rgb = step["color"]
        circle.line.color.rgb = step["color"]

        num_box = slide.shapes.add_textbox(step["x"], step["y"], Inches(0.6), Inches(0.6))
        tf = num_box.text_frame
        tf.text = step["num"]
        tf.vertical_anchor = MSO_ANCHOR.MIDDLE
        p = tf.paragraphs[0]
        p.font.size = Pt(24)
        p.font.bold = True
        p.font.color.rgb = RGBColor(255, 255, 255)
        p.alignment = PP_ALIGN.CENTER

        # Title
        title_box = slide.shapes.add_textbox(
            step["x"] - Inches(0.3), step["y"] + Inches(0.7),
            Inches(3.2), Inches(0.4)
        )
        tf = title_box.text_frame
        tf.text = step["title"]
        p = tf.paragraphs[0]
        p.font.size = Pt(18)
        p.font.bold = True
        p.font.color.rgb = RH_DARK
        p.alignment = PP_ALIGN.CENTER

        # Description
        desc_box = slide.shapes.add_textbox(
            step["x"] - Inches(0.5), step["y"] + Inches(1.2),
            Inches(3.6), Inches(1.2)
        )
        tf = desc_box.text_frame
        tf.text = step["desc"]
        tf.word_wrap = True
        p = tf.paragraphs[0]
        p.font.size = Pt(14)
        p.font.color.rgb = RH_GRAY
        p.alignment = PP_ALIGN.CENTER

        # Arrow to next step
        if i < len(steps) - 1:
            arrow = slide.shapes.add_connector(
                1,  # MSO_CONNECTOR.STRAIGHT
                steps[i]["x"] + Inches(3.5), steps[i]["y"] + Inches(0.3),
                steps[i + 1]["x"] - Inches(0.2), steps[i + 1]["y"] + Inches(0.3)
            )
            arrow.line.color.rgb = RH_GRAY
            arrow.line.width = Pt(3)

    # Output box
    output_y = Inches(4.5)
    output_box = slide.shapes.add_shape(
        MSO_SHAPE.ROUNDED_RECTANGLE,
        Inches(3), output_y, Inches(7.5), Inches(1.8)
    )
    output_box.fill.solid()
    output_box.fill.fore_color.rgb = RH_GREEN
    output_box.line.color.rgb = RH_GREEN

    # Arrow down to output
    down_arrow = slide.shapes.add_connector(
        1,
        Inches(6.66), Inches(3.5),
        Inches(6.66), output_y
    )
    down_arrow.line.color.rgb = RH_GRAY
    down_arrow.line.width = Pt(3)

    # Output title
    output_title = slide.shapes.add_textbox(
        Inches(3.2), output_y + Inches(0.2), Inches(7), Inches(0.4)
    )
    tf = output_title.text_frame
    tf.text = "✓  AI-Generated Compliance Report"
    p = tf.paragraphs[0]
    p.font.size = Pt(24)
    p.font.bold = True
    p.font.color.rgb = RGBColor(255, 255, 255)
    p.alignment = PP_ALIGN.CENTER

    # Output details
    output_detail = slide.shapes.add_textbox(
        Inches(3.5), output_y + Inches(0.7), Inches(6.5), Inches(0.9)
    )
    tf = output_detail.text_frame
    tf.text = "Automatic finding-to-clause mapping · Gap analysis · Corrective actions\nHebrew/English bilingual · Export to DOCX/Excel"
    tf.word_wrap = True
    p = tf.paragraphs[0]
    p.font.size = Pt(14)
    p.font.color.rgb = RGBColor(255, 255, 255)
    p.alignment = PP_ALIGN.CENTER

# Load existing presentation
prs = Presentation("/Users/ypreiger/Downloads/sources/iso-compliance-platform/docs/ppts/Enterprise_AI_Platform_RHOAI.pptx")

# Insert business case as slide 2 (after title)
slide = prs.slides.add_slide(prs.slide_layouts[6])
slides = list(prs.slides)

# Move new slide to position 1 (index 1, after title slide 0)
if len(slides) > 1:
    # Python-pptx doesn't support reordering, so we'll add it at the end
    # and document that it should be slide 2
    pass

add_business_case_slide(prs)

# Save
output_file = "/Users/ypreiger/Downloads/sources/iso-compliance-platform/docs/ppts/Enterprise_AI_Platform_RHOAI_Final.pptx"
prs.save(output_file)
print(f"✅ Business case slide added!")
print(f"   File: {output_file}")
print(f"   Total slides: {len(prs.slides)}")
print(f"   Note: New business case slide is at the end - manually move to position 2 in PowerPoint")
