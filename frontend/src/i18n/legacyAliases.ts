import type {MessageKey} from './locales/en';

/** English sentence compatibility aliases; remove entries as call sites move to semantic keys. */
export const legacyAliases:Readonly<Record<string,MessageKey>>={
  'Open':'common.open','Close':'common.close','Cancel':'common.cancel','Clear':'common.clear','Save':'common.save','Retry':'common.retry',
  'Loading…':'common.loading','Unavailable':'common.unavailable','Unknown':'common.unknown','Yes':'common.yes','No':'common.no',
  'Menu':'common.menu','Search':'common.search','Status':'common.status','Actions':'common.actions','Created':'common.created','Updated':'common.updated',
  'Evidence':'common.evidence','Findings':'common.findings','Notes':'common.notes','Source':'common.source','Result':'common.result',
  'Coverage':'common.coverage','Review':'common.review','Export':'common.export','Case list':'nav.caseList',
  'FRONTEND PROTOTYPE':'app.frontendPrototype','Analysis backend not connected':'app.backendDisconnected',
  'DEVELOPMENT FIXTURE · illustrative, not measured':'app.developmentFixture',
  'Precomputed fictional states · No live forensic analysis':'app.fixtureDescription',
  'Clarity through examination.':'app.clarityFooter','Workspace ready':'app.workspaceReady',
  'Not applicable':'run.notApplicable','Accepted':'findings.accepted',
  'Analyst record · does not change the machine result.':'findings.analystDoesNotChange',
  'Evaluation & benchmarks':'evaluation.title','Dataset':'evaluation.dataset','Model version':'evaluation.modelVersion',
  'Threshold':'evaluation.threshold','Run date':'evaluation.runDate','Not selected':'evaluation.notSelected',
  'No metrics were published for this state.':'evaluation.noMetrics','Published by':'evaluation.publishedBy',
  'Preview type not supported':'viewer.unsupported','Media preview could not be decoded':'viewer.decodeFailed',
  'Playback needs user action':'viewer.playbackAction','Preview timeline':'viewer.previewTimeline','Play':'viewer.play','Pause':'viewer.pause',
  'Mute':'viewer.mute','Unmute':'viewer.unmute','Zoom in':'viewer.zoomIn','Zoom out':'viewer.zoomOut','Reset zoom':'viewer.resetZoom',
  'Previous':'viewer.previous','Next':'viewer.next',
};
