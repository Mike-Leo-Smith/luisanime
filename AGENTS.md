# AFP Agent Development Guide

This document outlines the critical requirements, workflow patterns, skills, and lessons learned for developing agents in the Agentic Filming Pipeline (AFP).

## Critical Requirements

### 1. JSON Schema Enforcement

All agents that interact with LLMs must use structured output via JSON schemas:

```python
from src.schemas import ENTITY_SCHEMA
from src.agents.utils import get_llm_provider

def my_agent(state: PipelineState) -> PipelineState:
    provider = get_llm_provider(state, "agent_name")
    
    result = provider.generate_structured(
        prompt=prompt,
        response_schema=ENTITY_SCHEMA
    )
    # result is guaranteed to match the schema
```

**Why:** Prevents parsing errors, ensures type safety, reduces token waste on malformed outputs.

### 2. Provider Factory Pattern

Never instantiate providers directly. Always use the factory:

```python
from src.agents.utils import get_llm_provider, get_image_provider, get_video_provider

llm = get_llm_provider(state, "agent_name")
image_gen = get_image_provider(state, "agent_name")
video_gen = get_video_provider(state, "agent_name")
```

**Why:** Ensures consistent configuration, API key management, and provider switching.

### 3. Project Directory Structure

Agents must respect the project structure:

```
project/
├── src/           # Source materials (read-only)
├── assets/        # Generated assets (write)
├── index/         # Chapter index (write)
├── scenes/        # Scene organization (write)
├── cache/         # Cache files (write)
├── checkpoints/   # State snapshots (write)
├── output/        # Final deliverables (write)
└── logs/          # Logs (write)
```

**Access via ProjectManager:**
```python
from src.core.project import ProjectManager

pm = ProjectManager("./projects")
pm.load_project("my_project")

novel_path = pm.get_src_path("novel.txt")
entities_path = pm.get_assets_path("lore", "entities.json")
```

### 4. Progress Reporting

All long-running operations must report progress:

```python
def process_chapters(chapters):
    total = len(chapters)
    for i, chapter in enumerate(chapters, 1):
        progress = (i / total) * 100
        print(f"    [{i}/{total} {progress:.1f}%] Processing {chapter.id}...")
        # ... process chapter
```

**Why:** Users need visibility into multi-minute operations.

### 5. Error Handling

Agents must catch exceptions and set state["last_error"]:

```python
def my_agent(state: PipelineState) -> PipelineState:
    try:
        # ... agent logic
    except Exception as e:
        print(f"Error: {e}")
        state["last_error"] = str(e)
    return state
```

**Why:** Prevents pipeline crashes, enables retry logic.

## Workflow Patterns

### Agent File Template

```python
from src.core.state import PipelineState
from src.schemas import SOME_SCHEMA
from src.agents.utils import get_llm_provider

def agent_name(state: PipelineState) -> PipelineState:
    print("--- AGENT NAME: Description ---")
    
    provider = get_llm_provider(state, "agent_name")
    
    try:
        result = provider.generate_structured(
            prompt=build_prompt(state),
            response_schema=SOME_SCHEMA
        )
        state["field"] = transform_result(result)
        print(f"  Processed {len(result)} items")
    except Exception as e:
        print(f"Error: {e}")
        state["last_error"] = str(e)
    
    return state


def build_prompt(state: PipelineState) -> str:
    return f"""Context from state...
    
    Task: Do something specific.
    """
```

### Chapter-Aware Agents

For agents that process chapters:

```python
from src.agents.utils import get_chapter_db

def chapter_aware_agent(state: PipelineState) -> PipelineState:
    chapter_db = get_chapter_db(state)
    
    if chapter_db and len(chapter_db.chapters) > 0:
        # Process chapters with progress reporting
        for i, chapter in enumerate(chapter_db.get_all_chapters(), 1):
            print(f"  [{i}/{len(chapter_db.chapters)}] {chapter.id}")
            # ... process chapter
    else:
        # Fallback to novel_text
        novel_text = state["novel_text"]
        # ... process text
    
    return state
```

### State Mutation Pattern

Agents should:
1. Read from state
2. Process with LLM/providers
3. Write results to state
4. Return state (modified or not)

```python
def example_agent(state: PipelineState) -> PipelineState:
    # Read
    scenes = state["scenes"]
    current_idx = state["current_scene_index"]
    current_scene = scenes[current_idx]
    
    # Process
    shots = generate_shots(current_scene)
    
    # Write
    state["shot_list"] = shots
    state["current_shot_index"] = 0
    
    return state
```

## Agent Skills

### Required Skills

1. **LLM Prompt Engineering**
   - Clear task descriptions
   - Context window management
   - JSON output formatting

2. **Provider Abstraction**
   - Understanding factory pattern
   - Configuring per-agent models
   - Handling provider-specific quirks

3. **Schema Design**
   - Gemini-compatible JSON schemas (uppercase types)
   - No union types (use nullable instead)
   - Clear field descriptions

4. **Project Structure**
   - Correct directory usage
   - File path conventions
   - Checkpoint integration

5. **Error Resilience**
   - Exception handling
   - Graceful degradation
   - User-friendly error messages

### Optional Skills

