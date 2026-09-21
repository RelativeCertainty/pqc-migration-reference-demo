export type RecordData = Record<string, unknown>;
export type Role = 'analyst' | 'contributor' | 'contributor-two' | 'reviewer' | 'sponsor' | 'information-owner' | 'risk-lead' | 'business-reviewer' | 'viewer';
export type Session = { authenticated: boolean; role: Role | null; synthetic: true; csrfToken: string | null };
export type Baseline = {
  baselineId: string; inputSha256: string; asOf: string; tenantId: string;
  synthetic: true; assetCount: number; acceptanceStatus: string; sourceSystemWriteAuthority: false;
};
export type Family = {
  id: string; name: string; areaRef: string; assetCount: number; observationCount: number;
  status: 'synthetic_only'; profile?: RecordData;
};
export type Dashboard = {
  baseline: Baseline;
  counts: { assets: number; observations: number; dependencies: number; cryptographicUses: number;
    sourceFamilies: number; estateAreas: number; limitations: number; conflictedAssets: number;
    staleAssets: number; contextOnlyAssets: number; reports: number };
  families: Family[]; triageLanes: { id: string; count: number }[];
  limitations: { id: string; count: number }[]; boundary: string;
};
export type Asset = {
  id: string; displayName: string; familyIds: string[];
  status: 'conflict' | 'stale' | 'context_only' | 'evidence_present';
  hasConflict?: boolean; isStale?: boolean; isContextOnly?: boolean;
  observationCount: number; cryptographicUseCount: number; asset: RecordData;
};
export type AssetPage = { items: Asset[]; total: number; page: number; pageSize: number };
export type AssetDetail = { asset: Asset; observations: RecordData[]; dependencies: RecordData[];
  cryptographicUses: RecordData[]; limitations: RecordData[]; baseline: Baseline };
export type ReportMetadata = { id: string; phase: 'phase1' | 'phase2'; title: string; baselineId: string;
  inputSha256: string; createdAt: string; contentSha256: string; synthetic: true;
  acceptanceStatus: 'unaccepted'; workerRunId: string };
export type Report = { metadata: ReportMetadata; content: RecordData };
export type Run = { id: string; reportId: string | null; phase: string; status: string; actor: string;
  createdAt: string; manifestId: string; baselineId: string; result: { reportId?: string; contentSha256?: string; actionId?: string; artifactSha256?: string } };
