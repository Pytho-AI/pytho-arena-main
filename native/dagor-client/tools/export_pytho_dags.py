import argparse
import math
import shutil
import sys
from pathlib import Path

import addon_utils
import bpy

ASSETS = (
    ("orion_ucav.obj", "uav_orion", "orion_ucav_albedo.png", None),
    ("mq_1l_usa_lod2.obj", "mq_1l_usa", "mq_1l_usa_albedo.png", None),
    ("liberty_cargo_ship.obj", "cargo_ship_liberty", "liberty_cargo_ship_albedo.png", None),
    ("nasams_fcs_vehicle.obj", "nasams_fcs", "nasams_fcs_albedo.png", (0.22, 0.27, 0.17, 1.0)),
    (
        "range_watch_tower.obj",
        "range_watch_tower",
        "range_watch_tower_albedo.png",
        (0.31, 0.34, 0.34, 1.0),
    ),
)


def clear_scene() -> None:
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)
    for material in tuple(bpy.data.materials):
        bpy.data.materials.remove(material)


def stage_texture(
    source_dir: Path,
    output_dir: Path,
    texture_name: str,
    color: tuple[float, float, float, float] | None,
) -> None:
    destination = output_dir / texture_name
    if color is None:
        shutil.copy2(source_dir / texture_name, destination)
        return
    image = bpy.data.images.new(texture_name, width=16, height=16, alpha=True)
    image.pixels = list(color) * (16 * 16)
    image.filepath_raw = str(destination)
    image.file_format = "PNG"
    image.save()
    bpy.data.images.remove(image)


def export_asset(
    source_dir: Path,
    output_dir: Path,
    obj_name: str,
    asset_name: str,
    texture_name: str,
    flat_color: tuple[float, float, float, float] | None,
) -> None:
    clear_scene()
    stage_texture(source_dir, output_dir, texture_name, flat_color)
    bpy.ops.wm.obj_import(filepath=str(source_dir / obj_name))
    for obj in bpy.context.scene.objects:
        obj.name = asset_name
        obj.rotation_euler[2] -= math.pi / 2
        bpy.context.view_layer.objects.active = obj
        obj.select_set(True)
        bpy.ops.object.transform_apply(location=False, rotation=True, scale=False)
        obj.select_set(False)
    if not bpy.data.materials:
        material = bpy.data.materials.new(f"{asset_name}_material")
        for obj in bpy.context.scene.objects:
            if obj.type == "MESH":
                obj.data.materials.append(material)
    for material in bpy.data.materials:
        material.dagormat.shader_class = "rendinst_simple"
        material.dagormat.textures.tex0 = texture_name
    destination = output_dir / f"{asset_name}.lod00.dag"
    result = bpy.ops.export_scene.dag(
        filepath=str(destination), limits="Visible", modifiers=True, normals=True
    )
    if result != {"FINISHED"} or not destination.is_file():
        raise RuntimeError(f"Dagor export failed for {asset_name}: {result}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--addon-dir", type=Path, required=True)
    args = parser.parse_args(sys.argv[sys.argv.index("--") + 1 :])

    sys.path.insert(0, str(args.addon_dir))
    addon_utils.enable("dag4blend", default_set=True, persistent=False)
    if not addon_utils.check("dag4blend")[1]:
        raise RuntimeError("failed to enable the official dag4blend add-on")
    project_root = Path(__file__).resolve().parents[3]
    source_dir = (
        project_root / "src" / "pytho_arena" / "server" / "frontend-src" / "public" / "assets"
    )
    output_dir = project_root / "native" / "dagor-client" / "assets" / "source"
    output_dir.mkdir(parents=True, exist_ok=True)
    preferences = bpy.context.preferences.addons["dag4blend"].preferences
    project = preferences.projects.add()
    project.name = "Pytho"
    project.path = str(output_dir)
    preferences.project_active = "0"
    for obj_name, asset_name, texture_name, flat_color in ASSETS:
        export_asset(source_dir, output_dir, obj_name, asset_name, texture_name, flat_color)


if __name__ == "__main__":
    main()
