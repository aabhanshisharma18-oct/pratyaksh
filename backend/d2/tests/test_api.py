from __future__ import annotations
import importlib,io
from fastapi import FastAPI
from fastapi.testclient import TestClient
from PIL import Image
api=importlib.import_module("d2.api.router")
from d2.config import D2Config
from d2.services import D2Services

def client(tmp_path):
    api.services=D2Services(D2Config(tmp_path,tmp_path/"api.db",tmp_path/"originals",tmp_path/"derivatives",tmp_path/"exports","API examiner"));app=FastAPI();app.include_router(api.router);return TestClient(app)

def png():
    value=io.BytesIO();Image.new("RGB",(64,64),"navy").save(value,"PNG");return value.getvalue()

def test_operator_page_has_separate_panels(tmp_path):
    response=client(tmp_path).get("/d2");assert response.status_code==200;assert all(label in response.text for label in ("Integrity Status","Metadata Summary","Manipulation Analysis Results"));assert "does not detect deepfakes" in response.text

def test_embedded_operator_page_omits_duplicate_header(tmp_path):
    response=client(tmp_path).get("/d2?embedded=1&theme=dark");assert response.status_code==200;assert '<body class="embedded" data-theme="dark">' in response.text;assert "<header>" not in response.text;assert "Secure intake" in response.text

def test_embedded_operator_page_supports_hindi(tmp_path):
    response=client(tmp_path).get("/d2?embedded=1&theme=light&lang=hi");assert response.status_code==200;assert '<html lang="hi">' in response.text
    assert all(label in response.text for label in ("सुरक्षित इनटेक","अखंडता स्थिति","मेटाडेटा सारांश","हेरफेर विश्लेषण परिणाम"))

def test_intake_verify_metadata_and_export_endpoints(tmp_path):
    c=client(tmp_path);created=c.post("/api/d2/evidence",data={"case_id":"CASE-2026-101","receipt_context":"API test"},files={"file":("../../unsafe.png",png(),"image/png")});assert created.status_code==201;evidence_id=created.json()["evidence_id"];assert evidence_id=="CASE-2026-101-EVD-00001";assert c.post(f"/api/d2/evidence/{evidence_id}/verify").json()["integrity_status"]=="Hash Match";metadata=c.post(f"/api/d2/evidence/{evidence_id}/metadata");assert metadata.status_code==200 and "normalized" in metadata.json();package=c.post(f"/api/d2/evidence/{evidence_id}/export");assert package.status_code==200 and package.headers["content-type"]=="application/zip"

def test_copy_move_endpoint_status_contract(tmp_path):
    c=client(tmp_path);created=c.post("/api/d2/evidence",data={"case_id":"CASE-2026-102"},files={"file":("image.png",png(),"image/png")}).json();result=c.post(f"/api/d2/evidence/{created['evidence_id']}/analysis/copy-move",data={"block_size":16,"step":8,"min_cluster":3});assert result.status_code==200;body=result.json();assert body["format_support"]=="Supported" and body["decoding"]=="Succeeded" and body["analysis"]=="Completed";assert "not a universal authenticity verdict" in body["limitations"][0]
