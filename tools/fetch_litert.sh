#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LITERT_VERSION="2.2.0"
LITERT_SHA256="0aa619d80aef27303ad9c6e3759a20110f77e7b11ade9b68061b8c6e5904b0c6"
LITERT_URL="https://github.com/google-ai-edge/LiteRT/releases/download/v${LITERT_VERSION}/litert_cc_sdk.zip"
DEST_DIR="${ROOT_DIR}/third_party/litert"
ARCHIVE="${ROOT_DIR}/build/litert_cc_sdk-v${LITERT_VERSION}.zip"

mkdir -p "${ROOT_DIR}/build" "${DEST_DIR}"

if command -v sha256sum >/dev/null 2>&1; then
    SHA256_BIN="sha256sum"
else
    SHA256_BIN="shasum -a 256"
fi

if [[ -f "${ARCHIVE}" ]]; then
    echo "Using cached LiteRT SDK archive: ${ARCHIVE}"
else
    echo "Downloading LiteRT C++ SDK ${LITERT_VERSION}..."
    curl --fail --location --retry 3 --retry-all-errors \
        --output "${ARCHIVE}" "${LITERT_URL}"
fi

actual_sha="$(eval "${SHA256_BIN} \"${ARCHIVE}\"" | awk '{print $1}')"
if [[ "${actual_sha}" != "${LITERT_SHA256}" ]]; then
    echo "ERROR: LiteRT SDK checksum mismatch." >&2
    echo "Expected: ${LITERT_SHA256}" >&2
    echo "Actual:   ${actual_sha}" >&2
    rm -f "${ARCHIVE}"
    exit 1
fi

rm -rf "${DEST_DIR}"
mkdir -p "${DEST_DIR}"
unzip -q "${ARCHIVE}" -d "${DEST_DIR}"

if [[ ! -f "${DEST_DIR}/CMakeLists.txt" ]]; then
    echo "ERROR: extracted LiteRT SDK does not contain CMakeLists.txt at its root." >&2
    exit 1
fi

printf '%s\\n' "${LITERT_VERSION}" > "${DEST_DIR}/VERSION"
printf '%s\\n' "${LITERT_SHA256}" > "${DEST_DIR}/SHA256"

echo "LiteRT C++ SDK ${LITERT_VERSION} is ready at ${DEST_DIR}"
