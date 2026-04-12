"""
AXIOM Idle Behavior Engine — Makes the face feel alive
========================================================
Reads scene.json from vision daemon and plays contextual animations.
Only runs when respond.py isn't actively speaking (checks mute.flag).

Behaviors:
  - idle_chill: gentle blinks, tiny eye shifts, smile (no one around)
  - eye_tag: spot person, glance toward them, look away, glance back (shy)
  - tongue_out: playful tongue stick-out (for kids or fun moments)
  - curious_look: squint + head tilt when something interesting appears

Usage:
  python idle.py              # Run idle behavior engine
  python idle.py --test TAG   # Test a specific behavior once
"""
import os
import sys
import time
import json
import struct
import asyncio
import random
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(BASE_DIR), "backpack-project"))
from PIL import Image, ImageDraw

SCENE_FILE = os.path.join(BASE_DIR, "scene.json")
MUTE_FILE = os.path.join(BASE_DIR, "mute.flag")
LOG_FILE = os.path.join(BASE_DIR, "idle-log.txt")

# BLE config — replace with your device's address and characteristic UUIDs
ADDR = "XX:XX:XX:XX:XX:XX"
WC = "0000fff2-0000-1000-8000-00805f9b34fb"
NC = "0000fff1-0000-1000-8000-00805f9b34fb"

# Colors
BG_COLOR = (0, 0, 10)
EYE_COLOR = (0, 140, 200)
PUPIL_COLOR = (255, 255, 255)
TONGUE_COLOR = (200, 50, 80)
EYE_L = (22, 24)
EYE_R = (42, 24)

DEMO_KILL = [
    bytes.fromhex("aa55ffff0a000c00c10204020000dc03"),
    bytes.fromhex("aa55ffff0a000d00c10204020001de03"),
    bytes.fromhex("aa55ffff09000e00c1023001909804"),
]


