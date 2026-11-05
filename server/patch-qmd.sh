#!/bin/sh
# Give qmd's query expansion a thread setting, which qmd does not offer. With
# one thread per vCPU, generation on a CPU with two hardware threads per core
# runs about five times slower than with one per core (measured on the V100 VM).
# Without QMD_EXPAND_THREADS, qmd behaves as released; the GPU qmd never sets it.
set -eu
llm=/opt/qmd/node_modules/@tobilu/qmd/dist/llm.js
sed -i 's/^\( *\)contextSize: this\.expandContextSize,$/&\n\1...(process.env.QMD_EXPAND_THREADS ? { threads: Number(process.env.QMD_EXPAND_THREADS) } : {}),/' "$llm"
# An update of the pinned qmd must not lose this silently.
grep -q 'threads: Number(process.env.QMD_EXPAND_THREADS)' "$llm"
