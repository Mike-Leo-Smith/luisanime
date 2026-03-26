#!/usr/bin/env python3
import sys
import argparse
from pathlib import Path
from src.core.project_manager import ProjectManager
from src.core.state import PipelineState
from src.core.graph import app as pipeline_app


def create_project(args):
    pm = ProjectManager(args.projects_dir)

    config = {
        "video": {
            "style": args.style,
            "resolution": args.resolution,
            "fps": args.fps,
            "max_shots": args.max_shots,
        }
    }

    novel_text = Path(args.input).read_text(encoding="utf-8")
    project_path = pm.create_project(args.name, novel_text, config)
    print(f"Created project: {project_path}")
    print(f"Edit {project_path}/project.yaml to customize settings")


def run_pre_production(args):
    pm = ProjectManager(args.projects_dir)
    pm.load_project(args.name)
    if not pm.current_project or not pm.project_config:
        raise RuntimeError(
            f"Failed to load project '{args.name}' or missing project configuration"
        )

    print("Running pre-production stage...")
    novel_text = (pm.current_project / "input" / "novel.txt").read_text(
        encoding="utf-8"
    )

    initial_state = PipelineState(
        novel_text=novel_text,
        current_chapter_id=args.name,
        entity_graph={},
        scenes=[],
        current_scene_index=0,
        shot_list=[],
        current_shot_index=0,
        retry_count=0,
        last_error=None,
        approved_clips=[],
        project_dir=str(pm.current_project),
        style=pm.project_config["video"]["style"],
    )

    state = pipeline_app.invoke(initial_state)

    pm.save_asset("pre_production", "entities.json", dict(state["entity_graph"]))
    pm.save_asset("pre_production", "scenes.json", [s.dict() for s in state["scenes"]])
    pm.save_asset(
        "pre_production", "shots.json", [s.dict() for s in state["shot_list"]]
    )
    pm.save_checkpoint(
        "pre_production_complete",
        {
            "stage": "pre_production",
            "entities": len(state["entity_graph"]),
            "scenes": len(state["scenes"]),
            "shots": len(state["shot_list"]),
        },
    )
    pm.log(f"Pre-production complete: {len(state['shot_list'])} shots generated")

    print(f"Generated {len(state['shot_list'])} shots")
    print(f"Assets saved to {pm.current_project / '.staging' / 'pre_production'}")


def generate_assets(args):
    pm = ProjectManager(args.projects_dir)
    pm.load_project(args.name)
    if not pm.current_project or not pm.project_config:
        raise RuntimeError(
            f"Failed to load project '{args.name}' or missing project configuration"
        )

    shots_data = pm.load_asset("pre_production", "shots.json")
    if not shots_data:
        print("Error: No shots found. Run pre-production first.")
        sys.exit(1)

    from src.core.state import Shot

    shots = [Shot(**s) for s in shots_data]

    print(f"Generating keyframes for {len(shots)} shots...")

    for i, shot in enumerate(shots):
        if args.shot_number is not None and i != args.shot_number:
            continue

        print(f"\n[{i + 1}/{len(shots)}] Generating keyframe for shot {shot.id}...")

        state = PipelineState(
            novel_text="",
            current_chapter_id=args.name,
            entity_graph=pm.load_asset("pre_production", "entities.json") or {},
            scenes=[],
            current_scene_index=0,
            shot_list=shots,
            current_shot_index=i,
            retry_count=0,
            last_error=None,
            approved_clips=[],
            project_dir=str(pm.current_project),
            style=pm.project_config["video"]["style"],
        )

        from src.agents.asset_locking import storyboarder

        result = storyboarder(state)

        pm.save_checkpoint(
            f"keyframe_{shot.id}",
            {
                "shot_id": shot.id,
                "index": i,
                "keyframe_url": result["shot_list"][i].keyframe_url,
            },
        )
        pm.log(f"Generated keyframe for shot {shot.id}")

    print(
        f"\nKeyframes saved to {pm.current_project / '.staging' / 'assets' / 'keyframes'}"
    )


