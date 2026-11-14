"""File-provided metadata and offline C2PA validation for provenance reports."""
import io
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
from datetime import datetime


def recorded_metadata(raw):
    executable = shutil.which("exiftool")
    if not executable:
        return {}, "ExifTool unavailable; basic Pillow metadata retained."
    tags = [
        "Make", "Model", "Software", "CreateDate", "ModifyDate", "DateTimeOriginal",
        "GPSLatitude", "GPSLongitude", "GPSAltitude", "ImageWidth", "ImageHeight",
        "Artist", "Copyright", "Encoder", "LensModel",
    ]
    try:
        result = subprocess.run([executable, "-json", "-n", *["-" + tag for tag in tags], "-"],
                                input=raw, capture_output=True, timeout=15, check=True)
        data = json.loads(result.stdout)[0]
        return {key: str(value)[:1000] for key, value in data.items()
                if key != "SourceFile" and key not in {"ExifToolVersion", "Error", "Warning"}}, "ExifTool"
    except (subprocess.SubprocessError, ValueError, IndexError):
        return {}, "ExifTool failed; basic Pillow metadata retained."


def metadata_flags(metadata):
    flags = []
    software = metadata.get("Software", "")
    if software:
        flags.append("A software tag is recorded: " + software + ". This field can be edited.")
    created = metadata.get("CreateDate") or metadata.get("DateTimeOriginal")
    modified = metadata.get("ModifyDate")
    if created and modified:
        try:
            start = datetime.fromisoformat(created[:4] + "-" + created[5:7] + "-" + created[8:])
            end = datetime.fromisoformat(modified[:4] + "-" + modified[5:7] + "-" + modified[8:])
            if (start.tzinfo is None) == (end.tzinfo is None) and end < start:
                flags.append("The recorded modification date is earlier than the recorded creation date.")
        except (ValueError, TypeError):
            pass
    return flags


def credentials(raw, media_format):
    try:
        import c2pa
    except ImportError:
        return {"status": "unavailable", "observation": "C2PA reader unavailable.",
                "signature": "not_checked", "content_binding": "not_checked", "signer_trust": "not_checked"}
    mime = {"JPEG": "image/jpeg", "PNG": "image/png", "WEBP": "image/webp", "WAV":"audio/wav","MP3":"audio/mpeg","HEIF":"image/heic","MP4":"video/mp4"}[media_format]
    try:
        settings = {"verify": {"remote_manifest_fetch": False, "ocsp_fetch": False}}
        anchor = os.getenv("PRATYAKSH_C2PA_DEMO_ANCHOR")
        policy = "Default SDK trust anchors"
        if anchor:
            pem = Path(anchor).read_text()
            settings["trust"] = {"user_anchors": pem}
            policy = "Demo trust policy with a configured test anchor (SHA-256 " + hashlib.sha256(pem.encode()).hexdigest() + ")"
        context = c2pa.Context.from_dict(settings)
        with c2pa.Reader(mime, io.BytesIO(raw), context=context) as reader:
            store = json.loads(reader.json())
    except Exception as error:
        if type(error).__name__ == "_C2paManifestNotFound":
            return {"status": "absent", "observation": "No Content Credentials found. Absence alone does not establish whether this file is genuine or fake.",
                    "signature": "not_present", "content_binding": "not_present", "signer_trust": "not_present"}
        return {"status": "error", "observation": "Content Credentials could not be read or validated.",
                "signature": "unknown", "content_binding": "unknown", "signer_trust": "unknown",
                "error": str(error)[:500]}
    active = store.get("active_manifest")
    manifest = store.get("manifests", {}).get(active, {})
    validation = store.get("validation_results", {}).get("activeManifest", {})
    success = {item.get("code") for item in validation.get("success", [])}
    failure = {item.get("code") for item in validation.get("failure", [])}
    actions = []
    creator = []
    for assertion in manifest.get("assertions", []):
        label = assertion.get("label", "")
        data = assertion.get("data", {})
        if label.startswith("c2pa.actions"):
            actions.extend(data.get("actions", []))
        if label.startswith("stds.schema-org.CreativeWork"):
            creator.append(data)
    signature = manifest.get("signature_info", {})
    return {
        "status": "present", "observation": "Embedded Content Credentials inspected locally. Review signature, file binding and trust separately.",
        "trust_policy": policy,
        "active_manifest": active, "manifest_labels": list(store.get("manifests", {})),
        "manifest_digests": {label: hashlib.sha256(json.dumps(value,sort_keys=True,separators=(",",":")).encode()).hexdigest()
                             for label,value in store.get("manifests",{}).items()},
        "validation_state": store.get("validation_state", "unknown"),
        "signature": "valid" if "claimSignature.validated" in success else "invalid_or_unknown",
        "content_binding": "invalid" if failure & {"assertion.dataHash.mismatch", "assertion.bmffHash.mismatch", "assertion.boxesHash.mismatch"} else
                           "valid" if success & {"assertion.dataHash.match", "assertion.bmffHash.match", "assertion.boxesHash.match"} else "invalid_or_unknown",
        "signer_trust": "untrusted" if failure & {"signingCredential.untrusted", "signingCredential.invalid"} else
                        "trusted_by_configured_policy" if "signingCredential.trusted" in success else "not_established",
        "signer": signature, "creator_assertions": creator,
        "tools": manifest.get("claim_generator_info", []), "actions": actions,
        "validation_status": store.get("validation_status", []),
        "validation_results": validation,
        "network_policy": "Remote manifest and OCSP fetching disabled; trust depends on local validator configuration.",
    }


