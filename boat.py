import sys
import os
import math
import random
import argparse
import time
import glob

import pygame
import opc

from pprint import pprint

import sound_board

# Commonly used type annotations
Vector2 = tuple[int, int]
ColorRGB = tuple[int, int, int]
ColorGBR = tuple[int, int, int]

# Fade Candy Constants
FADECANDY_HOST = 'localhost'
FADECANDY_PORT = 7890
TEMPORAL_DITHERING = True

# Note: Modes are selected on a USB keypad.  Each mode should be K_KP*
MODES_KEYS = {pygame.K_KP1: 'dragon',
              pygame.K_KP2: 'boat',
              pygame.K_KP3: 'speed_boat',
              pygame.K_KP4: 'disco',
              pygame.K_KP5: 'slow',
              pygame.K_KP6: 'panic',
              pygame.K_KP7: 'debug',
              pygame.K_KP8: 'bright',
              pygame.K_KP9: 'off',
              pygame.K_KP0: 'america',
              pygame.K_KP_MULTIPLY: 'space',
              pygame.K_1: 'dragon',
              pygame.K_2: 'boat',
              pygame.K_3: 'speed_boat',
              pygame.K_4: 'disco',
              pygame.K_5: 'slow',
              pygame.K_6: 'panic',
              pygame.K_7: 'debug',
              pygame.K_8: 'bright',
              pygame.K_9: 'off',
              pygame.K_0: 'america',
              pygame.K_BACKQUOTE: 'space',
        }
MODES = set(MODES_KEYS.values())
DEFAULT_MODE = 'dragon'

# This is the number of LEDs in each element of the boat. Doesn't directly
# map to the LED positions on the fade candy.
RAIL_SIZE = 120
KITT_SIZE = 20
STERN_SIZE = 15
NOSE_SIZE = 30
WAVE_SIZE = 30
PROW = RAIL_SIZE - NOSE_SIZE
SPINNER_SIZE = 16
TAIL_SIZE = 8

# Note: Removed the poop deck lighting when they caught on fire a bit.
#       Also removed the ground effect when we redid the decking.  May add these back.

OFF = [(0, 0, 0)] * 64

# For display purposes.  The size of each LED in pixels and the space between LEDs
LED_SIZE = 8
LED_GAP  = 2

# Cheap way of controlling the animation speed.  We just change the frame rate.
RATES = dict(boat=20, 
             dragon=20,
             fast_boat=60, 
             speed_boat=120,
             disco=5, 
             slow=1,   # But I cheat here...
             panic=200,
             debug=10,
             bright=10,
             off=10,
             america=50,
             space=20,
            )

# How much the brightness is increased or decreased each step
BRIGHT_STEP = 0.1

# Time to fade out the lights and music when shutting down
FADE_TIME = 1000

# This is a single LED object.  If I were to start fresh, I might not
# do it this way but this let me develop/debug the boat and get it into
# a working state.
class Led:
    def __init__(self, 
                 pos: Vector2,
                 size: Vector2,
                 color: ColorRGB = (0,0,0)) -> None:
        self.color = color
        self.rect = pygame.Rect(pos, size)

    def draw(self, surf: pygame.Surface, scale: float = 1.0) -> None:
        color = [int(c * scale) for c in self.color]
        pygame.draw.rect(surf, color, self.rect)

