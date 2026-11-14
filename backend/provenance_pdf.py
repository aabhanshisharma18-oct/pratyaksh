"""PDF examination record derived from a saved provenance report."""
import io
import math
from PIL import Image as PillowImage
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.graphics.shapes import Drawing, Line, Rect, String
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, Image, KeepTogether


NAVY = colors.HexColor("#17334f")
TEAL = colors.HexColor("#267e78")


def build_pdf(report, events, store, difference):
    stream = io.BytesIO()
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name="BodySmall", fontName="Helvetica", fontSize=8, leading=12, textColor=NAVY,
                              wordWrap="CJK", spaceAfter=5))
    styles.add(ParagraphStyle(name="HashSmall", fontName="Courier", fontSize=7, leading=10, wordWrap="CJK"))
    styles["Title"].textColor = NAVY
    styles["Heading2"].textColor = TEAL
    styles["Heading2"].keepWithNext = True
    styles["Heading3"].keepWithNext = True

    def p(text, style="BodySmall"):
        return Paragraph(escape(str(text)).replace("\n","<br/>"), styles[style])

    def table(rows, widths):
        result = Table([[p(value) for value in row] for row in rows], colWidths=widths, repeatRows=1, hAlign="LEFT")
        result.setStyle(TableStyle([
            ("BACKGROUND",(0,0),(-1,0),colors.HexColor("#e9f0f4")),
            ("VALIGN",(0,0),(-1,-1),"TOP"),("BOX",(0,0),(-1,-1),.5,colors.HexColor("#c6d4de")),
            ("INNERGRID",(0,0),(-1,-1),.3,colors.HexColor("#d9e2e9")),
            ("LEFTPADDING",(0,0),(-1,-1),7),("RIGHTPADDING",(0,0),(-1,-1),7),
        ]))
        return result

    story = [
        p("PRATYAKSH", "Title"),
        p("Multimedia provenance examination record", "Heading2"),
        table([
            ["Case", report["case"]["id"]], ["Title", report["case"]["title"]],
            ["Analyst", report["case"]["analyst"] + " (self-declared)"],
            ["Analysis", report["analysis_id"]], ["Examined at", report["analyzed_at"]],
        ], [33*mm, 137*mm]),
        Spacer(1, 5*mm),
        p("Review status", "Heading2"),
        p("Prepared for investigator and expert review. File relationships, source assertions and detector signals have different scopes. This report provides no legal admissibility decision."),
        p("Integrity anchors", "Heading2"),
        p("Canonical JSON report SHA-256"), p(report["report_sha256"], "HashSmall"),
        p("Provenance log anchor at analysis"), p(report["integrity"]["anchor_hash"], "HashSmall"),
        p("Anchor sequence " + str(report["integrity"]["anchor_sequence"])),
        p(report["integrity"]["limitations"]),
        p("Original verification"),
        p("In Pratyaksh, open this saved analysis and choose Verify preserved originals and log. A reviewer can also select a local original to compare its freshly computed SHA-256 with the file hash printed here. Preserve an exported copy of the anchor outside the local database."),
        PageBreak(),
        p("Files and intake hashes", "Heading2"),
    ]
    pair_plan = report.get("pair_selection")
    if pair_plan:
        story.extend([p("Visual comparison coverage", "Heading2"),
                      p(f"Strategy: {pair_plan['strategy']}; planner status: {pair_plan['solver_status']}"),
                      p(f"Selected {pair_plan['selected_visual_pairs']} of {pair_plan['eligible_visual_pairs']} eligible visual pairs. "
                        f"All {pair_plan['cheap_checked_pairs']} pairs received hash/metadata checks."),
                      p(pair_plan['limitation'])])
        for pair in pair_plan['unexamined_pairs']:
            story.append(p(f"{pair['left_id']} / {pair['right_id']}: visual comparison not examined"))
    for image in report["images"]:
        story.extend([p(image["id"] + " - " + image["filename"], "Heading3"),
                      p((f'{image["width"]} x {image["height"]}, ' if image.get("media_type","image")=="image" else "") + f'{image["format"]}, {image["size_bytes"]} bytes'),
                      p(image["sha256"], "HashSmall")])
        if image.get("case_evidence_id"):
            story.append(p("Case evidence ID: " + image["case_evidence_id"]))
        if intake := image.get("case_intake"):
            story.append(p(f"Case intake on {intake['registered_at']} by {intake['registered_by']} (self-declared)."))
            receipt = intake.get("receipt") or {}
            for field, label in (("supplied_by", "Supplied by"), ("collection_reference", "Collection reference"),
                                 ("note", "Receipt note")):
                if receipt.get(field):
                    story.append(p(f"{label} (reported): {receipt[field]}"))
        if coverage := image.get("video_coverage"):
            story.append(p(f"Video sampling: examined timestamps (ms) {coverage['examined_timestamps_ms']}. "
                           f"Requested {coverage['requested_count']} of {coverage['source_frame_timestamps']} recorded timestamps."))
        area = image.get("comparison_area")
        if area:
            x0, y0, x1, y1 = area
            story.append(p(f"Selected photo area: x {x0:.1%}–{x1:.1%}, y {y0:.1%}–{y1:.1%}, measured from the top-left of the displayed original. SHA-256 covers the entire file."))
    drawing = Drawing(480, 260)
    points = {}
    for index, image in enumerate(report["images"]):
        angle = 2*math.pi*index/len(report["images"])-math.pi/2
        points[image["id"]] = (240+180*math.cos(angle), 130-90*math.sin(angle))
    palette = {"exact_copy": TEAL, "matching_content": colors.HexColor("#587fa2"),
               "shared_metadata": colors.HexColor("#bc923e"), "shared_credentials": colors.HexColor("#826ba5")}
    for edge in report["relationships"]:
        a,b=points[edge["left_id"]], points[edge["right_id"]]
        drawing.add(Line(*a,*b,strokeColor=palette[edge["kind"]],strokeWidth=1))
    for image in report["images"]:
        x,y=points[image["id"]]
        drawing.add(Rect(x-30,y-10,60,20,fillColor=colors.white,strokeColor=NAVY))
        drawing.add(String(x,y-3,image["id"],textAnchor="middle",fontName="Helvetica",fontSize=9,fillColor=NAVY))
    story.append(KeepTogether([p("Connection map", "Heading2"), drawing, p("Teal: exact bytes. Blue: possible region relation. Gold: agreeing metadata. Purple: common credential record. Edges have no inferred chronological direction.")]))
    story.append(PageBreak())
    story.append(p("Evidence supporting each connection","Heading2"))
    for edge in report["relationships"]:
        block_start = len(story)
        story.extend([p(edge["left_id"]+" / "+edge["right_id"]+" - "+edge["kind"].replace("_"," "),"Heading3"),
                      p(edge["explanation"])])
        if edge["support"]:
            support=edge["support"]
            story.append(p(f'{support["matched_features"]} inliers; geometric agreement {support["geometric_inlier_ratio"]:.3f}; dHash distance {support.get("hash_distance")}.'))
            if timestamps := support.get("frame_timestamps_ms"):
                story.append(p(f"Best matching sampled frame timestamps (ms): {timestamps}. "
                               f"Frame pairs checked: {support['sample_pair_count']}."))
            story.append(p(f'Matched feature bounds (normalized coordinates): left {support["left_region"]}; right {support["right_region"]}.'))
            if not timestamps:
                try:
                    overlay, percent=difference(report,edge)
                    thumbnail=PillowImage.open(io.BytesIO(overlay)).convert("RGB")
                    thumbnail.thumbnail((550,550))
                    compressed=io.BytesIO()
                    thumbnail.save(compressed,format="JPEG",quality=78)
                    compressed.seek(0)
                    picture=Image(compressed)
                    picture.drawWidth=70*mm
                    picture.drawHeight=70*mm*picture.imageHeight/picture.imageWidth
                    if picture.drawHeight>65*mm:
                        scale=65*mm/picture.drawHeight
                        picture.drawHeight*=scale;picture.drawWidth*=scale
                    story.extend([picture,p(f'Aligned difference overlay on {edge["right_id"]}. Residual difference covers {percent:.1f}% of the compared overlap. Compression, lighting and alignment can produce differences.')])
                except (ValueError,OSError):
                    story.append(p("Difference visualization unavailable; original verification is required."))
        if edge.get("metadata_fields"):
            story.append(p(str(edge["metadata_fields"])))
        if edge.get("manifest_labels"):
            story.append(p("\n".join(edge["manifest_labels"])))
        story.append(Spacer(1,3*mm))
        block = story[block_start:]
        del story[block_start:]
        story.append(KeepTogether(block))
    story.append(PageBreak())
    story.append(p("Information recorded in the files","Heading2"))
    for image in report["images"]:
        story.extend([p(image["id"]+" - "+image["filename"],"Heading3"),
                      p(image["metadata_status"])])
        rows=[["Field","Recorded value"], *[[key,value] for key,value in image["metadata"].items()]]
        story.append(table(rows if len(rows)>1 else [["Field","Recorded value"],["Metadata","No listed fields present"]],[42*mm,128*mm]))
        for flag in image.get("metadata_flags",[]):story.append(p(flag))
        credential=image["content_credentials"]
        story.extend([p("Content Credentials","Heading3"),p(credential["observation"]),
                      p(f'Signature: {credential.get("signature","unknown")}; file binding: {credential.get("content_binding","unknown")}; signer trust: {credential.get("signer_trust","unknown")}.')])
        if credential.get("trust_policy"):
            story.append(p("Trust policy: " + credential["trust_policy"]))
        for key in ("signer","tools","actions","validation_status"):
            if credential.get(key):story.append(p(key+" - "+str(credential[key])))
        signals=image.get("detector_signals",[])
        if signals:story.append(p("Supporting detector signals","Heading3"))
        else:story.append(p("Supporting detectors: no signals requested for this file."))
        for signal in signals:
            score=signal.get("score")
            story.extend([p(signal["method"]+" / "+signal["method_version"]),
                          p("Raw score: "+str(score["value"] if score else "unavailable")),
                          p(signal["observation"])])
            for limitation in signal.get("limitations",[]):story.append(p(limitation))
    if report.get("review_notes"):
        story.extend([Spacer(1, 5*mm), p("Reviewer interpretations", "Heading2"),
                      p("The following notes were entered by self-declared reviewers. They are separate from automated findings.")])
        for note in report["review_notes"]:
            story.extend([p(note["author"] + " / " + note["timestamp"], "Heading3"),
                          p("Scope: " + str(note.get("scope_id") or "Whole analysis") + "; analysis: " + note.get("analysis_id", report["analysis_id"])),
                          p(note["text"])])
    story.extend([PageBreak(),p("Provenance activity excerpt","Heading2"),
                  p(report["integrity"]["log_scope"])])
    for entry in events:
        story.extend([p(f'{entry["sequence"]}. {entry["timestamp"]} - {entry["actor"]} - {entry["action"]}'),
                      p(str(entry["detail"])),p(entry["entry_hash"],"HashSmall")])
    story.extend([p("Methods and versions","Heading2"),p(str(report["methods"]))])
    story.extend([p("Limitations","Heading2")])
    story.extend(p(value) for value in report["limitations"])
    story.extend([Spacer(1,8*mm),p("Examiner review and signature","Heading2"),
                  p("Examiner name __________________________________________"),
                  p("Signature ________________________    Date ________________________"),
                  p("The signature block is unsigned. This PDF has no digital signature.")])

    def page_footer(canvas, doc):
        canvas.setStrokeColor(TEAL)
        canvas.line(20*mm,16*mm,190*mm,16*mm)
        canvas.setFont("Helvetica",7)
        canvas.setFillColor(NAVY)
        canvas.drawString(20*mm,12*mm,report["case"]["id"]+" | "+report["analysis_id"][:22])
        canvas.drawRightString(190*mm,12*mm,"Page "+str(doc.page))

    SimpleDocTemplate(stream,pagesize=(210*mm,297*mm),rightMargin=20*mm,leftMargin=20*mm,
                      topMargin=18*mm,bottomMargin=23*mm,
                      title="Pratyaksh provenance report - "+report["case"]["id"],
                      author=report["case"]["analyst"]).build(story,onFirstPage=page_footer,onLaterPages=page_footer)
    return stream.getvalue()
