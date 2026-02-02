import pygame
import pymunk
import pymunk.pygame_util
import random
import colorsys
import math
import argparse
import sys
from level_io import load_level, save_level, get_default_emitter, list_levels, DEFAULT_LEVEL_PATH, LEVELS_DIR

# --- Configuration ---
WIDTH, HEIGHT = 800, 800
FPS = 60
MARBLE_COUNT = 100
MARBLE_RADIUS = 6
FUNNEL_WALL_THICKNESS = 5

# Physics Constants
GRAVITY = 350.0
ELASTICITY = 0.9
FRICTION = 0.3

# Colors
BG_COLOR = (20, 20, 30)
FUNNEL_COLOR = (200, 200, 200)
TEXT_COLOR = (255, 255, 255)


def get_rainbow_color(index, total):
    """Generates a unique color for each marble based on its index."""
    hue = index / total
    # Convert HSV to RGB (0-1 range to 0-255 range)
    r, g, b = colorsys.hsv_to_rgb(hue, 0.8, 1.0)
    return int(r * 255), int(g * 255), int(b * 255)


def get_color_name(hue):
    """Returns a color name based on hue value (0-1)."""
    color_ranges = [
        (0.00, "Red"),
        (0.05, "Orange"),
        (0.11, "Gold"),
        (0.16, "Yellow"),
        (0.22, "Lime"),
        (0.33, "Green"),
        (0.44, "Teal"),
        (0.50, "Cyan"),
        (0.58, "Sky"),
        (0.66, "Blue"),
        (0.75, "Purple"),
        (0.83, "Magenta"),
        (0.91, "Pink"),
        (1.00, "Red"),
    ]
    for threshold, name in color_ranges:
        if hue <= threshold:
            return name
    return "Red"


SHAPE_NAMES = {
    0: "Circle",
    3: "Triangle",
    4: "Square",
    5: "Pentagon",
    6: "Hexagon",
}


def get_polygon_vertices(sides, radius):
    """Generate vertices for a regular polygon with given number of sides."""
    vertices = []
    for i in range(sides):
        angle = (2 * math.pi * i / sides) - math.pi / 2  # Start from top
        x = radius * math.cos(angle)
        y = radius * math.sin(angle)
        vertices.append((x, y))
    return vertices


class Button:
    """Simple button class for pygame UI."""
    def __init__(self, x, y, width, height, text, color=(80, 80, 100), hover_color=(100, 100, 130)):
        self.rect = pygame.Rect(x, y, width, height)
        self.text = text
        self.color = color
        self.hover_color = hover_color
        self.font = pygame.font.SysFont("Arial", 18, bold=True)
        self.visible = True

    def draw(self, screen):
        if not self.visible:
            return
        mouse_pos = pygame.mouse.get_pos()
        color = self.hover_color if self.rect.collidepoint(mouse_pos) else self.color
        pygame.draw.rect(screen, color, self.rect, border_radius=8)
        pygame.draw.rect(screen, (150, 150, 150), self.rect, 2, border_radius=8)
        text_surf = self.font.render(self.text, True, TEXT_COLOR)
        text_rect = text_surf.get_rect(center=self.rect.center)
        screen.blit(text_surf, text_rect)

    def is_clicked(self, event):
        if not self.visible:
            return False
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            return self.rect.collidepoint(event.pos)
        return False

    def set_center(self, x, y):
        self.rect.center = (x, y)


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
        self.font = pygame.font.SysFont("Arial", 14)
        self.dragging = False
        self.visible = True
        self.track_rect = pygame.Rect(x, y + 20, width, 8)
        self._update_handle()

    def _update_handle(self):
        """Update handle position based on current value."""
        ratio = (self.value - self.min_val) / (self.max_val - self.min_val)
        handle_x = self.x + int(ratio * self.width)
        self.handle_rect = pygame.Rect(handle_x - 8, self.y + 16, 16, 16)

    def set_position(self, x, y):
        self.x = x
        self.y = y
        self.track_rect = pygame.Rect(x, y + 20, self.width, 8)
        self._update_handle()

    def draw(self, screen):
        if not self.visible:
            return
        # Draw label and value
        label_text = f"{self.label}: {self.format_str.format(self.value)}"
        label_surf = self.font.render(label_text, True, TEXT_COLOR)
        screen.blit(label_surf, (self.x, self.y))

        # Draw track
        pygame.draw.rect(screen, (60, 60, 80), self.track_rect, border_radius=4)

        # Draw filled portion
        ratio = (self.value - self.min_val) / (self.max_val - self.min_val)
        filled_width = int(ratio * self.width)
        filled_rect = pygame.Rect(self.x, self.y + 20, filled_width, 8)
        pygame.draw.rect(screen, (100, 150, 200), filled_rect, border_radius=4)

        # Draw handle
        pygame.draw.rect(screen, (200, 200, 220), self.handle_rect, border_radius=4)

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
        """Update value based on mouse x position."""
        ratio = (mouse_x - self.x) / self.width
        ratio = max(0, min(1, ratio))
        self.value = self.min_val + ratio * (self.max_val - self.min_val)
        self._update_handle()


