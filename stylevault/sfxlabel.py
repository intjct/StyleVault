"""Names the short sound effects (whoosh, pop, click...) with Google's YAMNet model, entirely on this computer.

The model file ships inside the program (models/yamnet.onnx). If it is missing or cannot load,
labels simply stay empty — nothing else breaks."""
from __future__ import annotations

import csv
import os
import subprocess

from . import tools

# AudioSet display name -> plain Thai group name shown in the program
THAI = {}
for _th, _names in {
    "เสียงวูบ (ฟิ้ว)": ["Whoosh, swoosh, swish", "Wind", "Rustling leaves"],
    "เสียงบูม / กระแทก": ["Boom", "Explosion", "Bang", "Thump, thud", "Bass drum", "Rumble", "Thunder", "Slam",
                          "Thunk", "Fireworks", "Gunshot, gunfire"],
    "เสียงป๊อป": ["Burst, pop", "Plop", "Bouncing"],
    "เสียงคลิก": ["Clickety-clack", "Tick", "Tick-tock", "Clicking", "Finger snapping", "Mechanisms", "Clatter"],
    "เสียงพิมพ์ดีด": ["Typing", "Typewriter", "Computer keyboard"],
    "เสียงชัตเตอร์กล้อง": ["Camera", "Single-lens reflex camera"],
    "เสียงติ๊ง / กระดิ่ง": ["Bell", "Ding", "Ding-dong", "Chime", "Wind chime", "Jingle bell", "Tubular bells",
                           "Glockenspiel", "Bicycle bell", "Church bell", "Change ringing (campanology)",
                           "Vibraphone", "Marimba, xylophone", "Doorbell", "Cowbell"],
    "เสียงบี๊บ": ["Beep, bleep", "Static", "Whir", "Chirp tone", "Sine wave", "Buzzer", "Pulse", "Electronic tuner", "Dial tone",
                 "Busy signal", "Synthesizer"],
    "เสียงปรบมือ": ["Clapping", "Applause"],
    "เสียงหัวเราะ": ["Laughter", "Giggle", "Chuckle, chortle", "Belly laugh", "Baby laughter", "Snicker"],
    "เสียงเชียร์ / ฝูงชน": ["Cheering", "Crowd", "Hubbub, speech noise, speech babble", "Children shouting"],
    "เสียงเงิน": ["Cash register", "Coin (dropping)"],
    "เสียงแก้ว / แตก": ["Glass", "Shatter", "Clang", "Chink, clink", "Breaking"],
    "เสียงตบ / แส้": ["Whip", "Slap, smack"],
    "เสียงกลอง": ["Drum", "Snare drum", "Drum kit", "Drum machine", "Cymbal", "Hi-hat", "Percussion",
                  "Drum roll", "Rimshot", "Timpani", "Tabla", "Wood block", "Tambourine", "Gong"],
    "เสียงเคาะ / ประตู": ["Knock", "Door", "Tap", "Sliding door", "Cupboard open or close", "Drawer open or close"],
    "เสียงสแครช": ["Scratching (performance technique)", "Scratch", "Scrape"],
    "เสียงการ์ตูน": ["Boing", "Squeak", "Sound effect", "Zing", "Toot", "Squish", "Hiccup"],
    "เสียงกระดาษ": ["Rustle", "Crumpling, crinkling", "Tearing"],
    "เสียงซิป": ["Zipper (clothing)"],
    "เสียงน้ำ": ["Splash, splatter", "Water", "Drip", "Pour", "Trickle, dribble", "Gurgling", "Liquid"],
    "เสียงหัวใจเต้น": ["Heart sounds, heartbeat", "Heart murmur"],
    "เสียงเตือน / โทรศัพท์": ["Siren", "Alarm", "Alarm clock", "Telephone bell ringing", "Ringtone", "Telephone",
                               "Smoke detector, smoke alarm", "Fire alarm", "Civil defense siren"],
    "เสียงเครื่องยนต์ / รถ": ["Car", "Vehicle", "Engine", "Motorcycle", "Race car, auto racing", "Accelerating, revving, vroom",
                              "Tire squeal", "Skidding", "Car passing by"],
    "เสียงสัตว์": ["Animal", "Dog", "Bark", "Cat", "Meow", "Bird", "Chirp, tweet", "Chicken, rooster", "Duck",
                  "Quack", "Cattle, bovinae", "Moo", "Pig", "Oink"],
    "เสียงพูด": ["Speech", "Child speech, kid speaking",
                "Conversation", "Narration, monologue", "Speech synthesizer", "Whispering", "Shout", "Yell", "Babbling"],
    "เสียงร้องเพลง": ["Singing", "Choir", "Child singing", "Rapping", "Humming",
                      "Synthetic singing", "Vocal music", "A capella"],
    "เสียงเพลง": ["Music", "Pop music", "Hip hop music", "Electronic music", "Techno", "Dubstep", "House music",
                  "Electronic dance music", "Rock music", "Musical instrument", "Piano", "Guitar", "Background music",
                  "Theme music", "Soundtrack music", "Video game music", "Ambient music", "Beatboxing", "Bass guitar",
                  "Electric guitar", "Orchestra", "Classical music", "Jingle (music)", "Christmas music", "Funk",
                  "Drum and bass", "Trance music", "Electronica", "Keyboard (musical)",
                  "Strum", "Plucked string instrument", "Bowed string instrument", "Violin, fiddle", "Brass instrument"],
    "เงียบ": ["Silence"],
}.items():
    for _n in _names:
        THAI.setdefault(_n, _th)

