from __future__ import annotations
import asyncio,hashlib,io,json,os,stat,zipfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import cv2,numpy as np,pytest
from fastapi import UploadFile
from PIL import Image,ImageDraw
from sqlalchemy import text
from d2.analysis.copy_move import CopyMoveAnalyzer
from d2.analysis.video_continuity import VideoContinuityAnalyzer
from d2.config import D2Config
from d2.services import D2Services

@pytest.fixture
def services(tmp_path):
    config=D2Config(tmp_path,tmp_path/"d2.db",tmp_path/"originals",tmp_path/"derivatives",tmp_path/"exports","Test examiner",10*1024*1024)
    return D2Services(config)

def upload(name,data):return UploadFile(filename=name,file=io.BytesIO(data))
def intake(services,data=b"forensic bytes",name="../../unsafe.png"):
    return asyncio.run(services.intake.intake("CASE-2026-001",upload(name,data),"Test receipt","Examiner"))

def test_streaming_hash_atomic_controlled_path_and_read_only(services):
    item=intake(services);path=Path(item.storage_path)
    assert item.id=="CASE-2026-001-EVD-00001";assert item.sha256==hashlib.sha256(b"forensic bytes").hexdigest();assert path.name=="original.bin" and "unsafe" not in str(path);assert not list(path.parent.glob("*.upload"));assert not os.stat(path).st_mode&stat.S_IWUSR

def test_concurrency_safe_sequential_ids(services):
    with ThreadPoolExecutor(max_workers=8) as pool:ids=list(pool.map(lambda _:services.intake.reserve_id("CASE-2026-002"),range(20)))
    assert len(set(ids))==20;assert sorted(int(x.rsplit("-",1)[1]) for x in ids)==list(range(1,21))

def test_hash_mismatch_is_separate_status(services):
    item=intake(services);path=Path(item.storage_path);os.chmod(path,0o644);path.write_bytes(b"changed");assert services.integrity.verify(item.id,"Examiner")["integrity_status"]=="Hash Mismatch"

def test_derivative_links_hashes_and_reverifies_parent(services):
    item=intake(services);derived=services.derivatives.create(item.id,"mask",b"pngbytes",".png","unit transform",{"threshold":1},{"test":"1"},"Examiner")
    assert derived.evidence_id==item.id and derived.sha256==hashlib.sha256(b"pngbytes").hexdigest();assert services.intake.get(item.id).integrity_status=="Hash Match"

def test_audit_is_append_only_and_chain_verifies(services):
    intake(services);assert services.audit.verify()["valid"]
    with pytest.raises(Exception):
        with services.database.engine.begin() as connection:connection.execute(text("UPDATE d2_audit_entries SET result='changed' WHERE sequence=1"))
    with services.database.engine.begin() as connection:connection.execute(text("DROP TRIGGER d2_audit_no_update"));connection.execute(text("UPDATE d2_audit_entries SET entry_hash='broken' WHERE sequence=1"))
    assert not services.audit.verify()["valid"]

def test_metadata_snapshot_neutral_camera_and_limitations(services):
    data=io.BytesIO();Image.new("RGB",(30,20),"red").save(data,"PNG");item=intake(services,data.getvalue(),"photo.png");snapshot=services.metadata.extract(item.id,"Examiner")
    assert "camera" in snapshot.normalized;assert any("does not prove" in x for x in snapshot.normalized["limitations"]);assert snapshot.raw

def copy_sample(tmp_path):
    rng=np.random.default_rng(7);array=rng.integers(0,256,(128,128,3),dtype=np.uint8);array[80:112,80:112]=array[16:48,16:48];image=tmp_path/"copy.png";Image.fromarray(array).save(image);mask=Image.new("L",(128,128));draw=ImageDraw.Draw(mask);draw.rectangle((16,16,47,47),fill=255);draw.rectangle((80,80,111,111),fill=255);truth=tmp_path/"mask.png";mask.save(truth);return image,truth

def test_copy_move_outputs_localization_and_metrics(tmp_path):
    image,truth=copy_sample(tmp_path);result=CopyMoveAnalyzer().analyze(image,truth)
    assert result.analysis=="Completed" and len(result.artifacts)==2 and result.findings["possible_regions"];assert set(result.evaluation)>={"iou","pixel_agreement","precision","recall","f1"};assert "not a universal authenticity verdict" in result.limitations[0]

def test_copy_move_corrupt_status_is_explicit(tmp_path):
    path=tmp_path/"bad.png";path.write_bytes(b"bad");result=CopyMoveAnalyzer().analyze(path);assert (result.format_support,result.decoding,result.analysis)==("Unsupported","Failed","Failed")

def test_video_duplicates_and_metrics(tmp_path):
    path=tmp_path/"video.avi";writer=cv2.VideoWriter(str(path),cv2.VideoWriter_fourcc(*"MJPG"),5,(64,48));assert writer.isOpened();rng=np.random.default_rng(3);frames=[rng.integers(0,256,(48,64,3),dtype=np.uint8) for _ in range(8)];frames[6]=frames[2].copy()
    for frame in frames:writer.write(frame)
    writer.release();result=VideoContinuityAnalyzer(sample_fps=5,max_frames=20,hamming_threshold=2).analyze(path,[[2,6]])
    assert result.analysis=="Completed" and result.findings["duplicate_pairs"];assert result.evaluation["recall"]>0;assert "not comprehensive" in result.limitations[0]

def test_export_package_integrity_and_completeness(services):
    data=io.BytesIO();Image.new("RGB",(30,20),"blue").save(data,"PNG");item=intake(services,data.getvalue(),"image.png");services.metadata.extract(item.id,"Examiner");package=services.exports.create(item.id,"Examiner")
    with zipfile.ZipFile(package) as archive:
        names=set(archive.namelist());assert {"original/original.bin","integrity/verification.json","metadata/snapshot.json","audit/events.json","limitations.json","manifest.json"}<=names;manifest=json.loads(archive.read("manifest.json"));assert all(hashlib.sha256(archive.read(x["path"])).hexdigest()==x["sha256"] for x in manifest["files"])
