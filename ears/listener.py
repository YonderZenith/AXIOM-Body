"""
AXIOM Ears — Continuous Listening with Relevance Filtering
============================================================
Listens to microphone via persistent audio stream, transcribes with Whisper,
decides if speech is directed at AXIOM or background chatter.

Uses a continuous InputStream (no open/close per chunk) so the mic light
stays solid and no audio is dropped between reads.

Usage:
  python listener.py              # Auto-detect microphone by name (survives reboots)
  python listener.py --device 1   # Override with specific index
"""
import os
import sys
import time
import json
import wave
import queue
import threading
import argparse
from datetime import datetime

import numpy as np
import sounddevice as sd
import torch
import whisper

# Ensure ffmpeg is on PATH before running
# Install via your package manager (e.g. apt install ffmpeg, brew install ffmpeg,
# or winget install ffmpeg on Windows) and ensure it is available on PATH.

# --- Config ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
HEARD_FILE = os.path.join(BASE_DIR, "heard.txt")
FLAG_FILE = os.path.join(BASE_DIR, "new-speech.flag")
LOG_FILE = os.path.join(BASE_DIR, "listener-log.txt")
ALL_HEARD_FILE = os.path.join(BASE_DIR, "all-heard.txt")
STREAM_FILE = os.path.join(BASE_DIR, "heard-stream.txt")  # Rolling transcript log for brain

SCENE_FILE = os.path.join(BASE_DIR, "scene.json")

SAMPLE_RATE = 16000
FRAME_MS = 30
MUTE_FILE = os.path.join(BASE_DIR, "mute.flag")  # Brain writes this while speaking
FRAME_SAMPLES = int(SAMPLE_RATE * FRAME_MS / 1000)  # 480
CHANNELS = 1

# VAD / recording settings
SILERO_THRESHOLD = 0.5  # Silero VAD confidence threshold (0-1, higher = stricter)
SPEECH_FRAMES_START = 4  # Fewer needed since Silero is more accurate
SILENCE_FRAMES_STOP = 15  # 15 chunks * 100ms = 1.5s of silence before stop
MIN_SPEECH_SECONDS = 0.8
MAX_SPEECH_SECONDS = 30
AMP_GATE = 0.06  # High gate — only close-mic voice passes, TV bleed filtered out
CHUNK_DURATION = 0.1  # 100ms chunks from the stream
CHUNK_SAMPLES = int(SAMPLE_RATE * CHUNK_DURATION)  # 1600

# Relevance keywords
WAKE_WORDS = [
    "axiom", "axium", "action", "accent", "axon", "aksim",
    "hey axiom", "yo axiom", "okay axiom",
]

COMMAND_PATTERNS = [
    "say something", "tell me", "what do you", "can you", "do you",
    "turn off", "turn on", "shut down", "wake up", "go to sleep",
    "what is", "what's", "how do", "how does", "explain",
    "show me", "look at", "check", "run", "start", "stop",
    "body on", "body off", "face on", "face off",
    "talk to me", "speak", "respond", "answer",
    "your face", "your eyes", "your mouth", "your body",
    "good job", "nice", "perfect", "cool", "sick",
    "qis", "protocol", "quadratic", "swarm",
]

BACKGROUND_PATTERNS = [
    "phone", "calling", "hey google", "hey siri", "alexa",
    "what time", "dinner", "lunch", "bathroom",
]


def log(msg):
    ts = datetime.now().strftime("%H:%M:%S")
    line = f"[{ts}] {msg}"
    try:
        print(line, flush=True)
    except UnicodeEncodeError:
        print(line.encode('ascii', 'replace').decode(), flush=True)
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except:
        pass


def classify_relevance(text, people_present=True):
    lower = text.lower().strip()
    if len(lower) < 3:
        return False, "low", "too short"
    for wake in WAKE_WORDS:
        if wake in lower:
            return True, "high", f"wake word: {wake}"
    for pattern in COMMAND_PATTERNS:
        if pattern in lower:
            return True, "medium", f"command pattern: {pattern}"
    for bg in BACKGROUND_PATTERNS:
        if bg in lower:
            return False, "medium", f"background: {bg}"
    # When someone's on camera, ears are only on because we SEE them
    # So almost everything heard is directed at us — be lenient
    if people_present:
        if len(lower) > 5:
            return True, "medium", "person present, assuming directed"
        if lower.endswith("?"):
            return True, "medium", "person present, question"
    if lower.endswith("?") and len(lower) > 15:
        return True, "low", "question detected"
    if len(lower) > 100:
        return False, "low", "long background speech"
    if 10 < len(lower) < 80:
        return True, "low", "conversational length, assuming directed"
    return False, "low", "no relevance signals"