class Checkbox:
    """Checkbox control for boolean values."""
    def __init__(self, x, y, size, label, initial_state=True):
        self.rect = pygame.Rect(x, y, size, size)
        self.label = label
        self.checked = initial_state
        self.font = pygame.font.SysFont("Arial", 14)
        self.visible = True
        self.color = (80, 80, 100)
        self.check_color = (100, 200, 100)

    def draw(self, screen):
        if not self.visible:
            return
        # Draw box
        pygame.draw.rect(screen, self.color, self.rect, border_radius=4)
        pygame.draw.rect(screen, (150, 150, 150), self.rect, 2, border_radius=4)
        
        # Draw check
        if self.checked:
            inner_rect = self.rect.inflate(-6, -6)
            pygame.draw.rect(screen, self.check_color, inner_rect, border_radius=2)
            
        # Draw label
        label_surf = self.font.render(self.label, True, TEXT_COLOR)
        # Vertically center label relative to box
        label_y = self.rect.y + (self.rect.height - label_surf.get_height()) // 2
        screen.blit(label_surf, (self.rect.right + 10, label_y))

    def handle_event(self, event):
        if not self.visible:
            return False
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            # Check click on box or label
            label_w = self.font.size(self.label)[0]
            total_rect = self.rect.union(pygame.Rect(self.rect.right, self.rect.y, label_w + 10, self.rect.height))
            if total_rect.collidepoint(event.pos):
                self.checked = not self.checked
                return True
        return False
    
    def set_position(self, x, y):
        self.rect.x = x
        self.rect.y = y


