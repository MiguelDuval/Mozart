#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DEPS="$ROOT/third_party"

clone_pinned() {
  local name="$1"
  local repo="$2"
  local commit="$3"
  local dir="$DEPS/$name"

  mkdir -p "$DEPS"

  if [ ! -d "$dir/.git" ]; then
    git clone "$repo" "$dir"
  fi

  git -C "$dir" fetch --no-tags origin
  git -C "$dir" checkout --detach "$commit"
}

clone_pinned "JUCE" \
  "https://github.com/juce-framework/JUCE.git" \
  "72782788ce18c2d4d760b28e0921d6ffc6431102"

clone_pinned "oboe" \
  "https://github.com/google/oboe.git" \
  "faa019cb12f448d18b5ab2b933272cf0c16763b2"

clone_pinned "ableton_link" \
  "https://github.com/Ableton/link.git" \
  "e9a2e414d63f55f1aad158370b007a6fbdc1eeb9"

clone_pinned "tracktion_engine" \
  "https://github.com/Tracktion/tracktion_engine.git" \
  "0a5f4e6a5f53d09c89b414a44386a12df7fa1ec6"

echo "Pinned Mozart dependencies are available under $DEPS."
