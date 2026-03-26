#!/usr/bin/env python3
import sys
import argparse
from pathlib import Path
from src.core.project import ProjectManager
from src.core.state import PipelineState
from src.core.graph import app as pipeline_app


def parse_segment_selection(args) -> dict:
    """Parse CLI segment selection arguments into config dict."""
    selection = {}

    if args.segment_range:
        # Parse character range (e.g., "0-10000") or percentage (e.g., "0.0-0.5")
        ranges = []
        for range_str in args.segment_range.split(","):
            range_str = range_str.strip()
            if ":" in range_str:
                # Percentage format: "0:0.5"
                start, end = range_str.split(":")
                ranges.append([float(start), float(end)])
            elif "-" in range_str:
                # Character position format: "0-10000"
                start, end = range_str.split("-")
                ranges.append([int(start), int(end)])
        if ":" in args.segment_range:
            selection["percent_ranges"] = ranges
        else:
            selection["char_ranges"] = ranges

    if args.chapters:
        selection["chapters"] = [int(c.strip()) for c in args.chapters.split(",")]

    if args.keywords:
        selection["keywords"] = [k.strip() for k in args.keywords.split(",")]

    return selection


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

    # Parse segment selection
    segment_selection = parse_segment_selection(args)
    if segment_selection:
        config["generation"] = {"segment_selection": segment_selection}
        print(f"Segment selection: {segment_selection}")

    novel_text = Path(args.input).read_text(encoding="utf-8")
    project_path = pm.create_project(args.name, novel_text, config)
    print(f"Created project: {project_path}")
    print(f"Edit {project_path}/config.yaml to customize settings")


def run_indexer(args):
    pm = ProjectManager(args.projects_dir)
    pm.load_project(args.name)
    if not pm.current_project or not pm.project_config:
        raise RuntimeError(f"Failed to load project '{args.name}'")

    from src.agents.lore_master import lore_master

    lore_dir = pm.current_project / "assets" / "lore"
    force = getattr(args, "force", False)
    if (lore_dir / "toc.json").exists() and not force:
        print(f"Lore master already ran. TOC exists at {lore_dir / 'toc.json'}")
        print("Use --force to re-run.")
        return

    if force and (lore_dir / "toc.json").exists():
        print("Force re-running lore master...")
        import shutil

        shutil.rmtree(lore_dir / "chapters", ignore_errors=True)
        (lore_dir / "toc.json").unlink(missing_ok=True)

    print("Running lore master...")
    novel_text = (pm.current_project / "src" / "novel.txt").read_text(encoding="utf-8")

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

    result = lore_master(initial_state)
    if result.get("last_error"):
        print(f"\nError: {result['last_error']}")
        sys.exit(1)

    print(f"\nLore Master complete!")
    print(f"  TOC: {lore_dir / 'toc.json'}")
    print(f"  Entities: {lore_dir / 'entities.json'}")


def run_lore_master(args):
    return run_indexer(args)

    if result["entity_graph"]:
        print("  Sample entities:")
        for name, entity in list(result["entity_graph"].items())[:5]:
            print(f"    - {name}: {entity.attributes.get('type', 'unknown')}")

        # Save entity graph to file
        entity_data = {
            name: entity.attributes for name, entity in result["entity_graph"].items()
        }
        pm.save_entity_graph(entity_data)
        print(f"\n  Saved entities to: {pm.get_assets_path('lore', 'entities.json')}")


