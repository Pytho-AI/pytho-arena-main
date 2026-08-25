#!/bin/sh
set -eu

client_dir=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
viewer_root=${PYTHO_DAGOR_VIEWER_ROOT:-/private/tmp/pytho-dagor-20260810/east-extract/samples/dngSceneViewer/viewer}
destination="$viewer_root/content/pytho/res"

if [ ! -d "$viewer_root/content/east_district" ]; then
  echo "not an extracted East District viewer: $viewer_root" >&2
  exit 2
fi

for source_file in \
  "$client_dir/assets/packs/pytho_assets.grp" \
  "$client_dir/assets/packs/pytho_assets.dxp.bin" \
  "$client_dir/assets/packs/grp_hdr.vromfs.bin"
do
  if [ ! -s "$source_file" ]; then
    echo "missing built Pytho resource: $source_file" >&2
    exit 2
  fi
done

mkdir -p "$destination"
install -m 0644 "$client_dir/assets/packs/pytho_assets.grp" "$destination/pytho_assets.grp"
install -m 0644 "$client_dir/assets/packs/pytho_assets.dxp.bin" "$destination/pytho_assets.dxp.bin"
install -m 0644 "$client_dir/assets/packs/grp_hdr.vromfs.bin" "$destination/grp_hdr.vromfs.bin"

echo "staged Pytho resources in $destination"
echo "the viewer still requires the source overlay build so settings.blk mounts content/pytho"
