"""
Standalone Level Editor for Marble Race Simulation.

Features:
- Wall & Platform CRUD: Create, select, edit properties, delete
- Emitter (Entry Pipe): Configure marble spawn point, angle, rate, count
- Live Physics Preview: Test marbles with Space key
- Grid Snapping: Configurable grid with toggle (G key)
- Undo/Redo: Command pattern with Ctrl+Z/Y

Keyboard Shortcuts:
    V - Select tool
    W - Wall tool
    P - Platform tool
    E - Emitter tool
    X - Delete tool
    Space - Toggle preview
    Ctrl+Z - Undo
    Ctrl+Y - Redo
    Ctrl+S - Save
    G - Toggle grid
    Del - Delete selected
"""

import pygame
import pymunk
import colorsys
import math
import random
from abc import ABC, abstractmethod
from pathlib import Path
from level_io import load_level, save_level, get_default_emitter, LEVELS_DIR, DEFAULT_LEVEL_PATH

# --- Configuration ---
DEFAULT_WIDTH, DEFAULT_HEIGHT = 1024, 768
CANVAS_SIZE = 800  # Viewport is 800x800 (scrollable)
FPS = 60

# Colors
BG_COLOR = (30, 30, 40)
CANVAS_BG = (20, 20, 30)
PANEL_BG = (40, 40, 55)
GRID_COLOR = (50, 50, 65)
TEXT_COLOR = (220, 220, 220)
HIGHLIGHT_COLOR = (100, 180, 255)
WALL_COLOR = (200, 200, 200)
PLATFORM_COLOR = (140, 200, 120)
EMITTER_COLOR = (100, 120, 180)
SELECTED_COLOR = (255, 200, 100)
PREVIEW_WALL_COLOR = (100, 150, 200)

# UI Dimensions
TOOLBAR_WIDTH = 80
PROPERTY_PANEL_WIDTH = 200
MENU_BAR_HEIGHT = 30
FILE_BROWSER_HEIGHT = 40


# --- Command Pattern for Undo/Redo ---

class Command(ABC):
    """Abstract base class for undoable commands."""

    @abstractmethod
    def execute(self, editor):
        """Execute the command."""
        pass

    @abstractmethod
    def undo(self, editor):
        """Undo the command."""
        pass


class AddWallCommand(Command):
    def __init__(self, wall):
        self.wall = wall

    def execute(self, editor):
        editor.walls.append(self.wall)

    def undo(self, editor):
        editor.walls.remove(self.wall)


class DeleteWallCommand(Command):
    def __init__(self, wall, index):
        self.wall = wall
        self.index = index

    def execute(self, editor):
        editor.walls.remove(self.wall)

    def undo(self, editor):
        editor.walls.insert(self.index, self.wall)


class AddPlatformCommand(Command):
    def __init__(self, platform):
        self.platform = platform

    def execute(self, editor):
        editor.platforms.append(self.platform)

    def undo(self, editor):
        editor.platforms.remove(self.platform)


class DeletePlatformCommand(Command):
    def __init__(self, platform, index):
        self.platform = platform
        self.index = index

    def execute(self, editor):
        editor.platforms.remove(self.platform)

    def undo(self, editor):
        editor.platforms.insert(self.index, self.platform)


class ModifyWallCommand(Command):
    def __init__(self, wall, old_start, old_end, new_start, new_end):
        self.wall = wall
        self.old_start = old_start
        self.old_end = old_end
        self.new_start = new_start
        self.new_end = new_end

    def execute(self, editor):
        idx = editor.walls.index(self.wall)
        editor.walls[idx] = (self.new_start, self.new_end)
        self.wall = editor.walls[idx]

    def undo(self, editor):
        idx = editor.walls.index(self.wall)
        editor.walls[idx] = (self.old_start, self.old_end)
        self.wall = editor.walls[idx]


class ModifyPlatformCommand(Command):
    def __init__(self, platform, old_props, new_props):
        self.platform = platform
        self.old_props = old_props.copy()
        self.new_props = new_props.copy()

    def execute(self, editor):
        idx = editor.platforms.index(self.platform)
        editor.platforms[idx].update(self.new_props)

    def undo(self, editor):
        idx = editor.platforms.index(self.platform)
        editor.platforms[idx].update(self.old_props)


class ModifyEmitterCommand(Command):
    def __init__(self, old_emitter, new_emitter):
        self.old_emitter = old_emitter.copy()
        self.new_emitter = new_emitter.copy()

    def execute(self, editor):
        editor.emitter.update(self.new_emitter)

    def undo(self, editor):
        editor.emitter.update(self.old_emitter)


class CommandHistory:
    """Manages undo/redo stacks."""

    def __init__(self):
        self.undo_stack = []
        self.redo_stack = []

    def execute(self, command, editor):
        """Execute a command and add it to history."""
        command.execute(editor)
        self.undo_stack.append(command)
        self.redo_stack.clear()

    def undo(self, editor):
        """Undo the last command."""
        if self.undo_stack:
            command = self.undo_stack.pop()
            command.undo(editor)
            self.redo_stack.append(command)
            return True
        return False

    def redo(self, editor):
        """Redo the last undone command."""
        if self.redo_stack:
            command = self.redo_stack.pop()
            command.execute(editor)
            self.undo_stack.append(command)
            return True
        return False

    def clear(self):
        """Clear all history."""
        self.undo_stack.clear()
        self.redo_stack.clear()


# --- Grid System ---

class GridSystem:
    """Manages grid snapping and display."""

    def __init__(self, size=20, enabled=True):
        self.size = size
        self.enabled = enabled

    def snap_point(self, point):
        """Snap a point to the grid if enabled."""
        if not self.enabled:
            return point
        x, y = point
        return (round(x / self.size) * self.size,
                round(y / self.size) * self.size)

    def draw(self, surface, viewport_rect):
        """Draw the grid on the canvas."""
        if not self.enabled:
            return

        # Draw vertical lines
        for x in range(0, CANVAS_SIZE + 1, self.size):
            pygame.draw.line(surface, GRID_COLOR, (x, 0), (x, CANVAS_SIZE))

        # Draw horizontal lines
        for y in range(0, CANVAS_SIZE + 1, self.size):
            pygame.draw.line(surface, GRID_COLOR, (0, y), (CANVAS_SIZE, y))


# --- UI Components ---

