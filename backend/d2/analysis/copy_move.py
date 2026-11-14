from __future__ import annotations
import io
from collections import Counter,defaultdict
from importlib.metadata import version
import numpy as np
from PIL import Image,ImageDraw
from .base import AnalysisResult,Analyzer
from .metrics import mask_metrics

LIMITATION="Copy-move localization result – possible duplicated regions. Repeated natural textures can produce false matches. This is not a universal authenticity verdict."

class CopyMoveAnalyzer(Analyzer):
    name="Exact overlapping-block shift clustering";version="1.0"
    def __init__(self,block_size=16,step=8,min_shift=24,min_cluster=3,max_dimension=1600): self.parameters={"block_size":block_size,"step":step,"min_shift":min_shift,"min_cluster":min_cluster,"max_dimension":max_dimension}
    def analyze(self,path,ground_truth=None):
        try:
            image=Image.open(path).convert("RGB");image.load()
        except Exception:
            return AnalysisResult("Unsupported","Failed","Failed",self.name,self.version,self.parameters,{},[],"The image could not be decoded.",[LIMITATION])
        if max(image.size)>self.parameters["max_dimension"]: image.thumbnail((self.parameters["max_dimension"],)*2)
        gray=np.asarray(image.convert("L"));b=self.parameters["block_size"];step=self.parameters["step"];groups=defaultdict(list)
        for y in range(0,max(0,gray.shape[0]-b+1),step):
            for x in range(0,max(0,gray.shape[1]-b+1),step): groups[gray[y:y+b,x:x+b].tobytes()].append((x,y))
        shifts=Counter();pairs=[]
        for points in groups.values():
            if 1<len(points)<=20:
                for i,a in enumerate(points):
                    for c in points[i+1:]:
                        dx,dy=c[0]-a[0],c[1]-a[1]
                        if abs(dx)+abs(dy)>=self.parameters["min_shift"]: shifts[(dx,dy)]+=1;pairs.append((a,c,(dx,dy)))
        accepted={shift for shift,count in shifts.items() if count>=self.parameters["min_cluster"]};mask=Image.new("L",image.size);draw=ImageDraw.Draw(mask);regions=[]
        for a,c,shift in pairs:
            if shift in accepted:
                for x,y in (a,c): draw.rectangle((x,y,x+b-1,y+b-1),fill=255);regions.append({"x":x,"y":y,"width":b,"height":b,"shift":{"dx":shift[0],"dy":shift[1]}})
        overlay=image.copy();od=ImageDraw.Draw(overlay,"RGBA")
        for region in regions: od.rectangle((region["x"],region["y"],region["x"]+b,region["y"]+b),fill=(255,65,54,70),outline=(255,30,20,220),width=2)
        mask_bytes=io.BytesIO();mask.save(mask_bytes,"PNG");overlay_bytes=io.BytesIO();overlay.save(overlay_bytes,"PNG")
        evaluation=None
        if ground_truth is not None:
            truth=Image.open(ground_truth).convert("L").resize(image.size,Image.Resampling.NEAREST);evaluation=mask_metrics(np.asarray(mask),np.asarray(truth))
        confidence=min(1.0,sum(shifts[s] for s in accepted)/max(1,(gray.shape[0]//step)*(gray.shape[1]//step)))
        return AnalysisResult("Supported","Succeeded","Completed",self.name,self.version,self.parameters,{"possible_regions":regions,"accepted_shift_clusters":[{"dx":s[0],"dy":s[1],"matching_blocks":shifts[s]} for s in sorted(accepted)],"similarity_score":round(confidence,6)},[{"kind":"copy_move_mask","suffix":".png","bytes":mask_bytes.getvalue()},{"kind":"copy_move_overlay","suffix":".png","bytes":overlay_bytes.getvalue()}],"Possible duplicated regions were localized." if regions else "No duplicated region met the configured exact-block threshold.",[LIMITATION,"The method detects exact repeated blocks and may miss resized, rotated, recompressed, or heavily edited copies."],evaluation)
