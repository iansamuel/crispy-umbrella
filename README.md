# Marble Funnel Simulation

Native Python marble physics simulation with an in-app level editor.

## Quickstart
```bash
python marble_race.py
```

## Controls
### Simulation
- Start: `Start` button
- Reset: `Reset` button (after finish)
- Editor toggle: `E`

### Editor
- Left drag: add wall segment
- Left click: add platform (spinning)
- Right click: delete nearest platform or wall
- Backspace: undo last wall
- `C`: clear all
- `R`: reset to default level
- `S`: save to `levels/edited.json`
- `L`: load from `levels/edited.json` (if present)
- `[` / `]`: cycle platform templates

## Level Format (JSON)
Levels live in `levels/` and define walls and spinning platforms.

Example:
```json
{
  "name": "default",
  "walls": [
    { "start": [50, 200], "end": [370, 500] }
  ],
  "platforms": [
    { "pos": [280, 350], "length": 50, "angular_velocity": 2.0 }
  ]
}
```

## Capture Frames
```bash
python capture_simulation.py
```
