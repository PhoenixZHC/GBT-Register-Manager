export type RegisterType = "R" | "P" | "PR";
export type CoordValue = "L" | "R";
export type ReadMode = "range" | "all";
export type ConflictPolicy = "overwrite" | "skip";

export interface ConnectionState {
  connected: boolean;
  ip: string;
  message: string;
}

export interface RangeSelector {
  mode: ReadMode;
  startId: number;
  endId: number;
}

export interface PreviewRowR {
  type: string;
  ID: number;
  value: number;
}

export interface PreviewRowP {
  Type: string;
  ID: number;
  X: number;
  Y: number;
  Z: number;
  A: number;
  B: number;
  C: number;
  TF: number;
  UF: number;
  Coord: CoordValue;
}

export interface PreviewRowPR {
  TYPE: string;
  ID: number;
  X: number;
  Y: number;
  Z: number;
  A: number;
  B: number;
  C: number;
  coord: CoordValue;
}

export type PreviewRow = PreviewRowR | PreviewRowP | PreviewRowPR;

export interface ReadRequest {
  registerType: RegisterType;
  programName?: string;
  selector: RangeSelector;
}

export interface ApplyRequest {
  registerType: RegisterType;
  programName?: string;
  conflictPolicy: ConflictPolicy;
  rows: Record<string, unknown>[];
}

export interface CommonResponse {
  ok: boolean;
  message: string;
  details?: string[];
}

/** 机器人侧信息（由 SDK 读取） */
export interface RobotMeta {
  model: string;
  controllerVersion: string;
}
