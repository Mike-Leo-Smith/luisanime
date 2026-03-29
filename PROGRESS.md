# Project Progress: Agentic Filming Pipeline (AFP)

## Current Status: AFC (Autonomous Film Crew) Architecture - IMPLEMENTED

The project has been refactored from a linear pipeline to a **LangGraph-based Autonomous Film Crew (AFC)** architecture with 9 specialized agents.

---

## Phase 1: Core Infrastructure - COMPLETED

### Configuration System
- [x] Created `src/config.py` with ConfigLoader supporting hierarchical config loading
- [x] Implemented per-agent configuration (each agent has its own provider, model, API key)
- [x] Environment variable resolution for API keys (ENV:VAR_NAME pattern)
- [x] Support for project-specific config.yaml files
- [x] Clean config.yaml.template with model definitions and agent references

### Provider Abstraction Layer
- [x] Created `src/providers/base.py` with base classes for LLM, Image, and Video providers
- [x] Implemented `src/providers/gemini.py` - Gemini LLM and image generation
- [x] Implemented `src/providers/minimax.py` - MiniMax video generation
- [x] Implemented `src/providers/openai_compat.py` - OpenAI-compatible LLM provider
- [x] Created `src/providers/factory.py` for dynamic provider instantiation
- [x] Added `generate_structured()` method for JSON schema enforcement
- [x] All providers respect config.yaml model settings

### State Management
- [x] Created `src/pipeline/state.py` with `AFCState` TypedDict
- [x] Implemented `FinancialLedger` for budget tracking
- [x] Implemented `ShotExecutionPlan` for shot-level IR
- [x] Annotation-based state merging for LangGraph compatibility

### Project Management
- [x] Created `src/pipeline/project.py` with AFC project structure
- [x] New structure: `00_project_config/`, `01_source_material/`, `02_screenplays/`, `03_lore_bible/`, `04_production_slate/`, `05_dailies/`, `06_logs/`
- [x] Checkpoint system for resumable pipeline execution
- [x] Legacy compatibility (symlinks for old paths)

### Workspace Management
- [x] Created `src/pipeline/workspace.py` with `AgenticWorkspace` class
- [x] File I/O utilities for agents
- [x] JSON serialization helpers

### LangGraph Workflow
- [x] Created `src/pipeline/graph.py` with complete workflow graph
- [x] Conditional routing functions for macro/micro loops
- [x] Circuit breaker implementation (escalation after 3 retries)
- [x] Retry loops for keyframe QA and render QA

### Main Entry Point
- [x] Updated `main.py` with simplified CLI (create, run, status)
- [x] State initialization from project
- [x] LangGraph invocation

---

## Phase 2: Agent Implementation - COMPLETED

### The Film Crew (All 9 Agents)

| Agent | Status | File | Description |
|-------|--------|------|-------------|
| **Screenwriter** | ✅ Complete | `src/agents/screenwriter.py` | Parses novel into structured scenes |
| **Showrunner** | ✅ Complete | `src/agents/showrunner.py` | Orchestrates workflow, audits budget |
| **Director** | ✅ Complete | `src/agents/director.py` | Generates shot plans with continuity |
| **Script Coordinator** | ✅ Complete | `src/agents/script_coordinator.py` | Manages shot queue |
| **Production Designer** | ✅ Complete | `src/agents/production_designer.py` | Establishes visual style |
| **Cinematographer** | ✅ Complete | `src/agents/cinematographer.py` | Generates keyframes |
| **Continuity Supervisor** | ✅ Complete | `src/agents/continuity_supervisor.py` | VLM-based QA |
| **Lead Animator** | ✅ Complete | `src/agents/lead_animator.py` | Generates video |
| **Editor** | ✅ Complete | `src/agents/editor.py` | Assembles final video |

### Agent Base Classes
- [x] Created `src/agents/base.py` with `BaseCreative`, `BaseOrchestrator`, `BaseQA`
- [x] Provider initialization from config
- [x] Workspace integration

### Agent Utilities
- [x] Created `src/agents/utils.py` - Provider configuration helpers
- [x] Created `src/agents/prompts.py` - System prompts for agents

### JSON Schema Support
- [x] Created `src/schemas.py` with structured output schemas:
  - Scene schema for Screenwriter
  - Shot list schema for Director
- [x] All LLM agents use `generate_structured()` for type-safe outputs

---

## Phase 3: Documentation - COMPLETED

### Updated Documentation
- [x] `README.md` - Updated with:
  - New AFC architecture
  - Correct agent list (9 agents)
  - New project structure (00-06 directories)
  - Simplified CLI (create, run, status)
  - LangGraph workflow description
- [x] `DESIGN.md` - Updated with:
  - LangGraph topology
  - Agent routing diagram
  - AFCState documentation
  - Circuit breaker pattern
  - Budget management
- [x] `PROGRESS.md` - This file, tracking current status
- [x] `AGENTS.md` - Agent development guide (still relevant)

---

## Phase 4: Deleted/Deprecated Components

