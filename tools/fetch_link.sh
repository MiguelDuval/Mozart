#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DEPS="$ROOT/third_party"
DIR="$DEPS/ableton_link"
REPO="https://github.com/Ableton/link.git"
COMMIT="e9a2e414d63f55f1aad158370b007a6fbdc1eeb9"

mkdir -p "$DEPS"

if [ ! -d "$DIR/.git" ]; then
  git clone "$REPO" "$DIR"
fi

git -C "$DIR" fetch --no-tags origin
git -C "$DIR" checkout --detach "$COMMIT"
git -C "$DIR" submodule sync --recursive
git -C "$DIR" submodule update --init --recursive

echo "Ableton Link is available at $DIR"
echo "Pinned commit: $COMMIT"
