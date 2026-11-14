from __future__ import annotations
import numpy as np

def mask_metrics(predicted,truth):
    predicted=np.asarray(predicted)>0;truth=np.asarray(truth)>0
    if predicted.shape!=truth.shape: raise ValueError("Ground-truth mask dimensions must match evidence")
    tp=int(np.logical_and(predicted,truth).sum());fp=int(np.logical_and(predicted,~truth).sum());fn=int(np.logical_and(~predicted,truth).sum());tn=int(np.logical_and(~predicted,~truth).sum());union=tp+fp+fn
    safe=lambda n,d:float(n/d) if d else (1.0 if n==0 else 0.0)
    precision=safe(tp,tp+fp);recall=safe(tp,tp+fn)
    return {"iou":safe(tp,union),"pixel_agreement":safe(tp+tn,tp+tn+fp+fn),"precision":precision,"recall":recall,"f1":safe(2*precision*recall,precision+recall),"tp":tp,"fp":fp,"fn":fn,"tn":tn}

def frame_metrics(detected,truth):
    detected={tuple(sorted(map(int,p))) for p in detected};truth={tuple(sorted(map(int,p))) for p in truth};tp=len(detected&truth);fp=len(detected-truth);fn=len(truth-detected);safe=lambda n,d:float(n/d) if d else (1.0 if n==0 else 0.0);p=safe(tp,tp+fp);r=safe(tp,tp+fn)
    return {"precision":p,"recall":r,"f1":safe(2*p*r,p+r),"true_positive_pairs":tp,"false_positive_pairs":fp,"missed_pairs":fn}
