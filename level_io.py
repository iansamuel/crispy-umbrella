import json
from pathlib import Path

LEVELS_DIR = Path(__file__).resolve().parent / "levels"
DEFAULT_LEVEL_PATH = LEVELS_DIR / "default.json"


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
    return {"name": data.get("name", "level"), "walls": walls, "platforms": platforms}


def save_level(path, walls, platforms, name="level"):
    LEVELS_DIR.mkdir(parents=True, exist_ok=True)
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
    }
    Path(path).write_text(json.dumps(payload, indent=2) + "\n")