1. **Vision-Language Models** (for QA Linter)
2. **Video Generation APIs** (for Animator)
3. **Image Generation APIs** (for Storyboarder)
4. **FFmpeg/Video Processing** (for Compositor)

## Lessons Learned

### 1. JSON Schema Compatibility

**Problem:** Gemini's API doesn't support standard JSON Schema features like `patternProperties` or union types (`["string", "null"]`).

**Solution:** Use Gemini's format:
```python
# Bad (standard JSON Schema)
{"type": ["string", "null"]}
{"patternProperties": {...}}

# Good (Gemini compatible)
{"type": "STRING", "nullable": True}
{"type": "ARRAY", "items": {...}}
```

### 2. Provider Response Handling

**Problem:** Different providers return different response formats.

**Solution:** Always use `generate_structured()` which normalizes responses:
```python
# Returns parsed dict, not LLMResponse
result = provider.generate_structured(prompt, schema)
```

### 3. Token Management

**Problem:** Long novels exceed context windows.

**Solution:** 
- Use chapter-based processing
- Truncate text with `[:3000]` for metadata extraction
- Use `[:8000]` for scene extraction

### 4. API Key Organization

**Problem:** Different agents need different API keys.

**Solution:** Model-specific keys in `.env`:
```
GEMINI_FLASH_API_KEY=...  # For high-token agents
GEMINI_PRO_API_KEY=...    # For reasoning agents
MINIMAX_IMAGE_API_KEY=... # For image generation
MINIMAX_VIDEO_API_KEY=... # For video generation
```

### 5. Project Path Migration

**Problem:** Old code used `memory/`, `input/`, `shared/` paths.

**Solution:** New structure uses:
- `src/` - Source materials (was `input/`)
- `index/` - Chapter index (was `memory/`)
- `assets/` - Generated assets (was `shared/`)
- `scenes/` - Scene organization (new)

### 6. Agent Organization

**Problem:** Monolithic agent files become unmaintainable.

**Solution:** One agent per file:
```
src/agents/
├── indexer.py          # Text segmentation
├── lore_master.py      # Entity extraction
├── screenwriter.py     # Scene chunking
├── director.py         # Shot generation
├── storyboarder.py     # Keyframe generation
├── animator.py         # Video generation
├── qa_linter.py        # Quality assurance
└── compositor.py       # Final assembly
```

### 7. Testing Strategy

**Problem:** Full pipeline tests are slow and expensive.

**Solution:** 
- Use short test novels (3 chapters max)
- Test agents individually
- Mock provider responses for unit tests
- Integration tests only for critical paths

## Checklist for New Agents

- [ ] Create `src/agents/{agent_name}.py`
- [ ] Import from `src.agents.utils` for providers
- [ ] Define JSON schema in `src/schemas.py` if needed
- [ ] Use `generate_structured()` for LLM calls
- [ ] Add progress reporting for loops
- [ ] Handle exceptions and set `state["last_error"]`
- [ ] Update `src/core/graph.py` if adding to workflow
- [ ] Add CLI command in `main.py` if standalone
- [ ] Update `DESIGN.md` with agent description
- [ ] Test with short novel

## Example: Complete Agent Implementation

```python
# src/agents/my_agent.py
from src.core.state import PipelineState, SomeIR
from src.schemas import MY_SCHEMA
from src.agents.utils import get_llm_provider, get_chapter_db


def my_agent(state: PipelineState) -> PipelineState:
    print("--- MY AGENT: Description ---")
    
    provider = get_llm_provider(state, "my_agent")
    chapter_db = get_chapter_db(state)
    
    if chapter_db and len(chapter_db.chapters) > 0:
        all_results = []
        chapters = chapter_db.get_all_chapters()
        total = len(chapters)
        
        for i, chapter in enumerate(chapters, 1):
            progress = (i / total) * 100
            print(f"    [{i}/{total} {progress:.1f}%] {chapter.id}...")
            
            try:
                result = provider.generate_structured(
                    prompt=build_prompt(chapter),
                    response_schema=MY_SCHEMA
                )
                all_results.extend(result)
            except Exception as e:
                print(f"      Error: {e}")
                continue
        
        state["my_results"] = [SomeIR(**r) for r in all_results]
        print(f"  Processed {len(all_results)} items")
    else:
        # Fallback to novel_text
        try:
            result = provider.generate_structured(
                prompt=build_prompt_from_text(state["novel_text"]),
                response_schema=MY_SCHEMA
            )
            state["my_results"] = [SomeIR(**r) for r in result]
        except Exception as e:
            print(f"Error: {e}")
            state["last_error"] = str(e)
    
    return state


def build_prompt(chapter) -> str:
    return f"""Process this chapter:
Title: {chapter.metadata.chapter_title}
Text: {chapter.text[:3000]}
"""


def build_prompt_from_text(text: str) -> str:
    return f"Process this text: {text[:5000]}"
```

## Resources

- **State Definition:** `src/core/state.py`
- **JSON Schemas:** `src/schemas.py`
- **Agent Utilities:** `src/agents/utils.py`
- **Provider Base:** `src/providers/base.py`
- **Project Manager:** `src/core/project.py`