### Removed Files
The following files from the old linear pipeline have been removed:
- `src/agents/indexer.py` → Functionality merged into Screenwriter
- `src/agents/lore_master.py` → Functionality merged into Production Designer
- `src/agents/storyboarder.py` → Renamed to Cinematographer
- `src/agents/animator.py` → Renamed to Lead Animator
- `src/agents/qa_linter.py` → Renamed to Continuity Supervisor
- `src/agents/compositor.py` → Renamed to Editor
- `src/agents/pre_production.py` → Split into individual agents
- `src/agents/production.py` → Split into individual agents
- `src/agents/post_production.py` → Split into individual agents
- `src/core/graph.py` (old) → Replaced with LangGraph version

### Deprecated CLI Commands
Old granular commands removed:
- `python main.py index ...`
- `python main.py lore ...`
- `python main.py scenes ...`
- `python main.py shots ...`
- `python main.py storyboard ...`
- `python main.py animate ...`
- `python main.py qa ...`
- `python main.py post-prod ...`

Replaced with:
- `python main.py create ...`
- `python main.py run ...`
- `python main.py status ...`

---

## Project Structure

### New AFC Structure

```
projects/{project_name}/
├── 00_project_config/         # Configuration
│   └── config.yaml
├── 01_source_material/        # Source novel
│   └── novel.txt
├── 02_screenplays/            # Scene scripts (JSON)
├── 03_lore_bible/             # Style guides, character sheets
├── 04_production_slate/       # Shot plans, keyframes
│   └── shots/
├── 05_dailies/                # Generated video clips
├── 06_logs/                   # Production logs
└── config.yaml                # Legacy config
```

### Source Structure

```
src/
├── agents/
│   ├── __init__.py
│   ├── base.py                # Base agent classes
│   ├── showrunner.py          # Orchestration agent
│   ├── screenwriter.py        # Novel parsing agent
│   ├── director.py            # Shot planning agent
│   ├── production_designer.py # Visual style agent
│   ├── cinematographer.py     # Keyframe generation agent
│   ├── lead_animator.py       # Video generation agent
│   ├── continuity_supervisor.py # QA agent
│   ├── script_coordinator.py  # Queue management agent
│   ├── editor.py              # Assembly agent
│   ├── previs_artist.py       # Pre-visualization (legacy)
│   ├── prompts.py             # System prompts
│   └── utils.py               # Agent utilities
├── pipeline/
│   ├── project.py             # Project management
│   ├── graph.py               # LangGraph workflow
│   ├── state.py               # AFCState definitions
│   ├── workspace.py           # File I/O for agents
│   └── chapters.py            # Chapter database
├── providers/
│   ├── base.py                # Provider base classes
│   ├── gemini.py              # Gemini provider
│   ├── minimax.py             # MiniMax provider
│   ├── openai_compat.py       # OpenAI-compatible provider
│   └── factory.py             # Provider factory
├── config.py                  # Configuration loader
└── schemas.py                 # JSON schemas
```

---

## Key Files

**Configuration:**
- `config.yaml.template` - Main configuration template
- `src/config.py` - ConfigLoader implementation

**Providers:**
- `src/providers/base.py` - Base provider classes
- `src/providers/gemini.py` - Gemini provider
- `src/providers/minimax.py` - MiniMax provider
- `src/providers/openai_compat.py` - OpenAI-compatible provider
- `src/providers/factory.py` - ProviderFactory

**Pipeline:**
- `src/pipeline/project.py` - Project management
- `src/pipeline/graph.py` - LangGraph workflow
- `src/pipeline/state.py` - AFCState definitions
- `src/pipeline/workspace.py` - AgenticWorkspace
- `src/pipeline/chapters.py` - Chapter database

**Entry Point:**
- `main.py` - CLI and pipeline runner

---

## Roadmap / Next Steps

### Short Term
- [ ] Add `--stage` flag to CLI for resuming from specific stage
- [ ] Add `--shot-index` flag for resuming from specific shot
- [ ] Implement actual cost tracking in providers
- [ ] Add progress persistence (checkpoints to disk)
- [ ] Add error recovery and retry logic

### Medium Term
- [ ] Implement lip-sync integration
- [ ] Add audio generation (TTS)
- [ ] Add music/BGM selection
- [ ] Implement advanced transitions in Editor
- [ ] Add support for more video providers (Veo, Sora, Kling)

### Long Term
- [ ] Web UI for project management
- [ ] Real-time progress monitoring
- [ ] Distributed execution support
- [ ] Advanced continuity tracking across scenes
- [ ] Custom model fine-tuning for style consistency

---

## Known Issues

1. **Type Checking**: Some agents have LSP errors around provider method calls - runtime works but type hints need refinement
2. **Cost Tracking**: Currently tracks at agent level but not integrated with actual API billing
3. **Checkpointing**: State is in-memory only; disk persistence not yet implemented
4. **Error Recovery**: Basic error handling in place but needs more robust retry logic

---

## Testing Status

- [x] Basic agent instantiation
- [x] Provider factory
- [x] Configuration loading
- [x] Project creation
- [ ] Full pipeline integration test (needs API keys)
- [ ] Individual agent unit tests
- [ ] Mock provider tests

---

*Last Updated: March 29, 2026*
*Architecture: Autonomous Film Crew (AFC) via LangGraph*
*Total Agents: 9*
