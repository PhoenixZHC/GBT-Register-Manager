export type RegisterType = "R" | "P" | "PR";
export type CoordValue = "L" | "R";
export type ReadMode = "range" | "all";
export type ConflictPolicy = "overwrite" | "skip";

export interface ConnectionState {
  connected: boolean;
  /** 控制柜 IP（显示用）。 */
  ip: string;
  /** 示教器 IP（可选）。无示教器时为空。 */
  teachPanelIp?: string;
  /** 是否在本机启动代理服务（四轴无 TP 时应为 true）。 */
  localProxy?: boolean;
  message: string;
}

/** 连接请求参数，对应 Tauri 的 `connect_robot` 命令。 */
export interface ConnectRequest {
  controllerIp: string;
  teachPanelIp?: string;
  localProxy: boolean;
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
