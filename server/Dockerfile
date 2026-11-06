FROM node:22.23.4-bookworm-slim@sha256:5ec23b7c622b00547753bc6ffd78085dd868a68aeb41c8e0a1418f033e13d96d AS node

# Build only the V100's sm70 backend. CUDA 13 has dropped this architecture.
# Optional platform packages would bundle additional CUDA libraries; compile
# against the same CUDA runtime layers used by wintermute's Whisper image.
FROM nvidia/cuda:12.6.3-devel-ubuntu22.04@sha256:d49bb8a4ff97fb5fe477947a3f02aa8c0a53eae77e11f00ec28618a0bcaa2ad1 AS qmd-build
COPY --from=node /usr/local/ /usr/local/
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
       build-essential python3 python3-dev git cmake curl ca-certificates pkg-config \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /opt/qmd
COPY server/package.json server/package-lock.json ./
RUN NODE_LLAMA_CPP_SKIP_DOWNLOAD=true npm ci --omit=optional \
    && NODE_LLAMA_CPP_CMAKE_OPTION_CMAKE_CUDA_ARCHITECTURES=70 \
       npx --no node-llama-cpp source download --gpu cuda \
    && rm -rf node_modules/node-llama-cpp/llama/llama.cpp /root/.npm

# Retain the loadable Release directory and its metadata. The CMake object
# tree and duplicate bin directory are not needed to load the native addon.
RUN find node_modules/node-llama-cpp/llama/localBuilds \
      -mindepth 2 -maxdepth 2 -type d ! -name Release -exec rm -rf {} + \
    && rm -f node_modules/node-llama-cpp/llama/gitRelease.bundle

FROM nvidia/cuda:12.6.3-runtime-ubuntu22.04@sha256:63a18dd805367dacfb077aeced8384ab2fb569598ec5f5f5220c3f90a5c23650
COPY --from=node /usr/local/ /usr/local/
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/opt/brain/server \
    PATH=/opt/brain/server/bin:/opt/qmd/node_modules/.bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin \
    HOME=/state \
    XDG_CACHE_HOME=/cache \
    BRAIN_DIR=/brain/repo \
    BRAIN_CODE_DIR=/brain/code \
    BRAIN_CODE_REPO=slds-lmu/wintermute-brain \
    BRAIN_REPO=slds-lmu/wintermute-brain-content-slds \
    BRAIN_QMD="" \
    QMD_LLAMA_GPU=cuda \
    QMD_EMBED_PARALLELISM=1 \
    GIT_CONFIG_COUNT=2 \
    GIT_CONFIG_KEY_0=credential.helper \
    GIT_CONFIG_VALUE_0=/opt/brain/server/bin/git-credential-brain \
    GIT_CONFIG_KEY_1=credential.useHttpPath \
    GIT_CONFIG_VALUE_1=true
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
       python3 python3-pip git git-lfs gh openssl curl ca-certificates libgomp1 libnuma1 \
    && groupadd --gid 2000 wintermute \
    && useradd --uid 2000 --gid wintermute --home-dir /state --no-create-home wintermute \
    && rm -rf /var/lib/apt/lists/*
ARG GITLEAKS_VERSION=8.30.1
RUN curl -fsSL "https://github.com/gitleaks/gitleaks/releases/download/v$GITLEAKS_VERSION/gitleaks_$GITLEAKS_VERSION""_linux_x64.tar.gz" \
      -o /tmp/gitleaks.tar.gz \
    && tar -xzf /tmp/gitleaks.tar.gz -C /usr/local/bin gitleaks \
    && rm /tmp/gitleaks.tar.gz \
    && npm install --global @anthropic-ai/claude-code@2.1.318 \
    && npm cache clean --force
COPY --from=qmd-build /opt/qmd/ /opt/qmd/
# Below the large qmd layer, so that a lock update does not move that layer.
COPY server/requirements.lock /tmp/requirements.lock
RUN python3 -m pip install --no-cache-dir --require-hashes --only-binary=:all: -r /tmp/requirements.lock
ENV NODE_LLAMA_CPP_CMAKE_OPTION_CMAKE_CUDA_ARCHITECTURES=70
WORKDIR /opt/brain
COPY server/ server/
COPY plugin/ plugin/
COPY CLAUDE.md ./
RUN chmod 755 server/bin/* \
    && mkdir -p /state /cache /brain \
    && chown 2000:2000 /state /cache /brain \
    && python3 -c "import brain_server.app" \
    && qmd --version
USER 2000:2000
EXPOSE 8181
CMD ["python3", "-m", "uvicorn", "brain_server.app:app", "--host", "0.0.0.0", "--port", "8181", "--no-access-log"]
