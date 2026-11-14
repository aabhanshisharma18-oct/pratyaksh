export const reportSections=[
 {id:'methods',label:'Methods and scope',required:true},
 {id:'evidence',label:'Evidence inventory',required:false},
 {id:'findings',label:'Forensic findings',required:true},
 {id:'coverage',label:'Examination coverage',required:true},
 {id:'notes',label:'Reviewer notes',required:false},
 {id:'limitations',label:'Limitations',required:true},
] as const;
export type ReportSection=typeof reportSections[number]['id'];
export const defaultSections:ReportSection[]=reportSections.map(section=>section.id);
export function savedSections(sections?:ReportSection[]):ReportSection[]{return sections??defaultSections}
export function sectionHeading(id:ReportSection,sections:ReportSection[]){
 const visible=reportSections.filter(section=>sections.includes(section.id));
 return `${visible.findIndex(section=>section.id===id)+1}. ${reportSections.find(section=>section.id===id)?.label}`;
}
