import original from '../assets/synthetic-case/original.png';
import edited from '../assets/synthetic-case/edited.png';
import voice from '../assets/synthetic-case/voice.wav';

export const syntheticCase = {
  title:'Synthetic Demo · Suspicious Payment Request',
  description:'Fictional training case. A clerk received a payment request with a voice note and two versions of an image. Compare the exhibits, review the voice signal, and document your findings. The reference image contains a red tag. An edited version covers it with a patch from the same image. The voice note uses synthetic speech.',
};
const exhibits = [
  {url:original,name:'01-reference-tag.png',mime:'image/png',type:'image'},
  {url:original,name:'02-renamed-copy.png',mime:'image/png',type:'image'},
  {url:edited,name:'03-tag-covered.png',mime:'image/png',type:'image'},
  {url:voice,name:'04-synthetic-voice.wav',mime:'audio/wav',type:'audio'},
] as const;

export async function loadSyntheticExhibits() {
  return Promise.all(exhibits.map(async exhibit=>{
    const response=await fetch(exhibit.url);
    if(!response.ok)throw new Error('A synthetic case exhibit could not be loaded.');
    return {type:exhibit.type,file:new File([await response.blob()],exhibit.name,{type:exhibit.mime})};
  }));
}
