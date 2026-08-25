#!/bin/sh
set -eu

client_dir=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
blender_bin=${PYTHO_BLENDER_BIN:-/private/tmp/blender-4.2.20/Blender.app/Contents/MacOS/Blender}
addon_dir=${PYTHO_DAG4BLEND_DIR:-/private/tmp/dag4blend-python}
dabuild_bin=${PYTHO_DABUILD_BIN:-/private/tmp/dagor-prebuilt-all/tools/dagor_cdk/macOS-x86_64/daBuild-dev}
viewer_root=${PYTHO_DAGOR_VIEWER_ROOT:-/private/tmp/pytho-dagor-20260810/east-extract/samples/dngSceneViewer/viewer}
shader_dump="$viewer_root/compiledShaders/gameMTL.ps50.shdump.bin"
blender_user_scripts=${PYTHO_BLENDER_USER_SCRIPTS:-/private/tmp/pytho-blender-user-scripts}

if [ ! -x "$blender_bin" ]; then
  echo "missing Blender 4.1+ executable: $blender_bin" >&2
  exit 2
fi
if [ ! -f "$addon_dir/dag4blend/__init__.py" ]; then
  echo "missing official dag4blend add-on: $addon_dir" >&2
  exit 2
fi
if [ ! -x "$dabuild_bin" ]; then
  echo "missing official daBuild executable: $dabuild_bin" >&2
  exit 2
fi
if [ ! -f "$shader_dump" ]; then
  echo "missing East District Metal shader dump: $shader_dump" >&2
  exit 2
fi

(cd "$client_dir/../.." && shasum -a 256 -c native/dagor-client/assets/source_manifest.sha256)

mkdir -p "$blender_user_scripts"
# dag4blend 2.5.0 builds this default path with Windows separators on every OS.
# Stage the official config at that literal path without changing the add-on.
cp "$addon_dir/dag4blend/dagorShaders.cfg" "${blender_user_scripts}\\addons\\dag4blend\\dagorShaders.cfg"
cp "$addon_dir/dag4blend/extras/remap.txt" "${blender_user_scripts}\\addons\\dag4blend\\extras\\remap.txt"
cp "$addon_dir/dag4blend/extras/library.blend" "${blender_user_scripts}\\addons\\dag4blend\\extras\\library.blend"

BLENDER_USER_SCRIPTS="$blender_user_scripts" "$blender_bin" --background --factory-startup \
  --python "$client_dir/tools/export_pytho_dags.py" -- --addon-dir "$addon_dir"

cd "$client_dir/assets"
"$dabuild_bin" -target:PC -rebuild application.blk

for output_file in build/pytho_assets.grp build/pytho_assets.dxp.bin build/grp_hdr.vromfs.bin; do
  if [ ! -s "$output_file" ]; then
    echo "daBuild did not create $output_file" >&2
    exit 1
  fi
done

mkdir -p packs
install -m 0644 build/pytho_assets.grp packs/pytho_assets.grp
install -m 0644 build/pytho_assets.dxp.bin packs/pytho_assets.dxp.bin
install -m 0644 build/grp_hdr.vromfs.bin packs/grp_hdr.vromfs.bin

echo "built and staged $client_dir/assets/packs/pytho_assets.grp"
echo "built and staged $client_dir/assets/packs/pytho_assets.dxp.bin"
echo "built and staged $client_dir/assets/packs/grp_hdr.vromfs.bin"
