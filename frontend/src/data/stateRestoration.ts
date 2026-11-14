export function restoreKnownId<T extends string>(value:unknown,known:readonly T[],fallback:T|null=null):T|null{return typeof value==='string'&&known.includes(value as T)?value as T:fallback}
export function readSession(key:string){try{return sessionStorage.getItem(key)}catch{return null}}
export function writeSession(key:string,value:string){try{sessionStorage.setItem(key,value)}catch{}}
