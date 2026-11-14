export const en={
  meta:{title:'Pratyaksh | Multimedia Forensics'},
  language:{
    groupLabel:'Language',
    switchTo:'Switch to {language}',
  },
  common:{
    open:'Open',close:'Close',cancel:'Cancel',clear:'Clear',save:'Save',retry:'Retry',loading:'Loading…',
    unavailable:'Unavailable',unknown:'Unknown',none:'None',yes:'Yes',no:'No',details:'Details',help:'Help',
    menu:'Menu',search:'Search',status:'Status',actions:'Actions',created:'Created',updated:'Updated',
    evidence:'Evidence',findings:'Findings',limitations:'Limitations',notes:'Notes',method:'Method',version:'Version',
    source:'Source',result:'Result',scope:'Scope',coverage:'Coverage',review:'Review',export:'Export',
    item_one:'{count} item',item_other:'{count} items',note_one:'{count} note',note_other:'{count} notes',
  },
  nav:{
    primary:'Primary navigation',skipToContent:'Skip to content',workspace:'Workspace',resources:'Resources',
    cases:'Cases',deepfakeDetection:'Deepfake Detection',authentication:'Authentication & Tampering',mediaAnalysis:'Media Analysis',
    provenance:'Provenance & Source Attribution',provenanceComparison:'Provenance & Comparison',explainability:'Explainable AI Dashboard',reports:'Reports',reviewReport:'Review & Report',evaluation:'Evaluation',overview:'Overview',
    evidence:'Evidence',auditLog:'Audit log',methodsLimits:'Methods & limits',settings:'Settings',
    closeNavigation:'Close navigation',openMenu:'Menu',caseList:'Case list',
  },
  app:{
    multimediaForensics:'Multimedia forensics',investigationWorkspace:'Investigation workspace',localPrototype:'Local prototype',searchPlaceholder:'Search evidence, IDs, hashes…',
    switchTheme:'Switch theme',workspaceContained:'Your workspace, contained.',browserSession:'Browser-local demo session',
    demoAnalyst:'Demo analyst',singleUserWorkspace:'Single-user workspace',frontendPrototype:'Frontend prototype',
    backendDisconnected:'Analysis backend not connected',developmentFixture:'Development fixture · illustrative, not measured',
    fixtureDescription:'Precomputed fictional states · No live forensic analysis',clarityFooter:'PRATYAKSH / Clarity through examination.',
    workspaceReady:'Workspace ready / v0.1.0',
  },
  session:{
    originalsPreserved:'Originals preserved and available to case analysis.',originalPreserved:'Original preserved. SHA-256 and receipt recorded.',
    serverIntake:'Server intake: {evidenceId}',inventoryRegistered:'Inventory registered: {filename} · client-declared SHA-256 · file not preserved · {receipt}',
    duplicateHash:'Duplicate hash also appears on {evidenceIds}.',inventoryAdded:'Inventory record added. File remains in browser memory and is not preserved on the server.',
    caseCreated:'Case created: {caseId} · creator self-declared',persistentCaseCreated:'Persistent case created on the server.',localCaseCreated:'Case created in this browser.',
    reviewerNotesUpdated:'Reviewer notes updated: {findingId} · self-declared analyst',fixtureRunRequested:'Simulated fixture run requested: {runId} · no analysis executed',
    analysisNotSent:'Analysis request not sent: {runId} · backend not connected',analysisQueued:'Persistent analysis queued: {runId}',
    newRunQueued:'New run {runId} queued.',runRecordedFailed:'Run {runId} recorded as failed. The request was not sent.',
    analysisFinished:'Persistent analysis finished. Review its coverage and findings.',retryRequested:'Retry requested for {oldRunId} → new {newRunId} (attempt {attempt})',
    retryQueued:'Retry requested: new run {newRunId} queued. {oldRunId} is unchanged.',verification:'SHA-256 verification: {evidenceId} · {status}',
    saveSampleFailed:'Unable to save the sample finding in this browser.',sampleAttached:'Illustrative finding attached. No model ran.',
    saveReportFailed:'Unable to save the report in this browser.',reportSaved:'Report revision saved. PDF and JSON use this snapshot.',
    fixtureFindingsLoaded:'FIXTURE · RUN-003 precomputed sample findings loaded',fixtureReferenceAdded:'FIXTURE · REF-001 added to the reference collection',
    fixtureCaseCreated:'FIXTURE · CASE-2026-014 created for the fictional scenario',fixtureEvent:'Illustrative event, not a real server record',
    browserAction:'Browser-session action · Demo analyst',fixtureBadge:'Fixture',localBadge:'Local',
  },
  landing:{
    heroLabel:'Pratyaksh multimedia forensics',heroAlt:'Pratyaksh digital forensics hero banner',home:'Pratyaksh home',
    environment:'Environment',capabilities:'Capabilities',pipeline:'Pipeline',preview:'Preview',compliance:'Compliance',
    getStarted:'Get started',viewSampleReport:'View Sample Report',chooseCase:'Choose a case',
    chooseCaseDescription:'Create an investigation or open an existing case.',addEvidence:'Add evidence',
    addEvidenceDescription:'Add an image, audio clip or video to the case.',reviewFindings:'Review findings',
    reviewFindingsDescription:'Inspect available findings and their limitations, then prepare a report.',openWorkspace:'Professional dashboard',checkSuspiciousFile:'Personal dashboard',
    previewTimeline:'Preview timeline',seekPercent:'Seek to {percent} percent',
    nationalCybercrimeInfo:'National cybercrime reporting information',copyright:'© 2026 Pratyaksh prototype',
    infrastructureAlt:'Abstract Indian digital infrastructure with a mobile device, city skyline and data racks',
    portraitAlt:'Public-domain 1839 Robert Cornelius self-portrait used as demonstration reference media',
    audioPortraitAlt:'Public-domain historical portrait accompanying the public-domain speech sample',
  },
  cases:{
    eyebrow:'Case list',description:'Every piece of evidence. One connected investigation.',newCase:'New case',
    search:'Search cases',allStatuses:'All statuses',sort:'Sort cases',newestFirst:'Newest first',oldestFirst:'Oldest first',
    lastActivityNewest:'Last activity · newest',lastActivityOldest:'Last activity · oldest',titleSort:'Title',
    noDescription:'No case description recorded.',lastActivity:'Last activity',evidenceItems:'Evidence items',
    processingStatus:'Processing status',active:'{count} active',failed:'{count} failed',completedFixtures:'Completed fixture records',
    openCase:'Open case',noMatching:'No matching cases',tryAnotherFilter:'Try another search or status filter.',
    empty:'No cases yet',emptyDescription:'Create a browser-local investigation workspace to begin.',createFirst:'Create your first case',
  },
  activity:{
    caseCreated:'Case created',evidenceRegistered:'Evidence registered',findingRecorded:'Finding recorded',reviewerNote:'Reviewer note',
    runStarted:'Run started',runCompleted:'Run completed',runFailed:'Run failed',runPartial:'Run partial',open:'Open',
    recent:'Recent activity',recentDescription:'Latest persistent case events.',viewAll:'View all',loading:'Loading activity…',
    loadError:'Activity could not be loaded.',empty:'No activity yet',emptyDescription:'Case changes will appear here.',
    eventType:'Event type',allEvents:'All events',evidenceId:'Evidence ID',actor:'Actor',from:'From',to:'To',
    noMatching:'No matching activity',clearFilters:'Try clearing one or more filters.',loadMore:'Load more',
  },
  evidenceTable:{
    empty:'No evidence found',emptyDescription:'Add evidence or try another search.',addEvidence:'Add evidence',selectAll:'Select all evidence',
    selectItem:'Select {name}',evidence:'Evidence',type:'Type',latestRun:'Latest run',fourChannel:'Four-channel review',
    added:'Added',links:'Links',notExamined:'Not examined',noRun:'No run',fixture:'Fixture',provenance:'Provenance',reports:'Reports',
    openItem:'Open {name}',select:'Select',
  },
  run:{
    queued:'Queued',running:'Running',completed:'Completed',partial:'Partial',failed:'Failed',unsupported:'Unsupported',
    notApplicable:'Not applicable',cancelled:'Cancelled',details:'Run details',closeDetails:'Close run details',attempt:'Attempt',
    origin:'Origin',requested:'Requested',started:'Started',configuration:'Configuration',channels:'Channels',coverage:'Coverage',
    samplingStrategy:'Sampling strategy',artifacts:'Artifacts',statusReason:'Status reason',backendStatus:'Backend status',
    sampledTimestamps:'Sampled timestamps',timestampUnavailable:'Timestamp unavailable',errors:'Errors',noErrors:'No run errors recorded.',
    exportJson:'Export run JSON',notReported:'Not reported',simulated:'simulated',completedAt:'Completed',retryable:'retryable',
    analysisRuns:'Analysis runs',noRunRecorded:'No run recorded',attemptLabel:'Attempt {attempt}',retryOf:'Retry of {runId}',simulatedFixture:'Simulated fixture run',
    requestedAt:'Requested {date}',startedAt:'Started {date}',completedOn:'Completed {date}',duration:'Duration {duration}',config:'Config {version}',
    plannedCoverage:'{examined} of {planned} planned samples examined; {unexamined} unexamined.',coverageNotReported:'Coverage not reported.',
    viewFindings:'View findings',retryNew:'Retry (new run)',noRuns:'No analysis runs',noRunsDescription:'Request analysis to create an immutable attempt record.',
    statusQueuedDescription:'Waiting to start. No results yet.',statusRunningDescription:'In progress.',
    statusCompletedDescription:'All requested checks finished. A completed run is not a clean result; read each finding.',
    statusPartialDescription:'Some checks finished; others did not.',statusFailedDescription:'The run failed. No assessment is implied.',
    statusUnsupportedDescription:'This media type or capability is unsupported. No assessment.',
    statusCancelledDescription:'Stopped before completion. No assessment unless findings are recorded.',
    coverageSummary:'{examined}/{planned} examined',coveragePercent:'{percent}% of requested samples',
    partialCoverage:'Partial coverage: {count} requested sample(s) were not examined. This is not a pass.',
  },
  findings:{
    analystReview:'Analyst review',machineResult:'Machine result',reviewerNotes:'Reviewer notes',unreviewed:'Unreviewed',
    reviewed:'Reviewed',questioned:'Questioned',accepted:'Accepted',recordNote:'Record your interpretation, question or next step…',
    addNote:'Add note',saving:'Saving…',status:'Status',note:'Note',noNotes:'No analyst notes have been recorded for this finding.',
    persistentRecords:'Persistent server records',browserRecords:'Browser-only records',
    automatedUnchanged:'Automated record · unchanged by analyst notes.',
    analystDoesNotChange:'Analyst record · does not change the machine result.',loadingNotes:'Loading reviewer notes…',
    notesLoadError:'Notes could not be loaded',noteSaveError:'Note could not be saved',draftPreserved:'{error}. Your draft is preserved; retrying is possible.',
    serverTimestamp:'Server timestamp {timestamp}',selfDeclared:'self-declared',browserOnlySuffix:'recorded in this browser only',latest:'latest {date}',
  },
  technical:{
    title:'Technical details',close:'Close technical details',finding:'Finding',run:'Run',executionStatus:'Execution status',
    analysisResult:'Analysis result',noResult:'No result',supportingArtifact:'Supporting artifact',location:'Location',notProvided:'Not provided',
    noLimitations:'No limitations recorded: treat this record as incomplete.',exportRaw:'Export raw finding',
  },
  evaluation:{
    title:'Evaluation & benchmarks',dataset:'Dataset',modelVersion:'Model version',threshold:'Threshold',runDate:'Run date',
    notSelected:'Not selected',noMetrics:'No metrics were published for this state.',publishedBy:'Published by {publisher}',
    thresholdSelection:'{value} · {objective} on {split}',coverageSummary:'Coverage: {examined} examined of {total}; {failed} failed; {abstained} abstained.',
    publisherRecord:'self-declared publisher record',loading:'Loading published evaluation results…',
    image:'Image',audio:'Audio',video:'Video',invalidPublisher:'{error}. Retry after the publisher corrects or restores the file.',
  },
  viewer:{
    unsupported:'Preview type not supported',decodeFailed:'Media preview could not be decoded',playbackAction:'Playback needs user action',
    previewTimeline:'Preview timeline',play:'Play',pause:'Pause',mute:'Mute',unmute:'Unmute',zoomIn:'Zoom in',zoomOut:'Zoom out',
    resetZoom:'Reset zoom',previous:'Previous',next:'Next',
  },
  time:{justNow:'just now'},
} as const;

type DotPath<T>=T extends string?never:{[K in keyof T&string]:T[K] extends string?K:T[K] extends Record<string,unknown>?`${K}.${DotPath<T[K]>}`:never}[keyof T&string];
export type MessageKey=DotPath<typeof en>;

export function flattenMessages(source:Record<string,unknown>,prefix=''):Record<string,string>{
  const result:Record<string,string>={};
  for(const [key,value] of Object.entries(source)){
    const path=prefix?`${prefix}.${key}`:key;
    if(typeof value==='string')result[path]=value;
    else if(value&&typeof value==='object')Object.assign(result,flattenMessages(value as Record<string,unknown>,path));
  }
  return result;
}

export const EN_MESSAGES=flattenMessages(en) as Readonly<Record<MessageKey,string>>;
