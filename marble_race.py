import pygame
import pymunk
import pymunk.pygame_util
import random
import colorsys
import math
from level_io import load_level, save_level, get_default_emitter, DEFAULT_LEVEL_PATH, LEVELS_DIR

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


class MarbleSimulation:
    def __init__(self):
        pygame.init()
        self.screen = pygame.display.set_mode((WIDTH, HEIGHT), pygame.FULLSCREEN)
        pygame.display.set_caption("Marble Funnel Simulation")
        self.clock = pygame.time.Clock()
        self.font = pygame.font.SysFont("Arial", 16)
        self.screen_width, self.screen_height = self.screen.get_size()
        self.prev_screen_size = (self.screen_width, self.screen_height)

        # Simulation state: "ready", "running", "finished"
        self.state = "ready"
        self.prev_state = None

        # UI Buttons
        self.start_button = Button(0, 0, 120, 40, "Start")
        self.reset_button = Button(0, 0, 120, 40, "Reset")
        self.reset_button.visible = False

        # Settings sliders (positioned at bottom left)
        slider_x = 20
        slider_width = 150
        col2_x = slider_x + slider_width + 40
        self.timer_slider = Slider(slider_x, HEIGHT - 180, slider_width,
                                   "Timer (sec)", 1, 60, 30, "{:.0f}")
        self.gravity_slider = Slider(slider_x, HEIGHT - 140, slider_width,
                                     "Gravity", 0, 1000, GRAVITY, "{:.0f}")
        self.bounce_slider = Slider(slider_x, HEIGHT - 100, slider_width,
                                    "Bounciness", 0.5, 2.0, ELASTICITY, "{:.2f}")
        self.speed_slider = Slider(col2_x, HEIGHT - 180, slider_width,
                                   "Speed", 0.25, 1.5, 0.75, "{:.2f}")
        self.emit_rate_slider = Slider(col2_x, HEIGHT - 140, slider_width,
                                       "Emit Rate", 1, 50, 20, "{:.0f}")
        self.marble_count_slider = Slider(col2_x, HEIGHT - 100, slider_width,
                                          "Marble Count", 10, 200, 100, "{:.0f}")

        self.sliders = [self.timer_slider, self.gravity_slider,
                        self.bounce_slider, self.speed_slider,
                        self.emit_rate_slider, self.marble_count_slider]

        self.update_viewport()
        self.layout_ui()

        self.default_level_path = DEFAULT_LEVEL_PATH
        self.edited_level_path = LEVELS_DIR / "edited.json"
        self.level_name = "level"
        self.level_walls = []
        self.level_platforms = []
        self.level_emitter = get_default_emitter()
        self.wall_shapes = []
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

        if not self.level_walls:
            self.load_level(self.default_level_path)
        else:
            self.rebuild_walls()
        self.create_rotating_platforms()
        self.prepare_marble_queue()

    def update_viewport(self):
        self.screen_width, self.screen_height = self.screen.get_size()
        self.scale = min(self.screen_width / WIDTH, self.screen_height / HEIGHT)
        self.scaled_width = int(WIDTH * self.scale)
        self.scaled_height = int(HEIGHT * self.scale)
        self.offset_x = (self.screen_width - self.scaled_width) // 2
        self.offset_y = (self.screen_height - self.scaled_height) // 2
        if (self.screen_width, self.screen_height) != self.prev_screen_size:
            self.prev_screen_size = (self.screen_width, self.screen_height)
            self.layout_ui()

    def layout_ui(self):
        self.start_button.set_center(self.screen_width // 2, self.screen_height - 40)
        self.reset_button.set_center(self.screen_width // 2, self.screen_height - 40)

        slider_x = 20
        slider_width = self.timer_slider.width
        base_y = self.screen_height - 180
        self.timer_slider.set_position(slider_x, base_y)
        self.gravity_slider.set_position(slider_x, base_y + 40)
        self.bounce_slider.set_position(slider_x, base_y + 80)
        self.speed_slider.set_position(slider_x + slider_width + 40, base_y)

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
        shape_types = [0, 3, 4, 5, 6]

        self.marble_queue = []
        for i in range(count):
            radius = MARBLE_RADIUS * random.uniform(0.8, 1.2)
            shape_type = random.choice(shape_types)
            hue = i / count
            color = get_rainbow_color(i, count)
            color_name = get_color_name(hue)
            shape_name = SHAPE_NAMES[shape_type]
            name = f"{color_name} {shape_name}"

            self.marble_queue.append({
                'id': i + 1,
                'radius': radius,
                'shape_type': shape_type,
                'color': color,
                'name': name,
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

                # Handle button clicks
                if self.state == "ready" and self.start_button.is_clicked(event):
                    self.start_simulation()
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
                self.start_button.draw(self.screen)
                self.draw_status(self.screen)
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
                save_level(self.edited_level_path, self.level_walls, self.level_platforms, self.level_emitter, name="edited")
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

    def draw_simulation(self, surface):
        # Draw Funnel Lines (Pymunk debug draw handles this, but let's make it cleaner)
        # We manually draw marbles to control their colors

        # 0. Draw Emitter
        self.draw_emitter(surface)

        # 1. Draw Funnel (Static shapes)
        for shape in self.space.shapes:
            if isinstance(shape, pymunk.Segment):
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
        surface.blit(surf, (10, 10))

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

        # Grid settings for displaying results
        start_x = 30
        start_y = 60
        cols = 5
        padding_x = 155
        padding_y = 35

        small_font = pygame.font.SysFont("Arial", 12)

        for i, m in enumerate(self.finished_rank):
            row = i // cols
            col = i % cols

            x = start_x + col * padding_x
            y = start_y + row * padding_y

            # Draw the marble (scaled up for display)
            display_radius = m['radius'] * 1.2
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
            surface.blit(rank_text, (x + 12, y - 6))

    def draw_editor(self, surface):
        # Draw emitter
        self.draw_emitter(surface)

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
    sim = MarbleSimulation()
    sim.run()