def run_production(args):
    pm = ProjectManager(args.projects_dir)
    pm.load_project(args.name)
    if not pm.current_project or not pm.project_config:
        raise RuntimeError(
            f"Failed to load project '{args.name}' or missing project configuration"
        )

    shots_data = pm.load_asset("pre_production", "shots.json")
    if not shots_data:
        print("Error: No shots found. Run pre-production first.")
        sys.exit(1)

    from src.core.state import Shot

    shots = [Shot(**s) for s in shots_data]

    keyframes_dir = pm.get_staging_path("assets", "keyframes")

    for i, shot in enumerate(shots):
        if args.shot_number is not None and i != args.shot_number:
            continue

        print(f"\n[{i + 1}/{len(shots)}] Processing shot {shot.id}...")

        keyframe_files = list(keyframes_dir.glob(f"*{shot.id}*.png"))
        if not keyframe_files:
            print(f"  Warning: No keyframe found for shot {shot.id}, skipping...")
            continue

        state = PipelineState(
            novel_text="",
            current_chapter_id=args.name,
            entity_graph={},
            scenes=[],
            current_scene_index=0,
            shot_list=shots,
            current_shot_index=i,
            retry_count=0,
            last_error=None,
            approved_clips=[],
            project_dir=str(pm.current_project),
            style=pm.project_config["video"]["style"],
        )

        max_retries = pm.project_config["generation"]["max_retries_per_shot"]
        approved = False

        for attempt in range(max_retries):
            print(f"  Attempt {attempt + 1}/{max_retries}...")

            from src.agents.production import animator, qa_linter

            state = animator(state)
            video_url = state["shot_list"][i].video_url

            if not video_url:
                print(f"  Animation failed, retrying...")
                continue

            state = qa_linter(state)

            if state["shot_list"][i].status == "approved":
                approved = True

                import requests

                clip_path = pm.get_staging_path("production", "clips", f"{shot.id}.mp4")
                r = requests.get(video_url, stream=True)
                with open(clip_path, "wb") as f:
                    for chunk in r.iter_content(chunk_size=8192):
                        f.write(chunk)

                pm.save_checkpoint(
                    f"clip_{shot.id}_approved",
                    {
                        "shot_id": shot.id,
                        "attempt": attempt + 1,
                        "clip_path": str(clip_path),
                    },
                )
                pm.log(f"Shot {shot.id} approved and saved")
                print(f"  Approved! Saved to {clip_path}")
                break
            else:
                print(f"  QA rejected: {state.get('last_error', 'Unknown')}")
                state["retry_count"] += 1

        if not approved:
            print(f"  Failed to approve shot {shot.id} after {max_retries} attempts")
            pm.log(f"Shot {shot.id} failed after {max_retries} retries", "ERROR")

    approved_clips = list(pm.get_staging_path("production", "clips").glob("*.mp4"))
    print(f"\nProduction complete: {len(approved_clips)}/{len(shots)} clips approved")


def run_post_production(args):
    pm = ProjectManager(args.projects_dir)
    pm.load_project(args.name)
    if not pm.current_project or not pm.project_config:
        raise RuntimeError(
            f"Failed to load project '{args.name}' or missing project configuration"
        )

    clips_dir = pm.get_staging_path("production", "clips")
    clips = sorted(clips_dir.glob("*.mp4"))

    if not clips:
        print("Error: No clips found. Run production first.")
        sys.exit(1)

    print(f"Running post-production on {len(clips)} clips...")

    approved_clips = [str(c) for c in clips]

    state = PipelineState(
        novel_text="",
        current_chapter_id=args.name,
        entity_graph={},
        scenes=[],
        current_scene_index=0,
        shot_list=[],
        current_shot_index=0,
        retry_count=0,
        last_error=None,
        approved_clips=approved_clips,
        project_dir=str(pm.current_project),
        style=pm.project_config["video"]["style"],
    )

    from src.agents.post_production import compositor

    result = compositor(state)

    final_video = result.get("final_video_path")
    if final_video and Path(final_video).exists():
        output_path = pm.get_output_path("final_video.mp4")
        import shutil

        shutil.copy(final_video, output_path)

        pm.save_checkpoint(
            "post_production_complete",
            {"final_video": str(output_path), "clips_used": len(approved_clips)},
        )
        pm.log(f"Post-production complete: {output_path}")
        print(f"Final video saved to: {output_path}")
    else:
        print("Error: Post-production failed")
        sys.exit(1)


