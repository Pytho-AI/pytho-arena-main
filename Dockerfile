# syntax=docker/dockerfile:1

# ---------------------------------------------------------------------------
# Stage 1: build the browser bundle.
#
# vite.config.ts writes to ../frontend with emptyOutDir: true, so this stage
# regenerates src/pytho_arena/server/frontend/ from source rather than trusting
# the committed copy. Node 22 satisfies vite 7's >=22.12 engine requirement.
# ---------------------------------------------------------------------------
FROM node:22-bookworm-slim AS frontend

# Mirror the repo's nesting: vite's outDir is the relative path "../frontend",
# so the source must sit at .../server/frontend-src for the bundle to land in
# .../server/frontend — the tree pyproject.toml ships as package data.
WORKDIR /build/src/pytho_arena/server/frontend-src

# Copy manifests first so the npm layer caches across source-only edits.
COPY src/pytho_arena/server/frontend-src/package.json \
     src/pytho_arena/server/frontend-src/package-lock.json ./
RUN npm ci

COPY src/pytho_arena/server/frontend-src/ ./

# `npm run build` is `tsc --noEmit && vite build`, so a type error fails the
# image build here rather than surfacing at runtime.
RUN npm run build


# ---------------------------------------------------------------------------
# Stage 2: python dependencies.
#
# Split from the runtime stage so the ~1GB torch download is not repeated when
# only application source changes.
# ---------------------------------------------------------------------------
FROM python:3.12-slim-bookworm AS python-deps

ENV PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1

# CPU-only torch wheels: ~1.5GB image instead of ~6GB for the CUDA default.
# To build a CUDA image instead, pass a CUDA wheel index, e.g.
#   --build-arg TORCH_INDEX_URL=https://download.pytorch.org/whl/cu124
ARG TORCH_INDEX_URL=https://download.pytorch.org/whl/cpu

WORKDIR /app

RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Install torch on its own so the pinned index applies only to it; the
# remaining dependencies resolve from PyPI normally.
RUN pip install --index-url "${TORCH_INDEX_URL}" "torch>=2.2"

# Dependency install driven by pyproject.toml alone. The source tree is not
# copied yet, so this layer survives application edits.
COPY pyproject.toml README.md ./
RUN mkdir -p src/pytho_arena \
 && printf '__version__ = "0.0.0"\n' > src/pytho_arena/__init__.py \
 && pip install '.[server]' \
 && pip uninstall -y pytho-arena \
 && rm -rf src


# ---------------------------------------------------------------------------
# Stage 3: runtime.
# ---------------------------------------------------------------------------
FROM python:3.12-slim-bookworm AS runtime

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1 \
    PATH="/opt/venv/bin:$PATH"

COPY --from=python-deps /opt/venv /opt/venv

WORKDIR /app

COPY pyproject.toml README.md ./
COPY src/ ./src/

# The built bundle overwrites whatever the source tree carried, so the image
# always ships a frontend generated from this commit's frontend-src/.
COPY --from=frontend /build/src/pytho_arena/server/frontend/ \
                     ./src/pytho_arena/server/frontend/

# --no-deps: every dependency is already present in the venv from stage 2, and
# this keeps the install from reaching the network for the CUDA torch default.
RUN pip install --no-deps -e .

# app.py resolves DEFAULT_DATA_DIR as Path.cwd()/"var"/"arena"; setting the
# env var explicitly decouples the storage path from the working directory.
ENV PYTHO_ARENA_DATA_DIR=/data/arena \
    PYTHO_ARENA_HOST=0.0.0.0 \
    PYTHO_ARENA_PORT=8096

# Non-root runtime user; /data is the mount point for scenarios and replays.
RUN useradd --create-home --uid 10001 arena \
 && mkdir -p /data/arena \
 && chown -R arena:arena /data /app
USER arena

VOLUME ["/data"]
EXPOSE 8096

HEALTHCHECK --interval=30s --timeout=5s --start-period=40s --retries=3 \
  CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8096/api/health', timeout=4).status == 200 else 1)"

CMD ["sh", "-c", "exec uvicorn pytho_arena.server.app:app --host \"$PYTHO_ARENA_HOST\" --port \"$PYTHO_ARENA_PORT\""]
