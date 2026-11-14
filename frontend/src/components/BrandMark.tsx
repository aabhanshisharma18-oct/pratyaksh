import mark from '../assets/pratyaksh-mark.svg';

export function BrandMark({className}: {className:string}) {
  return <span className={className} aria-hidden="true">
    <img src={mark} alt="" width={40} height={40} style={{display:'block',width:'100%',height:'100%'}}/>
  </span>;
}
