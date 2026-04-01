#!/usr/bin/env python3
import sys
import argparse
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

from src.pipeline.project import ProjectManager
from src.pipeline.state import AFCState, FinancialLedger
from src.pipeline.graph import app as pipeline_app


def create_project(args):
    pm = ProjectManager(args.projects_dir)
    config = {
        "video": {
            "style": args.style,
            "resolution": args.resolution,
            "fps": args.fps,
            "max_shots": args.max_shots,
        },
        "generation": {
            "segment_selection": {
                "chapters": [int(c.strip()) for c in args.chapters.split(",")]
                if args.chapters
                else []
            }
        },
    }
    novel_text = Path(args.input).read_text(encoding="utf-8")
    project_path = pm.create_project(args.name, novel_text, config)
    print(f"Created project: {project_path}")


def _get_initial_state(args, pm) -> AFCState:
    pm.load_project(args.name)
    novel_text = (pm.current_project / "01_source_material" / "novel.txt").read_text(
        encoding="utf-8"
    )

    return AFCState(
        workspace_root=str(pm.current_project),
        project_config=pm.project_config,
        novel_text=novel_text,
        ledger=FinancialLedger(project_budget_usd=100.0, accumulated_cost_usd=0.0),
        unprocessed_scenes=[],
        current_scene_path=None,
        unprocessed_shots=[],
        active_shot_plan=None,
        current_proxy_path=None,
        current_keyframe_path=None,
        current_render_path=None,
        scene_dailies_paths=[],
        completed_scenes_paths=[],
        previs_retry_count=0,
        render_retry_count=0,
        continuity_feedback=None,
        escalation_required=False,
    )


def run_pipeline(args):
    pm = ProjectManager(args.projects_dir)
    state = _get_initial_state(args, pm)
    print(f"🚀 Starting Autonomous Pipeline: {args.name}")
    # LangGraph handles the storyboard -> animate -> QA loop per shot
    final_state = pipeline_app.invoke(state)
    if final_state.get("last_error"):
        print(f"❌ Error: {final_state['last_error']}")
    else:
        print(f"✅ Success! Final video: {final_state.get('final_video_path')}")


def status(args):
    pm = ProjectManager(args.projects_dir)
    pm.load_project(args.name)
    summary = pm.get_stage_summary()
    print(
        f"Project: {args.name} | Scenes: {summary['total_scenes']} | Shots: {summary['total_shots']}"
    )
    for k, v in summary["shots_by_status"].items():
        print(f"  {k:15}: {v}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--projects-dir", default="./projects")
    subparsers = parser.add_subparsers(dest="command")

    cp = subparsers.add_parser("create")
    cp.add_argument("name")
    cp.add_argument("input")
    cp.add_argument("--chapters")
    cp.add_argument("--style", default="anime")
    cp.add_argument("--resolution", default="1080p")
    cp.add_argument("--fps", type=int, default=24)
    cp.add_argument("--max-shots", type=int, default=10)

    rp = subparsers.add_parser("run")
    rp.add_argument("name")
    rp.add_argument(
        "--stage",
        help="Start from a specific stage (index, lore, scenes, shots, storyboard, animate, qa, post-prod)",
    )
    rp.add_argument(
        "--shot-index", type=int, default=0, help="Start from a specific shot index"
    )

    sp = subparsers.add_parser("status")
    sp.add_argument("name")

    args = parser.parse_args()
    if args.command == "create":
        create_project(args)
    elif args.command == "run":
        run_pipeline(args)
    elif args.command == "status":
        status(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
