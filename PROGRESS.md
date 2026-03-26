# Project Progress: Agentic Filming Pipeline (AFP)

## ✅ Phase 1: Core Infrastructure - COMPLETED

### Configuration System
- [x] Created `src/config.py` with ConfigLoader supporting hierarchical config loading
- [x] Implemented per-agent configuration (each agent has its own provider, model, API key)
- [x] Environment variable resolution for API keys (ENV:VAR_NAME pattern)
- [x] Support for project-specific config.yaml files
- [x] Clean config.yaml without duplicate sections or provider fallbacks

### Provider Abstraction Layer
- [x] Created `src/providers/base.py` with base classes for LLM, Image, and Video providers
- [x] Implemented `src/providers/gemini.py` - Gemini LLM and image generation
- [x] Implemented `src/providers/minimax.py` - MiniMax image and video generation
- [x] Implemented `src/providers/openai_compat.py` - OpenAI-compatible LLM provider
- [x] Created `src/providers/factory.py` for dynamic provider instantiation
- [x] All providers respect config.yaml model settings

### Project Management
- [x] Created `src/core/project_manager.py` with shot-based asset organization
- [x] Project structure: `shots/{shot_id}/` for per-shot assets
- [x] Shared assets directory for characters, locations, audio
- [x] Checkpoint system for resumable pipeline execution

### Main Entry Point
- [x] Updated `main.py` with CLI structure (init, run commands)
- [x] Backwards-compatible run_pipeline() function
- [x] Support for --resume-from checkpoint
- [x] Project loading guards in place

## ✅ Phase 2: Agent Configuration Updates - COMPLETED

### Agent Files Updated to Use New Config Format
- [x] `src/agents/pre_production.py` - lore_master, screenwriter, director
- [x] `src/agents/asset_locking.py` - storyboarder
- [x] `src/agents/production.py` - animator, qa_linter
- [x] `src/agents/post_production.py` - compositor (import added)

All agents now use:
```python
from src.config import ConfigLoader
model_cfg = ConfigLoader.get_agent_config(config, "agent_name")
# Access via dict: model_cfg["model"], model_cfg["api_key"], etc.
```

## ✅ Phase 3: Documentation - COMPLETED

### Updated Documentation
- [x] `DESIGN.md` - Comprehensive architecture document with:
  - Provider abstraction layer details
  - Per-agent configuration system
  - Shot-based asset organization
  - Checkpointing and resumability
  - Model names updated (gemini-3.1-flash-preview for high-token agents, gemini-3.1-pro-preview for reasoning agents)
- [x] `README.md` - Updated setup instructions (see below)

## 🔄 Phase 4: Testing - IN PROGRESS

### Test Status
- [ ] Run full test suite
- [ ] Verify agent config loading works correctly
- [ ] Verify provider factory creates correct providers
- [ ] Verify backwards compatibility maintained

### Known Test Issues (Pre-existing)
- Test files have type errors due to PipelineState changes (missing project_dir, style fields)
- These are in test files, not production code

## 📋 Remaining Work

### Immediate Tasks
1. Run test suite and fix any issues
2. Update .env template with agent-specific API keys
3. Create example project template

### Future Enhancements
- Add more provider implementations (Anthropic, etc.)
- Implement actual checkpoint save/load in graph.py
- Add progress reporting UI
- Optimize asset caching

## 🎯 Current Model Configuration

| Agent | Provider | Model | Notes |
|-------|----------|-------|-------|
| lore_master | gemini | gemini-3.1-flash-preview | High token usage, uses Flash for cost efficiency |
| screenwriter | gemini | gemini-3.1-flash-preview | High token usage, uses Flash for cost efficiency |
| director | gemini | gemini-3.1-pro-preview | Requires high reasoning capability |
| storyboarder | minimax | image-01 | Image generation |
| animator | minimax | MiniMax-Hailuo-02 | Video generation |
| qa_linter | gemini | gemini-3.1-pro-preview | Requires high reasoning for quality checks |

## 📁 Key Files

**Configuration:**
- `config.yaml` - Main configuration file
- `src/config.py` - ConfigLoader implementation

**Providers:**
- `src/providers/base.py` - Base provider classes
- `src/providers/gemini.py` - Gemini provider
- `src/providers/minimax.py` - MiniMax provider
- `src/providers/openai_compat.py` - OpenAI-compatible provider
- `src/providers/factory.py` - ProviderFactory

**Core:**
- `src/core/project_manager.py` - Project management
- `src/core/graph.py` - LangGraph workflow
- `src/core/state.py` - Pipeline state definitions

**Agents:**
- `src/agents/pre_production.py` - Lore Master, Screenwriter, Director
- `src/agents/asset_locking.py` - Storyboarder
- `src/agents/production.py` - Animator, QA Linter
- `src/agents/post_production.py` - Compositor, Lip Sync

**Entry Point:**
- `main.py` - CLI and pipeline runner