def inspect_audio(raw, filename, image_id):
    import hashlib
    import tempfile
    from pathlib import Path
    executable = shutil.which("ffprobe")
    if not executable:
        raise ValueError("ffprobe is required for audio metadata")
    with tempfile.TemporaryDirectory(prefix="pratyaksh-audio-") as folder:
        path = Path(folder) / "media"
        path.write_bytes(raw)
        try:
            result = subprocess.run([executable,"-v","error","-show_format","-show_streams","-of","json",str(path)],
                                    capture_output=True,timeout=20,check=True)
            data = json.loads(result.stdout)
        except (subprocess.SubprocessError,ValueError) as error:
            raise ValueError("Unable to inspect audio") from error
    streams = data.get("streams",[])
    if any(stream.get("codec_type")=="video" for stream in streams) or not any(stream.get("codec_type")=="audio" for stream in streams):
        raise ValueError("Use WAV or MP3 audio; video support is pending")
    fmt = data.get("format",{})
    audio = next(stream for stream in streams if stream.get("codec_type")=="audio")
    format_name = "MP3" if "mp3" in fmt.get("format_name","") else "WAV" if "wav" in fmt.get("format_name","") else None
    if format_name is None:
        raise ValueError("Use WAV or MP3 audio")
    tags = {**fmt.get("tags",{}),**audio.get("tags",{})}
    metadata = {"Duration":str(fmt.get("duration","unknown")), "Codec":str(audio.get("codec_name","unknown")),
                "SampleRate":str(audio.get("sample_rate","unknown")), "Channels":str(audio.get("channels","unknown"))}
    metadata.update({key:str(value)[:1000] for key,value in tags.items()})
    return {
        "id":image_id,"filename":filename.replace("\\","/").rsplit("/",1)[-1][:255],
        "sha256":hashlib.sha256(raw).hexdigest(),"size_bytes":len(raw),"format":format_name,
        "media_type":"audio","width":0,"height":0,"metadata":metadata,"metadata_method":"ffprobe",
        "metadata_flags":metadata_flags(metadata),
        "source_observation":"Audio stream and file-provided tags inspected with ffprobe.",
        "metadata_status":"Information recorded in the file; origin and timestamps are unverified.",
        "content_credentials":credentials(raw,format_name),"detector_signals":[],
    }, None
