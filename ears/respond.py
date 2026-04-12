"""
AXIOM Respond — Speak text with synced mouth animation
========================================================
Called by the main AXIOM session when it decides to respond.
Handles: mute ears -> speak via ElevenLabs -> animate mouth -> unmute ears

Usage:
  python respond.py "Hello, I am AXIOM."
"""
import os
import sys
import time
import json
import struct
import asyncio
import random
import subprocess
import threading

# Ensure ffmpeg is on PATH before running
# Install via your package manager (e.g. apt install ffmpeg, brew install ffmpeg,
# or winget install ffmpeg on Windows) and ensure it is available on PATH.

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(BASE_DIR, "backpack-project"))
from PIL import Image, ImageDraw

SPEAK_SCRIPT = os.path.join(BASE_DIR, "scripts", "speak.cjs")
SIGNAL_FILE = os.path.join(BASE_DIR, "axiom", "voice-playing.signal")
MUTE_FILE = os.path.join(BASE_DIR, "axiom", "ears", "mute.flag")

# BLE config — replace with your device's address and characteristic UUIDs
ADDR = "XX:XX:XX:XX:XX:XX"
WC = "0000fff2-0000-1000-8000-00805f9b34fb"
NC = "0000fff1-0000-1000-8000-00805f9b34fb"

# Colors
BG_COLOR = (0, 0, 10)
EYE_COLOR = (0, 140, 200)
PUPIL_COLOR = (255, 255, 255)
EYE_L = (22, 24)
EYE_R = (42, 24)

DEMO_KILL = [
    bytes.fromhex("aa55ffff0a000c00c10204020000dc03"),
    bytes.fromhex("aa55ffff0a000d00c10204020001de03"),
    bytes.fromhex("aa55ffff09000e00c1023001909804"),
]


# --- Timing formula (tuned v5) ---
def estimate_duration(chars):
    if chars <= 60:
        divisor = 26.0
    elif chars >= 200:
        divisor = 36.0
    else:
        divisor = 26.0 + ((chars - 60) / 140) * 10.0
    return chars / divisor


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

def rc(x0, y0, x1, y1, r, g, b):
    d = bytearray(15)
    d[0] = 0x32; d[1] = 0x0D; d[2] = 0x01
    d[3] = r; d[4] = g; d[5] = b; d[6] = 0x00
    struct.pack_into('<H', d, 7, x0)
    struct.pack_into('<H', d, 9, y0)
    struct.pack_into('<H', d, 11, x1)
    struct.pack_into('<H', d, 13, y1)
    return bytes(d)


# --- Frame generators ---
def make_frame(draw_fn):
    img = Image.new('RGB', (64, 64), BG_COLOR)
    draw = ImageDraw.Draw(img)
    draw_fn(draw, img)
    return img

