"""
AXIOM Voice Loop — Fast listening daemon
==========================================
Replaces listener.py with a tighter, faster pipeline:
- faster-whisper (CTranslate2 optimized) instead of openai whisper
- Tighter silence detection (1.2s)
- Writes to same shared files (heard-stream.txt, new-speech.flag)
- Brain (main AXIOM session) reads these and decides responses

Usage:
  python voice_loop.py
  python voice_loop.py --device 1
"""
import os
import sys
import time
import json
import queue
import threading
import argparse
import numpy as np
import sounddevice as sd
import torch
from datetime import datetime

# Ensure ffmpeg is on PATH before running
# Install via your package manager (e.g. apt install ffmpeg, brew install ffmpeg,
# or winget install ffmpeg on Windows) and ensure it is available on PATH.

# --- Config ---
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EARS_DIR = os.path.join(BASE_DIR, "axiom", "ears")
SCENE_FILE = os.path.join(EARS_DIR, "scene.json")
STREAM_FILE = os.path.join(EARS_DIR, "heard-stream.txt")
ALL_HEARD_FILE = os.path.join(EARS_DIR, "all-heard.txt")
HEARD_FILE = os.path.join(EARS_DIR, "heard.txt")
FLAG_FILE = os.path.join(EARS_DIR, "new-speech.flag")
LOG_FILE = os.path.join(EARS_DIR, "voice-loop-log.txt")
MUTE_FILE = os.path.join(EARS_DIR, "mute.flag")

SAMPLE_RATE = 16000
CHANNELS = 1
AMP_GATE = 0.06
SILERO_THRESHOLD = 0.5
SILENCE_CHUNKS = 12       # 1.2s silence to stop (tighter than old 1.5s)
MAX_SPEECH_SECONDS = 10
MIN_SPEECH_SECONDS = 0.3
WAKE_COOLDOWN = 90

# Whisper hallucination filter
HALLUCINATIONS = {
    "", "you", "thank you", "thanks for watching",
    "the end", "thanks", "bye", "okay",
    "thank you for watching", "subtitles by the amara.org community",
}

_last_person_seen = 0


