"""Inventory local datasets and import reviewed cross-dataset labels without changing splits."""
import argparse
from collections import Counter
import csv
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil

MEDIA={'.jpg':'image','.jpeg':'image','.png':'image','.webp':'image','.image':'image',
       '.mp4':'video','.avi':'video','.mov':'video','.mkv':'video','.webm':'video',
       '.wav':'audio','.flac':'audio','.mp3':'audio','.m4a':'audio'}


def sha256(path):
    digest=hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda:stream.read(1024*1024),b''):digest.update(block)
    return digest.hexdigest()


def inventory(roots):
    result=[]
    for value in roots:
        root=Path(value).resolve()
        if not root.is_dir():raise ValueError('Missing directory: '+str(root))
        counts=Counter();sizes=Counter();folders=Counter();archives=0;archive_bytes=0
        for path in root.rglob('*'):
            if path.is_symlink() or not path.is_file():continue
            kind=MEDIA.get(path.suffix.lower())
            if kind:
                counts[kind]+=1;sizes[kind]+=path.stat().st_size
                folders['/'.join(path.relative_to(root).parts[:2])]+=1
            elif path.suffix.lower() in {'.zip','.gz','.tar','.7z'}:
                archives+=1;archive_bytes+=path.stat().st_size
        result.append({'root':str(root),'media_counts':dict(counts),'media_bytes':dict(sizes),
                       'folder_counts':dict(folders),'archive_count':archives,'archive_bytes':archive_bytes})
    return {'created_at':datetime.now(timezone.utc).isoformat(),'roots':result,
            'free_disk_bytes':shutil.disk_usage(roots[0]).free,'status':'inventory_only',
            'notes':['Counts are files on disk, not independent examples or trained-on counts.',
                     'Decoding, labels, licences, identities and near-duplicate leakage remain to be audited.']}


def merge(index,budget_bytes):
    with Path(index).open(newline='',encoding='utf-8') as stream:rows=list(csv.DictReader(stream))
    samples=[];groups={};seen={};counts=Counter();total=0;duplicates=0
    for row in rows:
        required=['dataset','path','label','split','group_id','manipulation_type','ground_truth','terms','source_url']
        if any(not row.get(key,'').strip() for key in required):raise ValueError('Missing required dataset metadata')
        if row['label'] not in {'genuine','synthetic'} or row['split'] not in {'train','development','test'}:
            raise ValueError('Invalid label or split')
        # IDs intentionally have no dataset prefix: the same source across corpora must share its ID.
        group=row['group_id']
        if group in groups and groups[group]!=row['split']:raise ValueError('Source group crosses splits: '+group)
        groups[group]=row['split']
        path=(Path(index).resolve().parent/row['path']).resolve()
        if not path.is_file():raise ValueError('Missing media: '+str(path))
        modality=MEDIA.get(path.suffix.lower())
        if not modality:raise ValueError('Unsupported media type')
        total+=path.stat().st_size
        if total>budget_bytes:raise ValueError('Indexed files exceed expansion budget')
        fingerprint=sha256(path)
        if fingerprint in seen:
            previous=seen[fingerprint]
            if (previous['split'],previous['label'])!=(row['split'],row['label']):
                raise ValueError('Duplicate bytes cross splits or have conflicting labels')
            duplicates+=1;continue
        sample={'sample_id':row['dataset']+'-'+fingerprint,'path':str(path),'sha256':fingerprint,
                'label':row['label'],'split':row['split'],'group_id':group,'media_type':modality,
                'manipulation_type':row['manipulation_type'],
                'ground_truth':{'basis':row['ground_truth'],'reference':row['source_url']},
                'source':row['dataset']+' | '+row['source_url'],'terms':row['terms'],
                'transformation':row.get('transformation') or 'none'}
        samples.append(sample);seen[fingerprint]=sample
        counts[row['dataset']+'/'+row['split']+'/'+row['label']]+=1
    if not samples:raise ValueError('No media indexed')
    return {'schema_version':'1.1','name':'Pratyaksh dataset expansion',
            'created_at':datetime.now(timezone.utc).isoformat(),'samples':samples,
            'audit':{'index_sha256':sha256(index),'input_rows':len(rows),'unique_files':len(samples),
                     'duplicates_removed':duplicates,'indexed_bytes_before_deduplication':total,'counts':dict(counts),
                     'status':'metadata_and_byte_hash_audit_only',
                     'limitations':['Labels and terms are supplied by the index author; review original records.',
                                    'Near duplicates and related identities need a separate audit before training.',
                                    'Preserve official test splits and record overlap between related datasets.',
                                    'Audio and video labels must be assigned separately.']}}


def main():
    parser=argparse.ArgumentParser(description=__doc__);sub=parser.add_subparsers(dest='action',required=True)
    inv=sub.add_parser('inventory');inv.add_argument('--root',action='append',required=True)
    inv.add_argument('--output',type=Path,required=True)
    imp=sub.add_parser('merge');imp.add_argument('--index',type=Path,required=True)
    imp.add_argument('--output',type=Path,required=True);imp.add_argument('--budget-gb',type=float,default=20)
    args=parser.parse_args()
    if args.output.exists():parser.error('Use a new output path; previous records are retained')
    if args.action=='inventory':result=inventory(args.root)
    else:
        if not 0<args.budget_gb<=20:parser.error('This expansion is limited to the authorised 20 GB')
        result=merge(args.index,int(args.budget_gb*10**9))
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(result,indent=2)+'\n');print('Saved',args.output)
    if args.action=='inventory':
        for row in result['roots']:print(row['root'],row['media_counts'],'archives:',row['archive_count'])
    else:print(result['audit'])


if __name__=='__main__':main()
