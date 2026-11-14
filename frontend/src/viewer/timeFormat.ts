export function clampMs(value:number,durationMs=Number.POSITIVE_INFINITY):number{
 if(!Number.isFinite(value))return 0;
 return Math.round(Math.min(Math.max(0,value),Math.max(0,durationMs)));
}

export function formatTimeMs(value:number):string{
 const total=clampMs(value);
 const ms=total%1000;
 const seconds=Math.floor(total/1000)%60;
 const minutes=Math.floor(total/60000)%60;
 const hours=Math.floor(total/3600000);
 const tail=`${seconds.toString().padStart(2,'0')}.${ms.toString().padStart(3,'0')}`;
 return hours?`${hours}:${minutes.toString().padStart(2,'0')}:${tail}`:`${minutes.toString().padStart(2,'0')}:${tail}`;
}

export function parseTimeMs(input:string):number|null{
 const text=input.trim();if(!text)return null;
 const parts=text.split(':');if(parts.length>3||parts.some(part=>part===''))return null;
 const numbers=parts.map(Number);if(numbers.some(value=>!Number.isFinite(value)||value<0))return null;
 let seconds=0;
 if(numbers.length===1)seconds=numbers[0];
 if(numbers.length===2)seconds=numbers[0]*60+numbers[1];
 if(numbers.length===3)seconds=numbers[0]*3600+numbers[1]*60+numbers[2];
 if((numbers.length>1&&numbers.at(-1)!>=60)||(numbers.length===3&&numbers[1]>=60))return null;
 return Math.round(seconds*1000);
}

export function frameStepMs(fps?:number|null):{ms:number;approximate:boolean}{
 return Number.isFinite(fps)&&fps!>0?{ms:Math.max(1,Math.round(1000/fps!)),approximate:false}:{ms:40,approximate:true};
}