def draw_eye(d, cx, cy, size=12):
    d.ellipse([cx-size//2, cy-size//2, cx+size//2, cy+size//2], fill=EYE_COLOR)

def draw_pupil(d, cx, cy, size=6):
    d.ellipse([cx-size//2, cy-size//2, cx+size//2, cy+size//2], fill=PUPIL_COLOR)

def draw_smile(d, cx=32, cy=48, width=24):
    d.arc([cx-width//2, cy-8, cx+width//2, cy+8], start=10, end=170, fill=EYE_COLOR, width=2)

def draw_mouth_open(d, cx=32, cy=47, w=16, h=12):
    d.ellipse([cx-w//2, cy-h//2, cx+w//2, cy+h//2], fill=EYE_COLOR)
    d.ellipse([cx-w//2+3, cy-h//2+3, cx+w//2-3, cy+h//2-3], fill=BG_COLOR)

def draw_mouth_half(d, cx=32, cy=47, w=12, h=6):
    d.ellipse([cx-w//2, cy-h//2, cx+w//2, cy+h//2], fill=EYE_COLOR)
    d.ellipse([cx-w//2+2, cy-h//2+2, cx+w//2-2, cy+h//2-2], fill=BG_COLOR)

def draw_mouth_wide(d, cx=32, cy=47, w=20, h=10):
    d.ellipse([cx-w//2, cy-h//2, cx+w//2, cy+h//2], fill=EYE_COLOR)
    d.ellipse([cx-w//2+3, cy-h//2+3, cx+w//2-3, cy+h//2-3], fill=BG_COLOR)

def draw_mouth_closed(d, cx=32, cy=48, width=18):
    d.line([(cx-width//2, cy), (cx+width//2, cy)], fill=EYE_COLOR, width=2)

def draw_eye_closed(d, cx, cy, width=14):
    d.rectangle([cx-width//2, cy-1, cx+width//2, cy+1], fill=EYE_COLOR)

def frame_thinking():
    """Thinking face — eyes look up-left, closed mouth, no smile"""
    def draw(d, img):
        draw_eye(d, EYE_L[0], EYE_L[1], 14)
        draw_eye(d, EYE_R[0], EYE_R[1], 14)
        draw_pupil(d, EYE_L[0]-3, EYE_L[1]-3, 5)
        draw_pupil(d, EYE_R[0]-3, EYE_R[1]-3, 5)
        draw_mouth_closed(d)
    return make_frame(draw)

def frame_happy(lx=0, ly=0):
    def draw(d, img):
        draw_eye(d, EYE_L[0], EYE_L[1], 14)
        draw_eye(d, EYE_R[0], EYE_R[1], 14)
        draw_pupil(d, EYE_L[0]+lx, EYE_L[1]+ly, 5)
        draw_pupil(d, EYE_R[0]+lx, EYE_R[1]+ly, 5)
        draw_smile(d)
    return make_frame(draw)

def frame_talk_open(lx=0, ly=0):
    def draw(d, img):
        draw_eye(d, EYE_L[0], EYE_L[1], 14)
        draw_eye(d, EYE_R[0], EYE_R[1], 14)
        draw_pupil(d, EYE_L[0]+lx, EYE_L[1]+ly, 5)
        draw_pupil(d, EYE_R[0]+lx, EYE_R[1]+ly, 5)
        draw_mouth_open(d)
    return make_frame(draw)

def frame_talk_half(lx=0, ly=0):
    def draw(d, img):
        draw_eye(d, EYE_L[0], EYE_L[1], 14)
        draw_eye(d, EYE_R[0], EYE_R[1], 14)
        draw_pupil(d, EYE_L[0]+lx, EYE_L[1]+ly, 5)
        draw_pupil(d, EYE_R[0]+lx, EYE_R[1]+ly, 5)
        draw_mouth_half(d)
    return make_frame(draw)

def frame_talk_wide(lx=0, ly=0):
    def draw(d, img):
        draw_eye(d, EYE_L[0], EYE_L[1], 14)
        draw_eye(d, EYE_R[0], EYE_R[1], 14)
        draw_pupil(d, EYE_L[0]+lx, EYE_L[1]+ly, 5)
        draw_pupil(d, EYE_R[0]+lx, EYE_R[1]+ly, 5)
        draw_mouth_wide(d)
    return make_frame(draw)

def frame_talk_closed(lx=0, ly=0):
    def draw(d, img):
        draw_eye(d, EYE_L[0], EYE_L[1], 14)
        draw_eye(d, EYE_R[0], EYE_R[1], 14)
        draw_pupil(d, EYE_L[0]+lx, EYE_L[1]+ly, 5)
        draw_pupil(d, EYE_R[0]+lx, EYE_R[1]+ly, 5)
        draw_mouth_closed(d)
    return make_frame(draw)

def frame_blink_closed():
    def draw(d, img):
        draw_eye_closed(d, EYE_L[0], EYE_L[1])
        draw_eye_closed(d, EYE_R[0], EYE_R[1])
        draw_smile(d)
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
async def clear_zone(c, y_start, y_end):
    for y in range(y_start, y_end):
        await c.write_gatt_char(WC, pkt(rc(8, y, 56, y, 0, 0, 10)), response=False)

async def draw_zone(c, img, y_start, y_end, clear=True):
    if clear:
        # Single clear rect for whole zone instead of row-by-row
        await c.write_gatt_char(WC, pkt(rc(8, y_start, 56, y_end - 1, 0, 0, 10)), response=False)
    rects = frame_to_rects(img)
    for r in rects:
        y = struct.unpack_from('<H', r, 9)[0]
        if y_start <= y <= y_end:
            await c.write_gatt_char(WC, pkt(r), response=False)

async def clear_full(c):
    for y in range(64):
        await c.write_gatt_char(WC, pkt(rc(0, y, 63, y, 0, 0, 10)), response=False)

async def draw_full(c, img):
    await clear_full(c)
    rects = frame_to_rects(img)
    for r in rects:
        await c.write_gatt_char(WC, pkt(r), response=False)
        await asyncio.sleep(0.012)

async def kill_demo(c):
    for cmd in DEMO_KILL:
        await c.write_gatt_char(WC, cmd, response=False)
        await asyncio.sleep(0.15)
    await asyncio.sleep(0.5)


# --- Main speak-with-face ---
async def speak_with_face(text):
    from bleak import BleakClient

    chars = len(text)
    est = estimate_duration(chars)
    print(f"Speaking: {chars} chars, est {est:.1f}s", flush=True)

    # Mute ears
    with open(MUTE_FILE, "w") as f:
        f.write("speaking")

    try:
        async with BleakClient(ADDR, timeout=15) as c:
            await c.start_notify(NC, lambda s, d: None)
            await kill_demo(c)

            # Show thinking face while TTS loads
            await draw_full(c, frame_thinking())

            # Clean old signal
            if os.path.exists(SIGNAL_FILE):
                os.remove(SIGNAL_FILE)

            # Start speech in background
            done = threading.Event()
            def speak_fn():
                try:
                    subprocess.run(["node", SPEAK_SCRIPT, text], timeout=120, capture_output=True)
                except: pass
                done.set()
            threading.Thread(target=speak_fn, daemon=True).start()

            # Wait for signal file
            wait_start = time.time()
            while not os.path.exists(SIGNAL_FILE) and time.time() - wait_start < 15:
                await asyncio.sleep(0.05)

            word_times = []
            if os.path.exists(SIGNAL_FILE):
                print(f"  Audio started after {time.time()-wait_start:.1f}s", flush=True)
                # Read word timing for mouth animation (but keep formula for duration)
                # API duration includes trailing silence — formula is more accurate
                try:
                    with open(SIGNAL_FILE, 'r') as sf:
                        sig = json.loads(sf.read())
                    word_times = sig.get('words', [])
                    if word_times:
                        # Scale word timestamps to fit formula duration
                        api_dur = sig.get('exactDurationSec', est)
                        if api_dur > 0:
                            scale = est / api_dur
                            for wt in word_times:
                                wt['s'] *= scale
                                wt['e'] *= scale
                        print(f"  Word timing: {len(word_times)} words (scaled to {est:.1f}s)", flush=True)
                except:
                    pass

            # Switch from thinking face to talking — redraw eyes to center
            await draw_zone(c, frame_happy(), 14, 34)

            # Animate mouth using word-level timing (or random fallback)
            open_shapes = [frame_talk_open, frame_talk_half, frame_talk_wide]
            mouth_start = time.time()
            frame_count = 0
            look_x, look_y = 0, 0
            last_eye_shift = mouth_start
            next_eye_shift = random.uniform(2.5, 5.0)
            last_blink = mouth_start
            next_blink = random.uniform(5, 9)

            while (time.time() - mouth_start) < est:
                now = time.time()
                elapsed = now - mouth_start

                # Eye shift
                if now - last_eye_shift > next_eye_shift:
                    look_x = random.choice([-3, -2, 0, 0, 2, 3])
                    look_y = random.choice([-1, 0, 0, 1])
                    last_eye_shift = now
                    next_eye_shift = random.uniform(2.5, 5.0)

                # Blink
                if now - last_blink > next_blink:
                    await draw_zone(c, frame_blink_closed(), 14, 34)
                    await asyncio.sleep(0.15)
                    last_blink = now
                    next_blink = random.uniform(5, 9)

                # Mouth — word-level: open during words, closed in gaps
                if word_times:
                    in_word = False
                    for wt in word_times:
                        if wt['s'] <= elapsed <= wt['e']:
                            in_word = True
                            break
                    if in_word:
                        shape = random.choice(open_shapes)
                        await draw_zone(c, shape(look_x, look_y), 36, 60)
                    else:
                        await draw_zone(c, frame_talk_closed(look_x, look_y), 36, 60)
                else:
                    # Fallback: random mouth shapes
                    idx = random.choices([0, 1, 2, 3], weights=[3, 2, 1, 2])[0]
                    shapes = [frame_talk_open, frame_talk_half, frame_talk_wide, frame_talk_closed]
                    await draw_zone(c, shapes[idx](look_x, look_y), 36, 60)

                if look_x != 0 or look_y != 0:
                    await draw_zone(c, frame_happy(look_x, look_y), 14, 34)

                frame_count += 1
                await asyncio.sleep(random.uniform(0.08, 0.12))

            # Return to smile — always reset full face
            await draw_full(c, frame_happy())

            total = time.time() - mouth_start
            print(f"  Mouth done: {frame_count} frames in {total:.1f}s (est {est:.1f}s)", flush=True)

            try:
                await c.stop_notify(NC)
            except Exception:
                pass  # Cleanup error — speech already done, ignore
    except Exception as e:
        # BLE failed before speech started — speak without face
        print(f"  BLE error: {e}, speaking without face", flush=True)
        subprocess.run(["node", SPEAK_SCRIPT, text], timeout=120, capture_output=True)
    finally:
        # Unmute ears quickly after speech ends
        time.sleep(0.1)
        try:
            os.remove(MUTE_FILE)
        except: pass


if __name__ == "__main__":
    text = " ".join(sys.argv[1:])
    if not text:
        print("Usage: python respond.py 'text to speak'")
        sys.exit(1)
    asyncio.run(speak_with_face(text))
