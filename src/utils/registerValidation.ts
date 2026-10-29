import type { RegisterType } from "../types";

export function validateRegisterRows(type: RegisterType, rows: Record<string, unknown>[]): void {
  const fail = () => { throw new Error("GBT_INVALID_REGISTER_DATA"); };
  const integer = (v: unknown, min = 0, max = 100000) => {
    if (v == null || typeof v === "boolean" || String(v).trim() === "") return fail();
    const n = Number(v);
    if (!Number.isInteger(n) || n < min || n > max) return fail();
    return n;
  };
  if (!rows.length || rows.length > 50000) fail();
  const ids = new Set<number>();
  for (const row of rows) {
    const id = integer(row.ID);
    if (ids.has(id)) fail();
    ids.add(id);
    const modern = Object.prototype.hasOwnProperty.call(row, "PoseType");
    const kind = modern ? String(row.PoseType ?? "").trim().toUpperCase() : "CART";
    if (type !== "R" && !["CART", "JOINT"].includes(kind)) fail();
    const jointKeys = Array.from({ length: 9 }, (_, i) => `J${i + 1}`);
    const cartKeys = [..."XYZABC"];
    for (const key of type === "R" ? ["value"] : kind === "JOINT" ? jointKeys : cartKeys) {
      const v = row[key];
      if (v == null || typeof v === "boolean" || String(v).trim() === "" || !Number.isFinite(Number(v))) fail();
    }
    if (type !== "R") {
      const key = type === "P" ? "Coord" : "coord";
      if (!(modern ? ["L", "R", "U"] : ["L", "R"]).includes(String(row[key] ?? row[`${key}（L/R）`] ?? "").trim().toUpperCase())) fail();
      if (modern) {
        for (const key of kind === "JOINT" ? cartKeys : jointKeys) {
          if (row[key] != null && String(row[key]).trim() !== "") fail();
        }
        for (const key of ["WristFlip", "ArmUpDown", "ArmBackFront"]) integer(row[key], -1, 1);
        for (let i = 1; i <= 9; i++) integer(row[`Turn${i}`], -2147483648, 2147483647);
        for (const key of ["Name", "Comment"]) if (row[key] != null && typeof row[key] !== "string") fail();
      }
    }
    if (type === "P") { integer(row.TF); integer(row.UF); }
  }
  if (Math.max(...ids) - Math.min(...ids) >= 10000) fail();
}
