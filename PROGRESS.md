# Project Progress: Agentic Filming Pipeline (AFP)

## Current Status: Full Pipeline Operational

The project uses a **LangGraph-based Autonomous Film Crew (AFC)** architecture with 9 specialized agents. The full pipeline runs end-to-end: novel text → scene parsing → shot planning → keyframe generation → video generation → per-scene assembly.

---

## Phase 1: Core Infrastructure — COMPLETED

### Configuration System
- [x] Hierarchical config loading (`src/config.py`)
- [x] Per-agent configuration (independent provider, model, API key per agent)
- [x] Environment variable resolution (`ENV:VAR_NAME` pattern)
- [x] Style presets (anime, cinematic) with no-text enforcement

### Provider Abstraction Layer
- [x] `src/providers/base.py` — Base classes for LLM, Image, Video
- [x] `src/providers/gemini.py` — Gemini 3.1 Pro (LLM + vision) and Gemini 3.1 Flash Image Preview
- [x] `src/providers/kling.py` — Kling v3-omni video generation with JWT auth and task polling
- [x] `src/providers/minimax.py` — MiniMax Hailuo-2.3 video generation
- [x] `src/providers/factory.py` — Dynamic provider instantiation
- [x] `generate_structured()` for JSON schema enforcement

### State Management
- [x] `AFCState` TypedDict with annotation-based merging
- [x] `ShotExecutionPlan` with `is_continuation` flag for shot continuation
- [x] `FinancialLedger` for budget tracking
- [x] Scene ID normalization (`scene_{n:02d}`)
- [x] Deterministic shot ID format (`scene_01_SHOT_001`)

### LangGraph Workflow
- [x] Complete workflow graph with macro (scene) and micro (shot) loops
- [x] Conditional routing (Showrunner → Director, Script Coordinator → Production Designer/Editor)
- [x] Circuit breaker (keyframe QA best-of-N fallback after 3 failures)
- [x] Video QA auto-pass (saves API costs)

---

## Phase 2: Agent Implementation — COMPLETED

| Agent | File | Key Features |
|-------|------|--------------|
| **Screenwriter** | `src/agents/screenwriter.py` | Novel → scenes, scene_id normalization |
| **Showrunner** | `src/agents/showrunner.py` | Budget audit, macro loop routing |
| **Director** | `src/agents/director.py` | Shot planning, `is_continuation` marking, deterministic shot IDs |
| **Script Coordinator** | `src/agents/script_coordinator.py` | Shot queue management, per-character state mutations, state clearing between shots |
| **Production Designer** | `src/agents/production_designer.py` | Master style, character design sheets, location reference images |
| **Cinematographer** | `src/agents/cinematographer.py` | Starting-frame keyframe generation, continuation frame extraction, versioned keyframes |
| **Continuity Supervisor** | `src/agents/continuity_supervisor.py` | VLM keyframe QA, best-of-N selection, auto-pass for continuation shots, mirror reflection handling |
| **Lead Animator** | `src/agents/lead_animator.py` | Video generation via Kling, continuation mode with merged actions, prompt distillation |
| **Editor** | `src/agents/editor.py` | Per-scene video assembly, scale/pad normalization for resolution mismatches |

---

## Phase 3: Quality & Continuity Features — COMPLETED

- [x] Versioned keyframes (`keyframe_v{n}.png`, up to 3 attempts)
- [x] Best-of-N keyframe fallback when all attempts fail QA
- [x] Character clothing descriptions in keyframe and video prompts
- [x] Location design generation and reference in keyframe prompts
- [x] Mirror reflection QA fix (laterally inverted details not flagged)
- [x] No-text enforcement in all generation prompts
- [x] Shot continuation (`is_continuation` flag):
  - Director marks at planning time
  - Cinematographer extracts last frame from previous video
  - Continuity Supervisor auto-passes continuation keyframes
  - Lead Animator uses `generate_video_continuation()` with merged action descriptions
- [x] Per-scene preview video assembly by Editor
- [x] Editor scale/pad/retry for resolution mismatches

---

## Phase 4: Provider Upgrades — COMPLETED

- [x] Migrated from MiniMax Hailuo-2.3 to Kling v3-omni as default video provider
- [x] Kling JWT authentication (`access_key` + `secret_key`)
- [x] Kling task creation, polling, and download
- [x] Kling `first_frame` image reference with `<<<image_1>>>` token
- [x] Migrated to Gemini 3.1 Pro for LLM
- [x] Migrated to Gemini 3.1 Flash Image Preview for image generation

---

## Known Issues

1. **Type Checking**: Some agents have Pyright errors around provider method calls (`self.llm` typed as `Optional`) — runtime works but type narrowing needs refinement
2. **Cost Tracking**: Budget tracked at agent level but not integrated with actual API billing data
3. **Checkpointing**: State is in-memory only; disk persistence not yet implemented
4. **Video QA**: Currently auto-passed to save API costs; can be re-enabled in config

---

## Roadmap

### Short Term
- [ ] Disk-based checkpointing for pipeline resume
- [ ] Actual API cost integration in providers
- [ ] Type narrowing fixes for provider attributes

### Medium Term
- [ ] Audio generation (TTS for dialogue, BGM)
- [ ] Lip-sync integration
- [ ] Advanced transitions (cross-fades, wipes) in Editor
- [ ] Web UI for project management and progress monitoring

### Long Term
- [ ] Distributed execution support
- [ ] Custom model fine-tuning for style consistency
- [ ] Real-time progress monitoring dashboard

---

*Last Updated: April 2, 2026*
*Architecture: Autonomous Film Crew (AFC) via LangGraph*
*Video Provider: Kling v3-omni*
*LLM: Gemini 3.1 Pro*