class Button:
    """Simple button class for pygame UI."""

    def __init__(self, x, y, width, height, text, color=(80, 80, 100),
                 hover_color=(100, 100, 130), toggle=False):
        self.rect = pygame.Rect(x, y, width, height)
        self.text = text
        self.color = color
        self.hover_color = hover_color
        self.active_color = (80, 130, 180)
        self.font = pygame.font.SysFont("Arial", 14, bold=True)
        self.visible = True
        self.toggle = toggle
        self.active = False

    def draw(self, screen):
        if not self.visible:
            return
        mouse_pos = pygame.mouse.get_pos()
        if self.active:
            color = self.active_color
        elif self.rect.collidepoint(mouse_pos):
            color = self.hover_color
        else:
            color = self.color
        pygame.draw.rect(screen, color, self.rect, border_radius=4)
        pygame.draw.rect(screen, (150, 150, 150), self.rect, 1, border_radius=4)
        text_surf = self.font.render(self.text, True, TEXT_COLOR)
        text_rect = text_surf.get_rect(center=self.rect.center)
        screen.blit(text_surf, text_rect)

    def is_clicked(self, event):
        if not self.visible:
            return False
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            return self.rect.collidepoint(event.pos)
        return False


class InputField:
    """Simple text input field for property editing."""

    def __init__(self, x, y, width, height, label, value=""):
        self.rect = pygame.Rect(x, y, width, height)
        self.label = label
        self.value = str(value)
        self.font = pygame.font.SysFont("Arial", 12)
        self.active = False
        self.cursor_visible = True
        self.cursor_timer = 0

    def draw(self, screen):
        # Draw label
        label_surf = self.font.render(self.label, True, TEXT_COLOR)
        screen.blit(label_surf, (self.rect.x, self.rect.y - 15))

        # Draw input box
        color = HIGHLIGHT_COLOR if self.active else (80, 80, 100)
        pygame.draw.rect(screen, (50, 50, 65), self.rect)
        pygame.draw.rect(screen, color, self.rect, 1)

        # Draw value
        display_value = self.value
        if self.active and self.cursor_visible:
            display_value += "|"
        value_surf = self.font.render(display_value, True, TEXT_COLOR)
        screen.blit(value_surf, (self.rect.x + 5, self.rect.y + 5))

    def update(self, dt):
        if self.active:
            self.cursor_timer += dt
            if self.cursor_timer > 500:
                self.cursor_visible = not self.cursor_visible
                self.cursor_timer = 0

    def handle_event(self, event):
        if event.type == pygame.MOUSEBUTTONDOWN:
            self.active = self.rect.collidepoint(event.pos)
            return self.active

        if self.active and event.type == pygame.KEYDOWN:
            if event.key == pygame.K_BACKSPACE:
                self.value = self.value[:-1]
                return True
            elif event.key == pygame.K_RETURN:
                self.active = False
                return True
            elif event.key == pygame.K_ESCAPE:
                self.active = False
                return True
            elif event.unicode.isprintable():
                self.value += event.unicode
                return True
        return False

    def get_float(self, default=0.0):
        try:
            return float(self.value)
        except ValueError:
            return default

    def set_value(self, value):
        if isinstance(value, float):
            self.value = f"{value:.1f}"
        else:
            self.value = str(value)


class Slider:
    """Slider control for adjusting numeric values."""

    def __init__(self, x, y, width, label, min_val, max_val, initial_val, format_str="{:.1f}"):
        self.x = x
        self.y = y
        self.width = width
        self.height = 20
        self.label = label
        self.min_val = min_val
        self.max_val = max_val
        self.value = initial_val
        self.format_str = format_str
        self.font = pygame.font.SysFont("Arial", 12)
        self.dragging = False
        self.visible = True
        self.track_rect = pygame.Rect(x, y + 16, width, 6)
        self._update_handle()

    def _update_handle(self):
        ratio = (self.value - self.min_val) / (self.max_val - self.min_val)
        handle_x = self.x + int(ratio * self.width)
        self.handle_rect = pygame.Rect(handle_x - 6, self.y + 12, 12, 14)

    def draw(self, screen):
        if not self.visible:
            return
        # Draw label and value
        label_text = f"{self.label}: {self.format_str.format(self.value)}"
        label_surf = self.font.render(label_text, True, TEXT_COLOR)
        screen.blit(label_surf, (self.x, self.y))

        # Draw track
        pygame.draw.rect(screen, (60, 60, 80), self.track_rect, border_radius=3)

        # Draw filled portion
        ratio = (self.value - self.min_val) / (self.max_val - self.min_val)
        filled_width = int(ratio * self.width)
        filled_rect = pygame.Rect(self.x, self.y + 16, filled_width, 6)
        pygame.draw.rect(screen, (100, 150, 200), filled_rect, border_radius=3)

        # Draw handle
        pygame.draw.rect(screen, (180, 180, 200), self.handle_rect, border_radius=3)

    def handle_event(self, event):
        if not self.visible:
            return False
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self.handle_rect.collidepoint(event.pos) or self.track_rect.collidepoint(event.pos):
                self.dragging = True
                self._update_value_from_mouse(event.pos[0])
                return True
        elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            self.dragging = False
        elif event.type == pygame.MOUSEMOTION and self.dragging:
            self._update_value_from_mouse(event.pos[0])
            return True
        return False

    def _update_value_from_mouse(self, mouse_x):
        ratio = (mouse_x - self.x) / self.width
        ratio = max(0, min(1, ratio))
        self.value = self.min_val + ratio * (self.max_val - self.min_val)
        self._update_handle()


# --- Preview Manager ---

