"""Timestamped observations from uploaded recordings."""
import json
from pathlib import Path
import sys
from subprocess import PIPE, TimeoutExpired, run
from tempfile import TemporaryDirectory
from threading import BoundedSemaphore
from typing import Literal

from fastapi import APIRouter, File, HTTPException, UploadFile
import numpy as np

router = APIRouter(prefix="/api/d1", tags=["Recording analysis"])
Mode = Literal["eyes", "posture", "speech"]
MODEL_DIR = Path(__file__).parent / "models" / "recording-analysis"
MAX_BYTES = 50 * 1024 * 1024
SECONDS = 20
FPS = 5
SIZE = 384
LANDMARK_VISIBILITY = 0.5
SLOTS = BoundedSemaphore(1)


def decode(path, stream, options):
    try:
        result = run(
            ["ffmpeg", "-nostdin", "-v", "error", "-protocol_whitelist", "file,pipe",
             "-format_whitelist", "mov,matroska,avi,mpeg,mpegts,ogg,wav,mp3,aac,flac,aiff,asf,flv,amr,caf",
             "-i", str(path), "-map", stream, "-t", str(SECONDS), *options, "pipe:1"],
            stdout=PIPE, stderr=PIPE, timeout=30, check=False,
        )
    except FileNotFoundError as exc:
        raise HTTPException(503, "FFmpeg is required for recording analysis.") from exc
    except TimeoutExpired as exc:
        raise HTTPException(422, "Decoding timed out. Try a shorter clip.") from exc
    if result.returncode or not result.stdout:
        raise HTTPException(422, f"Could not decode an {'audio' if ':a:' in stream else 'video'} track.")
    return result.stdout


