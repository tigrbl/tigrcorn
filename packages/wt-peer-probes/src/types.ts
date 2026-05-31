export type ProbeStageStatus = "pass" | "fail" | "skip";

export type WTPeerProbeStages = {
  api: ProbeStageStatus;
  ready: ProbeStageStatus;
  bidi: ProbeStageStatus;
  unidi: ProbeStageStatus;
  datagram: ProbeStageStatus;
  close: ProbeStageStatus;
};

export type WTPeerProbeReport = {
  probe: "tigrcorn.wt.peer";
  version: 1;
  peerId: string;
  runId: string;
  wtUrl: string;
  userAgent: string;
  platform: string;
  browserHints?: Record<string, unknown>;
  stages: WTPeerProbeStages;
  timingsMs: Record<string, number>;
  errors: Record<string, string>;
  ok: boolean;
};

export type WTPeerProbeOptions = {
  peerId: string;
  wtUrl: string;
  reportUrl?: string;
  timeoutMs?: number;
  requireDatagram?: boolean;
};