def save_heard(text, confidence, reason):
    entry = {
        "text": text,
        "timestamp": datetime.now().isoformat(),
        "confidence": confidence,
        "reason": reason,
    }
    with open(HEARD_FILE, "w", encoding="utf-8") as f:
        json.dump(entry, f, indent=2)


def save_all_heard(text, relevant, confidence, reason):
    ts = datetime.now().strftime("%H:%M:%S")
    tag = "RELEVANT" if relevant else "BACKGROUND"
    try:
        with open(ALL_HEARD_FILE, "a", encoding="utf-8") as f:
            f.write(f"[{ts}] [{tag}/{confidence}] {text} ({reason})\n")
    except:
        pass


def transcribe(model, audio_float32):
    """Transcribe float32 audio array with Whisper"""
    tmp_path = os.path.join(BASE_DIR, f"heard-{int(time.time())}.wav")
    try:
        with wave.open(tmp_path, 'wb') as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(SAMPLE_RATE)
            audio_int16 = (audio_float32 * 32767).astype(np.int16)
            wf.writeframes(audio_int16.tobytes())
        result = model.transcribe(tmp_path, language="en", fp16=False,
                                   no_speech_threshold=0.3)
        return result["text"].strip()
    except Exception as e:
        log(f"Transcribe error: {e}")
        return None
    finally:
        try:
            os.unlink(tmp_path)
        except:
            pass


HALLUCINATIONS = {
    "thank you", "thanks for watching", "subscribe",
    "you", ".", "...", "bye", "the end",
    "thank you for watching", "please subscribe",
    "", " ",
}


_last_person_seen = 0  # Timestamp of last camera person detection
WAKE_COOLDOWN = 90     # Stay awake 90s after last person detected

def check_people_present():
    """Check scene.json for people presence. Stays awake for 90s after last detection."""
    global _last_person_seen
    if not os.path.exists(SCENE_FILE):
        return True  # If no scene data, assume someone might be there
    try:
        with open(SCENE_FILE, 'r', encoding='utf-8') as f:
            scene = json.load(f)
        if scene.get("people_count", 0) > 0:
            _last_person_seen = time.time()
            return True
        # Cooldown — stay awake for 90s after person leaves
        if time.time() - _last_person_seen < WAKE_COOLDOWN:
            return True
        return False
    except:
        return True  # On error, default to listening


def find_microphone():
    """Find a working microphone device by actually testing each candidate."""
    devices = sd.query_devices()
    candidates = []
    for i, d in enumerate(devices):
        if d['max_input_channels'] > 0:
            candidates.append(i)
    # Test each candidate — return the first that actually opens at 16kHz
    for i in candidates:
        try:
            test = sd.rec(1600, samplerate=SAMPLE_RATE, channels=1, device=i, dtype='float32')
            sd.wait()
            log(f"Device {i} ({devices[i]['name']}) - OK")
            return i
        except Exception as e:
            log(f"Device {i} ({devices[i]['name']}) - failed: {e}")
    return None


