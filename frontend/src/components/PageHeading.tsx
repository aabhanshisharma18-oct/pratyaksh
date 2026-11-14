import type {ReactNode} from 'react';

type Props = {eyebrow:ReactNode;title:string;subtitle?:string;children?:ReactNode;className?:string;standalone?:boolean};

export function PageHeading({eyebrow,title,subtitle,children,className,standalone=true}:Props) {
  return <header className={['page-heading',standalone?'standalone':null,className].filter(Boolean).join(' ')}>
    <div><div className="eyebrow">{eyebrow}</div><h1>{title}</h1>{subtitle && <p>{subtitle}</p>}</div>
    {children}
  </header>;
}
