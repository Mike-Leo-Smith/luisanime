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

## Phase 5: Reference Image Pipeline & Prompt Enhancement — COMPLETED

- [x] Per-scene character/entity/location design generation by Production Designer
  - Designs saved to `03_lore_bible/designs/scenes/{scene_id}/`
  - Fallback to master designs if scene-specific not available
- [x] Scene-aware design fetching in Cinematographer (character + location references)
- [x] Reference images passed to Lead Animator → Kling video generation
  - `<<<image_1>>>` = keyframe (first_frame), `<<<image_2>>>` onwards = character/environment references
  - Reference images sent as `type: "reference"` in Kling `image_list`
- [x] `current_scene_path` propagation through pipeline state (Director → Production Designer → Cinematographer → Lead Animator → Editor)
- [x] Spatial consistency instructions in keyframe generation (room layout, furniture, object positions, door directions)
- [x] Spatial proportions and character relationships in keyframe prompts
- [x] Spatial consistency block in video generation distillation prompt
- [x] Detailed character clothing/positioning/action descriptions in video prompts (350-450 word target)
- [x] Rewritten `LEAD_ANIMATOR_PROMPT` with priority ordering: clothing > positioning > actions > expressions > camera/lighting

---

## Phase 6: Audio & Assembly — COMPLETED

- [x] Kling audio generation enabled (`sound: "on"` in API config, `enable_audio: True` in `VideoGenerationConfig`)
- [x] Editor audio-preserving assembly: split video/audio streams, `ffmpeg.concat(..., v=1, a=1)`, `acodec="aac"`
- [x] Fallback retry without audio if concat fails
- [x] Screenwriter dialogue design from original novel text (preserves verbatim dialogue, reconstructs indirect speech)

---

## Phase 7: Director & Video Prompt Refinement — IN PROGRESS

- [ ] **Director shot planning enhancement**: Ensure detailed, fluid shot breakdowns with smooth video continuity and logical cinematographic flow. Director must cover every narrative beat, ensure seamless shot-to-shot transitions, and plan pacing suitable for 5-10s video clips.
- [ ] **Dialogue preservation in video generation prompts**: Current distillation prompt rule #8 suppresses spoken words. Since Kling supports audio generation (`sound: "on"`), dialogue lines must be included in quotation marks per Kling docs so the model generates matching speech audio. Need to update `_build_distillation_prompt()` rule #8 and the `LEAD_ANIMATOR_PROMPT` system prompt.
- [ ] **Commit all accumulated changes** (7+ modified files from Phase 5-6, plus Phase 7 changes)

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
- [ ] Advanced transitions (cross-fades, wipes) in Editor
- [ ] Web UI for project management and progress monitoring
- [ ] Lip-sync refinement (currently relies on Kling audio generation)

### Long Term
- [ ] Distributed execution support
- [ ] Custom model fine-tuning for style consistency
- [ ] Real-time progress monitoring dashboard

---

*Last Updated: April 2, 2026*
*Architecture: Autonomous Film Crew (AFC) via LangGraph*
*Video Provider: Kling v3-omni (with audio generation)*
*LLM: Gemini 3.1 Pro*
*Image: Gemini 3.1 Flash Image Preview*
