import type {ProvenanceReport} from './data/provenance';
import type {CaseRecord, Evidence, Finding, Note} from './model';

export function makeReportSnapshot(
  activeCase: CaseRecord,
  revision: number,
  preparer: string,
  sections: string[],
  evidence: Evidence[],
  findings: Finding[],
  notes: Note[],
  provenance?: ProvenanceReport | null,
) {
  return {
    schema_version: '1.0',
    project: 'PRATYAKSH',
    case: activeCase,
    revision,
    preparer,
    generated_at: new Date().toISOString(),
    fixture: evidence.some(item => item.fixture) || findings.some(finding => finding.fixture),
    sections,
    evidence: evidence.map(({source, ...record}) => record),
    findings,
    notes,
    provenance: provenance ? {
      analysis_id:provenance.analysis_id, report_sha256:provenance.report_sha256,
      methods:provenance.methods, limitations:provenance.limitations,
      images:provenance.images.map(image=>({id:image.id,case_evidence_id:image.case_evidence_id,
        filename:image.filename,sha256:image.sha256,comparison_area:image.comparison_area,
        video_coverage:image.video_coverage,metadata:image.metadata,metadata_status:image.metadata_status,
        credentials:{status:image.content_credentials.status,signature:image.content_credentials.signature,
          content_binding:image.content_credentials.content_binding,signer_trust:image.content_credentials.signer_trust,
          trust_policy:image.content_credentials.trust_policy}})),
      relationships:provenance.relationships,
      review_notes:provenance.review_notes,
    } : null,
    limitations: [
      'A hash match only describes the bytes at the time of verification.',
      'Checks without a finding were not assessed for this report.',
      ...(findings.some(finding => finding.fixture) ? ['Sample findings are illustrative. No forensic inference was performed.'] : []),
    ],
  };
}

export type ReportSnapshot = ReturnType<typeof makeReportSnapshot>;
