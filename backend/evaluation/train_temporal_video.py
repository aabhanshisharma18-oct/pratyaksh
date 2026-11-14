"""Train a small face-sequence LSTM and compare it with UFD on frozen test clips.

Input: JSON list of {path, label: 0|1, split: train|development|test, group_id}.
All related source videos/identities must share one group_id. Split before extraction.
"""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
import math
from pathlib import Path
import random


def validate_manifest(rows, root):
    if not isinstance(rows,list) or not rows:
        raise ValueError('Manifest must be a nonempty list')
    groups, hashes = {}, {}
    result=[]
    for row in rows:
        split, label, group = row.get('split'), row.get('label'), row.get('group_id')
        if split not in {'train','development','test'} or type(label) is not int or label not in {0,1} or not isinstance(group,str) or not group.strip():
            raise ValueError('Each row needs split, integer label 0/1 and a nonempty group_id')
        if group in groups and groups[group] != split:
            raise ValueError('Related source group crosses splits: '+group)
        groups[group]=split
        path=(root/row['path']).resolve()
        if not path.is_file() or path.stat().st_size > 100*1024*1024:
            raise ValueError('Video missing or larger than 100 MiB: '+str(path))
        sha=hashlib.sha256(path.read_bytes()).hexdigest()
        if sha in hashes:
            raise ValueError('Duplicate video bytes in the manifest: '+str(path))
        hashes[sha]=split
        result.append({**row,'path':str(path),'sha256':sha})
    for split in ['train','development','test']:
        if any(sum(r['split']==split and r['label']==label for r in result)<2 for label in [0,1]):
            raise ValueError('Each split requires at least two videos from each class')
    return result


def metrics(labels,scores,threshold):
    counts={key:0 for key in ['tp','tn','fp','fn']}
    for label,score in zip(labels,scores):
        counts['tp' if label and score>=threshold else 'fn' if label else 'fp' if score>=threshold else 'tn']+=1
    tp,tn,fp,fn=(counts[k] for k in ['tp','tn','fp','fn'])
    n=len(labels)
    recall=tp/(tp+fn) if tp+fn else 0
    specificity=tn/(tn+fp) if tn+fp else 0
    accuracy=(tp+tn)/n if n else 0
    # Wilson interval for the measured sample accuracy, not an authenticity probability.
    z=1.96; den=1+z*z/n if n else 1
    centre=(accuracy+z*z/(2*n))/den if n else 0
    half=z*math.sqrt(accuracy*(1-accuracy)/n+z*z/(4*n*n))/den if n else 0
    return {'n':n,'confusion_matrix':counts,'accuracy':accuracy,'accuracy_95pct_wilson':[max(0,centre-half),min(1,centre+half)],
            'balanced_accuracy':(recall+specificity)/2,'recall_synthetic':recall,'false_positive_rate':1-specificity,
            'precision_synthetic':tp/(tp+fp) if tp+fp else 0}