# groups that describe "the whole background" rather than a single sound effect
BACKGROUND = {"เสียงพูด", "เสียงร้องเพลง", "เสียงเพลง", "เงียบ"}
OTHER_TH = "เสียงอื่นๆ"

_session = None
_names: list[str] | None = None
_failed = False


def model_path() -> str:
    env = os.environ.get("STYLEVAULT_YAMNET")
    if env:
        return env
    for sub in ("models", os.path.join("assets", "models")):
        p = os.path.join(tools.resource_dir(), sub, "yamnet.onnx")
        if os.path.isfile(p):
            return p
    return os.path.join(tools.resource_dir(), "models", "yamnet.onnx")


def class_map_path() -> str:
    return os.path.join(tools.resource_dir(), "assets", "yamnet_class_map.csv")


def class_names() -> list[str]:
    global _names
    if _names is None:
        with open(class_map_path(), encoding="utf-8") as f:
            _names = [row["display_name"] for row in csv.DictReader(f)]
    return _names


def available() -> bool:
    if _failed or not os.path.isfile(model_path()):
        return False
    try:
        import numpy  # noqa: F401
        import onnxruntime  # noqa: F401
    except Exception:
        return False
    return True


def _load():
    global _session, _failed
    if _session is None:
        try:
            import onnxruntime as ort
            opts = ort.SessionOptions()
            opts.intra_op_num_threads = max(1, min(4, (os.cpu_count() or 2) // 2))
            opts.log_severity_level = 3
            _session = ort.InferenceSession(model_path(), opts, providers=["CPUExecutionProvider"])
        except Exception:
            _failed = True
            raise
    return _session


def read_audio(path: str):
    """Any audio/video file -> 16 kHz mono float32 samples (via the bundled ffmpeg)."""
    import numpy as np
    ff = tools.find_ffmpeg() or "ffmpeg"
    r = subprocess.run([ff, "-v", "error", "-i", path, "-vn", "-ac", "1", "-ar", "16000", "-f", "f32le", "-"],
                       capture_output=True, timeout=60, creationflags=tools.NO_WINDOW)
    return np.frombuffer(r.stdout, dtype=np.float32).copy()


def scores(samples):
    """Average score per AudioSet class over the clip (array of 521)."""
    import numpy as np
    s = _load()
    x = np.asarray(samples, dtype=np.float32).reshape(-1)
    if x.size < 15600:                                   # the model needs at least 0.975 s
        x = np.pad(x, (0, 15600 - x.size))
    out = s.run(None, {s.get_inputs()[0].name: x})[0]
    out = np.asarray(out, dtype=np.float32)
    return out.reshape(-1, out.shape[-1]).mean(axis=0)


def pick(score_row) -> tuple[str, str, float]:
    """(English class, Thai group, confidence). Prefers a real sound effect over 'music'/'speech' in the background."""
    names = class_names()
    order = sorted(range(len(score_row)), key=lambda i: -float(score_row[i]))
    top = order[0]
    best_fx = next((i for i in order[:25] if THAI.get(names[i], OTHER_TH) not in BACKGROUND), None)
    choice = top
    if best_fx is not None:
        fx = float(score_row[best_fx])
        if fx >= 0.08 or fx >= 0.5 * float(score_row[top]):
            choice = best_fx
    name = names[choice]
    return name, THAI.get(name, OTHER_TH), round(float(score_row[choice]), 2)


def label_file(path: str) -> tuple[str, str, float] | None:
    x = read_audio(path)
    if x.size == 0:
        return None
    return pick(scores(x))


def label_sfx(raw_dir: str, sfx: list[dict]) -> int:
    """Fills label / label_th / confidence in-place for every sound-effect snippet. Returns how many got a label."""
    n = 0
    for item in sfx:
        p = os.path.join(raw_dir, item.get("file") or "")
        if not os.path.isfile(p):
            continue
        try:
            res = label_file(p)
        except Exception:
            if _failed:
                break
            continue
        if res:
            item["label"], item["label_th"], item["confidence"] = res
            n += 1
    return n
