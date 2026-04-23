#!/usr/bin/env node
/**
 * 构建前清理：删除容易"污染打包结果"的老产物与缓存。
 *
 * 踩过的坑：tsc 早期把 src/**\/*.ts 编译成了同名 .js，残留在源码目录里，Vite 解析
 * 时 .js 默认优先于 .ts，会把老 .js 当权威源打包，导致连接失败与 i18n 失效。
 * 这里每次构建前统一清掉这些"影子"产物以及 dist / Vite 缓存 / tsbuildinfo。
 *
 * 默认不清 src-tauri/target —— Rust 全量重编太慢。需要彻底重编时用：
 *   npm run clean -- --rust
 */
import { rm, readdir, stat } from "node:fs/promises";
import { existsSync } from "node:fs";
import { join, relative, sep } from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = fileURLToPath(new URL("..", import.meta.url));

const args = new Set(process.argv.slice(2));
const alsoRust = args.has("--rust") || args.has("--all");

/** 直接删除的目录/文件清单（相对 ROOT）。 */
const STATIC_TARGETS = [
  "dist",
  "node_modules/.vite",
  "node_modules/.cache",
  ".eslintcache"
];

if (alsoRust) {
  STATIC_TARGETS.push("src-tauri/target");
}

/** 递归扫描 src/ 下需要删除的"源码旁残留产物"。 */
const SRC_DIR = join(ROOT, "src");
const SRC_JUNK_SUFFIXES = [".js", ".js.map", ".d.ts", ".tsbuildinfo"];

async function walk(dir, out) {
  let entries;
  try {
    entries = await readdir(dir, { withFileTypes: true });
  } catch {
    return;
  }
  for (const e of entries) {
    const full = join(dir, e.name);
    if (e.isDirectory()) {
      await walk(full, out);
    } else if (e.isFile()) {
      if (SRC_JUNK_SUFFIXES.some((s) => e.name.endsWith(s))) {
        out.push(full);
      }
    }
  }
}

async function removePath(p) {
  if (!existsSync(p)) return false;
  await rm(p, { recursive: true, force: true });
  return true;
}

async function main() {
  const removed = [];

  for (const rel of STATIC_TARGETS) {
    const abs = join(ROOT, rel);
    if (await removePath(abs)) removed.push(rel);
  }

  const junk = [];
  await walk(SRC_DIR, junk);
  for (const f of junk) {
    if (await removePath(f)) {
      removed.push(relative(ROOT, f).split(sep).join("/"));
    }
  }

  // 根目录散落的 tsbuildinfo
  for (const name of ["tsconfig.tsbuildinfo", "tsconfig.app.tsbuildinfo"]) {
    const abs = join(ROOT, name);
    if (await removePath(abs)) removed.push(name);
  }

  if (removed.length === 0) {
    console.log("[clean] nothing to remove");
  } else {
    console.log(`[clean] removed ${removed.length} item(s):`);
    for (const r of removed) console.log(`  - ${r}`);
  }
}

main().catch((err) => {
  console.error("[clean] failed:", err);
  process.exit(1);
});
