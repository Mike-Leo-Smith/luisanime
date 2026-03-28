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

CHAPTER_BOUNDARY_SCHEMA = {
    "type": "ARRAY",
    "items": {
        "type": "OBJECT",
        "properties": {
            "chapter_number": {
                "type": "INTEGER",
                "description": "Sequential chapter number (1, 2, 3, etc.)",
            },
            "chapter_title": {
                "type": "STRING",
                "description": "The chapter title if available",
                "nullable": True,
            },
            "start_marker": {
                "type": "STRING",
                "description": "The exact text that marks the chapter start (first 50 chars)",
            },
        },
        "required": ["chapter_number", "start_marker"],
    },
}

L3_PATCH_SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "mutations": {
            "type": "ARRAY",
            "items": {
                "type": "OBJECT",
                "properties": {
                    "entity_id": {"type": "STRING"},
                    "mutation_type": {
                        "type": "STRING",
                        "enum": ["inventory_add", "inventory_remove", "inventory_modify", "physical_status_update", "appearance_update"]
                    },
                    "attribute_path": {"type": "STRING"},
                    "new_value": {"type": "STRING"}
                },
                "required": ["entity_id", "mutation_type", "attribute_path", "new_value"]
            }
        }
    },
    "required": ["mutations"]
}

SCENE_IR_SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "scenes": {
            "type": "ARRAY",
            "items": {
                "type": "OBJECT",
                "properties": {
                    "scene_id": {"type": "STRING"},
                    "environment": {
                        "type": "OBJECT",
                        "properties": {
                            "location": {"type": "STRING"},
                            "time_of_day": {"type": "STRING", "enum": ["Day", "Night", "Dusk", "Dawn", "Unknown"]},
                            "weather_lighting": {"type": "STRING"}
                        },
                        "required": ["location", "time_of_day"]
                    },
                    "active_entities": {
                        "type": "ARRAY",
                        "items": {"type": "STRING"}
                    },
                    "chronological_actions": {
                        "type": "ARRAY",
                        "items": {"type": "STRING"}
                    }
                },
                "required": ["scene_id", "environment", "active_entities", "chronological_actions"]
            }
        }
    },
    "required": ["scenes"]
}

ART_STYLE_SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "reasoning": {"type": "STRING"},
        "palette": {
            "type": "OBJECT",
            "properties": {
                "primary": {"type": "STRING"},
                "secondary": {"type": "STRING"},
                "lighting_mood": {"type": "STRING"}
            },
            "required": ["primary", "secondary", "lighting_mood"]
        },
        "character_consistency": {
            "type": "ARRAY",
            "items": {
                "type": "OBJECT",
                "properties": {
                    "name": {"type": "STRING"},
                    "version_name": {"type": "STRING", "description": "e.g. Young, Aged, In-Disguise"},
                    "visual_markers": {"type": "ARRAY", "items": {"type": "STRING"}},
                    "outfit_details": {"type": "STRING"}
                },
                "required": ["name", "version_name", "visual_markers"]
            }
        },
        "technical_specs": {
            "type": "OBJECT",
            "properties": {
                "negative_prompt": {"type": "STRING"},
                "aspect_ratio": {"type": "STRING"}
            }
        }
    },
    "required": ["reasoning", "palette", "character_consistency"]
}

SHOT_LIST_SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "reasoning": {"type": "STRING"},
        "shots": {
            "type": "ARRAY",
            "items": {
                "type": "OBJECT",
                "properties": {
                    "shot_id": {"type": "STRING"},
                    "scene_id": {"type": "STRING"},
                    "camera": {
                        "type": "OBJECT",
                        "properties": {
                            "framing": {"type": "STRING", "enum": ["Extreme Close-up", "Close-up", "Medium Shot", "Full Shot", "Wide Shot"]},
                            "movement": {"type": "STRING", "enum": ["Static", "Pan Left", "Pan Right", "Tilt Up", "Tilt Down", "Zoom In", "Zoom Out"]}
                        },
                        "required": ["framing", "movement"]
                    },
                    "visual_payload": {
                        "type": "OBJECT",
                        "properties": {
                            "prompt_begin": {"type": "STRING", "description": "Visual state at the start of the shot"},
                            "prompt_end": {"type": "STRING", "description": "Visual state at the end of the shot"},
                            "negative_prompt": {"type": "STRING"}
                        },
                        "required": ["prompt_begin", "prompt_end"]
                    },
                    "routing_flags": {
                        "type": "OBJECT",
                        "properties": {
                            "requires_lip_sync": {"type": "BOOLEAN"},
                            "rigid_body_only": {"type": "BOOLEAN"}
                        },
                        "required": ["requires_lip_sync", "rigid_body_only"]
                    },
                    "qa_checklist": {
                        "type": "ARRAY",
                        "items": {"type": "STRING"}
                    }
                },
                "required": ["shot_id", "camera", "visual_payload", "routing_flags", "qa_checklist"]
            }
        }
    },
    "required": ["reasoning", "shots"]
}

QA_EVALUATION_SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "reasoning": {"type": "STRING"},
        "is_pass": {"type": "BOOLEAN"},
        "failed_frames": {
            "type": "ARRAY", 
            "items": {"type": "STRING", "enum": ["begin", "end"]},
            "description": "List of frames that failed QA and need regeneration"
        },
        "failure_details": {
            "type": "OBJECT",
            "properties": {
                "failed_checklist_index": {"type": "INTEGER"},
                "failure_reason": {"type": "STRING"},
                "mitigation_suggestion": {"type": "STRING"}
            },
            "required": ["failed_checklist_index", "failure_reason", "mitigation_suggestion"]
        }
    },
    "required": ["reasoning", "is_pass"]
}