def select_threshold(labels,scores):
    candidates=sorted(set([0.,1.,*scores]))
    return max(candidates,key=lambda t:(metrics(labels,scores,t)['balanced_accuracy'],-metrics(labels,scores,t)['false_positive_rate']))


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--epochs',type=int,default=8)
    parser.add_argument('--device',choices=['cpu','mps','cuda'],default='cpu')
    args=parser.parse_args()
    if not 1<=args.epochs<=100: parser.error('epochs must be between 1 and 100')
    rows=validate_manifest(json.loads(args.manifest.read_text()),args.manifest.resolve().parent)
    if args.output.exists(): parser.error('Use a new output directory; do not overwrite previous test results')
    args.output.mkdir(parents=True)
    import torch
    from detector import ImageDetector, CLIP_WEIGHTS_SHA256
    from temporal_video import FaceSequenceExtractor, PREPROCESSING, make_model, digest
    from video_probe import VideoSampler
    torch.manual_seed(20261114); random.seed(20261114)
    encoder=ImageDetector(); extractor=FaceSequenceExtractor(encoder); sampler=VideoSampler()
    clips={split:[] for split in ['train','development','test']}; failures=[]
    # Extract train/development only. Test bytes are not decoded until selection is frozen.
    def extract(row):
        sampled=None
        try:
            sampled=sampler.sample(Path(row['path']).read_bytes(),row['path'],temporal=True)
            if sampled['rejected']: raise ValueError('Frame decode failure')
            features,records=extractor.extract(sampled['frames'])
            baseline=sum(encoder.predict(f['image'])['deepfake_score'] for f in sampled['frames'])/len(sampled['frames'])
            return {**row,'features':features,'records':records,'baseline':baseline}
        except Exception as exc:
            failures.append({'sha256':row['sha256'],'split':row['split'],'reason':str(exc)})
            return None
        finally:
            if sampled:
                for frame in sampled['frames']: frame['image'].close()
    for row in rows:
        if row['split']=='test': continue
        clip=extract(row)
        if clip: clips[row['split']].append(clip)
        print(row['split'], 'scored' if clip else 'unscored', row['path'],flush=True)
    for split in ['train','development']:
        if {r['label'] for r in clips[split]}!={0,1}: raise ValueError('Both classes must remain after extraction in '+split)
    model=make_model().to(args.device)
    optimizer=torch.optim.AdamW(model.parameters(),lr=.001,weight_decay=.01)
    positive=sum(r['label'] for r in clips['train']); negative=len(clips['train'])-positive
    loss_fn=torch.nn.BCEWithLogitsLoss(pos_weight=torch.tensor(negative/positive,device=args.device))
    def scores_for(items):
        model.eval()
        with torch.inference_mode():
            return [float(torch.sigmoid(model(r['features'].unsqueeze(0).to(args.device)))[0]) for r in items]
    dev_labels=[r['label'] for r in clips['development']]
    best=-1; selected_epoch=0; selected_threshold=None
    for epoch in range(args.epochs):
        model.train(); random.shuffle(clips['train'])
        for row in clips['train']:
            optimizer.zero_grad()
            logits=model(row['features'].unsqueeze(0).to(args.device))
            loss=loss_fn(logits,torch.tensor([float(row['label'])],device=args.device))
            loss.backward(); torch.nn.utils.clip_grad_norm_(model.parameters(),1.); optimizer.step()
        scores=scores_for(clips['development']); threshold=select_threshold(dev_labels,scores)
        measured=metrics(dev_labels,scores,threshold)
        print('epoch',epoch+1,'development balanced accuracy',measured['balanced_accuracy'],flush=True)
        if measured['balanced_accuracy']>best:
            best=measured['balanced_accuracy']; selected_epoch=epoch+1; selected_threshold=threshold
            torch.save({k:v.detach().cpu() for k,v in model.state_dict().items()},args.output/'head.pt')
    baseline_cutoff=select_threshold(dev_labels,[r['baseline'] for r in clips['development']])
    model.load_state_dict(torch.load(args.output/'head.pt',map_location=args.device,weights_only=True))
    for row in rows:
        if row['split']=='test':
            clip=extract(row)
            if clip: clips['test'].append(clip)
    if {r['label'] for r in clips['test']}!={0,1}: raise ValueError('Test extraction needs both classes; do not deploy this checkpoint')
    labels=[r['label'] for r in clips['test']]; scores=scores_for(clips['test'])
    result={'checkpoint_sha256':digest(args.output/'head.pt'),'backbone_sha256':CLIP_WEIGHTS_SHA256,
            'preprocessing':PREPROCESSING,'threshold':selected_threshold,'selected_epoch':selected_epoch,
            'seed':20261114,'architecture':'frozen CLIP face embeddings + LSTM(768,64) + linear(64,1)',
            'test':metrics(labels,scores,selected_threshold),
            'baseline':{'method':'UFD mean of the same opening-window frames','threshold':baseline_cutoff,
                        **metrics(labels,[r['baseline'] for r in clips['test']],baseline_cutoff)},
            'coverage':{split:{'submitted':sum(r['split']==split for r in rows),'scored':len(items),
                               'classes':dict(Counter(r['label'] for r in items))} for split,items in clips.items()},
            'unscored':failures,'manifest_sha256':digest(args.manifest),
            'notes':['Thresholds and epoch selected on development only; test used once in this invocation.',
                     'Metrics exclude unscored videos; coverage and failures are reported separately.',
                     'Group assignments supplied by the user; related identities and re-encoded near-duplicates require independent review.',
                     'Baseline uses the same opening window; this is not a full-video benchmark or a calibrated probability.']}
    (args.output/'manifest.json').write_text(json.dumps(result,indent=2))
    (args.output/'test-predictions.json').write_text(json.dumps([{'sha256':r['sha256'],'label':r['label'],
       'temporal_score':score,'ufd_mean':r['baseline'],'timestamps_ms':[f['timestamp_ms'] for f in r['records']]} for r,score in zip(clips['test'],scores)],indent=2))
    print(json.dumps(result,indent=2))


if __name__=='__main__': main()
