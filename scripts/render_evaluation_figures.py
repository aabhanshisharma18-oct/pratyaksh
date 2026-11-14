"""Render published aggregate counts; no models, training data or invented predictions."""
import argparse
import json
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle

ROOT=Path(__file__).resolve().parents[1]

def draw(ax,result):
    cm=result['confusion_matrix'];values=[[cm['tn'],cm['fp']],[cm['fn'],cm['tp']]]
    assert all(isinstance(v,int) and v>=0 for row in values for v in row)
    assert sum(sum(row) for row in values)==result['scored']
    words=[['Correct genuine','False alarm'],['Missed synthetic','Correct synthetic']]
    for row in range(2):
        for col in range(2):
            ax.add_patch(Rectangle((col-.5,row-.5),1,1,facecolor='#d4eee8' if row==col else '#fae3df',edgecolor='white',lw=3))
            ax.text(col,row-.07,f'{values[row][col]:,}',ha='center',va='center',fontsize=22,fontweight='bold',color='#17344b')
            ax.text(col,row+.20,words[row][col],ha='center',va='center',fontsize=10,color='#324b5c')
    ax.set(xlim=(-.5,1.5),ylim=(1.5,-.5),xticks=[0,1],yticks=[0,1],
           xticklabels=['Predicted genuine','Predicted synthetic'],yticklabels=['Actual genuine','Actual synthetic'])
    ax.tick_params(length=0,pad=8,labelsize=10)
    for spine in ax.spines.values():spine.set_visible(False)
    ax.set_aspect('equal')
    ax.set_title(result['title'],fontsize=14,fontweight='bold',color='#17344b',pad=20)
    return f"Accuracy {result['accuracy']:.2%}  |  Synthetic recall {result['synthetic_recall']:.2%}\nFalse alarms {result['false_positive_rate']:.2%}  |  Scored {result['scored']:,}/{result['selected']:,}"


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--summary',type=Path,default=ROOT/'docs/evaluation/results-summary.json')
    parser.add_argument('--output',type=Path,default=ROOT/'docs/evaluation/figures');args=parser.parse_args()
    data=json.loads(args.summary.read_text());by_id={r['id']:r for r in data['results']};args.output.mkdir(parents=True,exist_ok=True)
    groups=[('sbi-confusion',['sbi-still-images'],'Still-image pilot · test reused · 315 unscored images excluded'),
            ('audio-confusion',['aasist-asvspoof'],'ASVspoof 2019 LA balanced pilot · 27 rejected clips excluded'),
            ('whole-image-confusion',['ufd-genimage','clip-head-genimage'],'Tiny-GenImage pilot · same 96 sources × 3 correlated variants · offline comparison')]
    for name,ids,subtitle in groups:
        fig,axes=plt.subplots(1,len(ids),figsize=(7*len(ids),6.1),squeeze=False)
        for ax,id in zip(axes[0],ids):
            foot=draw(ax,by_id[id]);ax.text(.5,-.19,foot,transform=ax.transAxes,ha='center',va='top',fontsize=10,color='#324b5c')
        fig.suptitle(subtitle,fontsize=11,color='#405968',y=.96)
        fig.subplots_adjust(left=.19 if len(ids)==1 else .1,right=.97,top=.82,bottom=.25,wspace=.7)
        fig.text(.5,.035,'Dataset-specific screening results, not a probability that an uploaded file is fake.',ha='center',fontsize=9,color='#526574')
        for extension in ['png','svg']:fig.savefig(args.output/(name+'.'+extension),dpi=170,facecolor='white')
        svg=args.output/(name+'.svg')
        svg.write_text('\n'.join(line.rstrip() for line in svg.read_text().splitlines())+'\n')
        plt.close(fig)
    print('Rendered three confusion-matrix figures from four recorded model results.')


if __name__=='__main__':main()
