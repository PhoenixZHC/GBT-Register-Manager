import { invoke } from "@tauri-apps/api/core";
import type {
  ApplyRequest,
  CommonResponse,
  ConnectionState,
  ConnectRequest,
  ExtensionInfo,
  ReadRequest,
  RegisterType,
  RobotMeta
} from "../types";

const LOG = "[GBT-UI]";

function summarizeArgs(command: string, args: Record<string, unknown>): unknown {
  if (command === "apply_registers" && args.req && typeof args.req === "object") {
    const r = args.req as ApplyRequest;
    return {
      registerType: r.registerType,
      programName: r.programName,
      conflictPolicy: r.conflictPolicy,
      rowCount: r.rows.length
    };
  }
  if (command === "read_registers" && args.req && typeof args.req === "object") {
    const r = args.req as ReadRequest;
    return {
      registerType: r.registerType,
      programName: r.programName,
      selector: r.selector
    };
  }
  if (command === "export_preview_to_excel" && Array.isArray(args.rows)) {
    return { registerType: args.registerType, rowCount: args.rows.length };
  }
  return args;
}

function summarizeResult(command: string, result: unknown): unknown {
  if (command === "read_registers" && Array.isArray(result)) {
    return { rowCount: result.length };
  }
  if (command === "apply_registers" && result && typeof result === "object") {
    const r = result as CommonResponse;
    return { ok: r.ok, message: r.message, detailCount: r.details?.length ?? 0 };
  }
  if (command === "connect_robot" && result && typeof result === "object") {
    const r = result as ConnectionState;
    return { connected: r.connected, message: r.message };
  }
  if (
    (command === "export_preview_to_excel" || command === "export_template_excel") &&
    result &&
    typeof result === "object"
  ) {
    const r = result as CommonResponse;
    return { ok: r.ok, message: r.message };
  }
  return result;
}

const QUIET_COMMANDS = new Set(["get_connection_status", "get_app_version"]);

async function traceInvoke<T>(command: string, args: Record<string, unknown>, fn: () => Promise<T>): Promise<T> {
  const t0 = performance.now();
  const quiet = QUIET_COMMANDS.has(command);
  const logStart = quiet ? console.debug.bind(console) : console.info.bind(console);
  const logEnd = quiet ? console.debug.bind(console) : console.info.bind(console);
  logStart(`${LOG} ${command} → start`, summarizeArgs(command, args));
  try {
    const out = await fn();
    logEnd(
      `${LOG} ${command} → ok (${Math.round(performance.now() - t0)}ms)`,
      summarizeResult(command, out)
    );
    return out;
  } catch (e) {
    console.error(`${LOG} ${command} → error (${Math.round(performance.now() - t0)}ms)`, e);
    throw e;
  }
}

export async function connectRobot(req: ConnectRequest): Promise<ConnectionState> {
  return traceInvoke("connect_robot", { req }, () => invoke("connect_robot", { req }));
}

export async function getConnectionStatus(): Promise<ConnectionState> {
  return traceInvoke("get_connection_status", {}, () => invoke("get_connection_status"));
}

export async function disconnectRobot(): Promise<CommonResponse> {
  return traceInvoke("disconnect_robot", {}, () => invoke("disconnect_robot"));
}

export async function readRegisters(req: ReadRequest): Promise<Record<string, unknown>[]> {
  return traceInvoke("read_registers", { req }, () => invoke("read_registers", { req }));
}

export async function applyRegisters(req: ApplyRequest): Promise<CommonResponse> {
  return traceInvoke("apply_registers", { req }, () => invoke("apply_registers", { req }));
}

export async function exportPreviewToExcel(
  registerType: RegisterType,
  rows: Record<string, unknown>[]
): Promise<CommonResponse> {
  return traceInvoke(
    "export_preview_to_excel",
    { registerType, rows },
    () => invoke("export_preview_to_excel", { registerType, rows })
  );
}

export async function exportTemplate(registerType: RegisterType): Promise<CommonResponse> {
  return traceInvoke("export_template_excel", { registerType }, () =>
    invoke("export_template_excel", { registerType })
  );
}

export async function getAppVersion(): Promise<string> {
  return traceInvoke("get_app_version", {}, () => invoke("get_app_version"));
}

export async function fetchRobotMeta(): Promise<RobotMeta> {
  return traceInvoke("fetch_robot_meta", {}, () => invoke("fetch_robot_meta"));
}

/** 通过 SSH 执行 `pip3.12 list` 解析 Agilebot.Robot.SDK.A 版本（展示为 `+` 前主版本）；P/C/S 在填写示教器 IP 时走示教器，否则由后端返回空串。 */
export async function fetchRobotSdkVersion(modelHint?: string | null): Promise<string> {
  return traceInvoke("fetch_robot_sdk_version", { modelHint }, () =>
    invoke("fetch_robot_sdk_version", { modelHint: modelHint?.trim() || null })
  );
}

export async function installRobotExtension(localPath: string, modelHint?: string | null): Promise<ExtensionInfo> {
  return traceInvoke("install_robot_extension", { localPath, modelHint }, () =>
    invoke("install_robot_extension", {
      localPath,
      modelHint: modelHint?.trim() || null
    })
  );
}

export async function installRobotWheel(localPath: string, modelHint?: string | null): Promise<CommonResponse> {
  return traceInvoke("install_robot_wheel", { localPath, modelHint }, () =>
    invoke("install_robot_wheel", {
      localPath,
      modelHint: modelHint?.trim() || null
    })
  );
}

export interface ExportControllerLogsRequest {
  controllerIp: string;
  dateYyyyMmDd: string;
  sessionId?: number;
  progressOpId?: number;
}

export interface ExportTeachPanelLogsRequest {
  controllerIp: string;
  teachPanelIp: string;
  dateYyyyMmDd: string;
  sessionId?: number;
  progressOpId?: number;
}

export interface ExportProgramDataRequest {
  controllerIp: string;
  sessionId?: number;
  progressOpId?: number;
}

export async function exportControllerLogsZip(req: ExportControllerLogsRequest): Promise<CommonResponse> {
  return traceInvoke(
    "export_controller_logs_zip",
    { req },
    () => invoke("export_controller_logs_zip", { req })
  );
}

export async function exportTeachPanelLogsZip(req: ExportTeachPanelLogsRequest): Promise<CommonResponse> {
  return traceInvoke(
    "export_teach_panel_logs_zip",
    { req },
    () => invoke("export_teach_panel_logs_zip", { req })
  );
}

export async function exportProgramDataZip(req: ExportProgramDataRequest): Promise<CommonResponse> {
  return traceInvoke(
    "export_program_data_zip",
    { req },
    () => invoke("export_program_data_zip", { req })
  );
}
