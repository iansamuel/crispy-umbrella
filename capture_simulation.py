"""Capture key frames from the marble simulation."""
import pygame
import pymunk
import pymunk.pygame_util
import random
import colorsys
import os

# --- Configuration ---
WIDTH, HEIGHT = 800, 800
FPS = 60
MARBLE_COUNT = 100
MARBLE_RADIUS = 6
FUNNEL_WALL_THICKNESS = 5

# Physics Constants
GRAVITY = 900.0
ELASTICITY = 0.5
FRICTION = 0.3

# Colors
BG_COLOR = (20, 20, 30)
FUNNEL_COLOR = (200, 200, 200)
TEXT_COLOR = (255, 255, 255)

# Output directory
OUTPUT_DIR = "/home/user/crispy-umbrella/frames"


def get_rainbow_color(index, total):
    """Generates a unique color for each marble based on its index."""
    hue = index / total
    r, g, b = colorsys.hsv_to_rgb(hue, 0.8, 1.0)
    return int(r * 255), int(g * 255), int(b * 255)


class MarbleSimulation:
    def __init__(self):
        pygame.init()
        self.screen = pygame.display.set_mode((WIDTH, HEIGHT))
        pygame.display.set_caption("Marble Funnel Simulation")
        self.clock = pygame.time.Clock()
        self.font = pygame.font.SysFont("Arial", 16)
        self.large_font = pygame.font.SysFont("Arial", 24, bold=True)

        # Pymunk Setup
        self.space = pymunk.Space()
        self.space.gravity = (0, GRAVITY)

        self.marbles = []
        self.finished_rank = []
        self.simulation_over = False
        self.frame_count = 0
        self.captured_frames = set()

        os.makedirs(OUTPUT_DIR, exist_ok=True)

        self.create_funnel()
        self.spawn_marbles()

    def create_funnel(self):
        """Creates the static lines that form the funnel."""
        static_body = self.space.static_body

        center_x = WIDTH // 2
        funnel_top_y = 200
        funnel_neck_y = 500
        spout_bottom_y = 700
        neck_width = 30
        top_width = 350

        walls = [
            [(-top_width, funnel_top_y), (-neck_width, funnel_neck_y)],
            [(top_width, funnel_top_y), (neck_width, funnel_neck_y)],
            [(-neck_width, funnel_neck_y), (-neck_width, spout_bottom_y)],
            [(neck_width, funnel_neck_y), (neck_width, spout_bottom_y)],
        ]

        for p1, p2 in walls:
            start = (center_x + p1[0], p1[1])
            end = (center_x + p2[0], p2[1])

            shape = pymunk.Segment(static_body, start, end, FUNNEL_WALL_THICKNESS)
            shape.elasticity = 0.5
            shape.friction = 0.5
            self.space.add(shape)

    def spawn_marbles(self):
        """Creates 100 marbles in a grid pattern above the funnel."""
        random.seed(42)  # Fixed seed for reproducibility
        start_x = WIDTH // 2 - 200
        start_y = 50
        cols = 10
        spacing = MARBLE_RADIUS * 2 + 2

        for i in range(MARBLE_COUNT):
            row = i // cols
            col = i % cols

            x = start_x + (col * spacing) + random.uniform(-5, 5)
            y = start_y + (row * spacing)

            mass = 1
            moment = pymunk.moment_for_circle(mass, 0, MARBLE_RADIUS)
            body = pymunk.Body(mass, moment)
            body.position = (x, y)

            shape = pymunk.Circle(body, MARBLE_RADIUS)
            shape.elasticity = ELASTICITY
            shape.friction = FRICTION

            color = get_rainbow_color(i, MARBLE_COUNT)

            self.space.add(body, shape)

            self.marbles.append({
                'body': body,
                'shape': shape,
                'color': color,
                'id': i + 1,
                'active': True
            })

    def save_frame(self, name):
        """Save current screen to a file."""
        filepath = os.path.join(OUTPUT_DIR, f"{name}.png")
        pygame.image.save(self.screen, filepath)
        print(f"Saved: {filepath}")

    def run(self, max_frames=3000):
        # Capture milestones
        capture_points = {
            'start': 0,
            'falling': 30,
            'funnel_entry': 90,
            'bouncing': 180,
            'congestion': 300,
            'midway': None,  # When 50 marbles finish
            'nearly_done': None,  # When 90 marbles finish
        }

        while self.frame_count < max_frames:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    return

            self.screen.fill(BG_COLOR)

            if not self.simulation_over:
                self.update_physics()
                self.draw_simulation()

                # Capture at specific frame counts
                for name, frame in capture_points.items():
                    if frame == self.frame_count and name not in self.captured_frames:
                        self.save_frame(f"{self.frame_count:04d}_{name}")
                        self.captured_frames.add(name)

                # Capture at milestone completions
                finished = len(self.finished_rank)
                if finished == 50 and 'midway' not in self.captured_frames:
                    self.save_frame(f"{self.frame_count:04d}_midway_50_done")
                    self.captured_frames.add('midway')
                elif finished == 90 and 'nearly_done' not in self.captured_frames:
                    self.save_frame(f"{self.frame_count:04d}_nearly_done_90")
                    self.captured_frames.add('nearly_done')

            else:
                self.draw_results()
                if 'final' not in self.captured_frames:
                    self.save_frame(f"{self.frame_count:04d}_final_results")
                    self.captured_frames.add('final')
                    print("Simulation complete!")
                    pygame.quit()
                    return

            pygame.display.flip()
            self.clock.tick(FPS)
            self.frame_count += 1

    def update_physics(self):
        dt = 1.0 / FPS
        self.space.step(dt)

        for i in range(len(self.marbles) - 1, -1, -1):
            m = self.marbles[i]
            if m['active']:
                if m['body'].position.y > HEIGHT + MARBLE_RADIUS:
                    m['active'] = False
                    self.space.remove(m['body'], m['shape'])
                    self.finished_rank.append(m)

        if len(self.finished_rank) == MARBLE_COUNT:
            self.simulation_over = True

    def draw_simulation(self):
        # Draw Funnel
        for shape in self.space.shapes:
            if isinstance(shape, pymunk.Segment):
                p1_world = shape.body.local_to_world(shape.a)
                p2_world = shape.body.local_to_world(shape.b)
                pygame.draw.line(
                    self.screen, FUNNEL_COLOR, p1_world, p2_world,
                    int(shape.radius * 2)
                )

        # Draw Marbles
        for m in self.marbles:
            if m['active']:
                pos = m['body'].position
                pygame.draw.circle(
                    self.screen, m['color'],
                    (int(pos.x), int(pos.y)), MARBLE_RADIUS
                )
                pygame.draw.circle(
                    self.screen, (0, 0, 0),
                    (int(pos.x), int(pos.y)), MARBLE_RADIUS, 1
                )

        # Draw UI
        status_text = f"Finished: {len(self.finished_rank)} / {MARBLE_COUNT}"
        surf = self.font.render(status_text, True, TEXT_COLOR)
        self.screen.blit(surf, (10, 10))

        # Frame counter
        frame_text = self.font.render(f"Frame: {self.frame_count}", True, (100, 100, 100))
        self.screen.blit(frame_text, (10, 30))

    def draw_results(self):
        title = self.large_font.render("SIMULATION COMPLETE - RANK ORDER", True, TEXT_COLOR)
        self.screen.blit(title, (WIDTH // 2 - title.get_width() // 2, 30))

        start_x = 50
        start_y = 80
        cols = 10
        padding_x = 70
        padding_y = 50

        for i, m in enumerate(self.finished_rank):
            row = i // cols
            col = i % cols

            x = start_x + col * padding_x
            y = start_y + row * padding_y

            # Draw marble (larger)
            pygame.draw.circle(self.screen, m['color'], (x, y), int(MARBLE_RADIUS * 2))
            pygame.draw.circle(self.screen, (255, 255, 255), (x, y), int(MARBLE_RADIUS * 2), 1)

            # Draw Rank
            rank_text = self.font.render(f"#{i+1}", True, (200, 200, 200))
            self.screen.blit(rank_text, (x + 15, y - 8))

        # Footer
        footer = self.font.render("100 marbles dropped through a funnel - physics by Pymunk", True, (100, 100, 100))
        self.screen.blit(footer, (WIDTH // 2 - footer.get_width() // 2, HEIGHT - 30))


if __name__ == "__main__":
    sim = MarbleSimulation()
    sim.run()
