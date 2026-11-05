// Unpack the locked CPU-only llama.cpp backend into the directory argv[2].
// A separate image stage, so that it does not invalidate the native CUDA build.
import { execFileSync } from "node:child_process";
import { createHash } from "node:crypto";
import { mkdirSync, readFileSync, writeFileSync } from "node:fs";

const lock = JSON.parse(readFileSync("package-lock.json", "utf8"));
const entry = lock.packages["node_modules/@node-llama-cpp/linux-x64"];
const archive = Buffer.from(await (await fetch(entry.resolved)).arrayBuffer());
const integrity = "sha512-" + createHash("sha512").update(archive).digest("base64");
if (integrity !== entry.integrity) throw new Error(`${entry.resolved}: integrity mismatch`);
writeFileSync("backend.tgz", archive);
mkdirSync(process.argv[2], { recursive: true });
execFileSync("tar", ["xzf", "backend.tgz", "--strip-components=1", "-C", process.argv[2]]);
