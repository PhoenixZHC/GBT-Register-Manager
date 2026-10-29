import * as XLSX from "xlsx";
import type { RegisterType } from "../types";

/** 用户可翻译的 Excel 解析错误（在界面层用 i18n 渲染 message） */
export class ExcelUserError extends Error {
  readonly params?: Record<string, string>;

  constructor(messageKey: string, params?: Record<string, string>) {
    super(messageKey);
    this.name = "ExcelUserError";
    this.params = params;
  }
}

/** 导入时的保护阈值，避免用户误选超大表格导致渲染进程 OOM / 白屏。 */
export const IMPORT_MAX_FILE_BYTES = 10 * 1024 * 1024; // 10 MiB
export const IMPORT_MAX_ROWS = 50_000;

const legacyHeaders = {
  R: ["type", "ID", "value"],
  P: ["Type", "ID", "X", "Y", "Z", "A", "B", "C", "TF", "UF", "Coord"],
  PR: ["TYPE", "ID", "X", "Y", "Z", "A", "B", "C", "coord"]
} as const;

/** 旧版表头最后一列，导入时仍兼容 */
const LEGACY_LAST_HEADER: Record<RegisterType, string | null> = {
  R: null,
  P: "Coord（L/R）",
  PR: "coord（L/R）"
};

export function expectedHeaders(registerType: RegisterType): string[] {
  if (registerType === "R") return [...legacyHeaders.R];
  return [registerType === "P" ? "Type" : "TYPE", "ID", "PoseType", ..."XYZABC",
    ...Array.from({ length: 9 }, (_, i) => `J${i + 1}`),
    ...(registerType === "P" ? ["TF", "UF", "Coord"] : ["coord"]),
    "WristFlip", "ArmUpDown", "ArmBackFront", ...Array.from({ length: 9 }, (_, i) => `Turn${i + 1}`),
    "Name", "Comment"];
}

function matchedHeaders(header: string[], registerType: RegisterType): string[] | null {
  const modern = expectedHeaders(registerType);
  if (header.length === modern.length && header.every((value, i) => value === modern[i])) return modern;
  const expected = [...legacyHeaders[registerType]];
  if (header.length !== expected.length) return null;
  const last = expected.length - 1;
  for (let i = 0; i < expected.length; i++) {
    if (header[i] === expected[i]) continue;
    const legacy = LEGACY_LAST_HEADER[registerType];
    if (i === last && legacy && header[i] === legacy) continue;
    return null;
  }
  return expected;
}

export function parseExcelForPreview(file: File, registerType: RegisterType): Promise<Record<string, unknown>[]> {
  return new Promise((resolve, reject) => {
    if (file.size > IMPORT_MAX_FILE_BYTES) {
      reject(
        new ExcelUserError("excel.tooLarge", {
          limitMb: String(Math.round(IMPORT_MAX_FILE_BYTES / 1024 / 1024))
        })
      );
      return;
    }

    const reader = new FileReader();
    reader.onload = () => {
      try {
        const wb = XLSX.read(reader.result, { type: "array" });
        const firstSheet = wb.SheetNames[0];
        const ws = wb.Sheets[firstSheet];
        const matrix = XLSX.utils.sheet_to_json<(string | number)[]>(ws, { header: 1, raw: true });
        if (!matrix.length) {
          reject(new ExcelUserError("excel.empty"));
          return;
        }

        const header = (matrix[0] || []).map((cell) => String(cell ?? "").trim());
        const expected = matchedHeaders(header, registerType);
        if (!expected) {
          reject(
            new ExcelUserError("excel.headerMismatch", {
              expected: expectedHeaders(registerType).join(", "),
              actual: header.join(", ")
            })
          );
          return;
        }

        const dataRows = matrix
          .slice(1)
          .filter((row) => row.some((col) => String(col ?? "").trim() !== ""));

        if (dataRows.length > IMPORT_MAX_ROWS) {
          reject(
            new ExcelUserError("excel.tooManyRows", {
              limit: String(IMPORT_MAX_ROWS),
              actual: String(dataRows.length)
            })
          );
          return;
        }

        const rows = dataRows.map((row) => {
          const normalized: Record<string, unknown> = {};
          expected.forEach((key, idx) => {
            const value = row[idx];
            // 保留原始值供写入前校验，不能先舍入 ID/TF/UF 掩盖非法小数。
            normalized[key] = value;
          });
          return normalized;
        });

        resolve(rows);
      } catch (err) {
        reject(err);
      }
    };

    reader.onerror = () => reject(new ExcelUserError("excel.readFailed"));
    reader.readAsArrayBuffer(file);
  });
}
