import { invoke } from "@tauri-apps/api/core";
import type {
  ApplyRequest,
  CommonResponse,
  ConnectionState,
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

export async function connectRobot(ip: string): Promise<ConnectionState> {
  return traceInvoke("connect_robot", { ip }, () => invoke("connect_robot", { ip }));
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
