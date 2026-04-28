#!/usr/bin/env python3
import sys
import argparse
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

from src.pipeline.project import ProjectManager
from src.pipeline.state import (
    AFCState,
    FinancialLedger,
    ShotExecutionPlan,
    load_checkpoint,
)
from src.pipeline.graph import app as pipeline_app


class TeeStream:
    """Duplicates writes to both the original stream and a log file."""

    def __init__(self, original, log_file):
        self._original = original
        self._log_file = log_file

    def write(self, data):
        self._original.write(data)
        self._original.flush()
        self._log_file.write(data)
        self._log_file.flush()

    def flush(self):
        self._original.flush()
        self._log_file.flush()

    def fileno(self):
        return self._original.fileno()

    def isatty(self):
        return False


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

    state = AFCState(
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
        current_storyboard_path=None,
        current_render_path=None,
        scene_dailies_paths=[],
        completed_scenes_paths=[],
        keyframe_retry_count=0,
        render_retry_count=0,
        continuity_feedback=None,
        escalation_required=False,
        keyframe_is_reused_frame=False,
    )

    should_resume = getattr(args, "resume", False)
    if should_resume:
        ckpt = load_checkpoint(str(pm.current_project))
        if ckpt:
            print(f"💾 [Resume] Restoring from checkpoint...")
            state["unprocessed_scenes"] = ckpt.get("unprocessed_scenes", [])
            state["current_scene_path"] = ckpt.get("current_scene_path")
            state["completed_scenes_paths"] = ckpt.get("completed_scenes_paths", [])
            state["scene_dailies_paths"] = ckpt.get("scene_dailies_paths", [])
            raw_shots = ckpt.get("unprocessed_shots", [])
            state["unprocessed_shots"] = [ShotExecutionPlan(**s) for s in raw_shots]
            raw_active = ckpt.get("active_shot_plan")
            state["active_shot_plan"] = (
                ShotExecutionPlan(**raw_active) if raw_active else None
            )
            print(
                f"   unprocessed_scenes: {len(state['unprocessed_scenes'])}, "
                f"completed: {len(state['completed_scenes_paths'])}, "
                f"scene_dailies: {len(state['scene_dailies_paths'])}, "
                f"unprocessed_shots: {len(state['unprocessed_shots'])}, "
                f"active_shot: {state['active_shot_plan'].shot_id if state['active_shot_plan'] else None}"
            )
        else:
            print(f"💾 [Resume] No checkpoint found — starting fresh.")

    return state


def run_pipeline(args):
    pm = ProjectManager(args.projects_dir)
    state = _get_initial_state(args, pm)

    log_path = Path(state["workspace_root"]) / "pipeline.log"
    log_file = open(log_path, "w", encoding="utf-8")
    old_stdout, old_stderr = sys.stdout, sys.stderr
    sys.stdout = TeeStream(old_stdout, log_file)
    sys.stderr = TeeStream(old_stderr, log_file)

    try:
        print(f"🚀 Starting Autonomous Pipeline: {args.name}")
        print(f"📝 Logging to: {log_path}")
        final_state = pipeline_app.invoke(state)
        if final_state.get("last_error"):
            print(f"❌ Error: {final_state['last_error']}")
        else:
            completed = final_state.get("completed_scenes_paths", [])
            print(f"✅ Success! Completed scenes: {completed}")
    finally:
        sys.stdout = old_stdout
        sys.stderr = old_stderr
        log_file.close()
        print(f"📝 Full log saved to: {log_path}")


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
    rp.add_argument("--resume", action="store_true", help="Resume from last checkpoint")
    rp.add_argument(
        "--stage",
        help="Start from a specific stage (index, lore, scenes, shots, storyboard, animate, qa, post-prod)",
    )
    rp.add_argument(
        "--shot-index", type=int, default=0, help="Start from a specific shot index"
    )

    sp = subparsers.add_parser("status")
    sp.add_argument("name")

    serve_p = subparsers.add_parser("serve", help="Run the HITL web inspector")
    serve_p.add_argument("--host", default="127.0.0.1")
    serve_p.add_argument("--port", type=int, default=8765)

    args = parser.parse_args()
    if args.command == "create":
        create_project(args)
    elif args.command == "run":
        run_pipeline(args)
    elif args.command == "status":
        status(args)
    elif args.command == "serve":
        import uvicorn
        from src.server.app import create_app

        uvicorn.run(
            create_app(args.projects_dir),
            host=args.host,
            port=args.port,
        )
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
