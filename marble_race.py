import pygame
import pymunk
import pymunk.pygame_util
import random
import colorsys
import math

# --- Configuration ---
WIDTH, HEIGHT = 800, 800
FPS = 60
MARBLE_COUNT = 100
MARBLE_RADIUS = 6
FUNNEL_WALL_THICKNESS = 5

# Physics Constants
GRAVITY = 600.0
ELASTICITY = 1.1  # Bounciness (values > 1 are super bouncy)
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
        self.screen = pygame.display.set_mode((WIDTH, HEIGHT))
        pygame.display.set_caption("Marble Funnel Simulation")
        self.clock = pygame.time.Clock()
        self.font = pygame.font.SysFont("Arial", 16)

        # Simulation state: "ready", "running", "finished"
        self.state = "ready"

        # UI Buttons
        self.start_button = Button(WIDTH // 2 - 60, HEIGHT - 60, 120, 40, "Start")
        self.reset_button = Button(WIDTH // 2 - 60, HEIGHT - 60, 120, 40, "Reset")
        self.reset_button.visible = False

        # Settings sliders (positioned at bottom left)
        slider_x = 20
        slider_width = 150
        self.timer_slider = Slider(slider_x, HEIGHT - 180, slider_width,
                                   "Timer (sec)", 10, 120, 60, "{:.0f}")
        self.gravity_slider = Slider(slider_x, HEIGHT - 140, slider_width,
                                     "Gravity", 200, 1200, GRAVITY, "{:.0f}")
        self.bounce_slider = Slider(slider_x, HEIGHT - 100, slider_width,
                                    "Bounciness", 0.5, 2.0, ELASTICITY, "{:.2f}")
        self.speed_slider = Slider(slider_x + slider_width + 40, HEIGHT - 180, slider_width,
                                   "Speed", 0.25, 1.5, 0.75, "{:.2f}")

        self.sliders = [self.timer_slider, self.gravity_slider,
                        self.bounce_slider, self.speed_slider]

        self.setup_simulation()

    def setup_simulation(self):
        """Initialize or reset the physics simulation."""
        # Pymunk Setup
        self.space = pymunk.Space()
        self.space.gravity = (0, 0)  # Start with no gravity until simulation begins

        self.marbles = []       # List of marble data
        self.finished_rank = []  # List of marble data in order of finish

        self.create_funnel()
        self.create_rotating_platforms()
        self.spawn_marbles()

    def create_rotating_platforms(self):
        """Creates rotating platforms to add chaos to the simulation."""
        center_x = WIDTH // 2

        # Platform configurations: (x_offset, y_position, length, angular_velocity)
        platforms = [
            (-120, 350, 50, 2.0),   # Left platform, spins clockwise
            (120, 350, 50, -2.0),   # Right platform, spins counter-clockwise
            (0, 420, 40, 3.0),      # Center platform, spins faster
        ]

        self.rotating_bodies = []

        for x_offset, y_pos, length, angular_vel in platforms:
            # Create a kinematic body (controlled movement, not affected by forces)
            body = pymunk.Body(body_type=pymunk.Body.KINEMATIC)
            body.position = (center_x + x_offset, y_pos)
            body.angular_velocity = angular_vel

            # Create a line segment as the platform
            shape = pymunk.Segment(body, (-length, 0), (length, 0), 4)
            shape.elasticity = 0.8
            shape.friction = 0.5

            self.space.add(body, shape)
            self.rotating_bodies.append((body, shape))

    def create_funnel(self):
        """Creates the static lines that form the funnel."""
        static_body = self.space.static_body

        # Funnel coordinates
        center_x = WIDTH // 2
        funnel_top_y = 200
        funnel_neck_y = 500
        spout_bottom_y = 700
        neck_width = 30  # Narrow opening
        top_width = 350
        platform_width = 60  # Small platform at top center

        # Define line segments
        guard_height = 250  # Height of vertical guards above funnel top
        walls = [
            # Left diagonal wall
            [(-top_width, funnel_top_y), (-neck_width, funnel_neck_y)],
            # Right diagonal wall
            [(top_width, funnel_top_y), (neck_width, funnel_neck_y)],
            # Left spout wall
            [(-neck_width, funnel_neck_y), (-neck_width, spout_bottom_y)],
            # Right spout wall
            [(neck_width, funnel_neck_y), (neck_width, spout_bottom_y)],
            # Convex curved platform at top center (marbles roll off sides)
            [(-platform_width, funnel_top_y + 40), (-platform_width // 2, funnel_top_y + 15)],
            [(-platform_width // 2, funnel_top_y + 15), (0, funnel_top_y)],
            [(0, funnel_top_y), (platform_width // 2, funnel_top_y + 15)],
            [(platform_width // 2, funnel_top_y + 15), (platform_width, funnel_top_y + 40)],
            # Vertical guards at funnel edges to keep marbles in
            [(-top_width, funnel_top_y - guard_height), (-top_width, funnel_top_y)],
            [(top_width, funnel_top_y - guard_height), (top_width, funnel_top_y)],
        ]

        for p1, p2 in walls:
            # Adjust coordinates relative to center_x
            start = (center_x + p1[0], p1[1])
            end = (center_x + p2[0], p2[1])

            shape = pymunk.Segment(static_body, start, end, FUNNEL_WALL_THICKNESS)
            shape.elasticity = 0.5
            shape.friction = 0.5
            shape.color = (200, 200, 200, 255)  # RGBA
            self.space.add(shape)

    def spawn_marbles(self):
        """Creates 100 marbles in a grid pattern above the center platform."""
        # Spawn centered above the platform (platform is 120px wide at center)
        start_x = WIDTH // 2 - 70  # Narrower spawn area
        start_y = 50
        cols = 10
        spacing = MARBLE_RADIUS * 2 + 2

        # Shape types: 0=circle, 3=triangle, 4=square, 5=pentagon, 6=hexagon
        shape_types = [0, 3, 4, 5, 6]

        for i in range(MARBLE_COUNT):
            row = i // cols
            col = i % cols

            x = start_x + (col * spacing) + random.uniform(-5, 5)  # Slight jitter
            y = start_y + (row * spacing)

            # Randomly vary the radius slightly (80% to 120% of base)
            radius = MARBLE_RADIUS * random.uniform(0.8, 1.2)
            shape_type = random.choice(shape_types)

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

            shape.elasticity = ELASTICITY
            shape.friction = FRICTION

            hue = i / MARBLE_COUNT
            color = get_rainbow_color(i, MARBLE_COUNT)
            color_name = get_color_name(hue)
            shape_name = SHAPE_NAMES[shape_type]
            name = f"{color_name} {shape_name}"

            self.space.add(body, shape)

            # Store metadata
            self.marbles.append({
                'body': body,
                'shape': shape,
                'color': color,
                'id': i + 1,
                'active': True,
                'shape_type': shape_type,
                'radius': radius,
                'name': name
            })

    def run(self):
        while True:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    return

                # Handle slider events in ready state
                if self.state == "ready":
                    for slider in self.sliders:
                        slider.handle_event(event)

                # Handle button clicks
                if self.state == "ready" and self.start_button.is_clicked(event):
                    self.start_simulation()
                elif self.state == "finished" and self.reset_button.is_clicked(event):
                    self.reset_simulation()

            self.screen.fill(BG_COLOR)

            if self.state == "ready":
                self.draw_simulation()
                # Draw sliders
                for slider in self.sliders:
                    slider.draw(self.screen)
                self.start_button.draw(self.screen)
            elif self.state == "running":
                self.update_physics()
                self.draw_simulation()
            elif self.state == "finished":
                self.draw_results()
                self.reset_button.draw(self.screen)

            pygame.display.flip()
            self.clock.tick(FPS)

    def start_simulation(self):
        """Start the marble race."""
        self.state = "running"
        # Apply slider settings
        self.space.gravity = (0, self.gravity_slider.value)
        self.sim_speed = self.speed_slider.value
        self.time_limit = self.timer_slider.value
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
        if len(self.finished_rank) == MARBLE_COUNT:
            self.state = "finished"
            self.reset_button.visible = True
        elif self.time_remaining <= 0:
            # Time's up - remaining marbles tie for last
            self.end_with_timeout()

    def draw_simulation(self):
        # Draw Funnel Lines (Pymunk debug draw handles this, but let's make it cleaner)
        # We manually draw marbles to control their colors

        # 1. Draw Funnel (Static shapes)
        for shape in self.space.shapes:
            if isinstance(shape, pymunk.Segment):
                p1 = shape.a
                p2 = shape.b
                # Transform local to world if needed (static body usually identity)
                p1_world = shape.body.local_to_world(p1)
                p2_world = shape.body.local_to_world(p2)
                pygame.draw.line(
                    self.screen, FUNNEL_COLOR, p1_world, p2_world,
                    int(shape.radius * 2)
                )

        # 2. Draw Marbles
        for m in self.marbles:
            if m['active']:
                pos = m['body'].position
                if m['shape_type'] == 0:  # Circle
                    pygame.draw.circle(
                        self.screen, m['color'],
                        (int(pos.x), int(pos.y)), int(m['radius'])
                    )
                    pygame.draw.circle(
                        self.screen, (0, 0, 0),
                        (int(pos.x), int(pos.y)), int(m['radius']), 1
                    )
                else:  # Polygon
                    # Get world coordinates of vertices
                    vertices = [m['body'].local_to_world(v) for v in m['shape'].get_vertices()]
                    points = [(int(v.x), int(v.y)) for v in vertices]
                    pygame.draw.polygon(self.screen, m['color'], points)
                    pygame.draw.polygon(self.screen, (0, 0, 0), points, 1)

        # 3. Draw UI
        status_text = f"Finished: {len(self.finished_rank)} / {MARBLE_COUNT}"
        surf = self.font.render(status_text, True, TEXT_COLOR)
        self.screen.blit(surf, (10, 10))

        # Draw timer if simulation is running
        if self.state == "running":
            minutes = int(self.time_remaining // 60)
            seconds = int(self.time_remaining % 60)
            timer_color = (255, 100, 100) if self.time_remaining < 10 else TEXT_COLOR
            timer_text = f"Time: {minutes}:{seconds:02d}"
            timer_surf = self.font.render(timer_text, True, timer_color)
            self.screen.blit(timer_surf, (WIDTH - 100, 10))

    def draw_results(self):
        # Display the ranked order
        title = self.font.render("SIMULATION COMPLETE - RANK ORDER", True, TEXT_COLOR)
        self.screen.blit(title, (WIDTH // 2 - title.get_width() // 2, 20))

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
                pygame.draw.circle(self.screen, m['color'], (x, y), int(display_radius))
            else:  # Polygon
                vertices = get_polygon_vertices(m['shape_type'], display_radius)
                points = [(int(x + vx), int(y + vy)) for vx, vy in vertices]
                pygame.draw.polygon(self.screen, m['color'], points)

            # Draw the Rank # and name
            if m.get('tied_for_last'):
                rank_text = small_font.render(f"TIED {m['name']}", True, (255, 100, 100))
            else:
                rank_text = small_font.render(f"#{i+1} {m['name']}", True, (200, 200, 200))
            self.screen.blit(rank_text, (x + 12, y - 6))


if __name__ == "__main__":
    sim = MarbleSimulation()
    sim.run()
