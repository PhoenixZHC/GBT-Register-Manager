import type { RegisterType } from "../types";

export function validateRegisterRows(type: RegisterType, rows: Record<string, unknown>[]): void {
  const fail = () => { throw new Error("GBT_INVALID_REGISTER_DATA"); };
  const integer = (v: unknown) => {
    if (v == null || typeof v === "boolean" || String(v).trim() === "") return fail();
    const n = Number(v);
    if (!Number.isInteger(n) || n < 0 || n > 100000) return fail();
    return n;
  };
  if (!rows.length || rows.length > 50000) fail();
  const ids = new Set<number>();
  for (const row of rows) {
    const id = integer(row.ID);
    if (ids.has(id)) fail();
    ids.add(id);
    for (const key of type === "R" ? ["value"] : ["X", "Y", "Z", "A", "B", "C"]) {
      const v = row[key];
      if (v == null || typeof v === "boolean" || String(v).trim() === "" || !Number.isFinite(Number(v))) fail();
    }
    if (type !== "R") {
      const key = type === "P" ? "Coord" : "coord";
      if (!["L", "R"].includes(String(row[key] ?? row[`${key}（L/R）`] ?? "").trim().toUpperCase())) fail();
    }
    if (type === "P") { integer(row.TF); integer(row.UF); }
  }
  if (Math.max(...ids) - Math.min(...ids) >= 10000) fail();
}
