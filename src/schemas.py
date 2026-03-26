"""JSON schemas for structured LLM outputs - Gemini compatible format."""

CHAPTER_METADATA_SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "chapter_title": {
            "type": "STRING",
            "description": "The chapter title if available, empty string if none",
            "nullable": True,
        },
        "summary": {
            "type": "STRING",
            "description": "2-3 sentence summary of what happens in the chapter",
            "nullable": True,
        },
        "characters": {
            "type": "ARRAY",
            "items": {"type": "STRING"},
            "description": "List of character names that appear in the chapter",
        },
        "locations": {
            "type": "ARRAY",
            "items": {"type": "STRING"},
            "description": "List of locations mentioned in the chapter",
        },
        "plot_events": {
            "type": "ARRAY",
            "items": {"type": "STRING"},
            "description": "Key plot events (e.g., wedding, escape, fight)",
        },
        "emotional_tone": {
            "type": "STRING",
            "description": "Overall emotional tone (e.g., romantic, dramatic, tense)",
            "nullable": True,
        },
        "key_scenes": {
            "type": "ARRAY",
            "items": {"type": "STRING"},
            "description": "Brief descriptions of 2-3 key scenes",
        },
    },
    "required": ["characters", "locations", "plot_events", "key_scenes"],
}

ENTITY_SCHEMA = {
    "type": "ARRAY",
    "items": {
        "type": "OBJECT",
        "properties": {
            "name": {
                "type": "STRING",
                "description": "Name of the entity",
            },
            "entity_type": {
                "type": "STRING",
                "enum": ["character", "location", "item"],
                "description": "Type of entity",
            },
            "description": {
                "type": "STRING",
                "description": "Brief description of the entity",
            },
        },
        "required": ["name", "entity_type", "description"],
    },
}

SCENE_SCHEMA = {
    "type": "ARRAY",
    "items": {
        "type": "OBJECT",
        "properties": {
            "id": {
                "type": "STRING",
                "description": "Unique scene identifier (e.g., scene_1)",
            },
            "location": {
                "type": "STRING",
                "description": "Where the scene takes place",
            },
            "time_of_day": {
                "type": "STRING",
                "description": "Time of day (e.g., Day, Night, Dusk)",
            },
            "characters": {
                "type": "ARRAY",
                "items": {"type": "STRING"},
                "description": "List of character names present in the scene",
            },
            "description": {
                "type": "STRING",
                "description": "Concise summary of what happens in the scene",
            },
        },
        "required": ["id", "location", "time_of_day", "characters", "description"],
    },
}

SHOT_SCHEMA = {
    "type": "ARRAY",
    "items": {
        "type": "OBJECT",
        "properties": {
            "id": {
                "type": "STRING",
                "description": "Unique shot identifier (e.g., shot_1_1)",
            },
            "scene_id": {"type": "STRING", "description": "Reference to parent scene"},
            "prompt": {
                "type": "STRING",
                "description": "Detailed visual prompt for video generation model",
            },
            "camera_movement": {
                "type": "STRING",
                "description": "Camera movement (e.g., Static, Pan Left, Zoom In, Crane Shot)",
            },
            "duration": {"type": "NUMBER", "description": "Duration in seconds"},
        },
        "required": ["id", "scene_id", "prompt", "camera_movement", "duration"],
    },
}