def run_screenwriter(args):
    pm = ProjectManager(args.projects_dir)
    pm.load_project(args.name)
    if not pm.current_project or not pm.project_config:
        raise RuntimeError(f"Failed to load project '{args.name}'")

    from src.agents.screenwriter import screenwriter
    from src.core.state import PipelineState

    lore_dir = pm.current_project / "assets" / "lore"
    if not (lore_dir / "toc.json").exists():
        print(
            "Error: Lore master must run first. Run: python main.py lore " + args.name
        )
        sys.exit(1)

    print("Running screenwriter...")

    novel_text = (pm.current_project / "src" / "novel.txt").read_text(encoding="utf-8")

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

    result = screenwriter(initial_state)

    if result.get("last_error"):
        print(f"\nError: {result['last_error']}")
        sys.exit(1)

    import json

    scenes_dir = pm.current_project / "scenes"
    scenes_dir.mkdir(parents=True, exist_ok=True)
    scenes_file = scenes_dir / "scenes.json"

    scenes_data = []
    for scene in result["scenes"]:
        scenes_data.append(
            {
                "id": scene.id,
                "location": scene.location,
                "time_of_day": scene.time_of_day,
                "characters": scene.characters,
                "description": scene.description,
            }
        )

    scenes_file.write_text(
        json.dumps(scenes_data, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    print(f"\nScreenwriter complete!")
    print(f"  Scenes extracted: {len(result['scenes'])}")
    print(f"  Saved to: {scenes_file}")

    if result["scenes"]:
        print("  Sample scenes:")
        for scene in result["scenes"][:3]:
            print(f"    - {scene.id}: {scene.location} ({scene.time_of_day})")


def run_director(args):
    pm = ProjectManager(args.projects_dir)
    pm.load_project(args.name)
    if not pm.current_project or not pm.project_config:
        raise RuntimeError(f"Failed to load project '{args.name}'")

    from src.agents.director import director
    from src.core.state import PipelineState

    import json

    print("Running director...")

    from src.core.state import SceneIR

    scenes = [
        SceneIR(
            id="scene_1",
            location="Marseille Port",
            time_of_day="Day",
            characters=["Edmond Dantes", "Mercedes"],
            description="Edmond arrives at the port, greeted by his father",
        )
    ]

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
        config=pm.project_config,
    )

    result = director(initial_state)

    if result.get("last_error"):
        print(f"\nError: {result['last_error']}")
        sys.exit(1)

    shots_dir = pm.current_project / "scenes" / "shots"
    shots_dir.mkdir(parents=True, exist_ok=True)
    shots_file = shots_dir / "shots.json"

    shots_data = []
    for shot in result["shot_list"]:
        shots_data.append(
            {
                "id": shot.id,
                "scene_id": shot.scene_id,
                "prompt": shot.prompt,
                "camera_movement": shot.camera_movement,
                "duration": shot.duration,
                "status": shot.status,
            }
        )

    shots_file.write_text(
        json.dumps(shots_data, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    print(f"\nDirector complete!")
    print(f"  Shots generated: {len(result['shot_list'])}")
    print(f"  Saved to: {shots_file}")

    if result["shot_list"]:
        print("  Sample shots:")
        for shot in result["shot_list"][:3]:
            print(f"    - {shot.id}: {shot.camera_movement} ({shot.duration}s)")


def run_storyboarder(args):
    pm = ProjectManager(args.projects_dir)
    pm.load_project(args.name)
    if not pm.current_project or not pm.project_config:
        raise RuntimeError(f"Failed to load project '{args.name}'")

    from src.agents.storyboarder import storyboarder
    from src.core.state import PipelineState, Shot

    shots_file = pm.current_project / "scenes" / "shots" / "shots.json"
    if not shots_file.exists():
        print("Error: No shots found. Run: python main.py shots " + args.name)
        sys.exit(1)

    import json

    shots_data = json.loads(shots_file.read_text(encoding="utf-8"))
    shots = [Shot(**s) for s in shots_data]

    print(f"Generating keyframes for {len(shots)} shots...")

    initial_state = PipelineState(
        novel_text="",
        current_chapter_id=args.name,
        entity_graph={},
        scenes=[],
        current_scene_index=0,
        shot_list=shots,
        current_shot_index=0,
        retry_count=0,
        last_error=None,
        approved_clips=[],
        project_dir=str(pm.current_project),
        style=pm.project_config["video"]["style"],
    )

    result = storyboarder(initial_state)

    if result.get("last_error"):
        print(f"\nError: {result['last_error']}")
        sys.exit(1)

    updated_shots = []
    for shot in result["shot_list"]:
        updated_shots.append(
            {
                "id": shot.id,
                "scene_id": shot.scene_id,
                "prompt": shot.prompt,
                "camera_movement": shot.camera_movement,
                "duration": shot.duration,
                "status": shot.status,
                "keyframe_url": shot.keyframe_url,
            }
        )

    shots_file.write_text(
        json.dumps(updated_shots, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    print(f"\nStoryboarder complete!")
    print(
        f"  Keyframes generated: {len([s for s in result['shot_list'] if s.status == 'storyboarded'])}"
    )


def run_animator(args):
    pm = ProjectManager(args.projects_dir)
    pm.load_project(args.name)
    if not pm.current_project or not pm.project_config:
        raise RuntimeError(f"Failed to load project '{args.name}'")

    from src.agents.animator import animator
    from src.core.state import PipelineState, Shot

    shots_file = pm.current_project / "scenes" / "shots" / "shots.json"
    if not shots_file.exists():
        print("Error: No shots found. Run: python main.shots " + args.name)
        sys.exit(1)

    import json

    shots_data = json.loads(shots_file.read_text(encoding="utf-8"))
    shots = [Shot(**s) for s in shots_data]

    pending_shots = [s for s in shots if s.status == "storyboarded"]
    print(f"Animating {len(pending_shots)} shots...")

    initial_state = PipelineState(
        novel_text="",
        current_chapter_id=args.name,
        entity_graph={},
        scenes=[],
        current_scene_index=0,
        shot_list=shots,
        current_shot_index=0,
        retry_count=0,
        last_error=None,
        approved_clips=[],
        project_dir=str(pm.current_project),
        style=pm.project_config["video"]["style"],
    )

    for i in range(len(pending_shots)):
        initial_state["current_shot_index"] = i
        result = animator(initial_state)

        if result.get("last_error"):
            print(f"\nError on shot {i + 1}: {result['last_error']}")
            continue

    print(f"\nAnimator complete!")


def run_qa_linter(args):
    pm = ProjectManager(args.projects_dir)
    pm.load_project(args.name)
    if not pm.current_project or not pm.project_config:
        raise RuntimeError(f"Failed to load project '{args.name}'")

    from src.agents.qa_linter import qa_linter
    from src.core.state import PipelineState, Shot

    shots_file = pm.current_project / "scenes" / "shots" / "shots.json"
    if not shots_file.exists():
        print("Error: No shots found. Run: python main.py animate " + args.name)
        sys.exit(1)

    import json

    shots_data = json.loads(shots_file.read_text(encoding="utf-8"))
    shots = [Shot(**s) for s in shots_data]

    animated_shots = [s for s in shots if s.status == "animated"]
    print(f"QA checking {len(animated_shots)} shots...")

    initial_state = PipelineState(
        novel_text="",
        current_chapter_id=args.name,
        entity_graph={},
        scenes=[],
        current_scene_index=0,
        shot_list=shots,
        current_shot_index=0,
        retry_count=0,
        last_error=None,
        approved_clips=[],
        project_dir=str(pm.current_project),
        style=pm.project_config["video"]["style"],
    )

    for i in range(len(animated_shots)):
        initial_state["current_shot_index"] = i
        result = qa_linter(initial_state)

        if result.get("last_error"):
            print(f"\nError on shot {i + 1}: {result['last_error']}")
            continue

    approved_count = len([s for s in result["shot_list"] if s.status == "approved"])
    print(f"\nQA Linter complete!")
    print(f"  Approved: {approved_count}")
    print(f"  Rejected: {len(animated_shots) - approved_count}")


def run_compositor(args):
    pm = ProjectManager(args.projects_dir)
    pm.load_project(args.name)
    if not pm.current_project or not pm.project_config:
        raise RuntimeError(f"Failed to load project '{args.name}'")

    from src.agents.compositor import compositor
    from src.core.state import PipelineState, Shot

    shots_file = pm.current_project / "scenes" / "shots" / "shots.json"
    if not shots_file.exists():
        print("Error: No shots found. Run: python main.py animate " + args.name)
        sys.exit(1)

    import json

    shots_data = json.loads(shots_file.read_text(encoding="utf-8"))
    shots = [Shot(**s) for s in shots_data]

    approved_clips = [
        s.video_url for s in shots if s.status == "approved" and s.video_url
    ]

    if not approved_clips:
        print("Error: No approved clips found. Run: python main.py qa " + args.name)
        sys.exit(1)

    print(f"Compositing {len(approved_clips)} approved clips...")

    initial_state = PipelineState(
        novel_text="",
        current_chapter_id=args.name,
        entity_graph={},
        scenes=[],
        current_scene_index=0,
        shot_list=shots,
        current_shot_index=0,
        retry_count=0,
        last_error=None,
        approved_clips=approved_clips,
        project_dir=str(pm.current_project),
        style=pm.project_config["video"]["style"],
    )

    result = compositor(initial_state)

    if result.get("last_error"):
        print(f"\nError: {result['last_error']}")
        sys.exit(1)

    print(f"\nCompositor complete!")
    if result.get("final_video_path"):
        print(f"  Final video: {result['final_video_path']}")


def _old_run_indexer(args):

    from src.agents.indexer import text_segmenter

    index_dir = pm.current_project / "memory"
    if (index_dir / "toc.json").exists():
        print(f"Indexer already ran. TOC exists at {index_dir / 'toc.json'}")
        return

    print("Running indexer...")
    novel_text = (pm.current_project / "src" / "novel.txt").read_text(encoding="utf-8")

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

    result = text_segmenter(initial_state)
    print(f"\nIndexer complete!")
    print(f"  Project: {args.name}")
    print(f"  TOC: {pm.current_project / 'memory' / 'toc.json'}")


def run_pre_production(args):
    pm = ProjectManager(args.projects_dir)
    pm.load_project(args.name)
    if not pm.current_project or not pm.project_config:
        raise RuntimeError(f"Failed to load project '{args.name}'")

    print("Running pre-production stage...")

    lore_dir = pm.current_project / "assets" / "lore"
    toc_path = lore_dir / "toc.json"

    if not toc_path.exists():
        print("Lore master not run yet. Running lore master first...")
        run_indexer(args)
    else:
        print(f"Using existing lore data: {toc_path}")

    stage = getattr(args, "stage", "all")
    if stage == "lore":
        print("Lore stage complete.")
        return

    if stage in ("all", "scenes"):
        print("Running screenwriter...")
        run_screenwriter(args)

    if stage in ("all", "shots"):
        print("Running director...")
        run_director(args)

    print("\nPre-production complete!")


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

        from src.agents.storyboarder import storyboarder

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

        from src.agents.animator import animator
        from src.agents.qa_linter import qa_linter

        for attempt in range(max_retries):
            print(f"  Attempt {attempt + 1}/{max_retries}...")

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

    from src.agents.compositor import compositor

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
    create_parser.add_argument(
        "--segment-range",
        type=str,
        help="Character range to animate (e.g., '0-10000' or '0:1.0' for percentage)",
    )
    create_parser.add_argument(
        "--chapters",
        type=str,
        help="Comma-separated list of chapter numbers to animate (e.g., '1,2,3')",
    )
    create_parser.add_argument(
        "--keywords",
        type=str,
        help="Comma-separated keywords to select relevant paragraphs",
    )
    create_parser.set_defaults(func=create_project)

    indexer_parser = subparsers.add_parser(
        "indexer", aliases=["index"], help="Index novel into chapters"
    )
    indexer_parser.add_argument("name", help="Project name")
    indexer_parser.add_argument(
        "--force", action="store_true", help="Force re-indexing"
    )
    indexer_parser.set_defaults(func=run_indexer)

    lore_parser = subparsers.add_parser(
        "lore-master", aliases=["lore"], help="Extract entities (lore master)"
    )
    lore_parser.add_argument("name", help="Project name")
    lore_parser.set_defaults(func=run_lore_master)

    scenes_parser = subparsers.add_parser(
        "screenwriter", aliases=["scenes"], help="Generate scenes (screenwriter)"
    )
    scenes_parser.add_argument("name", help="Project name")
    scenes_parser.set_defaults(func=run_screenwriter)

    shots_parser = subparsers.add_parser(
        "director", aliases=["shots"], help="Generate shots (director)"
    )
    shots_parser.add_argument("name", help="Project name")
    shots_parser.set_defaults(func=run_director)

    storyboard_parser = subparsers.add_parser(
        "storyboarder", aliases=["storyboard"], help="Generate keyframes (storyboarder)"
    )
    storyboard_parser.add_argument("name", help="Project name")
    storyboard_parser.set_defaults(func=run_storyboarder)

    animate_parser = subparsers.add_parser(
        "animator", aliases=["animate"], help="Generate videos (animator)"
    )
    animate_parser.add_argument("name", help="Project name")
    animate_parser.set_defaults(func=run_animator)

    qa_parser = subparsers.add_parser(
        "qa-linter", aliases=["qa"], help="Run QA on videos (qa-linter)"
    )
    qa_parser.add_argument("name", help="Project name")
    qa_parser.set_defaults(func=run_qa_linter)

    pre_parser = subparsers.add_parser("pre-prod", help="Run full pre-production")
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
