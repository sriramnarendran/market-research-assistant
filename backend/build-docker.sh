#!/usr/bin/env bash
# Build the backend Docker image.
#
# First-time setup (Colima / Homebrew Docker without buildx):
#   ./build-docker.sh setup
#
# Local dev (native arch, plain docker build — works on Apple Silicon):
#   ./build-docker.sh local
#
# Push linux/amd64 to ACR (required for Azure Container Apps):
#   az acr login --name <acr-name>
#   ./build-docker.sh push <acr>.azurecr.io/market-research-backend:latest
#
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DOCKERFILE="$SCRIPT_DIR/Dockerfile"
CONTEXT="$SCRIPT_DIR"
BUILDER_NAME="${BUILDER_NAME:-mra-builder}"

print_buildx_help() {
  cat >&2 <<'EOF'
docker buildx is required to build linux/amd64 images on Apple Silicon.

Quick fix (Colima + Homebrew Docker):
  ./backend/build-docker.sh setup

Or manually:
  brew install docker-buildx
  mkdir -p ~/.docker/cli-plugins
  ln -sf "$(brew --prefix docker-buildx)/bin/docker-buildx" ~/.docker/cli-plugins/docker-buildx
  docker buildx create --name mra-builder --driver docker-container --use
  docker buildx inspect --bootstrap

Ensure Docker is running:
  colima start          # if you use Colima
  open -a Docker        # if you use Docker Desktop
EOF
}

ensure_docker() {
  if ! docker info >/dev/null 2>&1; then
    echo "ERROR: Docker is not running." >&2
    if command -v colima >/dev/null 2>&1; then
      echo "Start Colima: colima start" >&2
    else
      echo "Start Docker Desktop or your Docker VM." >&2
    fi
    exit 1
  fi
}

install_buildx_mac() {
  if [[ "$(uname -s)" != "Darwin" ]]; then
    return 1
  fi
  if ! command -v brew >/dev/null 2>&1; then
    echo "ERROR: Homebrew not found. Install buildx manually:" >&2
    print_buildx_help
    return 1
  fi

  echo ">>> Installing docker-buildx via Homebrew..."
  if ! brew list docker-buildx >/dev/null 2>&1; then
    brew install docker-buildx
  fi

  local plugin_dir="${HOME}/.docker/cli-plugins"
  local plugin_path="${plugin_dir}/docker-buildx"
  mkdir -p "$plugin_dir"
  ln -sf "$(brew --prefix docker-buildx)/bin/docker-buildx" "$plugin_path"

  if ! docker buildx version >/dev/null 2>&1; then
    echo "ERROR: buildx installed but 'docker buildx' still unavailable." >&2
    print_buildx_help
    return 1
  fi

  echo ">>> docker buildx $(docker buildx version | head -1)"
}

setup_buildx() {
  ensure_docker

  if ! docker buildx version >/dev/null 2>&1; then
    install_buildx_mac || exit 1
  fi

  if ! docker buildx inspect "$BUILDER_NAME" >/dev/null 2>&1; then
    echo ">>> Creating buildx builder '$BUILDER_NAME'..."
    docker buildx create --name "$BUILDER_NAME" --driver docker-container --use
  else
    docker buildx use "$BUILDER_NAME"
  fi

  echo ">>> Bootstrapping builder (pulls QEMU for cross-platform builds)..."
  docker buildx inspect --bootstrap

  echo ">>> Ready. Example:"
  echo "    az acr login --name <acr-name>"
  echo "    $0 push <acr>.azurecr.io/market-research-backend:latest"
}

ensure_buildx() {
  ensure_docker

  if ! docker buildx version >/dev/null 2>&1; then
    echo ">>> buildx not found — running setup..." >&2
    setup_buildx
    return
  fi

  if ! docker buildx inspect "$BUILDER_NAME" >/dev/null 2>&1; then
    docker buildx create --name "$BUILDER_NAME" --driver docker-container --use >/dev/null
  else
    docker buildx use "$BUILDER_NAME" >/dev/null
  fi
  docker buildx inspect --bootstrap >/dev/null
}

build_local() {
  local tag="${1:-market-research-backend:local}"
  ensure_docker
  echo ">>> Building $tag (native architecture, docker build)"
  docker build -f "$DOCKERFILE" -t "$tag" "$CONTEXT"
  echo ">>> Done: $tag"
}

build_amd64() {
  local tag="$1"
  local push="${2:-false}"
  ensure_buildx

  local -a args=(
    buildx build
    --platform linux/amd64
    -f "$DOCKERFILE"
    -t "$tag"
  )

  if [[ "$push" == "true" ]]; then
    args+=(--push)
  else
    args+=(--load)
  fi

  echo ">>> Building $tag (linux/amd64)"
  docker "${args[@]}" "$CONTEXT"
  echo ">>> Done: $tag"
}

case "${1:-local}" in
  setup)
    setup_buildx
    ;;
  local)
    build_local "${2:-market-research-backend:local}"
    ;;
  amd64)
    build_amd64 "${2:?Usage: build-docker.sh amd64 <image:tag>}" false
    ;;
  push)
    build_amd64 "${2:?Usage: build-docker.sh push <registry/image:tag>}" true
    ;;
  *)
    echo "Usage:" >&2
    echo "  $0 setup                      Install/configure buildx (run once on Colima/Mac)" >&2
    echo "  $0 local [tag]                Native arch (Mac dev)" >&2
    echo "  $0 amd64 <tag>                linux/amd64, load locally" >&2
    echo "  $0 push <registry/image:tag>  linux/amd64, push to registry" >&2
    exit 1
    ;;
esac