def main():
    parser = argparse.ArgumentParser(description="AXIOM Ears")
    parser.add_argument("--device", type=int, default=None)
    parser.add_argument("--model", default="small.en")
    args = parser.parse_args()

    device = args.device
    if device is None:
        device = find_microphone()
        if device is None:
            log("No preferred mic found, using default")
        else:
            log(f"Found microphone at device {device}")

    device_info = sd.query_devices(device, 'input')
    log(f"Using: {device_info['name']}")

    log(f"Loading Whisper model '{args.model}'...")
    model = whisper.load_model(args.model)
    log("Whisper model loaded")

    # Load Silero VAD — neural network, much better than webrtcvad at rejecting TV/noise
    log("Loading Silero VAD model...")
    silero_model, silero_utils = torch.hub.load(repo_or_dir='snakers4/silero-vad',
                                                  model='silero_vad',
                                                  force_reload=False,
                                                  trust_repo=True)
    log("Silero VAD loaded")

    # Audio queue — stream callback pushes chunks, main loop pulls them
    audio_q = queue.Queue()

    def audio_callback(indata, frames, time_info, status):
        """Called by sounddevice for each audio block. Runs in a separate thread."""
        if status:
            log(f"Stream status: {status}")
        # Copy the data so it persists after callback returns
        audio_q.put(indata[:, 0].copy())

    # Recording state
    speech_frames = 0
    silence_frames = 0
    recording = False
    record_start = 0
    audio_buffer = []

    ears_awake = True  # Track state for logging transitions
    log(f"Ears active. Silero VAD threshold {SILERO_THRESHOLD}, amp gate {AMP_GATE}")
    log("Opening persistent audio stream...")

    # Open a PERSISTENT input stream — mic light stays solid, no dropped audio
    with sd.InputStream(samplerate=SAMPLE_RATE, channels=CHANNELS,
                        device=device, dtype='float32',
                        blocksize=CHUNK_SAMPLES,
                        callback=audio_callback):
        log("Stream open. Listening...")

        while True:
            try:
                # Check mute flag — drain and discard audio while AXIOM is speaking
                if os.path.exists(MUTE_FILE):
                    while not audio_q.empty():
                        try:
                            audio_q.get_nowait()
                        except queue.Empty:
                            break
                    time.sleep(0.1)
                    speech_frames = 0
                    silence_frames = 0
                    recording = False
                    audio_buffer = []
                    continue

                # Sleep mode — no people on camera
                if not check_people_present():
                    # If we recently woke on sound, stay awake for a bit to process audio
                    if ears_awake and hasattr(main, '_sound_wake_time') and time.time() - main._sound_wake_time < 10:
                        pass  # Stay awake — sound-wake cooldown active
                    elif ears_awake:
                        log("Ears sleeping — no people on camera")
                        ears_awake = False

                    if not ears_awake:
                        # Still sample audio — if loud sound detected, wake up
                        # (camera updates every 10s, someone could walk in and talk)
                        try:
                            sleep_audio = audio_q.get(timeout=1.0)
                            sleep_amp = np.max(np.abs(sleep_audio))
                            if sleep_amp > AMP_GATE:
                                # Loud audio while sleeping — wake up on sound
                                log(f"Ears waking on sound (amp={sleep_amp:.3f}) — camera may be behind")
                                ears_awake = True
                                main._sound_wake_time = time.time()
                                # Don't drain — this audio chunk might be speech
                                # Put it back so the main loop processes it
                                audio_q.put(sleep_audio)
                            else:
                                # Quiet — drain and stay asleep
                                while not audio_q.empty():
                                    try:
                                        audio_q.get_nowait()
                                    except queue.Empty:
                                        break
                                speech_frames = 0
                                silence_frames = 0
                                recording = False
                                audio_buffer = []
                                continue
                        except queue.Empty:
                            continue
                elif not ears_awake:
                    log("Ears waking up — person detected on camera")
                    ears_awake = True

                # Get next audio chunk (blocks up to 0.1s, then loops to check mute)
                try:
                    audio_float = audio_q.get(timeout=0.1)
                except queue.Empty:
                    continue

                # Amplitude gate — skip if below noise floor
                chunk_amp = np.max(np.abs(audio_float))
                if chunk_amp < AMP_GATE:
                    silence_frames += 1
                    if not recording:
                        if silence_frames > 10:
                            speech_frames = 0
                        continue
                    # Recording + below gate = count silence, skip VAD
                    # Stop-recording check happens below at the normal spot
                else:
                    # Run Silero VAD on 512-sample windows (Silero requires exactly 512 at 16kHz)
                    chunk_has_speech = False
                    try:
                        for i in range(0, len(audio_float) - 512 + 1, 512):
                            window = torch.from_numpy(audio_float[i:i+512]).float()
                            confidence = silero_model(window, SAMPLE_RATE).item()
                            if confidence > SILERO_THRESHOLD:
                                chunk_has_speech = True
                                break
                    except Exception as e:
                        log(f"VAD error: {e}")
                        silero_model.reset_states()

                    if chunk_has_speech:
                        speech_frames += 1
                        silence_frames = 0
                    else:
                        silence_frames += 1

                # Start recording
                if not recording and speech_frames >= SPEECH_FRAMES_START:
                    recording = True
                    record_start = time.time()
                    audio_buffer = []
                    log("Speech detected, recording...")

                # Buffer audio while recording
                if recording:
                    audio_buffer.append(audio_float)

                    # Stop on silence
                    if silence_frames >= SILENCE_FRAMES_STOP:
                        recording = False
                        duration = time.time() - record_start
                        speech_frames = 0
                        silence_frames = 0

                        if duration >= MIN_SPEECH_SECONDS:
                            full_audio = np.concatenate(audio_buffer)
                            # Energy pre-filter — skip if clip is mostly silence
                            rms = np.sqrt(np.mean(full_audio ** 2))
                            if rms < 0.01:
                                log(f"Clip too quiet (RMS={rms:.4f}), skipped")
                                audio_buffer = []
                                continue
                            log(f"Recording done: {duration:.1f}s (RMS={rms:.3f}), transcribing...")
                            text = transcribe(model, full_audio)

                            if text and text.strip().lower() not in HALLUCINATIONS:
                                ts_now = datetime.now()
                                # Append to rolling stream log — brain reads this
                                try:
                                    with open(STREAM_FILE, "a", encoding="utf-8") as sf:
                                        sf.write(f"[{ts_now.strftime('%H:%M:%S')}] {text}\n")
                                except:
                                    pass
                                # Also save to heard.txt (latest utterance)
                                save_heard(text, "stream", "transcribed")
                                # Write flag for brain — new speech available
                                try:
                                    with open(FLAG_FILE, 'w', encoding='utf-8') as ff:
                                        json.dump({
                                            "text": text,
                                            "timestamp": ts_now.isoformat(),
                                            "source": "stream",
                                        }, ff, indent=2)
                                except:
                                    pass
                                log(f">> HEARD: {text}")
                                # Also log to all-heard for history
                                try:
                                    with open(ALL_HEARD_FILE, "a", encoding="utf-8") as af:
                                        af.write(f"[{ts_now.strftime('%H:%M:%S')}] {text}\n")
                                except:
                                    pass
                            else:
                                log(f"-- Filtered: {text}")
                        else:
                            log(f"Too short ({duration:.1f}s), skipped")

                        audio_buffer = []

                    # Safety cutoff — transcribe what we have instead of throwing it away
                    if time.time() - record_start > MAX_SPEECH_SECONDS:
                        recording = False
                        speech_frames = 0
                        silence_frames = 0
                        silero_model.reset_states()
                        if audio_buffer:
                            log(f"Cutoff at {MAX_SPEECH_SECONDS}s, transcribing...")
                            full_audio = np.concatenate(audio_buffer)
                            text = transcribe(model, full_audio)
                            if text and text.strip().lower() not in HALLUCINATIONS:
                                ts_now = datetime.now()
                                try:
                                    with open(STREAM_FILE, "a", encoding="utf-8") as sf:
                                        sf.write(f"[{ts_now.strftime('%H:%M:%S')}] {text}\n")
                                except:
                                    pass
                                save_heard(text, "stream", "transcribed")
                                try:
                                    with open(FLAG_FILE, 'w', encoding='utf-8') as ff:
                                        json.dump({
                                            "text": text,
                                            "timestamp": ts_now.isoformat(),
                                            "source": "stream",
                                        }, ff, indent=2)
                                except:
                                    pass
                                log(f">> HEARD: {text}")
                            else:
                                log(f"-- Filtered: {text}")
                        audio_buffer = []

                # Reset speech counter if lots of silence without recording
                if not recording and silence_frames > 10:
                    speech_frames = 0

            except KeyboardInterrupt:
                log("Stopped by user")
                break
            except Exception as e:
                log(f"Error: {e}")
                time.sleep(1)


if __name__ == "__main__":
    main()
