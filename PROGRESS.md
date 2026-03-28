# Project Progress: Agentic Filming Pipeline (AFP)

## Phase 1: Core Infrastructure - COMPLETED

### Configuration System
- [x] Created `src/config.py` with ConfigLoader supporting hierarchical config loading
- [x] Implemented per-agent configuration (each agent has its own provider, model, API key)
- [x] Environment variable resolution for API keys (ENV:VAR_NAME pattern)
- [x] Support for project-specific config.yaml files
- [x] Clean config.yaml with model definitions and agent references

### Provider Abstraction Layer
- [x] Created `src/providers/base.py` with base classes for LLM, Image, and Video providers
- [x] Implemented `src/providers/gemini.py` - Gemini LLM and image generation
- [x] Implemented `src/providers/minimax.py` - MiniMax LLM, image and video generation
- [x] Implemented `src/providers/openai_compat.py` - OpenAI-compatible LLM provider
- [x] Created `src/providers/factory.py` for dynamic provider instantiation
- [x] Added `generate_structured()` method for JSON schema enforcement
- [x] All providers respect config.yaml model settings

### Project Management
- [x] Created `src/core/project.py` with shot-based asset organization
- [x] Project structure: `src/`, `assets/`, `index/`, `scenes/`, `cache/`, `checkpoints/`, `output/`, `logs/`
- [x] Shared assets directory for characters, locations, audio, lore
- [x] Checkpoint system for resumable pipeline execution
- [x] Scene-based shot organization: `scenes/{scene_id}/shots/{shot_id}/`

### Main Entry Point
- [x] Updated `main.py` with CLI structure (create, index, lore, scenes, shots, storyboard, animate, qa, post-prod, status)
- [x] Support for running individual pipeline stages
- [x] Project loading guards in place

## Phase 2: Agent Refactoring - COMPLETED

### Individual Agent Files
- [x] `src/agents/indexer.py` - Chapter segmentation with metadata extraction
- [x] `src/agents/lore_master.py` - Entity extraction (characters, locations, items)
- [x] `src/agents/screenwriter.py` - Scene chunking from chapters
- [x] `src/agents/director.py` - Shot list generation from scenes
- [x] `src/agents/storyboarder.py` - Keyframe generation
- [x] `src/agents/animator.py` - Video generation
- [x] `src/agents/qa_linter.py` - Quality assurance with VLM
- [x] `src/agents/compositor.py` - Final assembly (lip-sync, stitching)
- [x] `src/agents/utils.py` - Shared utilities for agent configuration

### JSON Schema Support
- [x] Created `src/schemas.py` with structured output schemas:
  - `CHAPTER_METADATA_SCHEMA` - Chapter title, summary, characters, events
  - `ENTITY_SCHEMA` - Entity extraction with type and description
  - `SCENE_SCHEMA` - Scene metadata (id, location, time, characters)
  - `SHOT_SCHEMA` - Shot metadata (id, prompt, camera, duration)
- [x] All LLM agents use `generate_structured()` for type-safe outputs

### Deleted Old Files
- [x] Removed `src/agents/pre_production.py` (split into individual files)
- [x] Removed `src/agents/production.py` (split into individual files)
- [x] Removed `src/agents/asset_locking.py` (renamed to storyboarder.py)
- [x] Removed `src/agents/post_production.py` (renamed to compositor.py)
- [x] Removed `src/agents/chapter_utils.py` (merged into utils.py)

## Phase 3: Documentation - COMPLETED

### Updated Documentation
- [x] `README.md` - Updated with new project structure and CLI commands
- [x] `DESIGN.md` - Updated architecture document with:
  - New project structure (src/, assets/, index/, scenes/)
  - Individual agent files organization
  - JSON schema enforcement
  - Updated provider abstraction details
- [x] `PROGRESS.md` - This file, tracking current status

## Phase 4: Testing - COMPLETED

### Test Status
- [x] Test indexer agent (Chapter-based segmentation)
- [x] Test lore_master agent (Entity mutation extraction)
- [x] Test screenwriter agent (Scene IR compilation)
- [x] Test director agent (Shot list AST generation)
- [x] Test art_director agent (Art style specification)
- [x] Test storyboarder agent (Keyframe generation)
- [x] Test animator agent (Video rasterization)
- [x] Test image_qa & video_qa agents (Visual linter loops)
- [x] Test compositor agent (Final assembly)

### Resolved Issues
- Fixed bug in `animator.py` using wrong path utility (`get_production_shot_path`)
- Updated all unit tests to match new `PipelineState` and node-based architecture
- Removed obsolete and broken test files
- Replaced `qa_linter.py` with separate `image_qa.py` and `video_qa.py` for granularity

## Project Structure

```
project/
├── novel.txt              # Source novel text
├── index/                 # Chapter index
│   └── chapters/          # Individual chapter files
├── runtime/               # Intermediate Representations (IR)
│   ├── lore/              # Entity mutations
│   ├── screenplay/        # Scene IR
│   └── shot_list.json     # Compiled shot list AST
├── production/            # Generated assets
│   └── scene_{scene_id}/
│       ├── art_style/     # Art style references
│       └── shot_{shot_id}/
│           ├── keyframe_begin.png
│           ├── keyframe_end.png
│           ├── video.mp4
│           └── metadata.json
├── output/                # Final deliverables
├── logs/                  # Pipeline logs
└── config.yaml            # Project configuration
```

## Key Files

**Configuration:**
- `config.yaml` - Main configuration file
- `config.yaml.template` - Template with defaults
- `src/config.py` - ConfigLoader implementation

**Providers:**
- `src/providers/base.py` - Base provider classes
- `src/providers/gemini.py` - Gemini provider
- `src/providers/minimax.py` - MiniMax provider
- `src/providers/openai_compat.py` - OpenAI-compatible provider
- `src/providers/factory.py` - ProviderFactory

**Core:**
- `src/core/project.py` - Project management (renamed from project_manager.py)
- `src/core/graph.py` - LangGraph workflow
- `src/core/state.py` - Pipeline state definitions

**Agents:**
- `src/agents/indexer.py` - Text segmentation
- `src/agents/lore_master.py` - Entity extraction
- `src/agents/screenwriter.py` - Scene chunking
- `src/agents/director.py` - Shot list generation
- `src/agents/storyboarder.py` - Keyframe generation
- `src/agents/animator.py` - Video generation
- `src/agents/qa_linter.py` - Quality assurance
- `src/agents/compositor.py` - Final assembly
- `src/agents/utils.py` - Shared agent utilities
- `src/schemas.py` - JSON schemas for structured outputs

**Entry Point:**
- `main.py` - CLI and pipeline runner
