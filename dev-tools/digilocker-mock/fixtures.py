import json
import os
import sys

from config import settings

_personas: dict[str, dict] = {}


def load_personas() -> None:
    """Load personas from the JSON file. Fails fast if missing or malformed."""
    personas_path = settings.PERSONAS_FILE
    if not os.path.isabs(personas_path):
        # Resolve relative to the directory of this file
        base_dir = os.path.dirname(os.path.abspath(__file__))
        personas_path = os.path.join(base_dir, personas_path)

    if not os.path.exists(personas_path):
        print(f"ERROR: personas file not found at {personas_path}", file=sys.stderr)
        sys.exit(1)

    try:
        with open(personas_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except json.JSONDecodeError as exc:
        print(f"ERROR: personas file is not valid JSON: {exc}", file=sys.stderr)
        sys.exit(1)

    if not isinstance(data, list):
        print("ERROR: personas file must be a JSON array", file=sys.stderr)
        sys.exit(1)

    for persona in data:
        if "id" not in persona:
            print("ERROR: each persona must have an 'id' field", file=sys.stderr)
            sys.exit(1)
        _personas[persona["id"]] = persona

    print(f"Loaded {len(_personas)} persona(s): {list(_personas.keys())}")


def get_persona(persona_id: str) -> dict | None:
    return _personas.get(persona_id)


def list_personas() -> list[dict]:
    return [{"id": p["id"], "label": p.get("label", p["id"])} for p in _personas.values()]


def all_personas() -> dict[str, dict]:
    return _personas
