type ArtifactRun={artifacts:Array<{artifact_id:string;kind:string}>};
export type ArtifactView={ref:string;resolved:boolean;kind:string|null;label:string};
export function resolveArtifacts(refs:string[],run?:ArtifactRun):ArtifactView[]{const index=new Map((run?.artifacts??[]).map(item=>[item.artifact_id,item]));return refs.map(ref=>{const item=index.get(ref);return{ref,resolved:Boolean(item),kind:item?.kind??null,label:item?`${ref} · ${item.kind}`:`${ref} · artifact not available in this build`}})}