def log(msg):
    ts = datetime.now().strftime("%H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line, flush=True)
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except:
        pass


# --- BLE helpers ---
def pkt(data):
    inner = bytearray([0xAA, 0x55, 0xFF, 0xFF])
    inner.extend(struct.pack('<H', len(data) + 6))
    inner.extend(struct.pack('<H', 9))
    inner.extend([0xC1, 0x02])
    inner.extend(data)
    cs = sum(inner) & 0xFFFF
    inner.extend(struct.pack('<H', cs))
    return bytes(inner)


# --- Frame generators ---
def make_frame(draw_fn):
    img = Image.new('RGB', (64, 64), BG_COLOR)
    draw = ImageDraw.Draw(img)
    draw_fn(draw, img)
    return img


def draw_eye(d, cx, cy, size=14):
    d.ellipse([cx-size//2, cy-size//2, cx+size//2, cy+size//2], fill=EYE_COLOR)

def draw_pupil(d, cx, cy, size=5):
    d.ellipse([cx-size//2, cy-size//2, cx+size//2, cy+size//2], fill=PUPIL_COLOR)

def draw_smile(d, cx=32, cy=48, width=24):
    d.arc([cx-width//2, cy-8, cx+width//2, cy+8], start=10, end=170, fill=EYE_COLOR, width=2)

def draw_eye_closed(d, cx, cy, width=14):
    d.rectangle([cx-width//2, cy-1, cx+width//2, cy+1], fill=EYE_COLOR)

def draw_tongue(d, cx=32, cy=52, w=8, h=6):
    """Playful tongue sticking out"""
    d.ellipse([cx-w//2, cy, cx+w//2, cy+h], fill=TONGUE_COLOR)

def draw_squint_eye(d, cx, cy, size=14):
    """Half-closed eye for curious/skeptical look"""
    d.ellipse([cx-size//2, cy-size//4, cx+size//2, cy+size//4], fill=EYE_COLOR)

def draw_wide_eye(d, cx, cy, size=16):
    """Big wide eye for surprise"""
    d.ellipse([cx-size//2, cy-size//2, cx+size//2, cy+size//2], fill=EYE_COLOR)


def frame_happy(lx=0, ly=0, asymmetry=True):
    def draw(d, img):
        draw_eye(d, EYE_L[0], EYE_L[1])
        draw_eye(d, EYE_R[0], EYE_R[1])
        # Slight asymmetry: trailing eye lags by 1px (more organic)
        lag = 1 if (asymmetry and abs(lx) > 1) else 0
        trail_x = lx - lag if lx > 0 else lx + lag if lx < 0 else lx
        draw_pupil(d, EYE_L[0]+trail_x, EYE_L[1]+ly)
        draw_pupil(d, EYE_R[0]+lx, EYE_R[1]+ly)
        draw_smile(d)
    return make_frame(draw)

def frame_blink():
    def draw(d, img):
        draw_eye_closed(d, EYE_L[0], EYE_L[1])
        draw_eye_closed(d, EYE_R[0], EYE_R[1])
        draw_smile(d)
    return make_frame(draw)

def frame_tongue(lx=0, ly=0):
    def draw(d, img):
        draw_eye(d, EYE_L[0], EYE_L[1])
        draw_eye(d, EYE_R[0], EYE_R[1])
        draw_pupil(d, EYE_L[0]+lx, EYE_L[1]+ly)
        draw_pupil(d, EYE_R[0]+lx, EYE_R[1]+ly)
        # Open mouth (no smile) with tongue poking out
        d.ellipse([26, 44, 38, 54], fill=EYE_COLOR)   # Mouth opening
        d.ellipse([28, 46, 36, 52], fill=BG_COLOR)     # Mouth interior (dark)
        draw_tongue(d, cx=32, cy=50, w=8, h=7)         # Tongue coming out of mouth
    return make_frame(draw)

def frame_curious(lx=0, ly=0):
    """Squinty curious look"""
    def draw(d, img):
        draw_squint_eye(d, EYE_L[0], EYE_L[1])
        draw_eye(d, EYE_R[0], EYE_R[1])  # One eye normal, one squinted
        draw_pupil(d, EYE_L[0]+lx, EYE_L[1]+ly, 4)
        draw_pupil(d, EYE_R[0]+lx, EYE_R[1]+ly)
        draw_smile(d, width=16)
    return make_frame(draw)

def frame_surprised(lx=0, ly=0):
    """Wide-eyed surprise"""
    def draw(d, img):
        draw_wide_eye(d, EYE_L[0], EYE_L[1])
        draw_wide_eye(d, EYE_R[0], EYE_R[1])
        draw_pupil(d, EYE_L[0]+lx, EYE_L[1]+ly, 4)
        draw_pupil(d, EYE_R[0]+lx, EYE_R[1]+ly, 4)
        # Small O mouth for surprise
        d.ellipse([28, 45, 36, 53], fill=EYE_COLOR)
        d.ellipse([30, 47, 34, 51], fill=BG_COLOR)
    return make_frame(draw)


def frame_sleep(z_offset=0):
    """Sleeping face: closed eyes, slight smile, Z's floating"""
    ZZZ_COLOR = (80, 120, 200)
    def draw(d, img):
        # Closed eyes (curved down lines — sleeping)
        d.arc([EYE_L[0]-7, EYE_L[1]-2, EYE_L[0]+7, EYE_L[1]+6], start=0, end=180, fill=EYE_COLOR, width=2)
        d.arc([EYE_R[0]-7, EYE_R[1]-2, EYE_R[0]+7, EYE_R[1]+6], start=0, end=180, fill=EYE_COLOR, width=2)
        # Small gentle smile
        draw_smile(d, width=18)
        # Floating Z's — drift upward and to the right
        z_positions = [
            (48 + (z_offset % 8), 18 - (z_offset % 12), 6, ZZZ_COLOR),
            (52 + ((z_offset + 4) % 10), 10 - ((z_offset + 4) % 14), 4, (60, 90, 160)),
            (55 + ((z_offset + 8) % 6), 4 - ((z_offset + 8) % 10), 3, (40, 60, 120)),
        ]
        for zx, zy, sz, clr in z_positions:
            if 0 <= zy < 60 and 0 <= zx < 62:
                # Draw a Z shape
                d.line([(zx, zy), (zx+sz, zy)], fill=clr, width=1)
                d.line([(zx+sz, zy), (zx, zy+sz)], fill=clr, width=1)
                d.line([(zx, zy+sz), (zx+sz, zy+sz)], fill=clr, width=1)
    return make_frame(draw)


def frame_to_rects(img, min_brightness=15):
    rects = []
    pixels = img.load()
    w, h = img.size
    for y in range(h):
        x = 0
        while x < w:
            r, g, b = pixels[x, y]
            if r < min_brightness and g < min_brightness and b < min_brightness:
                x += 1; continue
            start_x = x
            while x < w:
                pr, pg, pb = pixels[x, y]
                if (pr, pg, pb) != (r, g, b): break
                x += 1
            d = bytearray(15)
            d[0]=0x32; d[1]=0x0D; d[2]=0x01; d[3]=r; d[4]=g; d[5]=b; d[6]=0x00
            struct.pack_into('<H', d, 7, start_x)
            struct.pack_into('<H', d, 9, y)
            struct.pack_into('<H', d, 11, x-1)
            struct.pack_into('<H', d, 13, y)
            rects.append(bytes(d))
    return rects


# --- BLE drawing ---
async def clear_full(c):
    for y in range(64):
        d = bytearray(15)
        d[0]=0x32; d[1]=0x0D; d[2]=0x01; d[3]=0; d[4]=0; d[5]=10; d[6]=0
        struct.pack_into('<H', d, 7, 0)
        struct.pack_into('<H', d, 9, y)
        struct.pack_into('<H', d, 11, 63)
        struct.pack_into('<H', d, 13, y)
        await c.write_gatt_char(WC, pkt(bytes(d)), response=False)

async def draw_full(c, img):
    await clear_full(c)
    for r in frame_to_rects(img):
        await c.write_gatt_char(WC, pkt(r), response=False)
        await asyncio.sleep(0.012)

async def draw_zone(c, img, y_start, y_end):
    # Clear zone
    for y in range(y_start, y_end):
        d = bytearray(15)
        d[0]=0x32; d[1]=0x0D; d[2]=0x01; d[3]=0; d[4]=0; d[5]=10; d[6]=0
        struct.pack_into('<H', d, 7, 8)
        struct.pack_into('<H', d, 9, y)
        struct.pack_into('<H', d, 11, 56)
        struct.pack_into('<H', d, 13, y)
        await c.write_gatt_char(WC, pkt(bytes(d)), response=False)
    # Draw zone
    for r in frame_to_rects(img):
        ry = struct.unpack_from('<H', r, 9)[0]
        if y_start <= ry <= y_end:
            await c.write_gatt_char(WC, pkt(r), response=False)

async def kill_demo(c):
    for cmd in DEMO_KILL:
        await c.write_gatt_char(WC, cmd, response=False)
        await asyncio.sleep(0.15)
    await asyncio.sleep(0.5)


# --- Scene reading ---
def read_scene():
    """Read latest scene data from vision daemon"""
    if not os.path.exists(SCENE_FILE):
        return None
    try:
        with open(SCENE_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except:
        return None


def is_speaking():
    """Check if respond.py is currently using the face"""
    return os.path.exists(MUTE_FILE)


# --- Behavior scripts ---
async def behavior_idle_chill(c):
    """Gentle idle: blinks, eye shifts, micro-saccades, just vibing"""
    log("Behavior: idle_chill")
    lx, ly = 0, 0

    for _ in range(random.randint(8, 15)):
        if is_speaking():
            return  # Yield to respond.py

        # Eye shift — bigger range, more frequent
        if random.random() < 0.5:
            lx = random.choice([-2, -1, -1, 0, 0, 1, 1, 2])
            ly = random.choice([-1, 0, 0, 0, 1])
            await draw_zone(c, frame_happy(lx, ly), 14, 34)
        # Micro-saccade — tiny jitter that makes eyes feel alive
        elif random.random() < 0.4:
            jx = lx + random.choice([-1, 0, 1])
            jy = ly + random.choice([-1, 0])
            jx = max(-3, min(3, jx))
            jy = max(-2, min(2, jy))
            await draw_zone(c, frame_happy(jx, jy), 14, 34)
            await asyncio.sleep(random.uniform(0.1, 0.3))
            await draw_zone(c, frame_happy(lx, ly), 14, 34)

        # Random blink
        if random.random() < 0.15:
            await draw_zone(c, frame_blink(), 14, 34)
            await asyncio.sleep(0.12)
            await draw_zone(c, frame_happy(lx, ly), 14, 34)

        await asyncio.sleep(random.uniform(0.8, 2.0))


async def behavior_eye_tag(c, gaze_x, gaze_y):
    """Spot a person, glance toward them, look away shyly, glance back"""
    # Scale gaze for more visible movement (clamp to -3..3)
    gx = max(-3, min(3, gaze_x * 2 if abs(gaze_x) < 2 else gaze_x))
    gy = max(-2, min(2, gaze_y))
    log(f"Behavior: eye_tag (target: {gx}, {gy})")

    # Start looking slightly off-center (more natural than dead center)
    start_x = random.choice([-1, 0, 1])
    await draw_zone(c, frame_happy(start_x, 0), 14, 34)
    await asyncio.sleep(random.uniform(0.8, 1.5))

    if is_speaking(): return

    # Blink-on-saccade: quick blink as eyes jump to person (most natural)
    await draw_zone(c, frame_blink(), 14, 34)
    await asyncio.sleep(0.1)
    await draw_zone(c, frame_happy(gx, gy), 14, 34)
    await asyncio.sleep(random.uniform(0.4, 0.8))

    if is_speaking(): return

    # Look away quickly (opposite direction, bigger swing)
    away_x = -gx if gx != 0 else random.choice([-3, 3])
    away_y = random.choice([-1, 0, 1])
    await draw_zone(c, frame_happy(away_x, away_y), 14, 34)
    await asyncio.sleep(random.uniform(0.6, 1.2))

    if is_speaking(): return

    # Blink before glancing back
    await draw_zone(c, frame_blink(), 14, 34)
    await asyncio.sleep(0.1)
    # Glance back with micro-saccade (not exactly the same spot — realistic)
    near_x = gx + random.choice([-1, 0, 0, 1])
    near_x = max(-3, min(3, near_x))
    await draw_zone(c, frame_happy(near_x, gy), 14, 34)
    await asyncio.sleep(random.uniform(1.0, 2.0))

    if is_speaking(): return

    # Settle on them with a blink
    await draw_zone(c, frame_blink(), 14, 34)
    await asyncio.sleep(0.12)
    await draw_zone(c, frame_happy(gx, gy), 14, 34)
    await asyncio.sleep(random.uniform(1.5, 3.0))

    # Drift back toward center naturally (not snap)
    mid_x = gx // 2
    await draw_zone(c, frame_happy(mid_x, 0), 14, 34)
    await asyncio.sleep(0.4)
    await draw_zone(c, frame_happy(0, 0), 14, 34)


async def behavior_attentive(c, gaze_x, gaze_y):
    """Active person tracking — eyes follow with frequent small movements"""
    gx = max(-3, min(3, gaze_x * 2 if abs(gaze_x) < 2 else gaze_x))
    gy = max(-2, min(2, gaze_y))
    log(f"Behavior: attentive (target: {gx}, {gy})")

    # Look at person
    await draw_zone(c, frame_happy(gx, gy), 14, 34)

    for _ in range(random.randint(6, 10)):
        if is_speaking():
            return

        # Small shifts around the target — like naturally tracking movement
        jx = gx + random.choice([-1, 0, 0, 1])
        jy = gy + random.choice([-1, 0, 0, 0])
        jx = max(-3, min(3, jx))
        jy = max(-2, min(2, jy))
        await draw_zone(c, frame_happy(jx, jy), 14, 34)

        # Occasional blink while looking at them
        if random.random() < 0.2:
            await asyncio.sleep(random.uniform(0.3, 0.6))
            await draw_zone(c, frame_blink(), 14, 34)
            await asyncio.sleep(0.12)
            await draw_zone(c, frame_happy(gx, gy), 14, 34)

        await asyncio.sleep(random.uniform(0.5, 1.2))


async def behavior_tongue_out(c, gaze_x=0, gaze_y=0):
    """Playful tongue stick-out"""
    log("Behavior: tongue_out")

    # Look at target
    await draw_zone(c, frame_happy(gaze_x, gaze_y), 14, 34)
    await asyncio.sleep(0.5)

    if is_speaking(): return

    # Tongue out!
    await draw_full(c, frame_tongue(gaze_x, gaze_y))
    await asyncio.sleep(random.uniform(1.5, 2.5))

    if is_speaking(): return

    # Pull tongue back, smile
    await draw_full(c, frame_happy(gaze_x, gaze_y))
    await asyncio.sleep(1.0)


async def behavior_curious(c, gaze_x=0, gaze_y=0):
    """Curious squint at something interesting"""
    log("Behavior: curious_look")

    # Normal look
    await draw_full(c, frame_happy(0, 0))
    await asyncio.sleep(0.8)

    if is_speaking(): return

    # Squint toward interesting thing
    await draw_full(c, frame_curious(gaze_x, gaze_y))
    await asyncio.sleep(random.uniform(2.0, 3.5))

    if is_speaking(): return

    # Back to normal
    await draw_full(c, frame_happy(0, 0))


async def behavior_surprised(c):
    """Quick surprised reaction"""
    log("Behavior: surprised")
    await draw_full(c, frame_surprised())
    await asyncio.sleep(random.uniform(1.0, 2.0))
    await draw_full(c, frame_happy())


async def behavior_sleep(c):
    """Sleep mode: closed eyes with Z's floating across the display"""
    log("Behavior: sleep_mode")
    z_phase = random.randint(0, 20)
    for i in range(random.randint(12, 20)):
        if is_speaking():
            await draw_full(c, frame_happy())
            return
        # Check if someone showed up
        scene = read_scene()
        if scene and scene.get("people_count", 0) > 0:
            # Wake up! Surprised face then happy
            log("Sleep -> wake up! Person detected")
            await behavior_surprised(c)
            return
        await draw_full(c, frame_sleep(z_phase + i))
        await asyncio.sleep(random.uniform(1.5, 2.5))


# --- Main loop ---
async def run_idle():
    """
    Connect-per-cycle approach: connect BLE, run one behavior, disconnect.
    This prevents BLE conflicts with respond.py which needs its own connection.
    """
    from bleak import BleakClient

    log("Idle engine starting (connect-per-cycle mode)")

    last_people = 0
    last_eye_tag = 0
    eye_tag_cooldown = 30
    tongue_cooldown = 120
    last_tongue = 0
    first_run = True
    ble_fail_count = 0
    BLE_MAX_BACKOFF = 60  # Cap backoff at 60 seconds

    while True:
        try:
            # Yield if AXIOM is speaking — don't even try to connect
            if is_speaking():
                await asyncio.sleep(1.0)
                continue

            # Read scene
            scene = read_scene()
            people = 0
            gaze_x, gaze_y = 0, 0

            if scene:
                people = scene.get("people_count", 0)
                gaze = scene.get("gaze_target", {})
                gaze_x = gaze.get("x", 0)
                gaze_y = gaze.get("y", 0)

            now = time.time()

            # Decide which behavior to run
            behavior = None
            behavior_args = ()

            if first_run:
                behavior = "init"
                first_run = False
            elif people > 0 and last_people == 0:
                behavior = "surprised_then_eye_tag"
                behavior_args = (gaze_x, gaze_y)
            elif people > 0 and now - last_eye_tag > eye_tag_cooldown:
                roll = random.random()
                if roll < 0.35:
                    behavior = "eye_tag"
                    behavior_args = (gaze_x, gaze_y)
                elif roll < 0.55:
                    behavior = "attentive"
                    behavior_args = (gaze_x, gaze_y)
                elif roll < 0.7 and now - last_tongue > tongue_cooldown:
                    behavior = "tongue"
                    behavior_args = (gaze_x, gaze_y)
                elif roll < 0.85:
                    behavior = "curious"
                    behavior_args = (gaze_x, gaze_y)
                else:
                    behavior = "chill"
            elif people == 0:
                behavior = "sleep"
                last_people = 0

            if behavior is None:
                await asyncio.sleep(2.0)
                last_people = people
                continue

            # Connect, run behavior, disconnect
            try:
                async with BleakClient(ADDR, timeout=10) as c:
                    await c.start_notify(NC, lambda s, d: None)

                    if behavior == "init":
                        await kill_demo(c)
                        await draw_full(c, frame_happy())
                        log("Idle engine active")

                    elif behavior == "surprised_then_eye_tag":
                        await behavior_surprised(c)
                        if not is_speaking():
                            await asyncio.sleep(0.5)
                            await behavior_eye_tag(c, *behavior_args)
                        last_eye_tag = now

                    elif behavior == "eye_tag":
                        await behavior_eye_tag(c, *behavior_args)
                        last_eye_tag = now

                    elif behavior == "tongue":
                        await behavior_tongue_out(c, *behavior_args)
                        last_tongue = now
                        last_eye_tag = now

                    elif behavior == "attentive":
                        await behavior_attentive(c, *behavior_args)
                        last_eye_tag = now

                    elif behavior == "curious":
                        await behavior_curious(c, *behavior_args)
                        last_eye_tag = now

                    elif behavior == "chill":
                        await behavior_idle_chill(c)

                    elif behavior == "sleep":
                        await behavior_sleep(c)

                    try:
                        await c.stop_notify(NC)
                    except:
                        pass

            except Exception as ble_err:
                ble_fail_count += 1
                backoff = min(5 * (2 ** (ble_fail_count - 1)), BLE_MAX_BACKOFF)
                log(f"BLE connect error ({ble_fail_count}x): {ble_err} — retry in {backoff}s")
                last_people = people  # Track state even when BLE is down
                await asyncio.sleep(backoff)
                continue

            # BLE reconnected after failures — push correct face immediately
            if ble_fail_count > 0:
                log(f"BLE recovered after {ble_fail_count} failures — state synced")
            ble_fail_count = 0  # Reset backoff on success
            last_people = people

            # Brief pause between cycles to not hammer BLE
            await asyncio.sleep(1.0)

        except KeyboardInterrupt:
            log("Idle engine stopped")
            break
        except Exception as e:
            log(f"Idle error: {e}")
            await asyncio.sleep(5)


async def test_behavior(name):
    from bleak import BleakClient

    async with BleakClient(ADDR, timeout=15) as c:
        await c.start_notify(NC, lambda s, d: None)
        await kill_demo(c)
        await draw_full(c, frame_happy())

        if name == "chill":
            await behavior_idle_chill(c)
        elif name == "eye_tag":
            await behavior_eye_tag(c, 3, 0)
        elif name == "attentive":
            await behavior_attentive(c, 2, 0)
        elif name == "tongue":
            await behavior_tongue_out(c, 0, 0)
        elif name == "curious":
            await behavior_curious(c, 2, -1)
        elif name == "surprised":
            await behavior_surprised(c)
        elif name == "sleep":
            await behavior_sleep(c)
        else:
            log(f"Unknown behavior: {name}")

        await draw_full(c, frame_happy())
        try:
            await c.stop_notify(NC)
        except:
            pass


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="AXIOM Idle Behaviors")
    parser.add_argument("--test", type=str, help="Test a behavior: chill, eye_tag, tongue, curious, surprised")
    args = parser.parse_args()

    if args.test:
        asyncio.run(test_behavior(args.test))
    else:
        asyncio.run(run_idle())