class MarbleSimulation:
    def __init__(self, initial_level=None):
        pygame.init()
        self.screen = pygame.display.set_mode((WIDTH, HEIGHT), pygame.FULLSCREEN)
        pygame.display.set_caption("Marble Funnel Simulation")
        self.clock = pygame.time.Clock()
        self.font = pygame.font.SysFont("Arial", 16)
        self.screen_width, self.screen_height = self.screen.get_size()
        self.prev_screen_size = (self.screen_width, self.screen_height)

        # Level Management
        self.level_files = list_levels()
        self.current_level_index = 0
        self.initial_level_name = initial_level

        # Simulation state: "ready", "running", "finished"
        self.state = "ready"
        self.prev_state = None

        # UI Buttons
        self.start_button = Button(0, 0, 120, 40, "Start")
        self.reset_button = Button(0, 0, 120, 40, "Reset")
        self.reset_button.visible = False

        # Level selection buttons
        self.prev_level_btn = Button(20, 50, 40, 30, "<")
        self.next_level_btn = Button(200, 50, 40, 30, ">")

        # Sidebar configuration
        self.SIDEBAR_WIDTH = 250
        self.sidebar_padding = 20

        # Settings sliders (positioned in sidebar)
        slider_width = self.SIDEBAR_WIDTH - 2 * self.sidebar_padding
        self.timer_slider = Slider(0, 0, slider_width, "Timer (sec)", 1, 60, 30, "{:.0f}")
        self.gravity_slider = Slider(0, 0, slider_width, "Gravity", 0, 1000, GRAVITY, "{:.0f}")
        self.bounce_slider = Slider(0, 0, slider_width, "Bounciness", 0.5, 2.0, ELASTICITY, "{:.2f}")
        self.speed_slider = Slider(0, 0, slider_width, "Speed", 0.25, 1.5, 0.75, "{:.2f}")
        self.emit_rate_slider = Slider(0, 0, slider_width, "Emit Rate", 1, 50, 20, "{:.0f}")
        self.marble_count_slider = Slider(0, 0, slider_width, "Marble Count", 10, 200, 100, "{:.0f}")
        
        self.sliders = [
            self.timer_slider, self.gravity_slider, self.bounce_slider, 
            self.speed_slider, self.emit_rate_slider, self.marble_count_slider
        ]
        
        self.random_shape_cb = Checkbox(0, 0, 20, "Randomize Shape", initial_state=True)
        self.random_color_cb = Checkbox(0, 0, 20, "Randomize Color", initial_state=True)
        self.random_size_cb = Checkbox(0, 0, 20, "Randomize Size", initial_state=True)
        
        self.checkboxes = [self.random_shape_cb, self.random_color_cb, self.random_size_cb]

        self.update_viewport()
        self.layout_ui()
        
        self.default_level_path = DEFAULT_LEVEL_PATH
        self.edited_level_path = LEVELS_DIR / "edited.json"
        self.level_name = "level"
        self.level_walls = []
        self.level_platforms = []
        self.level_conveyors = []
        self.level_emitter = get_default_emitter()
        self.wall_shapes = []
        self.conveyor_shapes = []
        self.platform_templates = [
            {"length": 50, "angular_velocity": 2.0},
            {"length": 50, "angular_velocity": -2.0},
            {"length": 40, "angular_velocity": 3.0},
        ]
        self.platform_template_index = 0

        # Editor state
        self.editor_dragging = False
        self.editor_start = None
        self.editor_end = None

        self.setup_simulation()

    def setup_simulation(self):
        """Initialize or reset the physics simulation."""
        # Pymunk Setup
        self.space = pymunk.Space()
        self.space.gravity = (0, 0)  # Start with no gravity until simulation begins
        self.wall_shapes = []

        self.marbles = []       # List of marble data
        self.finished_rank = []  # List of marble data in order of finish

        # Emitter state
        self.marbles_emitted = 0
        self.emit_accumulator = 0.0  # Accumulates time for emission timing
        self.marble_queue = []  # Pre-generated marble definitions to emit
        self.emit_rate = self.emit_rate_slider.value
        self.marble_count = int(self.marble_count_slider.value)

        # Initial Level Load
        if not self.level_walls:
            if self.initial_level_name:
                # Find index of requested level
                found = False
                for i, path in enumerate(self.level_files):
                    if path.stem == self.initial_level_name:
                        self.current_level_index = i
                        found = True
                        break
                if not found:
                    print(f"Level '{self.initial_level_name}' not found, loading random.")
                    self.current_level_index = random.randint(0, len(self.level_files) - 1)
            else:
                # Random level on startup
                if self.level_files:
                    self.current_level_index = random.randint(0, len(self.level_files) - 1)
            
            self.load_level_by_index(self.current_level_index)
        else:
            self.rebuild_walls()
        
        self.create_rotating_platforms()
        self.create_conveyors()
        self.prepare_marble_queue()

    def load_level_by_index(self, index):
        if not self.level_files:
            return
        self.current_level_index = index % len(self.level_files)
        path = self.level_files[self.current_level_index]
        self.load_level(path)

    def update_viewport(self):
        self.screen_width, self.screen_height = self.screen.get_size()
        
        # Calculate available space for simulation (everything right of sidebar)
        available_width = self.screen_width - self.SIDEBAR_WIDTH
        
        self.scale = min(available_width / WIDTH, self.screen_height / HEIGHT)
        self.scaled_width = int(WIDTH * self.scale)
        self.scaled_height = int(HEIGHT * self.scale)
        
        # Center in the available space to the right
        self.offset_x = self.SIDEBAR_WIDTH + (available_width - self.scaled_width) // 2
        self.offset_y = (self.screen_height - self.scaled_height) // 2
        
        if (self.screen_width, self.screen_height) != self.prev_screen_size:
            self.prev_screen_size = (self.screen_width, self.screen_height)
            self.layout_ui()

    def layout_ui(self):
        # Buttons center relative to the sidebar or available space? 
        # Original was bottom center of screen. Let's put Start/Reset at bottom of sidebar.
        
        sidebar_center = self.SIDEBAR_WIDTH // 2
        
        # Level navigation at top of sidebar
        self.prev_level_btn.rect.topleft = (self.sidebar_padding, 20)
        self.next_level_btn.rect.topright = (self.SIDEBAR_WIDTH - self.sidebar_padding, 20)
        
        # Sliders starting below level nav
        start_y = 100
        gap = 45
        
        for i, slider in enumerate(self.sliders):
            slider.set_position(self.sidebar_padding, start_y + i * gap)
            
        # Checkboxes below sliders
        checkbox_y = start_y + len(self.sliders) * gap + 10
        cb_gap = 25
        for i, cb in enumerate(self.checkboxes):
            cb.set_position(self.sidebar_padding, checkbox_y + i * cb_gap)
            
        # Action buttons at bottom of sidebar
        self.start_button.set_center(sidebar_center, self.screen_height - 60)
        self.reset_button.set_center(sidebar_center, self.screen_height - 60)

    def screen_to_world(self, pos):
        x, y = pos
        x -= self.offset_x
        y -= self.offset_y
        if x < 0 or y < 0 or x > self.scaled_width or y > self.scaled_height:
            return None
        return (x / self.scale, y / self.scale)

    def load_level(self, path):
        level = load_level(path)
        self.level_name = level.get("name", "level")
        self.level_walls = list(level.get("walls", []))
        self.level_platforms = list(level.get("platforms", []))
        self.level_conveyors = list(level.get("conveyors", []))
        self.level_emitter = level.get("emitter", get_default_emitter())
        self.rebuild_walls()

    def create_rotating_platforms(self):
        """Creates rotating platforms to add chaos to the simulation."""
        self.rotating_bodies = []

        for platform in self.level_platforms:
            pos = platform["pos"]
            length = platform["length"]
            angular_vel = platform["angular_velocity"]
            # Create a kinematic body (controlled movement, not affected by forces)
            body = pymunk.Body(body_type=pymunk.Body.KINEMATIC)
            body.position = pos
            body.angular_velocity = angular_vel

            # Create a line segment as the platform
            shape = pymunk.Segment(body, (-length, 0), (length, 0), 4)
            shape.elasticity = 0.8
            shape.friction = 0.5

            self.space.add(body, shape)
            self.rotating_bodies.append((body, shape))

    def create_conveyors(self):
        """Creates conveyor belt segments that move marbles along them."""
        # Remove old conveyor shapes if any
        if self.conveyor_shapes:
            for shape in self.conveyor_shapes:
                self.space.remove(shape)
        self.conveyor_shapes = []

        static_body = self.space.static_body

        for conv in self.level_conveyors:
            start = conv["start"]
            end = conv["end"]
            speed = conv["speed"]

            # Create the conveyor segment
            shape = pymunk.Segment(static_body, start, end, 6)
            shape.elasticity = 0.3
            shape.friction = 1.0  # High friction for conveyor grip

            # Calculate direction vector for surface velocity
            dx = end[0] - start[0]
            dy = end[1] - start[1]
            length = math.hypot(dx, dy)
            if length > 0:
                # Normalize and scale by speed
                dir_x = (dx / length) * speed
                dir_y = (dy / length) * speed
                shape.surface_velocity = (dir_x, dir_y)

            self.space.add(shape)
            self.conveyor_shapes.append(shape)

    def rebuild_walls(self):
        """Rebuilds static wall segments from current level data."""
        static_body = self.space.static_body
        if self.wall_shapes:
            for shape in self.wall_shapes:
                self.space.remove(shape)
        self.wall_shapes = []

        for start, end in self.level_walls:
            shape = pymunk.Segment(static_body, start, end, FUNNEL_WALL_THICKNESS)
            shape.elasticity = 0.5
            shape.friction = 0.5
            shape.color = (200, 200, 200, 255)  # RGBA
            self.space.add(shape)
            self.wall_shapes.append(shape)

    def prepare_marble_queue(self):
        """Prepares marble definitions to be emitted during simulation."""
        count = int(self.marble_count_slider.value)
        self.prepare_marble_queue_with_count(count)

    def prepare_marble_queue_with_count(self, count):
        """Prepares marble definitions with a specific count."""
        
        rand_shape = self.random_shape_cb.checked
        rand_color = self.random_color_cb.checked
        rand_size = self.random_size_cb.checked

        shape_types = [0, 3, 4, 5, 6]
        color_names = ["Red", "Orange", "Gold", "Yellow", "Lime", "Green",
                       "Teal", "Cyan", "Sky", "Blue", "Purple", "Magenta", "Pink"]

        # Determine available pools based on settings
        if rand_shape:
            avail_shapes = shape_types
        else:
            avail_shapes = [0] # Circle only

        if rand_color:
            avail_colors = color_names
        else:
            avail_colors = ["Red"]

        # Generate unique marbles from the available pools
        all_combinations = []
        for color_name in avail_colors:
            for shape_type in avail_shapes:
                shape_name = SHAPE_NAMES[shape_type]
                # Calculate color
                if color_name == "Red" and not rand_color:
                    # Pure Red
                    color = (255, 0, 0)
                else:
                    hue = color_names.index(color_name) / len(color_names)
                    r, g, b = colorsys.hsv_to_rgb(hue, 0.8, 1.0)
                    color = (int(r * 255), int(g * 255), int(b * 255))
                
                all_combinations.append({
                    'color_name': color_name,
                    'shape_type': shape_type,
                    'shape_name': shape_name,
                    'color': color,
                    'base_name': f"{color_name} {shape_name}",
                })

        # Sample or repeat to fill count
        self.marble_queue = []
        
        # If we have enough unique combos, sample them. 
        # If we don't (e.g. fixed shape/color), we loop and add numbers.
        
        for i in range(count):
            # Pick a base combo (round robin or random)
            # Use random choice to keep distribution even but random order
            combo = random.choice(all_combinations)
            
            # Determine Name
            # If we are reusing combos frequently (small pool), add numbers
            # If pool is large enough for unique sample, we could do that, but simple approach:
            # Always number if count > len(all_combinations) OR just number sequentially if pools are small?
            
            # Let's count occurrences of this base name so far? Too slow.
            # Simplified: Just append index + 1 if pool is small.
            if len(all_combinations) < count:
                 name = f"{combo['base_name']} #{i+1}"
            else:
                # We can try to be unique
                # But 'random.choice' allows duplicates. 'random.sample' doesn't.
                # If pool > count, use sample.
                pass 
        
        # Rework selection strategy:
        if len(all_combinations) >= count:
            selected_bases = random.sample(all_combinations, count)
            for combo in selected_bases:
                radius = MARBLE_RADIUS * random.uniform(0.8, 1.2) if rand_size else MARBLE_RADIUS
                self.marble_queue.append({
                    'id': len(self.marble_queue) + 1,
                    'radius': radius,
                    'shape_type': combo['shape_type'],
                    'color': combo['color'],
                    'name': combo['base_name'],
                })
        else:
            # Pool is smaller than count, we must duplicate.
            # Cycle through all combinations to ensure even distribution, then shuffle order.
            base_list = []
            num_full_cycles = count // len(all_combinations)
            remainder = count % len(all_combinations)
            
            for _ in range(num_full_cycles):
                base_list.extend(all_combinations)
            base_list.extend(random.sample(all_combinations, remainder))
            
            random.shuffle(base_list)
            
            # Now assign names with numbers
            # We need to track count per type to number them cleanly? 
            # Or just globally number? "Red Circle #1", "Red Circle #2"
            type_counts = {}
            
            for combo in base_list:
                t_name = combo['base_name']
                type_counts[t_name] = type_counts.get(t_name, 0) + 1
                number = type_counts[t_name]
                
                radius = MARBLE_RADIUS * random.uniform(0.8, 1.2) if rand_size else MARBLE_RADIUS
                
                # If there's only one of this type total, don't add number?
                # But here we know we are likely duplicating.
                # Actually, if we have 100 Red Circles, we definitely need numbers.
                name_suffix = f" #{number}"
                
                self.marble_queue.append({
                    'id': len(self.marble_queue) + 1,
                    'radius': radius,
                    'shape_type': combo['shape_type'],
                    'color': combo['color'],
                    'name': t_name + name_suffix,
                })

    def emit_marble(self):
        """Emit a single marble from the emitter."""
        if not self.marble_queue:
            return False

        emitter = self.level_emitter
        marble_def = self.marble_queue.pop(0)

        # Calculate spawn position within emitter width
        ex, ey = emitter["pos"]
        width = emitter["width"]
        angle_deg = emitter["angle"]
        speed = emitter["speed"]

        # Random position along the emitter width
        offset = random.uniform(-width / 2, width / 2)

        # Perpendicular to emission direction for width spread
        angle_rad = math.radians(angle_deg)
        perp_angle = angle_rad - math.pi / 2

        x = ex + offset * math.cos(perp_angle)
        y = ey + offset * math.sin(perp_angle)

        # Initial velocity in emission direction
        vx = speed * math.cos(angle_rad)
        vy = speed * math.sin(angle_rad)

        radius = marble_def['radius']
        shape_type = marble_def['shape_type']

        mass = 1
        if shape_type == 0:  # Circle
            moment = pymunk.moment_for_circle(mass, 0, radius)
            body = pymunk.Body(mass, moment)
            body.position = (x, y)
            shape = pymunk.Circle(body, radius)
        else:  # Polygon
            vertices = get_polygon_vertices(shape_type, radius)
            moment = pymunk.moment_for_poly(mass, vertices)
            body = pymunk.Body(mass, moment)
            body.position = (x, y)
            shape = pymunk.Poly(body, vertices)

        body.velocity = (vx, vy)
        shape.elasticity = self.bounce_slider.value
        shape.friction = FRICTION

        self.space.add(body, shape)

        self.marbles.append({
            'body': body,
            'shape': shape,
            'color': marble_def['color'],
            'id': marble_def['id'],
            'active': True,
            'shape_type': shape_type,
            'radius': radius,
            'name': marble_def['name'],
        })

        self.marbles_emitted += 1
        return True

    def run(self):
        while True:
            self.update_viewport()
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    return

                if event.type == pygame.KEYDOWN and event.key == pygame.K_e:
                    self.toggle_editor()
                    continue

                # ESC to stop and reset during running state
                if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                    if self.state == "running":
                        self.reset_simulation()
                        continue

                # Handle slider events in ready state
                if self.state == "ready":
                    for slider in self.sliders:
                        slider.handle_event(event)
                    
                    queue_changed = False
                    for cb in self.checkboxes:
                        if cb.handle_event(event):
                            queue_changed = True
                            
                    if queue_changed:
                        # Regenerate queue if any checkbox toggled
                        self.prepare_marble_queue_with_count(int(self.marble_count_slider.value))

                # Handle button clicks
                if self.state == "ready":
                    if self.start_button.is_clicked(event):
                        self.start_simulation()
                    elif self.prev_level_btn.is_clicked(event):
                        self.load_level_by_index(self.current_level_index - 1)
                        self.reset_simulation()
                    elif self.next_level_btn.is_clicked(event):
                        self.load_level_by_index(self.current_level_index + 1)
                        self.reset_simulation()
                
                elif self.state == "finished" and self.reset_button.is_clicked(event):
                    self.reset_simulation()
                elif self.state == "edit":
                    self.handle_editor_event(event)

            world_surface = pygame.Surface((WIDTH, HEIGHT))
            world_surface.fill(BG_COLOR)

            if self.state == "ready":
                self.draw_simulation(world_surface)
            elif self.state == "running":
                self.update_physics()
                self.draw_simulation(world_surface)
            elif self.state == "edit":
                self.draw_editor(world_surface)

            self.screen.fill(BG_COLOR)
            scaled_world = pygame.transform.smoothscale(
                world_surface, (self.scaled_width, self.scaled_height)
            )
            self.screen.blit(scaled_world, (self.offset_x, self.offset_y))

            if self.state == "ready":
                for slider in self.sliders:
                    slider.draw(self.screen)
                for cb in self.checkboxes:
                    cb.draw(self.screen)
                self.start_button.draw(self.screen)
                self.draw_status(self.screen)
                self.draw_level_selection(self.screen)
            elif self.state == "running":
                self.draw_status(self.screen)
            elif self.state == "finished":
                self.draw_results(self.screen)
                self.reset_button.draw(self.screen)
            elif self.state == "edit":
                self.draw_editor_ui(self.screen)

            pygame.display.flip()
            self.clock.tick(FPS)

    def toggle_editor(self):
        if self.state != "edit":
            self.prev_state = self.state
            self.state = "edit"
            self.space.gravity = (0, 0)
            self.start_button.visible = False
            self.reset_button.visible = False
            for slider in self.sliders:
                slider.visible = False
        else:
            self.editor_dragging = False
            self.editor_start = None
            self.editor_end = None
            self.state = "ready"
            for slider in self.sliders:
                slider.visible = True
            self.reset_simulation()

    def start_simulation(self):
        """Start the marble race."""
        self.state = "running"
        # Apply slider settings
        self.space.gravity = (0, self.gravity_slider.value)
        self.sim_speed = self.speed_slider.value
        self.time_limit = self.timer_slider.value
        self.emit_rate = self.emit_rate_slider.value
        self.marble_count = int(self.marble_count_slider.value)
        # Regenerate marble queue with slider count
        self.prepare_marble_queue_with_count(self.marble_count)
        # Apply bounciness to all marbles
        for m in self.marbles:
            m['shape'].elasticity = self.bounce_slider.value
        self.start_button.visible = False
        self.start_time = pygame.time.get_ticks()

    def reset_simulation(self):
        """Reset everything for a new race."""
        self.state = "ready"
        self.start_button.visible = True
        self.reset_button.visible = False
        self.setup_simulation()

    def handle_editor_event(self, event):
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_BACKSPACE:
                if self.level_walls:
                    self.level_walls.pop()
                    self.rebuild_walls()
            elif event.key == pygame.K_c:
                self.level_walls = []
                self.level_platforms = []
                self.rebuild_walls()
            elif event.key == pygame.K_r:
                self.load_level(self.default_level_path)
            elif event.key == pygame.K_s:
                save_level(self.edited_level_path, self.level_walls, self.level_platforms, self.level_emitter, self.level_conveyors, name="edited")
            elif event.key == pygame.K_l:
                if self.edited_level_path.exists():
                    self.load_level(self.edited_level_path)
            elif event.key == pygame.K_LEFTBRACKET:
                self.platform_template_index = (self.platform_template_index - 1) % len(self.platform_templates)
            elif event.key == pygame.K_RIGHTBRACKET:
                self.platform_template_index = (self.platform_template_index + 1) % len(self.platform_templates)

        if event.type == pygame.MOUSEBUTTONDOWN:
            world_pos = self.screen_to_world(event.pos)
            if event.button == 1:
                if world_pos is None:
                    return
                self.editor_dragging = True
                self.editor_start = world_pos
                self.editor_end = world_pos
            elif event.button == 3:
                if world_pos is None:
                    return
                if not self.delete_platform_at(world_pos):
                    self.delete_wall_at(world_pos)

        elif event.type == pygame.MOUSEMOTION and self.editor_dragging:
            world_pos = self.screen_to_world(event.pos)
            if world_pos is not None:
                self.editor_end = world_pos

        elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            if self.editor_dragging and self.editor_start and self.editor_end:
                if self.distance(self.editor_start, self.editor_end) > 4:
                    self.level_walls.append((self.editor_start, self.editor_end))
                    self.rebuild_walls()
                else:
                    self.add_platform_at(self.editor_end)
            self.editor_dragging = False
            self.editor_start = None
            self.editor_end = None

    def delete_wall_at(self, pos):
        if not self.level_walls:
            return
        best_idx = None
        best_dist = 9999
        for idx, (a, b) in enumerate(self.level_walls):
            dist = self.distance_to_segment(pos, a, b)
            if dist < best_dist:
                best_dist = dist
                best_idx = idx
        if best_idx is not None and best_dist <= 12:
            self.level_walls.pop(best_idx)
            self.rebuild_walls()

    def add_platform_at(self, pos):
        template = self.platform_templates[self.platform_template_index]
        self.level_platforms.append({
            "pos": (float(pos[0]), float(pos[1])),
            "length": float(template["length"]),
            "angular_velocity": float(template["angular_velocity"]),
        })

    def delete_platform_at(self, pos):
        if not self.level_platforms:
            return False
        best_idx = None
        best_dist = 9999
        for idx, platform in enumerate(self.level_platforms):
            cx, cy = platform["pos"]
            length = platform["length"]
            a = (cx - length, cy)
            b = (cx + length, cy)
            dist = self.distance_to_segment(pos, a, b)
            if dist < best_dist:
                best_dist = dist
                best_idx = idx
        if best_idx is not None and best_dist <= 12:
            self.level_platforms.pop(best_idx)
            return True
        return False

    def distance(self, a, b):
        return math.hypot(b[0] - a[0], b[1] - a[1])

    def distance_to_segment(self, p, a, b):
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

    def end_with_timeout(self):
        """End simulation due to timeout - remaining marbles tie for last."""
        # Get the last place rank
        last_rank = len(self.finished_rank) + 1

        # Add all remaining active marbles as tied for last
        for m in self.marbles:
            if m['active']:
                m['active'] = False
                m['tied_for_last'] = True
                # Remove from physics space
                self.space.remove(m['body'], m['shape'])
                self.finished_rank.append(m)

        self.state = "finished"
        self.reset_button.visible = True

    def update_physics(self):
        # Step the physics engine using speed from slider
        dt = self.sim_speed / FPS
        self.space.step(dt)

        # Emit marbles from the emitter
        if self.marble_queue:
            self.emit_accumulator += dt
            emit_interval = 1.0 / self.emit_rate
            while self.emit_accumulator >= emit_interval and self.marble_queue:
                self.emit_marble()
                self.emit_accumulator -= emit_interval

        # Check for marbles exiting the bottom
        # We iterate backwards to allow safe removal from the list
        for i in range(len(self.marbles) - 1, -1, -1):
            m = self.marbles[i]
            if m['active']:
                # If marble goes below the screen height (or funnel spout)
                if m['body'].position.y > HEIGHT + MARBLE_RADIUS:
                    m['active'] = False
                    # Remove from physics space
                    self.space.remove(m['body'], m['shape'])
                    # Add to rank list
                    self.finished_rank.append(m)

        # Check elapsed time
        elapsed = (pygame.time.get_ticks() - self.start_time) / 1000.0
        self.time_remaining = max(0, self.time_limit - elapsed)

        # Check if all marbles are done or time is up
        if len(self.finished_rank) == self.marble_count:
            self.state = "finished"
            self.reset_button.visible = True
        elif self.time_remaining <= 0:
            # Time's up - remaining marbles tie for last
            self.end_with_timeout()

    def draw_emitter(self, surface):
        """Draw the emitter/entry pipe."""
        emitter = self.level_emitter
        ex, ey = emitter["pos"]
        width = emitter["width"]
        angle_deg = emitter["angle"]

        angle_rad = math.radians(angle_deg)
        perp_angle = angle_rad - math.pi / 2

        # Calculate pipe endpoints
        half_width = width / 2
        pipe_length = 30  # Visual length of the pipe

        # Left and right edges of the pipe opening
        left_x = ex + half_width * math.cos(perp_angle)
        left_y = ey + half_width * math.sin(perp_angle)
        right_x = ex - half_width * math.cos(perp_angle)
        right_y = ey - half_width * math.sin(perp_angle)

        # Back of pipe (opposite direction of emission)
        back_dx = -pipe_length * math.cos(angle_rad)
        back_dy = -pipe_length * math.sin(angle_rad)

        # Draw pipe as a polygon
        pipe_color = (100, 120, 180)
        points = [
            (left_x, left_y),
            (right_x, right_y),
            (right_x + back_dx, right_y + back_dy),
            (left_x + back_dx, left_y + back_dy),
        ]
        pygame.draw.polygon(surface, pipe_color, points)
        pygame.draw.polygon(surface, (150, 170, 220), points, 2)

        # Draw emission direction indicator
        arrow_len = 15
        arrow_x = ex + arrow_len * math.cos(angle_rad)
        arrow_y = ey + arrow_len * math.sin(angle_rad)
        pygame.draw.line(surface, (200, 220, 255), (ex, ey), (arrow_x, arrow_y), 2)

    def draw_conveyors(self, surface):
        """Draw conveyor belts with direction indicators."""
        for conv in self.level_conveyors:
            start = conv["start"]
            end = conv["end"]
            speed = conv["speed"]

            # Draw the conveyor belt (thicker, different color)
            color = (80, 180, 80) if speed >= 0 else (180, 80, 80)
            pygame.draw.line(surface, color, start, end, 12)
            pygame.draw.line(surface, (60, 60, 60), start, end, 8)

            # Draw direction arrows along the belt
            dx = end[0] - start[0]
            dy = end[1] - start[1]
            length = math.hypot(dx, dy)
            if length > 0:
                # Normalize direction
                dir_x = dx / length
                dir_y = dy / length
                # Flip direction if speed is negative
                if speed < 0:
                    dir_x, dir_y = -dir_x, -dir_y

                # Draw arrows at intervals
                num_arrows = max(1, int(length / 30))
                for i in range(num_arrows):
                    t = (i + 0.5) / num_arrows
                    ax = start[0] + dx * t
                    ay = start[1] + dy * t

                    # Arrow head points
                    arrow_size = 6
                    perp_x, perp_y = -dir_y, dir_x  # perpendicular
                    tip_x = ax + dir_x * arrow_size
                    tip_y = ay + dir_y * arrow_size
                    left_x = ax - perp_x * arrow_size * 0.5
                    left_y = ay - perp_y * arrow_size * 0.5
                    right_x = ax + perp_x * arrow_size * 0.5
                    right_y = ay + perp_y * arrow_size * 0.5

                    pygame.draw.polygon(surface, (200, 255, 200),
                                       [(tip_x, tip_y), (left_x, left_y), (right_x, right_y)])

    def draw_simulation(self, surface):
        # Draw Funnel Lines (Pymunk debug draw handles this, but let's make it cleaner)
        # We manually draw marbles to control their colors

        # 0. Draw Emitter
        self.draw_emitter(surface)

        # 0.5. Draw Conveyors
        self.draw_conveyors(surface)

        # 1. Draw Funnel (Static shapes) - skip conveyor shapes
        for shape in self.space.shapes:
            if isinstance(shape, pymunk.Segment) and shape not in self.conveyor_shapes:
                p1 = shape.a
                p2 = shape.b
                # Transform local to world if needed (static body usually identity)
                p1_world = shape.body.local_to_world(p1)
                p2_world = shape.body.local_to_world(p2)
                pygame.draw.line(
                    surface, FUNNEL_COLOR, p1_world, p2_world,
                    int(shape.radius * 2)
                )

        # 2. Draw Marbles
        for m in self.marbles:
            if m['active']:
                pos = m['body'].position
                if m['shape_type'] == 0:  # Circle
                    pygame.draw.circle(
                        surface, m['color'],
                        (int(pos.x), int(pos.y)), int(m['radius'])
                    )
                    pygame.draw.circle(
                        surface, (0, 0, 0),
                        (int(pos.x), int(pos.y)), int(m['radius']), 1
                    )
                else:  # Polygon
                    # Get world coordinates of vertices
                    vertices = [m['body'].local_to_world(v) for v in m['shape'].get_vertices()]
                    points = [(int(v.x), int(v.y)) for v in vertices]
                    pygame.draw.polygon(surface, m['color'], points)
                    pygame.draw.polygon(surface, (0, 0, 0), points, 1)

    def draw_status(self, surface):
        total_count = getattr(self, 'marble_count', int(self.marble_count_slider.value))
        status_text = f"Emitted: {self.marbles_emitted}/{total_count}  Finished: {len(self.finished_rank)}/{total_count}"
        surf = self.font.render(status_text, True, TEXT_COLOR)
        # Position at (offset_x + 10, 10) to be in top-left of game area
        surface.blit(surf, (self.offset_x + 10, 10))

        if self.state == "running":
            minutes = int(self.time_remaining // 60)
            seconds = int(self.time_remaining % 60)
            timer_color = (255, 100, 100) if self.time_remaining < 10 else TEXT_COLOR
            timer_text = f"Time: {minutes}:{seconds:02d}"
            timer_surf = self.font.render(timer_text, True, timer_color)
            surface.blit(timer_surf, (self.screen_width - 120, 10))

    def draw_results(self, surface):
        # Display the ranked order
        title = self.font.render("SIMULATION COMPLETE - RANK ORDER", True, TEXT_COLOR)
        surface.blit(title, (self.screen_width // 2 - title.get_width() // 2, 20))

        total = len(self.finished_rank)
        if total == 0:
            return

        # Calculate optimal grid layout based on count and screen size
        available_width = self.screen_width - 40  # smaller margins to use more space
        available_height = self.screen_height - 120  # title + button area

        # Calculate optimal columns to fill horizontal space
        # Aim for entries around 120-140px wide
        target_entry_width = 130
        best_cols = max(4, available_width // target_entry_width)
        best_cols = min(best_cols, 12)  # cap at 12 columns

        # Calculate rows needed
        rows = (total + best_cols - 1) // best_cols

        # Calculate actual spacing
        best_padding_x = available_width // best_cols
        best_padding_y = min(32, available_height // max(rows, 1))
        best_padding_y = max(20, best_padding_y)  # minimum row height

        # Font size: minimum 9, scale with row height
        best_font_size = max(9, min(12, best_padding_y // 2 - 2))

        start_x = 30
        start_y = 60
        small_font = pygame.font.SysFont("Arial", best_font_size)
        display_scale = best_padding_y / 35  # scale marble display size

        for i, m in enumerate(self.finished_rank):
            row = i // best_cols
            col = i % best_cols

            x = start_x + col * best_padding_x
            y = start_y + row * best_padding_y

            # Draw the marble (scaled based on layout)
            display_radius = m['radius'] * 1.2 * display_scale
            display_radius = max(3, min(display_radius, 10))  # clamp size
            if m['shape_type'] == 0:  # Circle
                pygame.draw.circle(surface, m['color'], (x, y), int(display_radius))
            else:  # Polygon
                vertices = get_polygon_vertices(m['shape_type'], display_radius)
                points = [(int(x + vx), int(y + vy)) for vx, vy in vertices]
                pygame.draw.polygon(surface, m['color'], points)

            # Draw the Rank # and name
            if m.get('tied_for_last'):
                rank_text = small_font.render(f"DNF {m['name']}", True, (255, 100, 100))
            else:
                rank_text = small_font.render(f"#{i+1} {m['name']}", True, (200, 200, 200))
            surface.blit(rank_text, (x + int(display_radius) + 4, y - best_font_size // 2))

    def draw_level_selection(self, surface):
        """Draw level selection UI."""
        self.prev_level_btn.draw(surface)
        self.next_level_btn.draw(surface)
        
        # Draw level name centered in sidebar
        level_text = f"Level: {self.level_name}"
        text_surf = self.font.render(level_text, True, TEXT_COLOR)
        
        center_x = self.SIDEBAR_WIDTH // 2
        text_rect = text_surf.get_rect(center=(center_x, 35))
        surface.blit(text_surf, text_rect)

    def draw_editor(self, surface):
        # Draw emitter
        self.draw_emitter(surface)

        # Draw conveyors
        self.draw_conveyors(surface)

        # Draw existing walls
        for start, end in self.level_walls:
            pygame.draw.line(
                surface, FUNNEL_COLOR, start, end, FUNNEL_WALL_THICKNESS * 2
            )

        # Draw platforms
        for platform in self.level_platforms:
            cx, cy = platform["pos"]
            length = platform["length"]
            a = (cx - length, cy)
            b = (cx + length, cy)
            pygame.draw.line(surface, (180, 220, 140), a, b, 6)

        # Draw preview segment
        if self.editor_dragging and self.editor_start and self.editor_end:
            pygame.draw.line(
                surface, (120, 200, 255), self.editor_start, self.editor_end, 2
            )

    def draw_editor_ui(self, surface):
        template = self.platform_templates[self.platform_template_index]
        template_label = f"Platform [{self.platform_template_index + 1}/{len(self.platform_templates)}] len={int(template['length'])} av={template['angular_velocity']:.1f}"

        # Editor UI
        lines = [
            "EDITOR MODE (E to exit)",
            "Left drag: add wall",
            "Left click: add platform",
            "Right click: delete platform/wall",
            "Backspace: undo last",
            "C: clear all  R: reset default",
            "S: save edited  L: load edited",
            "[ / ]: cycle platform type",
            template_label,
        ]
        for i, text in enumerate(lines):
            surf = self.font.render(text, True, (220, 220, 220))
            surface.blit(surf, (10, 10 + i * 18))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Marble Race Simulation")
    parser.add_argument("--level", type=str, help="Name of the level to load (without .json)")
    args = parser.parse_args()

    sim = MarbleSimulation(initial_level=args.level)
    sim.run()
