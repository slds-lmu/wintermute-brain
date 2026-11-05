// Fail the image build if the CPU qmd could not load its backend.
import { getLlama } from "/opt/qmd/node_modules/node-llama-cpp/dist/index.js";

const llama = await getLlama({ gpu: false, build: "never", skipDownload: true, progressLogs: false });
if (llama.gpu !== false) throw new Error(`expected a CPU backend, got ${llama.gpu}`);
console.log(`CPU backend loaded: ${llama.cpuMathCores} math cores`);
await llama.dispose();
