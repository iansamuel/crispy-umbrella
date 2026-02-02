# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

A marble physics simulation using Pygame for rendering and Pymunk for 2D rigid body physics. Colored marbles drop through a funnel and are ranked by finish order.

## Commands

```bash
# Install dependencies
pip install -r requirements.txt

# Run the interactive simulation
python marble_race.py
```

## Architecture

- **marble_race.py**: Main interactive simulation with `MarbleSimulation` class that handles the game loop, physics updates, rendering, and in-app level editor
- **level_io.py**: Level load/save helpers for JSON levels in `levels/`
- **levels/*.json**: Level data (walls + spinning platforms)

Main script structure:
- Physics space setup with Pymunk (`pymunk.Space` with gravity)
- Static funnel geometry stored in `levels/*.json` under `walls`
- Rotating platforms stored in `levels/*.json` under `platforms`
- 100 dynamic marble bodies arranged in a 10x10 grid with rainbow HSV colors
- Main loop: physics step → collision detection → remove finished marbles → render

## Key Configuration (top of both files)

- `WIDTH, HEIGHT = 800, 800` - Window dimensions
- `MARBLE_COUNT = 100` - Number of marbles
- `GRAVITY = 900.0` - Pymunk gravity constant
- `ELASTICITY = 0.5` / `FRICTION = 0.3` - Marble physics properties

## Level format
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

## Quick commands
- Run simulation: `python marble_race.py`
- Run capture: `python capture_simulation.py`
