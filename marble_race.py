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


class MarbleSimulation:
    def __init__(self):
        pygame.init()
        self.screen = pygame.display.set_mode((WIDTH, HEIGHT))
        pygame.display.set_caption("Marble Funnel Simulation")
        self.clock = pygame.time.Clock()
        self.font = pygame.font.SysFont("Arial", 16)

        # Pymunk Setup
        self.space = pymunk.Space()
        self.space.gravity = (0, GRAVITY)
        self.draw_options = pymunk.pygame_util.DrawOptions(self.screen)

        # Disable default Pymunk debug colors so we can use our own
        self.draw_options.flags = pymunk.pygame_util.DrawOptions.DRAW_SHAPES

        self.marbles = []       # List of (body, shape, color, id)
        self.finished_rank = []  # List of marble data in order of finish
        self.simulation_over = False

        self.create_funnel()
        self.spawn_marbles()

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

            self.screen.fill(BG_COLOR)

            if not self.simulation_over:
                self.update_physics()
                self.draw_simulation()
            else:
                self.draw_results()

            pygame.display.flip()
            self.clock.tick(FPS)

    def update_physics(self):
        # Step the physics engine
        dt = 1.0 / FPS
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

        # Check if all marbles are done
        if len(self.finished_rank) == MARBLE_COUNT:
            self.simulation_over = True

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
            rank_text = small_font.render(f"#{i+1} {m['name']}", True, (200, 200, 200))
            self.screen.blit(rank_text, (x + 12, y - 6))


if __name__ == "__main__":
    sim = MarbleSimulation()
    sim.run()
