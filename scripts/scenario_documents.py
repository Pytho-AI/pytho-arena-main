#!/usr/bin/env python3
"""Import or export JLC-style scenario background documents."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from pytho_arena.scenario.documents import export_scenario_document, import_scenario_document
from pytho_arena.scenario.models import ScenarioSpec


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)

    importer = commands.add_parser("import", help="Convert a DOCX brief to scenario JSON")
    importer.add_argument("input", type=Path)
    importer.add_argument("--scenario-out", type=Path, required=True)
    importer.add_argument("--report-out", type=Path, required=True)

    exporter = commands.add_parser("export", help="Convert scenario JSON to a DOCX brief")
    exporter.add_argument("input", type=Path)
    exporter.add_argument("--output", type=Path, required=True)
    exporter.add_argument("--hero-image", type=Path)

    args = parser.parse_args()
    if args.command == "import":
        result = import_scenario_document(args.input.read_bytes(), args.input.name)
        args.scenario_out.parent.mkdir(parents=True, exist_ok=True)
        args.report_out.parent.mkdir(parents=True, exist_ok=True)
        args.scenario_out.write_text(
            json.dumps(result.scenario.model_dump(mode="json"), indent=2) + "\n",
            encoding="utf-8",
        )
        args.report_out.write_text(
            json.dumps(result.report.model_dump(mode="json"), indent=2) + "\n",
            encoding="utf-8",
        )
        print(
            f"Imported {args.input.name}: {result.scenario.scenario_id}, "
            f"{len(result.report.asset_resolution)} asset categories resolved"
        )
        return

    scenario = ScenarioSpec.model_validate_json(args.input.read_text(encoding="utf-8"))
    output = export_scenario_document(scenario, args.output, hero_image=args.hero_image)
    print(f"Exported {scenario.scenario_id} to {output}")


if __name__ == "__main__":
    main()
