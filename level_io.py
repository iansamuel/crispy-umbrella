import json
from pathlib import Path

LEVELS_DIR = Path(__file__).resolve().parent / "levels"
DEFAULT_LEVEL_PATH = LEVELS_DIR / "default.json"


def get_default_emitter():
    """Return a default emitter configuration."""
    return {
        "pos": (400.0, 80.0),
        "angle": 90.0,  # degrees, 90 = straight down
        "width": 60.0,  # opening width in pixels
        "rate": 20.0,  # marbles per second
        "count": 100,  # total marbles to emit
        "speed": 50.0,  # initial velocity magnitude
    }


def list_levels():
    """Return a list of all available level files (Paths)."""
    if not LEVELS_DIR.exists():
        return []
    return sorted(list(LEVELS_DIR.glob("*.json")), key=lambda p: p.stem)


def load_level(path):
    data = json.loads(Path(path).read_text())
    walls = []
    for wall in data.get("walls", []):
        start = wall.get("start", [0, 0])
        end = wall.get("end", [0, 0])
        walls.append(((float(start[0]), float(start[1])), (float(end[0]), float(end[1]))))
    platforms = []
    for platform in data.get("platforms", []):
        pos = platform.get("pos", [0, 0])
        platforms.append({
            "pos": (float(pos[0]), float(pos[1])),
            "length": float(platform.get("length", 40)),
            "angular_velocity": float(platform.get("angular_velocity", 0.0)),
        })

    # Load emitter (use default if not present)
    emitter_data = data.get("emitter", None)
    if emitter_data:
        pos = emitter_data.get("pos", [400, 80])
        emitter = {
            "pos": (float(pos[0]), float(pos[1])),
            "angle": float(emitter_data.get("angle", 90.0)),
            "width": float(emitter_data.get("width", 60.0)),
            "rate": float(emitter_data.get("rate", 20.0)),
            "count": int(emitter_data.get("count", 100)),
            "speed": float(emitter_data.get("speed", 50.0)),
        }
    else:
        emitter = get_default_emitter()

    # Load conveyors
    conveyors = []
    for conv in data.get("conveyors", []):
        start = conv.get("start", [0, 0])
        end = conv.get("end", [0, 0])
        conveyors.append({
            "start": (float(start[0]), float(start[1])),
            "end": (float(end[0]), float(end[1])),
            "speed": float(conv.get("speed", 100.0)),
        })

    return {"name": data.get("name", "level"), "walls": walls, "platforms": platforms, "emitter": emitter, "conveyors": conveyors}


def save_level(path, walls, platforms, emitter=None, conveyors=None, name="level"):
    LEVELS_DIR.mkdir(parents=True, exist_ok=True)
    if emitter is None:
        emitter = get_default_emitter()
    if conveyors is None:
        conveyors = []
    payload = {
        "name": name,
        "walls": [
            {
                "start": [int(round(a[0])), int(round(a[1]))],
                "end": [int(round(b[0])), int(round(b[1]))],
            }
            for a, b in walls
        ],
        "platforms": [
            {
                "pos": [int(round(p["pos"][0])), int(round(p["pos"][1]))],
                "length": int(round(p["length"])),
                "angular_velocity": float(p["angular_velocity"]),
            }
            for p in platforms
        ],
        "conveyors": [
            {
                "start": [int(round(c["start"][0])), int(round(c["start"][1]))],
                "end": [int(round(c["end"][0])), int(round(c["end"][1]))],
                "speed": float(c["speed"]),
            }
            for c in conveyors
        ],
        "emitter": {
            "pos": [int(round(emitter["pos"][0])), int(round(emitter["pos"][1]))],
            "angle": float(emitter["angle"]),
            "width": float(emitter["width"]),
            "rate": float(emitter["rate"]),
            "count": int(emitter["count"]),
            "speed": float(emitter["speed"]),
        },
    }
    Path(path).write_text(json.dumps(payload, indent=2) + "\n")
