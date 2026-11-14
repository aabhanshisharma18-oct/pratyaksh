import importlib.util
import json
import zipfile
from pathlib import Path

import pytest


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "import_automated_demo.py"
SPEC = importlib.util.spec_from_file_location("import_automated_demo", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


def test_committed_manifest_is_strict_and_complete():
    records = MODULE.load_manifest()
    assert len(records) == 9
    assert records["01-reference-synthetic.png"][1] == "Reference"
    assert records["02-exact-copy.png"][1] == "Evidence"
    assert records["01-reference-synthetic.png"][2] == records["02-exact-copy.png"][2]
    assert records["08-synthetic-voice.wav"][0] == "audio"
    assert records["09-motion-control.mp4"][0] == "video"


def test_manifest_rejects_invalid_hash(tmp_path):
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps({"schema_version": "1.0", "case_marker": MODULE.CASE_MARKER,
                                "files": [{"filename": "x.png", "media_type": "image",
                                           "role": "Evidence", "sha256": "not-a-hash"}]}))
    with pytest.raises(ValueError, match="Invalid automated-demo manifest record"):
        MODULE.load_manifest(path)


def test_archive_reader_rejects_parent_paths(tmp_path, monkeypatch):
    archive = tmp_path / "unsafe.zip"
    with zipfile.ZipFile(archive, "w") as bundle:
        bundle.writestr("../escape.png", b"payload")
    monkeypatch.setattr(MODULE, "EXPECTED", {"escape.png": ("image", "Evidence", "0" * 64)})
    with pytest.raises(SystemExit, match="Unsafe or unexpected archive path"):
        MODULE.read_archive(archive)