class PreviewManager:
    """Manages live physics preview mode."""

    MARBLE_RADIUS = 6
    GRAVITY = 600.0
    ELASTICITY = 1.1

    def __init__(self):
        self.space = None
        self.marbles = []
        self.marble_queue = []
        self.emitter = None
        self.emit_accumulator = 0.0
        self.active = False

    def start(self, walls, platforms, emitter):
        """Start physics preview with current level geometry."""
        self.space = pymunk.Space()
        self.space.gravity = (0, self.GRAVITY)
        self.marbles = []
        self.emitter = emitter
        self.emit_accumulator = 0.0

        # Create walls
        static_body = self.space.static_body
        for start, end in walls:
            shape = pymunk.Segment(static_body, start, end, 5)
            shape.elasticity = 0.5
            shape.friction = 0.5
            self.space.add(shape)

        # Create rotating platforms
        for platform in platforms:
            pos = platform["pos"]
            length = platform["length"]
            angular_vel = platform["angular_velocity"]

            body = pymunk.Body(body_type=pymunk.Body.KINEMATIC)
            body.position = pos
            body.angular_velocity = angular_vel

            shape = pymunk.Segment(body, (-length, 0), (length, 0), 4)
            shape.elasticity = 0.8
            shape.friction = 0.5
            self.space.add(body, shape)

        # Prepare marble queue (use 20 for preview)
        preview_count = min(20, emitter.get("count", 100))
        self.marble_queue = []
        for i in range(preview_count):
            hue = i / preview_count
            r, g, b = colorsys.hsv_to_rgb(hue, 0.8, 1.0)
            color = (int(r * 255), int(g * 255), int(b * 255))
            self.marble_queue.append({'color': color})

        self.active = True

    def emit_marble(self):
        """Emit a single marble from the emitter."""
        if not self.marble_queue or not self.emitter:
            return False

        marble_def = self.marble_queue.pop(0)

        ex, ey = self.emitter["pos"]
        width = self.emitter["width"]
        angle_deg = self.emitter["angle"]
        speed = self.emitter["speed"]

        offset = random.uniform(-width / 2, width / 2)
        angle_rad = math.radians(angle_deg)
        perp_angle = angle_rad - math.pi / 2

        x = ex + offset * math.cos(perp_angle)
        y = ey + offset * math.sin(perp_angle)

        vx = speed * math.cos(angle_rad)
        vy = speed * math.sin(angle_rad)

        mass = 1
        moment = pymunk.moment_for_circle(mass, 0, self.MARBLE_RADIUS)
        body = pymunk.Body(mass, moment)
        body.position = (x, y)
        body.velocity = (vx, vy)

        shape = pymunk.Circle(body, self.MARBLE_RADIUS)
        shape.elasticity = self.ELASTICITY
        shape.friction = 0.3

        self.space.add(body, shape)

        self.marbles.append({
            'body': body,
            'shape': shape,
            'color': marble_def['color'],
            'active': True
        })
        return True

    def stop(self):
        """Stop physics preview."""
        self.space = None
        self.marbles = []
        self.marble_queue = []
        self.emitter = None
        self.active = False

    def update(self, dt):
        """Step the physics simulation."""
        if not self.active or not self.space:
            return

        self.space.step(dt)

        # Emit marbles from the emitter
        if self.marble_queue and self.emitter:
            rate = self.emitter.get("rate", 20.0)
            self.emit_accumulator += dt
            emit_interval = 1.0 / rate
            while self.emit_accumulator >= emit_interval and self.marble_queue:
                self.emit_marble()
                self.emit_accumulator -= emit_interval

        # Remove marbles that exit the bottom
        for m in self.marbles:
            if m['active'] and m['body'].position.y > CANVAS_SIZE + self.MARBLE_RADIUS:
                m['active'] = False
                self.space.remove(m['body'], m['shape'])

    def draw(self, surface):
        """Draw the preview simulation."""
        if not self.active:
            return

        # Draw emitter
        if self.emitter:
            self.draw_emitter(surface, self.emitter)

        # Draw walls and platforms
        for shape in self.space.shapes:
            if isinstance(shape, pymunk.Segment):
                p1 = shape.body.local_to_world(shape.a)
                p2 = shape.body.local_to_world(shape.b)
                pygame.draw.line(surface, WALL_COLOR, p1, p2, int(shape.radius * 2))

        # Draw marbles
        for m in self.marbles:
            if m['active']:
                pos = m['body'].position
                pygame.draw.circle(surface, m['color'],
                                   (int(pos.x), int(pos.y)), self.MARBLE_RADIUS)
                pygame.draw.circle(surface, (0, 0, 0),
                                   (int(pos.x), int(pos.y)), self.MARBLE_RADIUS, 1)

    def draw_emitter(self, surface, emitter):
        """Draw the emitter pipe."""
        ex, ey = emitter["pos"]
        width = emitter["width"]
        angle_deg = emitter["angle"]

        angle_rad = math.radians(angle_deg)
        perp_angle = angle_rad - math.pi / 2

        half_width = width / 2
        pipe_length = 30

        left_x = ex + half_width * math.cos(perp_angle)
        left_y = ey + half_width * math.sin(perp_angle)
        right_x = ex - half_width * math.cos(perp_angle)
        right_y = ey - half_width * math.sin(perp_angle)

        back_dx = -pipe_length * math.cos(angle_rad)
        back_dy = -pipe_length * math.sin(angle_rad)

        points = [
            (left_x, left_y),
            (right_x, right_y),
            (right_x + back_dx, right_y + back_dy),
            (left_x + back_dx, left_y + back_dy),
        ]
        pygame.draw.polygon(surface, EMITTER_COLOR, points)
        pygame.draw.polygon(surface, (150, 170, 220), points, 2)


# --- Main Level Editor ---

