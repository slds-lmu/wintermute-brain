// Validate the local build selected by the runtime, without compiling.
import { getLlama } from "/opt/qmd/node_modules/node-llama-cpp/dist/index.js";

try {
  const llama = await getLlama({ gpu: "cuda", build: "never" });
  console.log(JSON.stringify({ gpu: llama.gpu, vram: await llama.getVramState() }));
  process.exit(llama.gpu === "cuda" ? 0 : 1);
} catch (error) {
  console.error(error.message);
  process.exit(1);
}
