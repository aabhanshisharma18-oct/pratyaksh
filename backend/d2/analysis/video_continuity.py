from __future__ import annotations
import hashlib
import cv2,numpy as np
from .base import AnalysisResult,Analyzer
from .metrics import frame_metrics
LIMITATION="Frame continuity observation only. Static scenes or certain encoding behaviors can also produce identical frames. This is not comprehensive tampering authentication."

def ahash(frame):
    small=cv2.resize(cv2.cvtColor(frame,cv2.COLOR_BGR2GRAY),(8,8),interpolation=cv2.INTER_AREA);bits=(small>=small.mean()).flatten();return sum(int(bit)<<index for index,bit in enumerate(bits))

class VideoContinuityAnalyzer(Analyzer):
    name="Bounded fixed-rate exact/aHash duplicate-frame comparison";version="1.0"
    def __init__(self,sample_fps=1.0,max_frames=120,max_duration_seconds=120.0,hamming_threshold=2): self.parameters={"sample_fps":sample_fps,"max_frames":max_frames,"max_duration_seconds":max_duration_seconds,"hamming_threshold":hamming_threshold}
    def analyze(self,path,ground_truth_pairs=None):
        capture=cv2.VideoCapture(str(path))
        if not capture.isOpened(): return AnalysisResult("Unsupported","Failed","Failed",self.name,self.version,self.parameters,{},[],"The video container could not be decoded.",[LIMITATION])
        source_fps=capture.get(cv2.CAP_PROP_FPS) or 25.0;frame_count=capture.get(cv2.CAP_PROP_FRAME_COUNT) or 0;duration=frame_count/source_fps;step=max(1,round(source_fps/self.parameters["sample_fps"]));samples=[];index=0
        while len(samples)<self.parameters["max_frames"] and index/source_fps<=self.parameters["max_duration_seconds"]:
            capture.set(cv2.CAP_PROP_POS_FRAMES,index);ok,frame=capture.read()
            if not ok: break
            samples.append({"frame_index":index,"timestamp_ms":round(index/source_fps*1000),"exact":hashlib.sha256(frame.tobytes()).hexdigest(),"ahash":ahash(frame)});index+=step
        capture.release();pairs=[]
        for i,a in enumerate(samples):
            for b in samples[i+1:]:
                distance=(a["ahash"]^b["ahash"]).bit_count()
                if a["exact"]==b["exact"] or distance<=self.parameters["hamming_threshold"]: pairs.append({"first_frame":a["frame_index"],"second_frame":b["frame_index"],"first_timestamp_ms":a["timestamp_ms"],"second_timestamp_ms":b["timestamp_ms"],"exact":a["exact"]==b["exact"],"hamming_distance":distance})
        detected=[[p["first_frame"],p["second_frame"]] for p in pairs];evaluation=frame_metrics(detected,ground_truth_pairs) if ground_truth_pairs is not None else None
        partial=duration>self.parameters["max_duration_seconds"] or frame_count>self.parameters["max_frames"]*step
        return AnalysisResult("Supported","Succeeded","Partial" if partial else "Completed",self.name,self.version,self.parameters,{"sampled_frames":len(samples),"source_fps":source_fps,"source_duration_seconds":duration,"duplicate_pairs":pairs},[],f"Observed {len(pairs)} exact or near-exact sampled-frame pair(s).",[LIMITATION,"Sampling is bounded and can miss events between sampled frames."],evaluation)
