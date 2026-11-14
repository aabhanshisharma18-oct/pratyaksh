import type {Evidence, Finding} from './model';

export const SERVER_INTAKE = import.meta.env.DEV && import.meta.env.VITE_EVIDENCE_API === 'true';

type IntakeRecord = {
  evidence_id: string;
  case_id: string;
  filename: string;
  sha256: string;
  received_at: string;
  receipt_context: string;
  size_bytes: number;
  width: number;
  height: number;
  media_type: string;
};

export type Verification = {
  evidence_id: string;
  expected_sha256: string;
  actual_sha256: string | null;
  checked_at: string;
  status: 'match' | 'mismatch' | 'unavailable';
};

async function request<T>(url: string, init?: RequestInit): Promise<T> {
  const response = await fetch(url, init);
  if (!response.ok) {
    const body = await response.json().catch(() => null);
    throw new Error(typeof body?.detail === 'string' ? body.detail : 'Evidence service request failed.');
  }
  return response.json();
}

function asEvidence(record: IntakeRecord): Evidence {
  return {
    id: record.evidence_id,
    caseId: record.case_id,
    name: record.filename,
    hash: record.sha256,
    received: record.received_at,
    receiptContext: record.receipt_context,
    type: 'image',
    mime: record.media_type,
    sizeBytes: record.size_bytes,
    role: 'Evidence',
    size: (record.size_bytes / 1024 / 1024).toFixed(2) + ' MB',
    dimensions: record.width + ' × ' + record.height,
    duration: '—',
    fixture: false,
    status: 'Not analyzed',
    source: '/api/evidence/' + record.evidence_id + '/media',
  };
}

export async function listEvidence(caseId: string, signal: AbortSignal) {
  const records = await request<IntakeRecord[]>('/api/evidence?case_id=' + encodeURIComponent(caseId), {signal});
  return records.map(asEvidence);
}

export async function preserveEvidence(caseId: string, file: File, receiptContext: string) {
  const form = new FormData();
  form.set('file', file);
  form.set('case_id', caseId);
  form.set('receipt_context', receiptContext);
  return asEvidence(await request<IntakeRecord>('/api/evidence', {method: 'POST', body: form}));
}

export function verifyEvidence(id: string) {
  return request<Verification>('/api/evidence/' + encodeURIComponent(id) + '/verify', {method: 'POST'});
}

export function sampleFinding(evidenceId: string): Finding {
  const suffix = evidenceId.replace('EVID-', '');
  return {
    schema_version: '1.0',
    evidence_id: evidenceId,
    finding_id: 'F-' + suffix,
    run_id: 'RUN-' + suffix,
    category: 'synthetic_media',
    execution_status: 'completed',
    result: 'inconclusive',
    observation: 'Sample image finding for the reporting demonstration. No detector examined this image.',
    method: 'Synthetic media reporting fixture',
    method_version: 'fixture-1.0',
    scope: 'Illustrative whole-image result',
    score: null,
    location: null,
    support_refs: [],
    limitations: ['This finding was attached for demonstration. No forensic inference was performed.'],
    review_status: 'unreviewed',
    fixture: true,
  };
}