# Contains all of the LED strand animation routines.
class Boat:
    # The boat has a Larson Scanner on the bow because... why would you
    # not if that was an option.  If the pirates of the mid-1600's had
    # addressable LEDs you can be 100% sure they would have done this too.
    kitt_size = 3
    kitt_dark = (64, 64, 64)

    rail_level = (128, 128, 128)
    rail_decay = 20
    rail_prob = 0.13

    # Note: The ground effect (wave) LEDs have been removed for renovation
    #       but will probably be added back at some point
    wave_level = 192

    # Note: The poop deck LEDs are gone and good riddance to the GBR fire
    #       hazards! Also, they made wiring way more difficult that any
    #       ammount of colourfull joy they brought to this world.  Also,
    #       they tended to smoke or burn at high brightnesses.
    # poop_level = (96, 0, 0)
    # poop_decay = 15
    # poop_fires = 3

    def __init__(self, verbose: bool = False):
        self.wave_left  = generate_waves(self.wave_level, True)
        self.wave_right = generate_waves(self.wave_level, False)
        self.rail_left  = generate_rail(self.rail_level, True)
        self.rail_right = generate_rail(self.rail_level, False)
        self.kitt = generate_kitt(self.kitt_dark)

        self.strips = (self.wave_left,
                       self.wave_right,
                       self.rail_left,
                       self.rail_right,
                       self.kitt,
                      )

        self.kitt_pos = 0
        self.kitt_dir = 1
        self.wave_offset = 0.0
        self.brightness = 1.0
        self.disco_delay = 0

        self._mode = DEFAULT_MODE
        self.verbose = verbose

    @property
    def mode(self) -> str:
        return self._mode

    @mode.setter
    def mode(self, value: str) -> None:
        self._mode = value
        self.disco_delay = 0

    @property
    def strands(self) -> list:
        strands = [[] for i in range(8)]
        empty = [(0, 0, 0)] * 4

        # Old setup: [Initial Incorrect Guesses]
        # Strand 0: Ground effects -- 850 mA
        # Strand 1: Left stern -- 600 mA
        # Strand 2: Left bow -- 480 mA
        # Strand 3: Right stern -- 600 mA
        # Strand 4: Right bow -- 480 mA
        # Strand 5: Poop deck -- 350 mA

        # Strand[0]: Right stern (reversed)
        strands[0] = [led.color for led in self.rail_right[::-1][RAIL_SIZE//2-KITT_SIZE:]] + \
                     empty

        # Strand[1]: Right bow
        strands[1] = [led.color for led in self.rail_right[RAIL_SIZE//2:]] + \
                     [led.color for led in self.kitt[:KITT_SIZE]] + \
                     empty

        # Strand[2]: Left stern (reversed)
        strands[2] = [led.color for led in self.rail_left[::-1][RAIL_SIZE//2-KITT_SIZE:]] + \
                     empty

        # Strand[3]: Left bow
        strands[3] = [led.color for led in self.rail_left[RAIL_SIZE//2:]] + \
                     [led.color for led in self.kitt[KITT_SIZE:][::-1]] + \
                     empty

        # Strand[4]: Ground Effects
        strands[4] = [led.color for led in self.wave_left] + \
                     [led.color for led in self.wave_right[::-1]] + \
                     empty
        
        return strands

    def click(self, pos: Vector2) -> None:
        # Only really useful in debug mode
        for strip_ix, strip in enumerate(self.strips):
            for led_ix, led in enumerate(strip):
                if led.rect.collidepoint(pos):
                    old = led.color
                    new = (255, 255, 255) if old == (0, 0, 0) else (0, 0, 0)
                    print(f"Strand{strip_ix}[{led_ix}]: {old} -> {new}")
                    led.color = new
                    return

    def update(self, dt_ms: int) -> None:
        # The dt was only used on the space ship to control the speed
        # of the spinning nacelles.  Keeping it for now as we might
        # want it for the dragon.
        dt = dt_ms / 1e3
        
        # Run the currently selected animation routine.
        getattr(self, self.mode)()
        
    def debug(self):
        pass

    # This routine was used for the Rose, White, and Blue parade.  Unfortunatly:
    # (a) The parade was in full daylight and no one could see the LEDs
    # (b) The white stripes were on the wrong side of the boat.
    def america(self) -> None:
        if not hasattr(self, 'usa'):
            self.usa = [(255, 0, 0), (255, 255, 255), (0, 0, 255)]

        # Animate the waves
        changed = False
        r, g, b = self.usa[0]
        d_color = 5
        for ix in range(len(self.wave_left)):
            for edge in (self.wave_left, self.wave_right):
                if edge[ix].color != self.usa[0]:
                    changed = True
                    next = (edge[ix].color[0] + max(-d_color, (min(d_color, r - edge[ix].color[0]))),
                            edge[ix].color[1] + max(-d_color, (min(d_color, g - edge[ix].color[1]))),
                            edge[ix].color[2] + max(-d_color, (min(d_color, b - edge[ix].color[2]))),
                           )
                    edge[ix].color = next
        if not changed:
            self.usa = self.usa[1:] + [self.usa[0]]

        # Animate Larson scanner
        self.kitt_pos += self.kitt_dir
        if (self.kitt_pos < 1) or (self.kitt_pos > (KITT_SIZE - 2) * 2):
            edge = self.rail_left if self.kitt_pos < 1 else self.rail_right
            for i in range(RAIL_SIZE - KITT_SIZE - 6, RAIL_SIZE - KITT_SIZE):
                edge[i].color = (255, 255, 255)
            self.kitt_dir *= -1
            self.kitt_pos += self.kitt_dir
        else:
            self.rail_left[RAIL_SIZE - KITT_SIZE - 1].color = (255, 0, 0)
            self.rail_right[RAIL_SIZE - KITT_SIZE - 1].color = (0, 0, 255)
        
        for led in self.kitt:
            led.color = self.kitt_dark
        for ix in range(self.kitt_pos, self.kitt_pos + self.kitt_size):
            self.kitt[ix].color = (255, 255, 255)
        half = self.kitt_pos + self.kitt_size if self.kitt_dir == 1 else self.kitt_pos - 1
        self.kitt[half].color = (192, 192, 192)

        # Pull the white stripes along the rails
        for ix in range(RAIL_SIZE-KITT_SIZE-1):
            self.rail_left[ix].color = self.rail_left[ix+1].color
            self.rail_right[ix].color = self.rail_right[ix+1].color

    def speed_boat(self) -> None:
        self.boat()     # The regular boat but super fast

    def fast_boat(self) -> None:
        self.boat()     # The regular boat but faster

    # The enterprise LED routines.
    def dragon(self) -> None:
        self.boat(alt_mode='dragon')

    # The enterprise LED routines.
    def space(self) -> None:
        self.boat(alt_mode='space')

    # The pirate ship LED routines.
    def boat(self, alt_mode: str = None) -> None:
        # Animate the waves:
        #       Remember the old biorythm BASIC programs you could type
        #       in from a computer magazine.  This is basically that only
        #       without the cheat code where my cirthday was always the 
        #       best one.  Makes a scrolling sin wave with a smaller sine
        #       wave (noise) on top.  The waves are in shades of blue with
        #       peaks in pure white (chop)
        self.wave_offset += 0.31
        t = self.wave_offset
        for ix, led in enumerate(self.wave_left):
            level = self.wave_level
            level += math.sin(t + ix) * 64
            level += math.sin(t + (ix >> 2)) * 24
            color = (0, 0, level) if level <= 255 else (255, 255, 255)
            self.wave_left[ix].color = color
            self.wave_right[ix].color = color

        # Update speckles:
        #       The rails are solid grey but have spots to break up the
        #       monotony. The spots fade to grey over time.
        target = self.rail_level[0]
        for rail in (self.rail_left, self.rail_right):
            for ix, led in enumerate(rail):
                if led.color[0] != target:
                    new_color = max(self.rail_level[0], led.color[0] - self.rail_decay)
                    led.color = (new_color, new_color, new_color)

            if random.random() < self.rail_prob:
                dot = random.randrange(RAIL_SIZE - KITT_SIZE - 2) + 1
                rail[dot].color = (255, 255, 255)
                rail[dot-1].color = (200, 200, 200)
                rail[dot+1].color = (200, 200, 200)

        # The enterprise and dragon don't get the KITT-esque Larson scanner
        if alt_mode is not None:
            self.kitt_pos += self.kitt_dir
            if (self.kitt_pos < 1) or (self.kitt_pos > (KITT_SIZE - 2) * 2):
                self.kitt_dir *= -1
                self.kitt_pos += self.kitt_dir
            for led in self.kitt:
                led.color = self.kitt_dark
            for ix in range(self.kitt_pos, self.kitt_pos + self.kitt_size):
                self.kitt[ix].color = (255, 0, 0)
            half = self.kitt_pos + self.kitt_size if self.kitt_dir == 1 else self.kitt_pos - 1
            self.kitt[half].color = (192, 0, 0)
        else:
            for led in self.kitt:
                led.color = (255, 255, 255)
                # TODO: Make this interesting for the dragon.  Maybe flickering flames?

        # Add indicators:
        #       Add collision lights on the corners of the boat.  Red on the left
        #       and green on the right.
        for starboard, rail in enumerate([self.rail_left, self.rail_right]):
            color = (0, 255, 0) if starboard else (255, 0, 0)  # Good port wine is red
            for ix in range(STERN_SIZE, STERN_SIZE+3):
                rail[ix].color = color
            for ix in range(RAIL_SIZE-NOSE_SIZE-2, RAIL_SIZE-NOSE_SIZE+1):
                rail[ix].color = color

    def slow(self) -> None:
        if self.disco_delay == 0:
            #self.disco(low=128)  # Too pastel
            self.disco()
            self.disco_delay = 5
        else:
            self.disco_delay -= 1

    def panic(self) -> None:
        self.disco()

    def disco(self, low: int = 0, high: int = 255) -> None:
        for strip in self.strips:
            for led in strip:
                led.color = (random.randint(low, high),
                             random.randint(low, high),
                             random.randint(low, high))

    # Added this after figuring out that there was no way to turn off the
    # lights except to unplug the LED power supply or the Pi.
    def off(self) -> None:
        for strip in self.strips:
            for led in strip:
                led.color = (0, 0, 0)

    # Turn on all of the LEDs to full power.  Great for debugging and setting
    # the poop deck on fire.
    def bright(self) -> None:
        for strip in self.strips:
            for led in strip:
                led.color = (255, 255, 255)

    def draw(self, surf: pygame.Surface) -> None:
        for strip in self.strips:
            for led in strip:
                led.draw(surf, self.brightness)

# Only needed for funky poop deck LEDs
def rgb2gbr(c: ColorRGB) -> ColorGBR:
    return (c[1], c[0], c[2])

def generate_waves(level: int, top: bool = True) -> None:
    color = (0, 0, level)

    y = (LED_SIZE + LED_GAP) * 12
    if not top:
        bottom = ((LED_SIZE + LED_GAP) * NOSE_SIZE * 2) - LED_SIZE - LED_GAP
        y = bottom - y
    base_x = (LED_SIZE + LED_GAP) * 30

    pixels = []
    for ix in range(WAVE_SIZE):
        x = ((LED_SIZE + LED_GAP) * ix) + base_x
        pixels.append(Led((x, y), (LED_SIZE, LED_SIZE), color))
    return pixels

def get_rail_pos(ix: int) -> tuple[int, int]:
    if ix < STERN_SIZE:
        x = 0
        dy = (LED_SIZE + LED_GAP) * (STERN_SIZE - ix)
    else:
        x = (LED_SIZE + LED_GAP) * (ix - STERN_SIZE)
        dy = max(0, (LED_SIZE + LED_GAP) * (ix - PROW))

    return x, dy

def generate_rail(brightness: int, top: bool = True) -> list[Led]:
    bottom = ((LED_SIZE + LED_GAP) * NOSE_SIZE * 2) - LED_SIZE - LED_GAP
    pixels = []

    for ix in range(RAIL_SIZE - KITT_SIZE):
        x, dy = get_rail_pos(ix)
        y = dy if top else bottom - dy
        pixels.append(Led((x, y), (LED_SIZE, LED_SIZE), brightness))
    return pixels

def generate_kitt(dark_level: int) -> list[Led]:
    bottom = ((LED_SIZE + LED_GAP) * NOSE_SIZE * 2) - LED_SIZE - LED_GAP
    pixels = []

    for ix in range(RAIL_SIZE - KITT_SIZE, RAIL_SIZE):
        x, dy = get_rail_pos(ix)
        pixels.append(Led((x, dy), (LED_SIZE, LED_SIZE), dark_level))

    for ix in range(RAIL_SIZE - 1, RAIL_SIZE - KITT_SIZE - 1, -1):
        x, dy = get_rail_pos(ix)
        pixels.append(Led((x, bottom - dy), (LED_SIZE, LED_SIZE), dark_level))

    return pixels

def parse_args():
    global LED_SIZE     # Hacky McHack calling
    
    parser = argparse.ArgumentParser(description='Pirate LED Controller')
    parser.add_argument('sound_json', action='store', help="Sound board config JSON file")
    parser.add_argument('--host', action='store', default=FADECANDY_HOST,
                        help='Fadecandy client hostname')
    parser.add_argument('--port', action='store', type=int, default=FADECANDY_PORT,
                        help='Fadecandy client port number')
    parser.add_argument('--size', action='store', type=int, default=LED_SIZE,
                        help='Size of the LEDs in pixels')
    parser.add_argument('-n', '--dry_run', action='store_true', help='No fadecandy connection')
    args = parser.parse_args()
    assert 1024 <= args.port <= 65535
    assert 1 <= args.size

    LED_SIZE = args.size

    return args

def main(args) -> None:
    client = opc.Client(f'{args.host}:{args.port}') if not args.dry_run else None

    pygame.init()
    pygame.mixer.init()
    width = (RAIL_SIZE - STERN_SIZE) * (LED_SIZE + LED_GAP)
    height = NOSE_SIZE * (LED_SIZE + LED_GAP) * 2
    screen = pygame.display.set_mode((width, height), 0, 32)
    pygame.display.set_caption("Boat Light Sim")
    print("Loading SFX...", flush=True)
    sounds = sound_board.load_json(args.sound_json)
    sounds.start()
        
    boat = Boat()
    rate = int(1.0 / RATES[boat.mode] * 1000)  # frame rate in ms

    running = True
    while running:
        # Great big giant IF/THEN/ELSE for the event queue.  Not ideal.
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN:
                # Handle the key presses.
                if event.key == pygame.K_ESCAPE:
                    running = False

                # Handle the change in animation routines.
                elif event.key in MODES_KEYS:
                    new_mode = MODES_KEYS[event.key]
                    if new_mode != boat.mode:
                        print(f"Setting mode: {MODES_KEYS[event.key]!r}")
                        print(f"{new_mode=}")
                        for music in sounds.ambients:
                            fn = os.path.split(music.filename)[-1]
                            if fn.startswith(new_mode):
                                sounds.play_ambient(music)
                                print("Playing:", music)
                                break
                        boat.mode = new_mode
                        rate = int(1.0 / RATES[boat.mode] * 1000)  # frame rate in ms

                # The default is to run the lights at full brightness.  This can
                # be a bit much is some situations.  Use the +/- on the numeric
                # keypad to change the brightness.
                elif event.key == pygame.K_KP_PLUS:
                    boat.brightness = min(1.0, boat.brightness + BRIGHT_STEP)
                    print(f"Brightness increased to {boat.brightness:0.02f}")
                elif event.key == pygame.K_KP_MINUS:
                    boat.brightness = max(0.1, boat.brightness - BRIGHT_STEP)
                    print(f"Brightness decreased to {boat.brightness:0.02f}")

                # Sounds can be played by pressing keys.  The keyboard is hidden
                # in the starboard poopdeck area.  Be subtle and it looks/sounds
                # amazing.
                else:
                    action = sounds.key_press(event.unicode)
                    if not action:
                        # print(f"Unknown key {event.unicode!r}, {event.key=}")
                        pass
            
            # For debugging, you can click on an individual LED and have it
            # toggle.  This is great for debugging and finding out which LEDs
            # are bad.
            elif event.type == pygame.MOUSEBUTTONDOWN:
                if event.button == 1:
                    boat.click(event.pos)

        # Update the display.
        dt = pygame.time.wait(rate)
        boat.update(dt)
        boat.draw(screen)
        pygame.display.flip()

        # Update the LEDs.
        if client:
            strands = boat.strands
            client.put_pixels(sum(strands, []))
            if not TEMPORAL_DITHERING:
                client.put_pixels(sum(strands, []))

    # When quitting, fade out the LEDs and the sounds.
    quit_fade = [(0, 0, 0)] * 512
    if client:
        client.put_pixels(sum(strands, []))
        time.sleep(FADE_TIME / 1000.0)
        client.put_pixels(quit_fade)

    pygame.mixer.music.fadeout(FADE_TIME)  # Stop the background sounds
    pygame.mixer.fadeout(FADE_TIME)        # Stop any sound effects
    time.sleep(FADE_TIME / 1000.0)

    # Turn off all of the LEDs when exiting
    if client:
        client.put_pixels(quit_fade)
        client.put_pixels(quit_fade)

    pygame.quit()

if __name__ == '__main__':
    main(parse_args())

