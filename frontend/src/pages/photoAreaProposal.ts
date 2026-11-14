type PhotoArea = [number, number, number, number];

/** Find a large inset rectangle with consistent edges on all four sides. */
export function proposePhotoArea(image:HTMLImageElement):PhotoArea|undefined {
  const canvas=document.createElement('canvas');
  const scale=160/Math.max(image.naturalWidth,image.naturalHeight);
  const width=canvas.width=Math.round(image.naturalWidth*scale);
  const height=canvas.height=Math.round(image.naturalHeight*scale);
  if(Math.min(width,height)<40)return;
  const context=canvas.getContext('2d',{willReadFrequently:true});
  if(!context)return;
  context.drawImage(image,0,0,width,height);
  const {data}=context.getImageData(0,0,width,height);
  const rows=Array.from({length:height},()=>new Float32Array(width+1));
  const columns=Array.from({length:width},()=>new Float32Array(height+1));
  function contrast(a:number,b:number) {
    return (Math.abs(data[a]-data[b])+Math.abs(data[a+1]-data[b+1])+Math.abs(data[a+2]-data[b+2]))/3;
  }
  for(let y=0;y<height;y++)for(let x=0;x<width;x++){
    const offset=(y*width+x)*4;
    rows[y][x+1]=rows[y][x]+(y?Math.min(contrast(offset,offset-width*4)/25,1):0);
    columns[x][y+1]=columns[x][y]+(x?Math.min(contrast(offset,offset-4)/25,1):0);
  }
  function peaks(lines:Float32Array[]) {
    const ranked=lines.map((line,index)=>({index,value:line[line.length-1]}))
      .slice(3,-3).sort((a,b)=>b.value-a.value);
    const result:number[]=[];
    for(const {index} of ranked){
      if(result.every(previous=>Math.abs(index-previous)>=3))result.push(index);
      if(result.length===10)break;
    }
    return result.sort((a,b)=>a-b);
  }
  const xs=peaks(columns),ys=peaks(rows);
  let best:PhotoArea|undefined;
  let bestScore=0;
  for(const left of xs)for(const right of xs){
    const w=right-left;
    if(w<width*.25)continue;
    for(const top of ys)for(const bottom of ys){
      const h=bottom-top;
      const area=w*h/(width*height);
      if(h<height*.24||area<.13||area>.85||w/h>4||h/w>4)continue;
      const sides=[
        (rows[top][right]-rows[top][left])/w,
        (rows[bottom][right]-rows[bottom][left])/w,
        (columns[left][bottom]-columns[left][top])/h,
        (columns[right][bottom]-columns[right][top])/h,
      ];
      const weakest=Math.min(...sides);
      if(weakest<.38)continue;
      const score=weakest*.55+sides.reduce((a,b)=>a+b,0)*.075+area*.15;
      if(score>bestScore){
        bestScore=score;
        best=[left/width,top/height,right/width,bottom/height];
      }
    }
  }
  return best;
}
