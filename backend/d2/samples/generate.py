from __future__ import annotations
import json
from pathlib import Path
import cv2,numpy as np
from PIL import Image,ImageDraw
from ..analysis.copy_move import CopyMoveAnalyzer
from ..analysis.video_continuity import VideoContinuityAnalyzer

def generate(root=None):
    root=Path(root or Path(__file__).parents[3]/"samples"/"d2");root.mkdir(parents=True,exist_ok=True);rng=np.random.default_rng(20261112)
    control=rng.integers(0,256,(128,128,3),dtype=np.uint8);Image.fromarray(control).save(root/"control-unedited.png")
    modified=control.copy();modified[80:112,80:112]=modified[16:48,16:48];Image.fromarray(modified).save(root/"copy-move.png")
    mask=Image.new("L",(128,128));draw=ImageDraw.Draw(mask);draw.rectangle((16,16,47,47),fill=255);draw.rectangle((80,80,111,111),fill=255);mask.save(root/"copy-move-mask.png")
    tiles=np.indices((128,128)).sum(axis=0)%16<8;Image.fromarray(np.where(tiles[...,None],220,40).astype(np.uint8).repeat(3,2)).save(root/"repeating-texture-false-alarm.png")
    (root/"corrupt.png").write_bytes(b"not an image");(root/"unsupported.txt").write_text("unsupported media control",encoding="utf-8")
    video=root/"duplicate-frames.avi";writer=cv2.VideoWriter(str(video),cv2.VideoWriter_fourcc(*"MJPG"),5,(96,64));frames=[rng.integers(0,256,(64,96,3),dtype=np.uint8) for _ in range(12)];frames[7]=frames[2].copy()
    for frame in frames:writer.write(frame)
    writer.release();truth={"source_fps":5,"duplicate_pairs":[[2,7]],"note":"Frames 2 and 7 were deliberately made identical before MJPEG encoding."};(root/"duplicate-frames.json").write_text(json.dumps(truth,indent=2),encoding="utf-8")
    image_result=CopyMoveAnalyzer().analyze(root/"copy-move.png",root/"copy-move-mask.png");video_result=VideoContinuityAnalyzer(sample_fps=5,max_frames=20,hamming_threshold=2).analyze(video,truth["duplicate_pairs"])
    report={"seed":20261112,"image":{"statuses":{"format_support":image_result.format_support,"decoding":image_result.decoding,"analysis":image_result.analysis},"evaluation":image_result.evaluation,"limitations":image_result.limitations},"video":{"statuses":{"format_support":video_result.format_support,"decoding":video_result.decoding,"analysis":video_result.analysis},"evaluation":video_result.evaluation,"limitations":video_result.limitations},"controls":["control-unedited.png","repeating-texture-false-alarm.png","corrupt.png","unsupported.txt"]};(root/"evaluation-report.json").write_text(json.dumps(report,indent=2),encoding="utf-8");return report

if __name__=="__main__":print(json.dumps(generate(),indent=2))