def log(msg):
    ts = datetime.now().strftime("%H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line, flush=True)
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except:
        pass


def check_people_present():
    global _last_person_seen
    if not os.path.exists(SCENE_FILE):
        return True
    try:
        with open(SCENE_FILE, 'r', encoding='utf-8') as f:
            scene = json.load(f)
        if scene.get("people_count", 0) > 0:
            _last_person_seen = time.time()
            return True
        if time.time() - _last_person_seen < WAKE_COOLDOWN:
            return True
        return False
    except:
        return True


def log_speech(text):
    """Write to all shared files so brain session can see what was heard."""
    ts = datetime.now()
    try:
        with open(STREAM_FILE, "a", encoding="utf-8") as f:
            f.write(f"[{ts.strftime('%H:%M:%S')}] {text}\n")
    except:
        pass
    try:
        with open(HEARD_FILE, "w", encoding="utf-8") as f:
            json.dump({"text": text, "timestamp": ts.isoformat(),
                        "confidence": "stream", "reason": "transcribed"}, f, indent=2)
    except:
        pass
    try:
        with open(FLAG_FILE, "w", encoding="utf-8") as f:
            json.dump({"text": text, "timestamp": ts.isoformat(),
                        "source": "voice_loop"}, f, indent=2)
    except:
        pass
    try:
        with open(ALL_HEARD_FILE, "a", encoding="utf-8") as f:
            f.write(f"[{ts.strftime('%H:%M:%S')}] {text}\n")
    except:
        pass


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--device", type=int, default=None, help="Audio input device index")
    parser.add_argument("--model", type=str, default="small.en",
                        help="faster-whisper model: tiny.en, base.en, small.en, medium.en, turbo")
    args = parser.parse_args()

    log("=== AXIOM Voice Loop starting ===")

    # --- Load faster-whisper ---
    try:
        from faster_whisper import WhisperModel
        log(f"Loading faster-whisper '{args.model}' (CTranslate2)...")
        t0 = time.time()
        whisper_model = WhisperModel(args.model, device="cpu", compute_type="int8")
        log(f"faster-whisper loaded in {time.time()-t0:.1f}s")
        use_faster = True
    except Exception as e:
        log(f"faster-whisper failed ({e}), falling back to openai whisper")
        import whisper
        whisper_model = whisper.load_model(args.model)
        log(f"openai whisper {args.model} loaded")
        use_faster = False

    # --- Load Silero VAD ---
    log("Loading Silero VAD...")
    silero_model, _ = torch.hub.load(repo_or_dir='snakers4/silero-vad',
                                      model='silero_vad', force_reload=False)
    log("Silero VAD loaded")

    # --- Audio queue + stream ---
    audio_q = queue.Queue()

    def audio_callback(indata, frames, time_info, status):
        audio_q.put(indata[:, 0].copy())

    device = args.device
    log(f"Opening mic (device {device})...")
    stream = sd.InputStream(
        samplerate=SAMPLE_RATE, channels=CHANNELS,
        dtype='float32', blocksize=1600,
        device=device, callback=audio_callback
    )
    stream.start()
    log("Mic open. Voice loop active.")

    # --- Transcribe function ---
    def transcribe(audio):
        if use_faster:
            # faster-whisper expects float32 numpy array
            segments, info = whisper_model.transcribe(
                audio, language="en", beam_size=1,
                vad_filter=False,  # We already do VAD
                no_speech_threshold=0.3
            )
            text = " ".join(seg.text for seg in segments).strip()
            return text
        else:
            result = whisper_model.transcribe(
                audio, language="en",
                no_speech_prob=0.3, fp16=False
            )
            return result.get("text", "").strip()

    # --- Main loop state ---
    recording = False
    audio_buffer = []
    speech_frames = 0
    silence_frames = 0
    record_start = 0
    ears_awake = True
    sound_wake_time = 0

    while True:
        try:
            # --- Mute check ---
            if os.path.exists(MUTE_FILE):
                while not audio_q.empty():
                    try: audio_q.get_nowait()
                    except queue.Empty: break
                time.sleep(0.1)
                speech_frames = 0
                silence_frames = 0
                recording = False
                audio_buffer = []
                continue

            # --- Sleep mode ---
            if not check_people_present():
                if ears_awake and (time.time() - sound_wake_time > 10):
                    log("Ears sleeping — no people")
                    ears_awake = False

                if not ears_awake:
                    try:
                        sleep_audio = audio_q.get(timeout=1.0)
                        sleep_amp = np.max(np.abs(sleep_audio))
                        if sleep_amp > AMP_GATE:
                            log(f"Sound wake (amp={sleep_amp:.3f})")
                            ears_awake = True
                            sound_wake_time = time.time()
                            audio_q.put(sleep_audio)
                        else:
                            # Drain queue quietly
                            while not audio_q.empty():
                                try: audio_q.get_nowait()
                                except queue.Empty: break
                            speech_frames = 0
                            silence_frames = 0
                            recording = False
                            audio_buffer = []
                            continue
                    except queue.Empty:
                        continue
            elif not ears_awake:
                log("Ears waking — person detected")
                ears_awake = True

            # --- Get audio chunk ---
            try:
                audio_float = audio_q.get(timeout=0.5)
            except queue.Empty:
                continue

            # --- Amp gate ---
            chunk_amp = np.max(np.abs(audio_float))
            if chunk_amp < AMP_GATE:
                silence_frames += 1
                if not recording:
                    if silence_frames > 10:
                        speech_frames = 0
                    continue
                # Recording + below gate = count as silence, fall through
            else:
                # --- Silero VAD ---
                chunk_has_speech = False
                try:
                    for i in range(0, len(audio_float) - 512 + 1, 512):
                        window = torch.from_numpy(audio_float[i:i + 512]).float()
                        conf = silero_model(window, SAMPLE_RATE).item()
                        if conf > SILERO_THRESHOLD:
                            chunk_has_speech = True
                            break
                except Exception as e:
                    log(f"VAD error: {e}")
                    silero_model.reset_states()

                if chunk_has_speech:
                    speech_frames += 1
                    silence_frames = 0
                    if not recording and speech_frames >= 3:
                        recording = True
                        record_start = time.time()
                        audio_buffer = []
                        log("Recording...")
                else:
                    silence_frames += 1

            # --- Buffer while recording ---
            if recording:
                audio_buffer.append(audio_float)

            # --- Stop recording on silence ---
            if recording and silence_frames >= SILENCE_CHUNKS:
                recording = False
                speech_frames = 0
                silence_frames = 0
                silero_model.reset_states()

                if audio_buffer:
                    duration = time.time() - record_start
                    full_audio = np.concatenate(audio_buffer)
                    rms = np.sqrt(np.mean(full_audio ** 2))

                    if duration < MIN_SPEECH_SECONDS:
                        log(f"Too short ({duration:.1f}s)")
                        audio_buffer = []
                        continue

                    if rms < 0.008:
                        log(f"Too quiet (RMS={rms:.4f})")
                        audio_buffer = []
                        continue

                    # === TRANSCRIBE ===
                    t_start = time.time()
                    text = transcribe(full_audio)
                    t_elapsed = time.time() - t_start

                    if text and text.strip().lower() not in HALLUCINATIONS:
                        log(f">> HEARD ({t_elapsed:.1f}s): {text}")
                        log_speech(text)
                    else:
                        log(f"-- Filtered ({t_elapsed:.1f}s): {text}")

                audio_buffer = []

            # --- Safety cutoff ---
            if recording and time.time() - record_start > MAX_SPEECH_SECONDS:
                recording = False
                speech_frames = 0
                silence_frames = 0
                silero_model.reset_states()
                if audio_buffer:
                    full_audio = np.concatenate(audio_buffer)
                    log(f"Cutoff at {MAX_SPEECH_SECONDS}s, transcribing...")
                    text = transcribe(full_audio)
                    if text and text.strip().lower() not in HALLUCINATIONS:
                        log(f">> HEARD (cutoff): {text}")
                        log_speech(text)
                audio_buffer = []

        except KeyboardInterrupt:
            log("Voice loop stopped")
            break
        except Exception as e:
            log(f"Error: {e}")
            time.sleep(1)


if __name__ == "__main__":
    main()
