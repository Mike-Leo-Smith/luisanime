# test_project

AFP Video Project

## Structure

- `src/` - Source materials (novel.txt, scripts)
- `assets/` - Generated assets (characters, locations, lore, audio)
- `index/` - Chapter index and metadata
- `scenes/` - Scene-based shot organization
- `cache/` - Cache files
- `checkpoints/` - Pipeline checkpoints
- `output/` - Final deliverables
- `logs/` - Pipeline logs
- `config.yaml` - Project configuration

## Pipeline Stages

1. `index` - Segment novel into chapters
2. `lore` - Extract entities (characters, locations, items)
3. `scenes` - Break into scenes
4. `shots` - Generate shot list
5. `storyboard` - Generate keyframes
6. `animate` - Generate video clips
7. `qa` - Quality assurance
8. `composite` - Final assembly

## Usage

```bash
python main.py lore test_project
python main.py scenes test_project
python main.py shots test_project
python main.py produce test_project
```
