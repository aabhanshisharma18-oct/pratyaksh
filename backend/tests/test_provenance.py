import io
import sys
import os
import json
from tempfile import TemporaryDirectory
from unittest.mock import patch
import unittest
from pathlib import Path

try:
    import cv2
    import numpy as np
except ImportError:
    cv2 = np = None
from fastapi import FastAPI
from fastapi.testclient import TestClient
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from provenance import analyze_images, inspect_image, router
from provenance_store import ProvenanceStore


def png(image):
    stream = io.BytesIO()
    image.save(stream, format="PNG")
    return stream.getvalue()


def textured_image(seed=42):
    rng = np.random.default_rng(seed)
    pixels = np.full((500, 700, 3), 235, dtype=np.uint8)
    for _ in range(200):
        x, y = rng.integers(15, 485, size=2)
        color = tuple(int(v) for v in rng.integers(0, 200, size=3))
        cv2.circle(pixels, (int(x), int(y)), int(rng.integers(4, 15)), color, -1)
    return Image.fromarray(pixels)


class ProvenanceTests(unittest.TestCase):
    def setUp(self):
        self.directory = TemporaryDirectory()
        self.environment = patch.dict(os.environ, {"PRATYAKSH_PROVENANCE_DIR": self.directory.name})
        self.environment.start()

    def tearDown(self):
        self.environment.stop()
        self.directory.cleanup()

    def test_upload_preview_decodes_heic_without_intake(self):
        try:
            import pillow_heif
        except ImportError:
            self.skipTest("HEIC decoder unavailable")
        image = Image.new("RGB", (120, 80), "navy")
        exif = image.getexif()
        exif[274] = 6
        source = io.BytesIO()
        pillow_heif.from_pillow(image).save(source)
        app = FastAPI()
        app.include_router(router)
        with TestClient(app) as client:
            response = client.post("/api/d1/provenance/preview", files={
                "file": ("photo.HEIC", source.getvalue(), "image/heic"),
            })
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.headers["cache-control"], "no-store")
            with Image.open(io.BytesIO(response.content)) as preview:
                self.assertEqual((preview.format, preview.size), ("JPEG", (120, 80)))
            rotated = io.BytesIO()
            image.save(rotated, format="JPEG", exif=exif)
            response = client.post("/api/d1/provenance/preview", files={
                "file": ("rotated.jpg", rotated.getvalue(), "image/jpeg"),
            })
            self.assertEqual(response.status_code, 200)
            with Image.open(io.BytesIO(response.content)) as preview:
                self.assertEqual(preview.size, (80, 120))
            invalid = client.post("/api/d1/provenance/preview", files={
                "file": ("broken.heic", b"invalid", "image/heic"),
            })
            self.assertEqual(invalid.status_code, 400)
        self.assertEqual(list(Path(self.directory.name).iterdir()), [])

    def test_case_original_feeds_run_and_provenance_by_id(self):
        from cases.repository import CaseRepository
        from cases.router import create_cases_router
        from runs.repository import RunRepository
        from runs.router import create_runs_router

        database = Path(self.directory.name) / "cases.db"
        cases = CaseRepository(database)
        case_id = cases.create_case("Single intake", "", "Reviewer")["id"]
        other_id = cases.create_case("Other case", "", "Reviewer")["id"]
        runs = RunRepository(database)
        app = FastAPI()
        app.include_router(create_cases_router(cases), prefix="/api")
        app.include_router(create_runs_router(runs, type("Scheduler", (), {"enqueue": lambda *_: None})(),
                                              Path(self.directory.name)), prefix="/api")
        app.include_router(router)
        data = png(Image.new("RGB", (80, 80), "navy"))
        with patch("cases.router.get_case_repository", return_value=cases), TestClient(app) as client:
            base = f"/api/cases/{case_id}/originals"
            first = client.post(base, files={"file": ("original.png", data, "image/png")},
                                data={"supplied_by": "Evidence desk", "collection_reference": "REF-01"}).json()
            self.assertEqual(first["receipt"]["collection_reference"], "REF-01")
            second = client.post(base, files={"file": ("copy.png", data, "image/png")}).json()
            self.assertTrue(first["preserved"])
            self.assertEqual(first["hash_source"], "server_computed")
            self.assertEqual(client.get(f"{base}/{first['evidence_id']}").content, data)
            self.assertEqual(client.get(f"/api/cases/{other_id}/originals/{first['evidence_id']}").status_code, 404)
            run_response = client.post(f"/api/evidence/{first['evidence_id']}/runs", data={"case_id": case_id})
            self.assertEqual(run_response.status_code, 202, run_response.text)
            self.assertEqual(runs.input_path(run_response.json()["run_id"]).read_bytes(), data)
            response = client.post(f"/api/d1/provenance/cases/{case_id}/analyze", json={
                "evidence_ids": [first["evidence_id"], second["evidence_id"]],
            })
            self.assertEqual(response.status_code, 200, response.text)
            report = response.json()
            self.assertEqual(report["images"][0]["case_evidence_id"], first["evidence_id"])
            self.assertEqual(report["images"][0]["case_intake"]["receipt"]["supplied_by"], "Evidence desk")
            self.assertFalse(report["images"][0]["case_intake"]["registered_by_verified"])
            self.assertEqual(report["relationships"][0]["kind"], "exact_copy")
            self.assertEqual(client.get(f"/api/d1/provenance/cases/{case_id}/latest").json()["analysis_id"],
                             report["analysis_id"])

    @unittest.skipIf(cv2 is None, "OpenCV required")
    def test_video_provenance_links_reencoded_frames_at_recorded_times(self):
        import subprocess
        from video_probe import VideoSampler

        if not VideoSampler.available():
            self.skipTest("FFmpeg required")
        folder = Path(self.directory.name)
        image = folder / "scene.png"
        textured_image().save(image)
        first, second = folder / "first.mp4", folder / "second.mp4"
        subprocess.run(["ffmpeg", "-v", "error", "-loop", "1", "-i", str(image),
                        "-t", "2", "-r", "12", "-pix_fmt", "yuv420p", str(first)],
                       capture_output=True, check=True, timeout=20)
        subprocess.run(["ffmpeg", "-v", "error", "-i", str(first), "-vf", "scale=350:250",
                        "-pix_fmt", "yuv420p", str(second)], capture_output=True, check=True, timeout=20)
        report = analyze_images([(path.name, path.read_bytes()) for path in (first, second)])
        edge = next(item for item in report["relationships"] if item["kind"] == "matching_content")
        for timestamp, record in zip(edge["support"]["frame_timestamps_ms"], report["images"], strict=True):
            self.assertIn(timestamp, record["video_coverage"]["examined_timestamps_ms"])
            self.assertLessEqual(record["video_coverage"]["requested_count"], 4)
        self.assertEqual(edge["support"]["sample_pair_count"], 1)

    def test_exact_copy_uses_bytes_even_with_different_names(self):
        raw = png(Image.new("RGB", (100, 100), "navy"))
        report = analyze_images([("a.png", raw), ("renamed.png", raw)])
        self.assertEqual(report["relationships"][0]["kind"], "exact_copy")
        self.assertEqual(report["compared_pairs"], 1)
        self.assertIn(report["images"][0]["content_credentials"]["status"], {"absent", "unavailable"})

    @unittest.skipIf(cv2 is None, "Install requirements-provenance.txt for visual matching")
    def test_known_crop_is_connected_using_image_content(self):
        original = textured_image()
        crop = original.crop((60, 40, 430, 450)).resize((600, 660))
        report = analyze_images([("source.png", png(original)), ("crop.png", png(crop))])
        edge = report["relationships"][0]
        self.assertEqual(edge["kind"], "matching_content")
        self.assertGreaterEqual(edge["support"]["matched_features"], 16)
        self.assertTrue(all(0 <= value <= 1 for value in edge["support"]["left_region"]))

    @unittest.skipIf(cv2 is None, "OpenCV required")
    def test_selected_photo_area_preserves_original_and_limits_match_points(self):
        photo = textured_image()
        screenshot = Image.new("RGB", (1000, 800), "navy")
        screenshot.paste(photo, (150, 160))
        original = png(screenshot)
        area = [.15, .20, .85, .825]
        app = FastAPI()
        app.include_router(router)
        with TestClient(app) as client:
            response = client.post("/api/d1/provenance/analyze", data={
                "comparison_areas": json.dumps([area, None]),
            }, files=[("files", ("screen.png", original, "image/png")),
                      ("files", ("photo.png", png(photo), "image/png"))])
            self.assertEqual(response.status_code, 200, response.text)
            report = response.json()
            self.assertEqual(report["images"][0]["comparison_area"], area)
            base = "/api/d1/provenance/reports/" + report["analysis_id"]
            self.assertEqual(client.get(base + "/images/IMG-01").content, original)
            support = report["relationships"][0]["support"]
            self.assertGreaterEqual(len(support["point_pairs"]), 16)
            for x, y, _, _ in support["point_pairs"]:
                self.assertTrue(area[0] <= x <= area[2] and area[1] <= y <= area[3])
            response = client.get(base + "/relationships/REL-001/difference")
            self.assertEqual(response.status_code, 200, response.text)
            pdf = client.post(base + "/pdf")
            self.assertEqual(pdf.status_code, 200, pdf.text if pdf.status_code != 200 else "")
            from pypdf import PdfReader
            text = " ".join(page.extract_text() for page in PdfReader(io.BytesIO(pdf.content)).pages)
            self.assertIn("Selected photo area", text)
            extended = client.post(base + "/extend", files={
                "files": ("copy.png", png(photo), "image/png"),
            })
            self.assertEqual(extended.status_code, 200, extended.text)
            self.assertEqual(extended.json()["images"][0]["comparison_area"], area)
            invalid = client.post("/api/d1/provenance/analyze", data={
                "comparison_areas": "[[0,0,2,1],null]",
            }, files=[("files", ("screen.png", original, "image/png")),
                      ("files", ("photo.png", png(photo), "image/png"))])
            self.assertEqual(invalid.status_code, 400)

    def test_different_flat_images_do_not_create_visual_connection(self):
        report = analyze_images([
            ("blue.png", png(Image.new("RGB", (100, 100), "blue"))),
            ("red.png", png(Image.new("RGB", (100, 100), "red"))),
        ])
        self.assertEqual(report["relationships"], [])

    def test_metadata_is_reported_as_file_provided(self):
        image = Image.new("RGB", (50, 30), "gray")
        exif = Image.Exif()
        exif[271] = "Example Camera Maker"
        exif[272] = "Example Model"
        stream = io.BytesIO()
        image.save(stream, format="JPEG", exif=exif)
        record, _ = inspect_image(stream.getvalue(), "../camera.jpg", "IMG-01")
        self.assertEqual(record["filename"], "camera.jpg")
        self.assertEqual(record["metadata"]["Model"], "Example Model")
        self.assertIn("unverified", record["metadata_status"])

    def test_rejects_empty_and_corrupt_images(self):
        with self.assertRaises(ValueError):
            analyze_images([("a.png", b""), ("b.png", b"invalid")])
        with self.assertRaises(ValueError):
            inspect_image(b"invalid", "a.png", "IMG-01")

    def test_endpoint_validates_file_count_and_returns_report(self):
        app = FastAPI()
        app.include_router(router)
        raw = png(Image.new("RGB", (50, 50), "teal"))
        with TestClient(app) as client:
            one = client.post("/api/d1/provenance/analyze", files=[("files", ("one.png", raw, "image/png"))])
            self.assertEqual(one.status_code, 400)
            two = client.post("/api/d1/provenance/analyze", files=[
                ("files", ("one.png", raw, "image/png")), ("files", ("two.png", raw, "image/png")),
            ])
            self.assertEqual(two.status_code, 200)
            self.assertEqual(two.json()["relationships"][0]["kind"], "exact_copy")

    def test_preserved_originals_and_chain_detect_edit_and_truncation(self):
        raw = png(Image.new("RGB", (60, 60), "blue"))
        inputs = [("a.png", raw), ("b.png", raw)]
        store = ProvenanceStore()
        report = store.save(analyze_images(inputs), inputs, "CASE-T", "Analyst", "Test")
        self.assertTrue(store.verify(report)["all_originals_match"])
        original = store.blob_path(report["images"][0]["sha256"])
        self.assertEqual(original.stat().st_mode & 0o222, 0)
        db = store.connect()
        db.execute("DELETE FROM provenance_events WHERE sequence=?", (report["integrity"]["anchor_sequence"],))
        db.commit()
        db.close()
        self.assertFalse(store.verify(report)["anchor_matches"])

    def test_event_mutation_and_original_mutation_are_detected(self):
        raw = png(Image.new("RGB", (60, 60), "blue"))
        inputs = [("a.png", raw), ("b.png", raw)]
        store = ProvenanceStore()
        report = store.save(analyze_images(inputs), inputs, "CASE-T", "Analyst", "Test")
        db = store.connect()
        row = db.execute("SELECT body FROM provenance_events WHERE sequence=1").fetchone()
        body = json.loads(row["body"])
        body["actor"] = "Changed actor"
        db.execute("UPDATE provenance_events SET body=? WHERE sequence=1", (json.dumps(body),))
        db.commit()
        db.close()
        self.assertFalse(store.verify(report)["chain_valid"])
        original = store.blob_path(report["images"][0]["sha256"])
        original.chmod(0o600)
        original.write_bytes(b"changed")
        self.assertFalse(store.verify(report)["all_originals_match"])
        with self.assertRaises(ValueError):
            store.preserve(raw)

    def test_detector_revision_retains_previous_report(self):
        raw = png(Image.new("RGB", (60, 60), "blue"))
        inputs = [("a.png", raw), ("b.png", raw)]
        store = ProvenanceStore()
        report = store.save(analyze_images(inputs), inputs, "CASE-T", "Analyst", "Test")
        revision = store.revision(report, "IMG-01", [{"method":"test", "score":1}])
        self.assertNotEqual(revision["analysis_id"], report["analysis_id"])
        self.assertEqual(store.get(report["analysis_id"])["images"][0]["detector_signals"], [])
        self.assertTrue(store.verify(revision)["chain_valid"])
        self.assertTrue(store.verify(report)["anchor_matches"])

    def test_local_original_verification_matches_and_rejects_different_bytes(self):
        app = FastAPI()
        app.include_router(router)
        raw = png(Image.new("RGB", (60, 60), "blue"))
        with TestClient(app) as client:
            report = client.post("/api/d1/provenance/analyze", files=[
                ("files", ("a.png", raw, "image/png")), ("files", ("b.png", raw, "image/png")),
            ]).json()
            url = "/api/d1/provenance/reports/" + report["analysis_id"] + "/images/IMG-01/verify"
            self.assertTrue(client.post(url,files={"file":("a.png",raw,"image/png")}).json()["matches"])
            self.assertFalse(client.post(url,files={"file":("a.png",b"changed","image/png")}).json()["matches"])

    def test_export_preserves_numeric_representation_for_hash(self):
        from provenance_store import digest
        app = FastAPI()
        app.include_router(router)
        raw = png(Image.new("RGB", (60, 60), "blue"))
        with TestClient(app) as client:
            report = client.post("/api/d1/provenance/analyze", files=[
                ("files", ("a.png", raw, "image/png")), ("files", ("b.png", raw, "image/png")),
            ]).json()
            response = client.get("/api/d1/provenance/reports/" + report["analysis_id"] + "/export")
            exported = json.loads(response.content)
            expected = exported.pop("report_sha256")
            self.assertEqual(digest(exported), expected)

    def test_pdf_contains_record_hash_and_blocks_after_tampering(self):
        try:
            from pypdf import PdfReader
            import reportlab
        except ImportError:
            self.skipTest("PDF verification dependencies not installed")
        app = FastAPI()
        app.include_router(router)
        raw = png(Image.new("RGB", (60, 60), "blue"))
        with TestClient(app) as client:
            report = client.post("/api/d1/provenance/analyze", files=[
                ("files", ("a.png", raw, "image/png")), ("files", ("b.png", raw, "image/png")),
            ]).json()
            url="/api/d1/provenance/reports/" + report["analysis_id"] + "/pdf"
            pdf=client.post(url)
            self.assertEqual(pdf.status_code,200)
            text="".join(page.extract_text() for page in PdfReader(io.BytesIO(pdf.content)).pages)
            self.assertIn(report["report_sha256"],text)
            self.assertIn("Signature",text)
            path=ProvenanceStore().blob_path(report["images"][0]["sha256"])
            path.chmod(0o600)
            path.write_bytes(b"changed")
            self.assertEqual(client.post(url).status_code,409)

    def test_heic_original_is_preserved_and_preview_is_jpeg(self):
        try:
            import pillow_heif
        except ImportError:
            self.skipTest("HEIC decoder not installed")
        pillow_heif.register_heif_opener()
        stream=io.BytesIO()
        Image.new("RGB",(64,80),"teal").save(stream,format="HEIF")
        raw=stream.getvalue()
        app=FastAPI()
        app.include_router(router)
        with TestClient(app) as client:
            response=client.post("/api/d1/provenance/analyze",files=[
                ("files",("a.HEIC",raw,"image/heic")),("files",("b.HEIC",raw,"image/heic")),
            ])
            self.assertEqual(response.status_code,200,response.text)
            report=response.json()
            self.assertEqual(report["images"][0]["format"],"HEIF")
            self.assertEqual(report["relationships"][0]["kind"],"exact_copy")
            base="/api/d1/provenance/reports/"+report["analysis_id"]+"/images/IMG-01"
            self.assertEqual(client.get(base).content,raw)
            preview=client.get(base+"/preview")
            self.assertEqual(preview.status_code,200)
            with Image.open(io.BytesIO(preview.content)) as image:
                self.assertEqual(image.format,"JPEG")
                self.assertEqual(image.size,(64,80))

    @unittest.skipIf(cv2 is None, "OpenCV required")
    def test_aligned_difference_highlights_controlled_added_region(self):
        from PIL import ImageDraw
        from provenance import difference_image
        original = textured_image()
        edited = original.copy()
        ImageDraw.Draw(edited).rectangle((520, 200, 680, 300), fill=(16, 32, 48))
        inputs = [("original.png", png(original)), ("edited.png", png(edited))]
        store = ProvenanceStore()
        report = store.save(analyze_images(inputs), inputs, "CASE-DIFF", "Analyst", "Controlled edit")
        edge = next(item for item in report["relationships"] if item["kind"] == "matching_content")
        raw, percent = difference_image(report, edge)
        self.assertGreater(percent, 1)
        self.assertLess(percent, 10)
        with Image.open(io.BytesIO(raw)) as overlay:
            self.assertEqual(overlay.size, original.size)
            red, green, blue = overlay.getpixel((560, 250))
            self.assertGreater(red, green)
            self.assertGreater(red, blue)

    def make_client_report(self):
        app = FastAPI()
        app.include_router(router)
        client = TestClient(app)
        raw = png(Image.new("RGB", (60, 60), "blue"))
        report = client.post("/api/d1/provenance/analyze", files=[
            ("files", ("a.png", raw, "image/png")), ("files", ("b.png", raw, "image/png")),
        ]).json()
        return client, report, raw

    def test_reviewer_note_is_immutable_scoped_and_in_pdf(self):
        from pypdf import PdfReader
        client, report, raw = self.make_client_report()
        base = "/api/d1/provenance/reports/"
        note = {"author": "Reviewer B", "text": "Same bytes; origin remains unverified.", "scope_id": "IMG-01"}
        response = client.post(base+report["analysis_id"]+"/notes", json=note)
        self.assertEqual(response.status_code, 200, response.text)
        revised = response.json()
        self.assertEqual(revised["review_notes"][0]["text"], note["text"])
        self.assertNotIn("review_notes", client.get(base+report["analysis_id"]).json())
        self.assertNotEqual(revised["analysis_id"], report["analysis_id"])
        self.assertTrue(ProvenanceStore().verify(revised)["chain_valid"])
        self.assertEqual(ProvenanceStore().events(report["case"]["id"])[-1]["actor"], "Reviewer B")
        bad = client.post(base+report["analysis_id"]+"/notes", json={**note,"scope_id":"unknown"})
        self.assertEqual(bad.status_code, 400)
        pdf = client.post(base+revised["analysis_id"]+"/pdf")
        text = "".join(page.extract_text() for page in PdfReader(io.BytesIO(pdf.content)).pages)
        self.assertIn(note["text"], text)

    def test_extended_analysis_retains_files_and_old_snapshot(self):
        client, report, raw = self.make_client_report()
        base = "/api/d1/provenance/reports/"
        response = client.post(base+report["analysis_id"]+"/extend", files=[("files",("third.png",raw,"image/png"))])
        self.assertEqual(response.status_code, 200, response.text)
        extended = response.json()
        self.assertEqual(len(extended["images"]), 3)
        self.assertEqual(extended["parent_analysis_id"], report["analysis_id"])
        self.assertEqual(extended["compared_pairs"], 3)
        self.assertEqual(len(client.get(base+report["analysis_id"]).json()["images"]), 2)
        self.assertTrue(ProvenanceStore().verify(extended)["all_originals_match"])

    def test_package_offline_verification_and_changed_file_detection(self):
        import zipfile
        from verify_provenance_package import verify
        client, report, raw = self.make_client_report()
        response = client.post("/api/d1/provenance/reports/"+report["analysis_id"]+"/bundle")
        self.assertEqual(response.status_code, 200, response.text)
        with TemporaryDirectory() as destination:
            with zipfile.ZipFile(io.BytesIO(response.content)) as bundle:
                bundle.extractall(destination)
            checked = verify(destination, response.headers["X-Manifest-SHA256"])
            self.assertEqual(checked["originals"], 2)
            with self.assertRaisesRegex(ValueError, "externally retained"):
                verify(destination, "0"*64)
            original = next((Path(destination)/"originals").iterdir())
            original.write_bytes(b"changed")
            with self.assertRaisesRegex(ValueError, "changed package file"):
                verify(destination)

    def test_recording_stops_on_damaged_existing_chain(self):
        client, report, raw = self.make_client_report()
        store = ProvenanceStore()
        db = store.connect()
        db.execute("UPDATE provenance_events SET body='{}' WHERE sequence=1")
        db.commit()
        db.close()
        with self.assertRaisesRegex(ValueError, "chain failed"):
            store.log_action(report, "test", {})
        response = client.post("/api/d1/provenance/reports/"+report["analysis_id"]+"/bundle")
        self.assertEqual(response.status_code,409)



if __name__ == "__main__":
    unittest.main()