class LevelEditor:
    """Main level editor application."""

    # Editor modes
    MODE_SELECT = "select"
    MODE_WALL = "wall"
    MODE_PLATFORM = "platform"
    MODE_EMITTER = "emitter"
    MODE_DELETE = "delete"
    MODE_PREVIEW = "preview"

    def __init__(self):
        pygame.init()
        self.screen = pygame.display.set_mode((DEFAULT_WIDTH, DEFAULT_HEIGHT), pygame.RESIZABLE)
        pygame.display.set_caption("Marble Race - Level Editor")
        self.clock = pygame.time.Clock()
        self.font = pygame.font.SysFont("Arial", 14)
        self.small_font = pygame.font.SysFont("Arial", 11)

        self.width, self.height = DEFAULT_WIDTH, DEFAULT_HEIGHT

        # Level data
        self.walls = []
        self.platforms = []
        self.emitter = get_default_emitter()
        self.level_name = "untitled"
        self.current_file = None
        self.modified = False

        # Editor state
        self.mode = self.MODE_SELECT
        self.selected_wall = None
        self.selected_platform = None
        self.selected_emitter = False  # True when emitter is selected
        self.selected_handle = None  # For wall endpoint dragging
        self.dragging_emitter = False  # For dragging the emitter

        # Drawing state
        self.drawing = False
        self.draw_start = None
        self.draw_end = None

        # Systems
        self.grid = GridSystem(size=20, enabled=True)
        self.history = CommandHistory()
        self.preview = PreviewManager()

        # Calculate initial layout
        self.update_layout()

        # Create UI components
        self.create_ui()

        # Load level files
        self.refresh_level_list()

        # Load default level
        self.load_level(DEFAULT_LEVEL_PATH)

    def update_layout(self):
        """Update layout dimensions based on window size."""
        self.width, self.height = self.screen.get_size()

        # Calculate canvas area
        self.canvas_x = TOOLBAR_WIDTH
        self.canvas_y = MENU_BAR_HEIGHT
        self.canvas_w = self.width - TOOLBAR_WIDTH - PROPERTY_PANEL_WIDTH
        self.canvas_h = self.height - MENU_BAR_HEIGHT - FILE_BROWSER_HEIGHT

        # Canvas viewport (centered 800x800 within canvas area)
        self.viewport_scale = min(self.canvas_w / CANVAS_SIZE, self.canvas_h / CANVAS_SIZE)
        self.viewport_w = int(CANVAS_SIZE * self.viewport_scale)
        self.viewport_h = int(CANVAS_SIZE * self.viewport_scale)
        self.viewport_x = self.canvas_x + (self.canvas_w - self.viewport_w) // 2
        self.viewport_y = self.canvas_y + (self.canvas_h - self.viewport_h) // 2

    def create_ui(self):
        """Create all UI components."""
        # Tool buttons
        btn_y = MENU_BAR_HEIGHT + 20
        btn_h = 50
        btn_w = 60
        btn_gap = 10

        self.tool_buttons = {
            self.MODE_SELECT: Button(10, btn_y, btn_w, btn_h, "Sel", toggle=True),
            self.MODE_WALL: Button(10, btn_y + btn_h + btn_gap, btn_w, btn_h, "Wall", toggle=True),
            self.MODE_PLATFORM: Button(10, btn_y + 2*(btn_h + btn_gap), btn_w, btn_h, "Plat", toggle=True),
            self.MODE_EMITTER: Button(10, btn_y + 3*(btn_h + btn_gap), btn_w, btn_h, "Emit", toggle=True),
            self.MODE_DELETE: Button(10, btn_y + 4*(btn_h + btn_gap), btn_w, btn_h, "Del", toggle=True),
        }
        self.tool_buttons[self.MODE_SELECT].active = True

        # Preview button
        self.preview_button = Button(10, btn_y + 5*(btn_h + btn_gap) + 20, btn_w, btn_h, "Test",
                                     color=(60, 100, 80), hover_color=(80, 130, 100))

        # Grid toggle button
        self.grid_button = Button(10, btn_y + 6*(btn_h + btn_gap) + 30, btn_w, 30, "Grid", toggle=True)
        self.grid_button.active = True

        # Property panel input fields (will be positioned in draw)
        self.prop_fields = {}

        # File browser buttons
        self.new_button = Button(0, 0, 60, 28, "New")
        self.save_button = Button(0, 0, 60, 28, "Save")
        self.save_as_button = Button(0, 0, 80, 28, "Save As")

        # Level file buttons (created dynamically)
        self.level_buttons = []

    def refresh_level_list(self):
        """Refresh the list of level files."""
        self.level_files = list(LEVELS_DIR.glob("*.json"))
        self.level_files.sort(key=lambda p: p.stem)

    def screen_to_canvas(self, pos):
        """Convert screen coordinates to canvas coordinates."""
        x, y = pos
        if not (self.viewport_x <= x <= self.viewport_x + self.viewport_w and
                self.viewport_y <= y <= self.viewport_y + self.viewport_h):
            return None

        canvas_x = (x - self.viewport_x) / self.viewport_scale
        canvas_y = (y - self.viewport_y) / self.viewport_scale
        return (canvas_x, canvas_y)

    def canvas_to_screen(self, pos):
        """Convert canvas coordinates to screen coordinates."""
        x, y = pos
        screen_x = self.viewport_x + x * self.viewport_scale
        screen_y = self.viewport_y + y * self.viewport_scale
        return (screen_x, screen_y)

    def distance_to_segment(self, p, a, b):
        """Calculate distance from point p to line segment a-b."""
        ax, ay = a
        bx, by = b
        px, py = p
        abx = bx - ax
        aby = by - ay
        ab_len_sq = abx * abx + aby * aby
        if ab_len_sq == 0:
            return math.hypot(px - ax, py - ay)
        t = ((px - ax) * abx + (py - ay) * aby) / ab_len_sq
        t = max(0.0, min(1.0, t))
        cx = ax + t * abx
        cy = ay + t * aby
        return math.hypot(px - cx, py - cy)

    def distance_to_point(self, p1, p2):
        """Calculate distance between two points."""
        return math.hypot(p2[0] - p1[0], p2[1] - p1[1])

    def find_wall_at(self, pos, threshold=10):
        """Find a wall near the given position."""
        best_idx = None
        best_dist = threshold + 1
        for idx, (a, b) in enumerate(self.walls):
            dist = self.distance_to_segment(pos, a, b)
            if dist < best_dist:
                best_dist = dist
                best_idx = idx
        return best_idx if best_dist <= threshold else None

    def find_wall_handle_at(self, pos, threshold=8):
        """Find a wall endpoint handle near the given position."""
        for idx, (start, end) in enumerate(self.walls):
            if self.distance_to_point(pos, start) <= threshold:
                return (idx, 'start')
            if self.distance_to_point(pos, end) <= threshold:
                return (idx, 'end')
        return None

    def find_platform_at(self, pos, threshold=15):
        """Find a platform near the given position."""
        best_idx = None
        best_dist = threshold + 1
        for idx, platform in enumerate(self.platforms):
            cx, cy = platform["pos"]
            length = platform["length"]
            a = (cx - length, cy)
            b = (cx + length, cy)
            dist = self.distance_to_segment(pos, a, b)
            if dist < best_dist:
                best_dist = dist
                best_idx = idx
        return best_idx if best_dist <= threshold else None

    def is_near_emitter(self, pos, threshold=30):
        """Check if a point is near the emitter."""
        ex, ey = self.emitter["pos"]
        dist = self.distance_to_point(pos, (ex, ey))
        return dist <= threshold

    def set_mode(self, mode):
        """Switch to a new editor mode."""
        self.mode = mode
        self.selected_wall = None
        self.selected_platform = None
        self.selected_emitter = False
        self.selected_handle = None
        self.dragging_emitter = False
        self.drawing = False
        self.draw_start = None
        self.draw_end = None

        # Update tool button states
        for m, btn in self.tool_buttons.items():
            btn.active = (m == mode)

    def load_level(self, path):
        """Load a level from file."""
        try:
            level = load_level(path)
            self.walls = list(level.get("walls", []))
            self.platforms = list(level.get("platforms", []))
            self.emitter = level.get("emitter", get_default_emitter())
            self.level_name = level.get("name", "level")
            self.current_file = Path(path)
            self.modified = False
            self.history.clear()
            self.selected_wall = None
            self.selected_platform = None
            self.selected_emitter = False
        except Exception as e:
            print(f"Error loading level: {e}")

    def save_level(self, path=None):
        """Save the current level to file."""
        if path is None:
            path = self.current_file
        if path is None:
            path = LEVELS_DIR / "untitled.json"

        try:
            save_level(path, self.walls, self.platforms, self.emitter, name=self.level_name)
            self.current_file = Path(path)
            self.modified = False
            self.refresh_level_list()
        except Exception as e:
            print(f"Error saving level: {e}")

    def new_level(self):
        """Create a new empty level."""
        self.walls = []
        self.platforms = []
        self.emitter = get_default_emitter()
        self.level_name = "untitled"
        self.current_file = None
        self.modified = False
        self.history.clear()
        self.selected_wall = None
        self.selected_platform = None

    def handle_event(self, event):
        """Handle pygame events."""
        if event.type == pygame.QUIT:
            return False

        if event.type == pygame.VIDEORESIZE:
            self.width, self.height = event.size
            self.screen = pygame.display.set_mode((self.width, self.height), pygame.RESIZABLE)
            self.update_layout()

        # Handle preview mode separately
        if self.mode == self.MODE_PREVIEW:
            if event.type == pygame.KEYDOWN:
                if event.key in (pygame.K_SPACE, pygame.K_ESCAPE):
                    self.preview.stop()
                    self.set_mode(self.MODE_SELECT)
            return True

        # Keyboard shortcuts
        if event.type == pygame.KEYDOWN:
            mods = pygame.key.get_mods()
            ctrl = mods & pygame.KMOD_CTRL

            if ctrl and event.key == pygame.K_z:
                if self.history.undo(self):
                    self.modified = True
            elif ctrl and event.key == pygame.K_y:
                if self.history.redo(self):
                    self.modified = True
            elif ctrl and event.key == pygame.K_s:
                self.save_level()
            elif event.key == pygame.K_v:
                self.set_mode(self.MODE_SELECT)
            elif event.key == pygame.K_w:
                self.set_mode(self.MODE_WALL)
            elif event.key == pygame.K_p:
                self.set_mode(self.MODE_PLATFORM)
            elif event.key == pygame.K_e:
                self.set_mode(self.MODE_EMITTER)
            elif event.key == pygame.K_x:
                self.set_mode(self.MODE_DELETE)
            elif event.key == pygame.K_g:
                self.grid.enabled = not self.grid.enabled
                self.grid_button.active = self.grid.enabled
            elif event.key == pygame.K_SPACE:
                self.preview.start(self.walls, self.platforms, self.emitter)
                self.mode = self.MODE_PREVIEW
            elif event.key == pygame.K_DELETE:
                self.delete_selected()

        # Tool button clicks
        for mode, btn in self.tool_buttons.items():
            if btn.is_clicked(event):
                self.set_mode(mode)
                return True

        if self.preview_button.is_clicked(event):
            self.preview.start(self.walls, self.platforms, self.emitter)
            self.mode = self.MODE_PREVIEW
            return True

        if self.grid_button.is_clicked(event):
            self.grid.enabled = not self.grid.enabled
            self.grid_button.active = self.grid.enabled
            return True

        # File browser buttons
        if self.new_button.is_clicked(event):
            self.new_level()
            return True
        if self.save_button.is_clicked(event):
            self.save_level()
            return True
        if self.save_as_button.is_clicked(event):
            # Simple save as: save to "edited.json"
            new_path = LEVELS_DIR / "edited.json"
            self.save_level(new_path)
            return True

        # Level file buttons
        for btn, path in self.level_buttons:
            if btn.is_clicked(event):
                self.load_level(path)
                return True

        # Handle property field inputs
        for name, field in self.prop_fields.items():
            if field.handle_event(event):
                self.apply_property_changes()
                return True

        # Canvas interactions
        canvas_pos = self.screen_to_canvas(pygame.mouse.get_pos() if event.type == pygame.MOUSEMOTION
                                           else getattr(event, 'pos', (0, 0)))

        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if canvas_pos:
                self.handle_canvas_click(canvas_pos)
        elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            if self.drawing:
                self.finish_drawing()
            self.dragging_emitter = False
        elif event.type == pygame.MOUSEMOTION:
            if self.drawing and canvas_pos:
                self.draw_end = self.grid.snap_point(canvas_pos)
            elif self.selected_handle and canvas_pos and pygame.mouse.get_pressed()[0]:
                self.drag_wall_handle(canvas_pos)
            elif self.dragging_emitter and canvas_pos and pygame.mouse.get_pressed()[0]:
                self.drag_emitter(canvas_pos)

        return True

    def handle_canvas_click(self, pos):
        """Handle a click on the canvas."""
        snapped_pos = self.grid.snap_point(pos)

        if self.mode == self.MODE_SELECT:
            # Check for wall handle first
            handle = self.find_wall_handle_at(pos)
            if handle:
                self.selected_wall = handle[0]
                self.selected_handle = handle
                self.selected_platform = None
                self.selected_emitter = False
                self.update_property_fields()
                return

            # Then check for wall selection
            wall_idx = self.find_wall_at(pos)
            if wall_idx is not None:
                self.selected_wall = wall_idx
                self.selected_platform = None
                self.selected_emitter = False
                self.selected_handle = None
                self.update_property_fields()
                return

            # Then check for platform
            plat_idx = self.find_platform_at(pos)
            if plat_idx is not None:
                self.selected_platform = plat_idx
                self.selected_wall = None
                self.selected_emitter = False
                self.selected_handle = None
                self.update_property_fields()
                return

            # Then check for emitter
            if self.is_near_emitter(pos):
                self.selected_emitter = True
                self.selected_wall = None
                self.selected_platform = None
                self.selected_handle = None
                self.dragging_emitter = True
                self.update_property_fields()
                return

            # Clicked on empty space
            self.selected_wall = None
            self.selected_platform = None
            self.selected_emitter = False
            self.selected_handle = None
            self.update_property_fields()

        elif self.mode == self.MODE_WALL:
            self.drawing = True
            self.draw_start = snapped_pos
            self.draw_end = snapped_pos

        elif self.mode == self.MODE_PLATFORM:
            # Create a new platform at click position
            platform = {
                "pos": (float(snapped_pos[0]), float(snapped_pos[1])),
                "length": 50.0,
                "angular_velocity": 2.0
            }
            cmd = AddPlatformCommand(platform)
            self.history.execute(cmd, self)
            self.modified = True
            self.selected_platform = len(self.platforms) - 1
            self.selected_wall = None
            self.selected_emitter = False
            self.update_property_fields()

        elif self.mode == self.MODE_EMITTER:
            # Move the emitter to clicked position
            old_emitter = self.emitter.copy()
            new_emitter = self.emitter.copy()
            new_emitter["pos"] = (float(snapped_pos[0]), float(snapped_pos[1]))
            cmd = ModifyEmitterCommand(old_emitter, new_emitter)
            self.history.execute(cmd, self)
            self.modified = True
            self.selected_emitter = True
            self.selected_wall = None
            self.selected_platform = None
            self.update_property_fields()

        elif self.mode == self.MODE_DELETE:
            # Try to delete platform first, then wall
            plat_idx = self.find_platform_at(pos)
            if plat_idx is not None:
                platform = self.platforms[plat_idx]
                cmd = DeletePlatformCommand(platform, plat_idx)
                self.history.execute(cmd, self)
                self.modified = True
                if self.selected_platform == plat_idx:
                    self.selected_platform = None
                return

            wall_idx = self.find_wall_at(pos)
            if wall_idx is not None:
                wall = self.walls[wall_idx]
                cmd = DeleteWallCommand(wall, wall_idx)
                self.history.execute(cmd, self)
                self.modified = True
                if self.selected_wall == wall_idx:
                    self.selected_wall = None

    def drag_wall_handle(self, pos):
        """Drag a wall endpoint handle."""
        if not self.selected_handle:
            return

        idx, which = self.selected_handle
        snapped = self.grid.snap_point(pos)

        old_wall = self.walls[idx]
        if which == 'start':
            new_wall = (snapped, old_wall[1])
        else:
            new_wall = (old_wall[0], snapped)

        self.walls[idx] = new_wall
        self.modified = True

    def drag_emitter(self, pos):
        """Drag the emitter to a new position."""
        snapped = self.grid.snap_point(pos)
        self.emitter["pos"] = (float(snapped[0]), float(snapped[1]))
        self.modified = True
        self.update_property_fields()

    def finish_drawing(self):
        """Finish drawing a wall."""
        if not self.drawing or not self.draw_start or not self.draw_end:
            self.drawing = False
            return

        # Only create wall if it has some length
        if self.distance_to_point(self.draw_start, self.draw_end) > 5:
            wall = (self.draw_start, self.draw_end)
            cmd = AddWallCommand(wall)
            self.history.execute(cmd, self)
            self.modified = True
            self.selected_wall = len(self.walls) - 1
            self.selected_platform = None
            self.update_property_fields()

        self.drawing = False
        self.draw_start = None
        self.draw_end = None

    def delete_selected(self):
        """Delete the currently selected element."""
        if self.selected_platform is not None:
            platform = self.platforms[self.selected_platform]
            cmd = DeletePlatformCommand(platform, self.selected_platform)
            self.history.execute(cmd, self)
            self.modified = True
            self.selected_platform = None
            self.update_property_fields()
        elif self.selected_wall is not None:
            wall = self.walls[self.selected_wall]
            cmd = DeleteWallCommand(wall, self.selected_wall)
            self.history.execute(cmd, self)
            self.modified = True
            self.selected_wall = None
            self.update_property_fields()

    def update_property_fields(self):
        """Update property panel input fields for current selection."""
        self.prop_fields.clear()

        prop_x = self.width - PROPERTY_PANEL_WIDTH + 15
        prop_y = MENU_BAR_HEIGHT + 80
        field_w = PROPERTY_PANEL_WIDTH - 30
        field_h = 22
        field_gap = 45

        if self.selected_wall is not None and self.selected_wall < len(self.walls):
            start, end = self.walls[self.selected_wall]

            self.prop_fields['start_x'] = InputField(prop_x, prop_y, field_w, field_h, "Start X")
            self.prop_fields['start_x'].set_value(start[0])

            self.prop_fields['start_y'] = InputField(prop_x, prop_y + field_gap, field_w, field_h, "Start Y")
            self.prop_fields['start_y'].set_value(start[1])

            self.prop_fields['end_x'] = InputField(prop_x, prop_y + 2*field_gap, field_w, field_h, "End X")
            self.prop_fields['end_x'].set_value(end[0])

            self.prop_fields['end_y'] = InputField(prop_x, prop_y + 3*field_gap, field_w, field_h, "End Y")
            self.prop_fields['end_y'].set_value(end[1])

        elif self.selected_platform is not None and self.selected_platform < len(self.platforms):
            plat = self.platforms[self.selected_platform]

            self.prop_fields['pos_x'] = InputField(prop_x, prop_y, field_w, field_h, "X Position")
            self.prop_fields['pos_x'].set_value(plat['pos'][0])

            self.prop_fields['pos_y'] = InputField(prop_x, prop_y + field_gap, field_w, field_h, "Y Position")
            self.prop_fields['pos_y'].set_value(plat['pos'][1])

            self.prop_fields['length'] = InputField(prop_x, prop_y + 2*field_gap, field_w, field_h, "Length")
            self.prop_fields['length'].set_value(plat['length'])

            self.prop_fields['ang_vel'] = InputField(prop_x, prop_y + 3*field_gap, field_w, field_h, "Angular Vel")
            self.prop_fields['ang_vel'].set_value(plat['angular_velocity'])

        elif self.selected_emitter:
            self.prop_fields['emit_x'] = InputField(prop_x, prop_y, field_w, field_h, "X Position")
            self.prop_fields['emit_x'].set_value(self.emitter['pos'][0])

            self.prop_fields['emit_y'] = InputField(prop_x, prop_y + field_gap, field_w, field_h, "Y Position")
            self.prop_fields['emit_y'].set_value(self.emitter['pos'][1])

            self.prop_fields['emit_angle'] = InputField(prop_x, prop_y + 2*field_gap, field_w, field_h, "Angle (deg)")
            self.prop_fields['emit_angle'].set_value(self.emitter['angle'])

            self.prop_fields['emit_width'] = InputField(prop_x, prop_y + 3*field_gap, field_w, field_h, "Width")
            self.prop_fields['emit_width'].set_value(self.emitter['width'])

            self.prop_fields['emit_rate'] = InputField(prop_x, prop_y + 4*field_gap, field_w, field_h, "Rate (/sec)")
            self.prop_fields['emit_rate'].set_value(self.emitter['rate'])

            self.prop_fields['emit_count'] = InputField(prop_x, prop_y + 5*field_gap, field_w, field_h, "Count")
            self.prop_fields['emit_count'].set_value(self.emitter['count'])

            self.prop_fields['emit_speed'] = InputField(prop_x, prop_y + 6*field_gap, field_w, field_h, "Speed")
            self.prop_fields['emit_speed'].set_value(self.emitter['speed'])

    def apply_property_changes(self):
        """Apply changes from property fields to the selected element."""
        if self.selected_wall is not None and self.selected_wall < len(self.walls):
            if all(k in self.prop_fields for k in ['start_x', 'start_y', 'end_x', 'end_y']):
                new_start = (self.prop_fields['start_x'].get_float(),
                            self.prop_fields['start_y'].get_float())
                new_end = (self.prop_fields['end_x'].get_float(),
                          self.prop_fields['end_y'].get_float())
                self.walls[self.selected_wall] = (new_start, new_end)
                self.modified = True

        elif self.selected_platform is not None and self.selected_platform < len(self.platforms):
            if all(k in self.prop_fields for k in ['pos_x', 'pos_y', 'length', 'ang_vel']):
                self.platforms[self.selected_platform]['pos'] = (
                    self.prop_fields['pos_x'].get_float(),
                    self.prop_fields['pos_y'].get_float()
                )
                self.platforms[self.selected_platform]['length'] = self.prop_fields['length'].get_float()
                self.platforms[self.selected_platform]['angular_velocity'] = self.prop_fields['ang_vel'].get_float()
                self.modified = True

        elif self.selected_emitter:
            emitter_keys = ['emit_x', 'emit_y', 'emit_angle', 'emit_width', 'emit_rate', 'emit_count', 'emit_speed']
            if all(k in self.prop_fields for k in emitter_keys):
                self.emitter['pos'] = (
                    self.prop_fields['emit_x'].get_float(),
                    self.prop_fields['emit_y'].get_float()
                )
                self.emitter['angle'] = self.prop_fields['emit_angle'].get_float()
                self.emitter['width'] = self.prop_fields['emit_width'].get_float()
                self.emitter['rate'] = self.prop_fields['emit_rate'].get_float()
                self.emitter['count'] = int(self.prop_fields['emit_count'].get_float())
                self.emitter['speed'] = self.prop_fields['emit_speed'].get_float()
                self.modified = True

    def draw_emitter(self, surface):
        """Draw the emitter/entry pipe."""
        emitter = self.emitter
        ex, ey = emitter["pos"]
        width = emitter["width"]
        angle_deg = emitter["angle"]

        angle_rad = math.radians(angle_deg)
        perp_angle = angle_rad - math.pi / 2

        half_width = width / 2
        pipe_length = 30

        left_x = ex + half_width * math.cos(perp_angle)
        left_y = ey + half_width * math.sin(perp_angle)
        right_x = ex - half_width * math.cos(perp_angle)
        right_y = ey - half_width * math.sin(perp_angle)

        back_dx = -pipe_length * math.cos(angle_rad)
        back_dy = -pipe_length * math.sin(angle_rad)

        points = [
            (left_x, left_y),
            (right_x, right_y),
            (right_x + back_dx, right_y + back_dy),
            (left_x + back_dx, left_y + back_dy),
        ]

        # Use selected color if emitter is selected
        color = SELECTED_COLOR if self.selected_emitter else EMITTER_COLOR
        pygame.draw.polygon(surface, color, points)
        pygame.draw.polygon(surface, (150, 170, 220), points, 2)

        # Draw emission direction indicator
        arrow_len = 15
        arrow_x = ex + arrow_len * math.cos(angle_rad)
        arrow_y = ey + arrow_len * math.sin(angle_rad)
        pygame.draw.line(surface, (200, 220, 255), (ex, ey), (arrow_x, arrow_y), 2)

        # Draw center handle if selected
        if self.selected_emitter:
            pygame.draw.circle(surface, HIGHLIGHT_COLOR, (int(ex), int(ey)), 6)

    def draw(self):
        """Draw the entire editor interface."""
        self.screen.fill(BG_COLOR)

        # Draw menu bar
        pygame.draw.rect(self.screen, PANEL_BG, (0, 0, self.width, MENU_BAR_HEIGHT))
        title = f"Level Editor - {self.level_name}"
        if self.modified:
            title += " *"
        title_surf = self.font.render(title, True, TEXT_COLOR)
        self.screen.blit(title_surf, (10, 7))

        # Draw shortcuts hint
        shortcuts = "V:Select  W:Wall  P:Platform  E:Emitter  X:Delete  Space:Test  G:Grid  Ctrl+Z/Y:Undo/Redo"
        shortcuts_surf = self.small_font.render(shortcuts, True, (150, 150, 150))
        self.screen.blit(shortcuts_surf, (200, 9))

        # Draw toolbar panel
        pygame.draw.rect(self.screen, PANEL_BG, (0, MENU_BAR_HEIGHT, TOOLBAR_WIDTH, self.height - MENU_BAR_HEIGHT))

        # Draw tool buttons
        for btn in self.tool_buttons.values():
            btn.draw(self.screen)
        self.preview_button.draw(self.screen)
        self.grid_button.draw(self.screen)

        # Draw canvas area
        pygame.draw.rect(self.screen, (25, 25, 35),
                        (self.canvas_x, self.canvas_y, self.canvas_w, self.canvas_h))

        # Draw the actual canvas content
        canvas_surface = pygame.Surface((CANVAS_SIZE, CANVAS_SIZE))
        canvas_surface.fill(CANVAS_BG)

        if self.mode == self.MODE_PREVIEW and self.preview.active:
            self.preview.draw(canvas_surface)
        else:
            # Draw grid
            self.grid.draw(canvas_surface, None)

            # Draw walls
            for idx, (start, end) in enumerate(self.walls):
                color = SELECTED_COLOR if idx == self.selected_wall else WALL_COLOR
                pygame.draw.line(canvas_surface, color, start, end, 10)

                # Draw handles if selected
                if idx == self.selected_wall:
                    pygame.draw.circle(canvas_surface, HIGHLIGHT_COLOR,
                                      (int(start[0]), int(start[1])), 6)
                    pygame.draw.circle(canvas_surface, HIGHLIGHT_COLOR,
                                      (int(end[0]), int(end[1])), 6)

            # Draw platforms
            for idx, platform in enumerate(self.platforms):
                cx, cy = platform["pos"]
                length = platform["length"]
                a = (cx - length, cy)
                b = (cx + length, cy)
                color = SELECTED_COLOR if idx == self.selected_platform else PLATFORM_COLOR
                pygame.draw.line(canvas_surface, color, a, b, 8)
                # Draw center point
                pygame.draw.circle(canvas_surface, (255, 255, 255), (int(cx), int(cy)), 3)

            # Draw emitter
            self.draw_emitter(canvas_surface)

            # Draw preview line when creating wall
            if self.drawing and self.draw_start and self.draw_end:
                pygame.draw.line(canvas_surface, PREVIEW_WALL_COLOR,
                               self.draw_start, self.draw_end, 3)

        # Scale and blit canvas to viewport
        scaled_canvas = pygame.transform.smoothscale(canvas_surface, (self.viewport_w, self.viewport_h))
        self.screen.blit(scaled_canvas, (self.viewport_x, self.viewport_y))

        # Draw viewport border
        pygame.draw.rect(self.screen, (80, 80, 100),
                        (self.viewport_x, self.viewport_y, self.viewport_w, self.viewport_h), 2)

        # Draw property panel
        prop_panel_x = self.width - PROPERTY_PANEL_WIDTH
        pygame.draw.rect(self.screen, PANEL_BG,
                        (prop_panel_x, MENU_BAR_HEIGHT, PROPERTY_PANEL_WIDTH, self.height - MENU_BAR_HEIGHT))

        # Draw property panel title
        panel_title = "Properties"
        if self.selected_wall is not None:
            panel_title = "Wall Properties"
        elif self.selected_platform is not None:
            panel_title = "Platform Properties"
        elif self.selected_emitter:
            panel_title = "Emitter Properties"
        title_surf = self.font.render(panel_title, True, TEXT_COLOR)
        self.screen.blit(title_surf, (prop_panel_x + 15, MENU_BAR_HEIGHT + 15))

        # Draw selection info
        if self.selected_wall is not None:
            info = f"Wall #{self.selected_wall + 1}"
        elif self.selected_platform is not None:
            info = f"Platform #{self.selected_platform + 1}"
        elif self.selected_emitter:
            info = "Entry Pipe"
        else:
            info = "Nothing selected"
        info_surf = self.small_font.render(info, True, (150, 150, 150))
        self.screen.blit(info_surf, (prop_panel_x + 15, MENU_BAR_HEIGHT + 40))

        # Draw property fields
        for field in self.prop_fields.values():
            field.draw(self.screen)

        # Draw stats
        stats_y = self.height - FILE_BROWSER_HEIGHT - 60
        stats = [
            f"Walls: {len(self.walls)}",
            f"Platforms: {len(self.platforms)}",
            f"Grid: {'On' if self.grid.enabled else 'Off'} ({self.grid.size}px)"
        ]
        for i, stat in enumerate(stats):
            surf = self.small_font.render(stat, True, (150, 150, 150))
            self.screen.blit(surf, (prop_panel_x + 15, stats_y + i * 16))

        # Draw file browser panel
        browser_y = self.height - FILE_BROWSER_HEIGHT
        pygame.draw.rect(self.screen, PANEL_BG, (0, browser_y, self.width, FILE_BROWSER_HEIGHT))
        pygame.draw.line(self.screen, (60, 60, 80), (0, browser_y), (self.width, browser_y), 1)

        # Position and draw file browser buttons
        btn_x = TOOLBAR_WIDTH + 10
        btn_y = browser_y + 6

        self.new_button.rect.x = btn_x
        self.new_button.rect.y = btn_y
        self.new_button.draw(self.screen)

        btn_x += 70
        self.save_button.rect.x = btn_x
        self.save_button.rect.y = btn_y
        self.save_button.draw(self.screen)

        btn_x += 70
        self.save_as_button.rect.x = btn_x
        self.save_as_button.rect.y = btn_y
        self.save_as_button.draw(self.screen)

        # Draw level file buttons
        btn_x += 100
        self.level_buttons.clear()
        for path in self.level_files[:6]:  # Show up to 6 level files
            name = path.stem
            is_current = path == self.current_file
            btn_color = (60, 100, 80) if is_current else (70, 70, 90)
            btn = Button(btn_x, btn_y, len(name) * 8 + 20, 28, name, color=btn_color)
            btn.draw(self.screen)
            self.level_buttons.append((btn, path))
            btn_x += len(name) * 8 + 30

        # Draw mode indicator if in preview
        if self.mode == self.MODE_PREVIEW:
            overlay = pygame.Surface((self.width, 30))
            overlay.fill((40, 80, 60))
            overlay.set_alpha(200)
            self.screen.blit(overlay, (0, MENU_BAR_HEIGHT))
            preview_text = self.font.render("PREVIEW MODE - Press Space or Escape to exit", True, (255, 255, 255))
            self.screen.blit(preview_text, (self.width // 2 - preview_text.get_width() // 2, MENU_BAR_HEIGHT + 7))

        pygame.display.flip()

    def run(self):
        """Main editor loop."""
        running = True
        last_time = pygame.time.get_ticks()

        while running:
            current_time = pygame.time.get_ticks()
            dt = (current_time - last_time) / 1000.0
            last_time = current_time

            for event in pygame.event.get():
                if not self.handle_event(event):
                    running = False

            # Update preview physics
            if self.mode == self.MODE_PREVIEW:
                self.preview.update(1.0 / FPS)

            # Update input field cursors
            for field in self.prop_fields.values():
                field.update(current_time)

            self.draw()
            self.clock.tick(FPS)

        pygame.quit()


if __name__ == "__main__":
    editor = LevelEditor()
    editor.run()