def analyze_speech(path):
    rate = 16_000
    signal = np.frombuffer(decode(path, "0:a:0", ["-vn", "-ac", "1", "-ar", str(rate),
                                                   "-c:a", "pcm_s16le", "-f", "s16le"]), "<i2")
    rows = []
    for start in range(0, len(signal), rate // 2):
        window = signal[start:start + rate // 2].astype(np.float64) / 32768
        dbfs = 20 * np.log10(max(float(np.sqrt((window ** 2).mean())), 1e-6))
        rows.append({"time_ms": round(start / rate * 1000),
                     "values": [round(float(dbfs), 1), "Quiet" if dbfs < -40 else "Audible"]})
    return {
        "method": "FFmpeg + RMS signal level (500 ms windows)",
        "columns": ["Level (dBFS)", "Audio activity"],
        "rows": rows,
        "duration_ms": round(len(signal) / rate * 1000),
        "notes": "Quiet means average audio level below −40 dBFS. Background sounds can register as audible. This scan measures audio activity and pauses; it does not transcribe speech or assess emotion or sentiment.",
    }


def eye_values(result):
    if len(result.face_landmarks) != 1 or not result.face_blendshapes:
        return None
    scores = {item.category_name: item.score for item in result.face_blendshapes[0]}
    keys = ("eyeBlinkLeft", "eyeBlinkRight")
    if any(key not in scores for key in keys):
        return None
    directions = {"Left": ("eyeLookOutLeft", "eyeLookInRight"),
                  "Right": ("eyeLookInLeft", "eyeLookOutRight"),
                  "Up": ("eyeLookUpLeft", "eyeLookUpRight"),
                  "Down": ("eyeLookDownLeft", "eyeLookDownRight")}
    left, right = (scores[key] for key in keys)
    if max(left, right) >= 0.5:
        return [round(left, 3), round(right, 3), "Unavailable during closure"]
    strengths = {label: sum(scores.get(key, 0.0) for key in pair) / 2
                 for label, pair in directions.items()}
    strongest = max(strengths, key=strengths.get)
    cue = strongest if strengths[strongest] >= 0.35 else "No dominant direction"
    return [round(left, 3), round(right, 3), cue]


def posture_values(result):
    if len(result.pose_landmarks) != 1:
        return None
    points = result.pose_landmarks[0]
    shoulder_a, shoulder_b, hip_a, hip_b = (points[i] for i in (11, 12, 23, 24))
    if any(point.visibility < LANDMARK_VISIBILITY for point in (shoulder_a, shoulder_b)):
        return None
    left, right = sorted((shoulder_a, shoulder_b), key=lambda point: point.x)
    shoulder_tilt = np.degrees(np.arctan2(right.y-left.y, right.x-left.x))
    lean = None
    if all(point.visibility >= LANDMARK_VISIBILITY for point in (hip_a, hip_b)):
        dx = (shoulder_a.x+shoulder_b.x-hip_a.x-hip_b.x)/2
        dy = (hip_a.y+hip_b.y-shoulder_a.y-shoulder_b.y)/2
        if dy > 0.025:
            lean = round(float(np.degrees(np.arctan2(dx, dy))), 1)
    wrist_pairs = [("Left", points[15], shoulder_a), ("Right", points[16], shoulder_b)]
    visible_wrists = [(name, wrist.y < shoulder.y) for name, wrist, shoulder in wrist_pairs
                      if wrist.visibility >= LANDMARK_VISIBILITY]
    raised = [name for name, is_raised in visible_wrists if is_raised]
    wrist_display = ", ".join(raised) or ("None observed" if visible_wrists else None)
    return [round(float(shoulder_tilt), 1), lean, wrist_display]


def analyze_visual(path, mode):
    try:
        import mediapipe as mp
    except ImportError as exc:
        raise HTTPException(503, "Install the recording analysis dependencies and models.") from exc
    eyes = mode == "eyes"
    model = MODEL_DIR / ("face_landmarker.task" if eyes else "pose_landmarker_lite.task")
    if not model.is_file():
        raise HTTPException(503, "Run setup_recording_analysis.py to install the landmark models.")
    raw = decode(path, "0:v:0", [
        "-an", "-vf", f"fps={FPS},scale={SIZE}:{SIZE}:force_original_aspect_ratio=decrease,"
        f"pad={SIZE}:{SIZE}:(ow-iw)/2:(oh-ih)/2,setsar=1",
        "-frames:v", str(FPS * SECONDS), "-pix_fmt", "rgb24", "-c:v", "rawvideo", "-f", "rawvideo",
    ])
    frames = np.frombuffer(raw, np.uint8).reshape(-1, SIZE, SIZE, 3)
    vision = mp.tasks.vision
    config = {"base_options": mp.tasks.BaseOptions(model_asset_path=str(model)),
              "running_mode": vision.RunningMode.VIDEO}
    if eyes:
        worker = vision.FaceLandmarker.create_from_options(
            vision.FaceLandmarkerOptions(**config, num_faces=2, output_face_blendshapes=True))
    else:
        worker = vision.PoseLandmarker.create_from_options(
            vision.PoseLandmarkerOptions(**config, num_poses=2))
    with worker:
        rows = []
        for index, frame in enumerate(frames):
            time = index * 1000 // FPS
            result = worker.detect_for_video(mp.Image(image_format=mp.ImageFormat.SRGB, data=frame), time)
            rows.append({"time_ms": time, "values": eye_values(result) if eyes else posture_values(result)})
    return {
        "method": "MediaPipe Face Landmarker" if eyes else "MediaPipe Pose Landmarker Lite",
        "columns": ["Left closure score", "Right closure score", "Eye direction cue"] if eyes else
                   ["Shoulder tilt (°)", "Torso lean (°)", "Wrists above shoulders"],
        "rows": rows,
        "duration_ms": len(frames) * 1000 // FPS,
        "notes": ("Eye directions are model cues relative to the face. Five samples per second can miss quick blinks. "
                  "Only frames with one usable face are scored." if eyes else
                  "Angles are measured in the image. Camera tilt and framing affect the result. "
                  "Only frames with one usable pose are scored."),
    }


def run_visual_worker(path, mode):
    # Native landmark initialization can abort on machines without a graphics context.
    try:
        result = run([sys.executable, str(Path(__file__).resolve()), mode, str(path)],
                     stdout=PIPE, stderr=PIPE, timeout=120, check=False)
    except TimeoutExpired as exc:
        raise HTTPException(422, "Visual analysis timed out. Try a shorter clip.") from exc
    if result.returncode:
        raise HTTPException(503, "The local landmark runtime could not analyze the recording.")
    payload = json.loads(result.stdout)
    if "error" in payload:
        raise HTTPException(payload["status"], payload["error"])
    return payload


@router.post("/recording-analysis/{mode}")
def recording_analysis(mode: Mode, file: UploadFile = File(...)):
    if not SLOTS.acquire(blocking=False):
        raise HTTPException(429, "Another recording analysis is running. Try again shortly.")
    try:
        with TemporaryDirectory(prefix="pratyaksh-recording-") as folder:
            path = Path(folder) / "recording"
            total = 0
            with path.open("wb") as destination:
                while chunk := file.file.read(1024 * 1024):
                    total += len(chunk)
                    if total > MAX_BYTES:
                        raise HTTPException(413, "Recording exceeds 50 MiB.")
                    destination.write(chunk)
            if not total:
                raise HTTPException(400, "Choose a non-empty recording.")
            result = analyze_speech(path) if mode == "speech" else run_visual_worker(path, mode)
            return {**result, "scored": sum(row["values"] is not None for row in result["rows"])}
    finally:
        file.file.close()
        SLOTS.release()


if __name__ == "__main__":
    try:
        print(json.dumps(analyze_visual(Path(sys.argv[2]), sys.argv[1])))
    except HTTPException as error:
        print(json.dumps({"status": error.status_code, "error": error.detail}))
