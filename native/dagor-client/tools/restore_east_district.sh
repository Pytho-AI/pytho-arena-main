#!/bin/sh
set -eu

client_dir=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
restore_root=${1:-${PYTHO_DAGOR_RESTORE_ROOT:-/private/tmp/pytho-dagor-20260810}}
archive="$restore_root/east_district-dagor.p1.tar.gz"
extract_root="$restore_root/east-extract"
viewer_root="$extract_root/samples/dngSceneViewer/viewer"
archive_url="https://dagorenginedata.cdn.gaijin.net/rel-fea0a2b3ae5acdb25e088e57a8fb1f77d5ba3e1d/east_district-dagor.p1.tar.gz"
archive_sha256="641e5797d4b3af639b9d794892b95aafabad81f629f2f3180506ba22f8245416"

mkdir -p "$restore_root"
if [ ! -f "$archive" ]; then
  partial_archive="$archive.partial"
  curl -fL --retry 3 --output "$partial_archive" "$archive_url"
  actual_sha256=$(shasum -a 256 "$partial_archive" | awk '{print $1}')
  if [ "$actual_sha256" != "$archive_sha256" ]; then
    echo "East District archive checksum mismatch: $actual_sha256" >&2
    exit 2
  fi
  mv "$partial_archive" "$archive"
fi

actual_sha256=$(shasum -a 256 "$archive" | awk '{print $1}')
if [ "$actual_sha256" != "$archive_sha256" ]; then
  echo "East District archive checksum mismatch: $actual_sha256" >&2
  exit 2
fi

if [ ! -d "$viewer_root/content/east_district" ]; then
  mkdir -p "$extract_root"
  tar -xzf "$archive" -C "$extract_root"
fi

PYTHO_DAGOR_VIEWER_ROOT="$viewer_root" sh "$client_dir/tools/stage_pytho_viewer.sh"

echo "restored official East District viewer in $viewer_root"
echo "Pytho packs are staged; building the patched AOT viewer still requires the pinned Dagor source toolchain"