def status(args):
    pm = ProjectManager(args.projects_dir)
    pm.load_project(args.name)
    if not pm.current_project or not pm.project_config:
        raise RuntimeError(
            f"Failed to load project '{args.name}' or missing project configuration"
        )

    stages = pm.get_stage_status()
    checkpoints = pm.list_checkpoints()

    print(f"Project: {args.name}")
    print(f"Location: {pm.current_project}")
    print()
    print("Stage Status:")
    for stage, completed in stages.items():
        status = "✓" if completed else "○"
        print(f"  {status} {stage}")
    print()
    print(f"Checkpoints: {', '.join(checkpoints) if checkpoints else 'None'}")


def main():
    parser = argparse.ArgumentParser(description="Agentic Filming Pipeline")
    parser.add_argument(
        "--projects-dir", default="./projects", help="Projects root directory"
    )

    subparsers = parser.add_subparsers(dest="command", help="Commands")

    create_parser = subparsers.add_parser("create", help="Create a new project")
    create_parser.add_argument("name", help="Project name")
    create_parser.add_argument("input", help="Input novel text file")
    create_parser.add_argument(
        "--style", default="anime", choices=["anime", "cinematic", "realistic"]
    )
    create_parser.add_argument(
        "--resolution", default="1080p", choices=["720p", "1080p", "4k"]
    )
    create_parser.add_argument("--fps", type=int, default=24)
    create_parser.add_argument("--max-shots", type=int, default=10)
    create_parser.set_defaults(func=create_project)

    pre_parser = subparsers.add_parser("pre-prod", help="Run pre-production stage")
    pre_parser.add_argument("name", help="Project name")
    pre_parser.set_defaults(func=run_pre_production)

    assets_parser = subparsers.add_parser("assets", help="Generate keyframe assets")
    assets_parser.add_argument("name", help="Project name")
    assets_parser.add_argument(
        "--shot-number", type=int, help="Generate specific shot only"
    )
    assets_parser.set_defaults(func=generate_assets)

    prod_parser = subparsers.add_parser("produce", help="Run production stage")
    prod_parser.add_argument("name", help="Project name")
    prod_parser.add_argument(
        "--shot-number", type=int, help="Process specific shot only"
    )
    prod_parser.set_defaults(func=run_production)

    post_parser = subparsers.add_parser("post-prod", help="Run post-production stage")
    post_parser.add_argument("name", help="Project name")
    post_parser.set_defaults(func=run_post_production)

    status_parser = subparsers.add_parser("status", help="Show project status")
    status_parser.add_argument("name", help="Project name")
    status_parser.set_defaults(func=status)

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    args.func(args)


def run_pipeline(text: str, style: str = "anime", project_dir: str = "./workspace"):
    from src.core.graph import app as pipeline_app
    import uuid

    initial_state = PipelineState(
        novel_text=text,
        current_chapter_id=str(uuid.uuid4()),
        entity_graph={},
        scenes=[],
        current_scene_index=0,
        shot_list=[],
        current_shot_index=0,
        retry_count=0,
        last_error=None,
        approved_clips=[],
        project_dir=project_dir,
        style=style,
    )

    print("Starting Agentic Filming Pipeline...")
    final_state = pipeline_app.invoke(initial_state)

    print("\nPipeline Completed!")
    print(f"Total Scenes: {len(final_state['scenes'])}")
    print(f"Total Shots: {len(final_state['shot_list'])}")
    print(f"Entities Found: {list(final_state['entity_graph'].keys())}")

    return final_state


if __name__ == "__main__":
    main()
