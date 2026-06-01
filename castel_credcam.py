from __future__ import annotations

import argparse
import csv
import hashlib
import itertools
import logging
import json
import os
import re
import sys
import unicodedata
import shutil
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime
from functools import lru_cache
from pathlib import Path
from typing import List, Optional, Tuple

import cv2
import numpy as np


APP_TITLE = "CastelCredCam"
WINDOW_NAME = "CastelCredCam Preview"
PHOTOS_DIRNAME = "fotos"
BACKUP_PHOTOS_DIRNAME = "fotos_respaldo"
TEST_FOLDER_NAME = "_pruebas"
CSV_FILENAME = "index.csv"
RETAKE_AUDIT_FILENAME = "retakes.csv"
MAX_CAMERA_INDEX = 12
WARMUP_FRAMES = 12
CAMERA_RESOLUTION_FILENAME = "camera_resolution.json"
CAMERA_BACKENDS = [
    ("DirectShow", cv2.CAP_DSHOW),
    ("MediaFoundation", cv2.CAP_MSMF),
    ("Automatico", cv2.CAP_ANY),
]
BACKEND_LOOKUP = {
    "dshow": ("DirectShow", cv2.CAP_DSHOW),
    "msmf": ("MediaFoundation", cv2.CAP_MSMF),
    "any": ("Automatico", cv2.CAP_ANY),
}
MIN_FRAME_STD = 3.0
TEXT_FONT = cv2.FONT_HERSHEY_SIMPLEX
TEXT_SCALE = 0.58
TEXT_THICKNESS = 1
TEXT_LINE = 21
AUTOFRAME_TARGET_SIZE = (1500, 2000)
AUTOFRAME_MAX_DETECT_WIDTH = 1280
AUTOFRAME_FAST_DETECT_WIDTH = 720
AUTOFRAME_MIN_FACE_SIZE = 36
AUTOFRAME_MIN_EYE_W = 12
AUTOFRAME_MIN_EYE_H = 8
AUTOFRAME_FACE_EXPANSION = 1.85
AUTOFRAME_FACE_HEIGHT_RATIO = 0.60
AUTOFRAME_EYE_TOP_RATIO = 0.24
AUTOFRAME_HEADROOM_RATIO = 0.42
AUTOFRAME_CHEST_MARGIN_RATIO = 0.10
AUTOFRAME_FALLBACK_HEIGHT_RATIO = 0.82
AUTOFRAME_MIN_EYE_SEPARATION_RATIO = 0.18
AUTOFRAME_MAX_EYE_SEPARATION_RATIO = 0.68
AUTOFRAME_MAX_EYE_LEVEL_DELTA_RATIO = 0.14
AUTOFRAME_MAX_UNIQUE_CANDIDATES = 12
AUTOFRAME_FAST_MAX_UNIQUE_CANDIDATES = 6
PREFERRED_CAMERA_RESOLUTIONS = [
    (1280, 720),
    (1920, 1080),
    (1600, 1200),
    (1280, 960),
    (960, 720),
    (640, 480),
    (640, 360),
    (2560, 1440),
]
CAMERA_ALIASES_FILENAME = "camera_aliases.json"
LAST_CAMERA_FILENAME = "last_camera.json"
LOGS_DIRNAME = "logs"


def get_logs_dir(app_dir: Path) -> Path:
    return app_dir / LOGS_DIRNAME


def setup_logging(app_dir: Path, component: str) -> tuple[logging.Logger, Path]:
    logs_dir = get_logs_dir(app_dir)
    logs_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_path = logs_dir / f"{component}_{stamp}_{os.getpid()}.log"

    logger = logging.getLogger(f"CastelCredCam.{component}")
    logger.setLevel(logging.DEBUG)
    logger.handlers.clear()
    logger.propagate = False

    formatter = logging.Formatter(
        "%(asctime)s | %(levelname)s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    file_handler = logging.FileHandler(log_path, encoding="utf-8")
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    stream_handler = logging.StreamHandler(sys.stdout)
    stream_handler.setLevel(logging.INFO)
    stream_handler.setFormatter(formatter)
    logger.addHandler(stream_handler)

    return logger, log_path


@dataclass
class PhotoRecord:
    id: int
    filename: str
    student_name: str
    course: str
    timestamp: str
    rut: str = ""


def _photo_record_key(record: PhotoRecord) -> tuple[str, str, str, str]:
    return (
        record.filename.strip(),
        record.student_name.strip(),
        record.course.strip(),
        record.rut.strip(),
    )


@dataclass
class SessionContext:
    mode: str
    course_display: str
    course_slug: str
    photos_root: Path
    backup_root: Path
    session_dir: Path
    backup_dir: Path
    csv_path: Path
    records: List[PhotoRecord]
    session_started_at: datetime

    @property
    def next_id(self) -> int:
        return len(self.records) + 1

    def filename_for(self, photo_id: int) -> str:
        prefix = "PRUEBA" if self.mode == "test" else self.course_slug
        return f"{prefix}_{photo_id:03d}.jpg"


def silence_opencv_logs() -> None:
    try:
        cv2.utils.logging.setLogLevel(cv2.utils.logging.LOG_LEVEL_ERROR)
    except Exception:
        pass


@contextmanager
def suppress_native_stderr():
    stderr = None
    duplicated = None
    try:
        stderr = sys.stderr.fileno()
        duplicated = os.dup(stderr)
        with open(os.devnull, "w") as devnull:
            os.dup2(devnull.fileno(), stderr)
            yield
    except Exception:
        yield
    finally:
        try:
            if duplicated is not None and stderr is not None:
                os.dup2(duplicated, stderr)
                os.close(duplicated)
        except Exception:
            pass


def load_last_camera(app_dir: Path) -> tuple[Optional[int], Optional[str]]:
    path = app_dir / LAST_CAMERA_FILENAME
    if not path.exists():
        return None, None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        index = payload.get("index")
        backend = payload.get("backend")
        if isinstance(index, int) and isinstance(backend, str):
            return index, backend.lower()
    except Exception:
        pass
    return None, None


def save_last_camera(app_dir: Path, index: int, backend_key: str) -> None:
    path = app_dir / LAST_CAMERA_FILENAME
    payload = {"index": index, "backend": backend_key}
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _camera_resolution_key(index: int, backend_key: str) -> str:
    return f"{index}:{backend_key.lower()}"


def load_camera_resolution(app_dir: Path, index: int, backend_key: str) -> Optional[tuple[int, int]]:
    path = app_dir / CAMERA_RESOLUTION_FILENAME
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None

    item = payload.get(_camera_resolution_key(index, backend_key))
    if not isinstance(item, dict):
        return None
    try:
        width = int(item.get("width"))
        height = int(item.get("height"))
    except Exception:
        return None
    if width <= 0 or height <= 0:
        return None
    return width, height


def save_camera_resolution(app_dir: Path, index: int, backend_key: str, resolution: Optional[tuple[int, int]]) -> None:
    path = app_dir / CAMERA_RESOLUTION_FILENAME
    payload: dict[str, dict[str, int]] = {}
    if path.exists():
        try:
            loaded = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(loaded, dict):
                payload = {
                    key: value
                    for key, value in loaded.items()
                    if isinstance(key, str) and isinstance(value, dict)
                }
        except Exception:
            payload = {}

    key = _camera_resolution_key(index, backend_key)
    if resolution is None:
        payload.pop(key, None)
    else:
        width, height = resolution
        payload[key] = {"width": int(width), "height": int(height)}

    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def load_camera_aliases(app_dir: Path) -> dict[tuple[int, str], str]:
    alias_path = app_dir / CAMERA_ALIASES_FILENAME
    if not alias_path.exists():
        return {}

    try:
        payload = json.loads(alias_path.read_text(encoding="utf-8"))
    except Exception:
        return {}

    aliases: dict[tuple[int, str], str] = {}
    for item in payload.get("aliases", []):
        try:
            index = int(item["index"])
            backend = str(item["backend"]).lower()
            label = str(item["label"]).strip()
        except Exception:
            continue
        if label:
            aliases[(index, backend)] = label
    return aliases


def get_camera_alias(aliases: dict[tuple[int, str], str], index: int, backend_id: int) -> str:
    backend_key = next((key for key, value in BACKEND_LOOKUP.items() if value[1] == backend_id), "any")
    return aliases.get((index, backend_key), f"Camara {index}")


def backend_key_from_id(backend_id: int) -> str:
    for key, value in BACKEND_LOOKUP.items():
        if value[1] == backend_id:
            return key
    return "any"


def backend_name_from_id(backend_id: int) -> str:
    for name, value in CAMERA_BACKENDS:
        if value == backend_id:
            return name
    return "Automatico"


def camera_priority(alias: str, backend_name: str) -> tuple[int, int]:
    alias_lower = alias.lower()
    if "obs" in alias_lower or "virtual camera" in alias_lower:
        score = 0
    elif "droid" in alias_lower:
        score = 1
    elif "camo" in alias_lower:
        score = 2
    elif "ivcam" in alias_lower:
        score = 3
    elif "laptop" in alias_lower or "integrated" in alias_lower:
        score = 6
    elif "inestable" in alias_lower:
        score = 9
    else:
        score = 5

    backend_score = 0 if backend_name == "DirectShow" else 1
    return score, backend_score


def camera_source_kind(alias: str, backend_name: str) -> str:
    alias_lower = alias.lower()
    if "obs" in alias_lower or "virtual camera" in alias_lower:
        return "OBS"
    if "droid" in alias_lower:
        return "DroidCam"
    if "camo" in alias_lower:
        return "Camo"
    if "ivcam" in alias_lower:
        return "iVCam"
    if "laptop" in alias_lower or "integrated" in alias_lower:
        return "Integrada"
    if backend_name == "DirectShow":
        return "DirectShow"
    return "Camara"


def sanitize_folder_name(value: str) -> str:
    cleaned = re.sub(r"\s+", "", value.strip())
    cleaned = re.sub(r"[^A-Za-z0-9_-]", "", cleaned)
    return cleaned or "Curso"


def sanitize_file_component(value: str) -> str:
    text = unicodedata.normalize("NFKD", str(value).strip())
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = re.sub(r"[^\w\s-]", "", text, flags=re.UNICODE)
    text = re.sub(r"\s+", " ", text).strip()
    text = text.replace("/", "-").replace("\\", "-")
    text = re.sub(r"-{2,}", "-", text)
    return text or "sin_nombre"


def rut_no_hyphen(rut: str) -> str:
    return re.sub(r"[^0-9Kk]", "", str(rut).strip()).upper()


def build_photo_filename(student_name: str, course: str, rut: str) -> str:
    safe_name = sanitize_file_component(student_name)
    safe_course = sanitize_file_component(course)
    safe_rut = rut_no_hyphen(rut) or "SIN_RUT"
    return f"{safe_name}-{safe_course}-{safe_rut}.jpg"


def backup_course_dir(photos_root: Path, course_slug: str) -> Path:
    return photos_root.parent / BACKUP_PHOTOS_DIRNAME / course_slug


def ensure_photo_backup(source_path: Path, backup_path: Path) -> None:
    backup_path.parent.mkdir(parents=True, exist_ok=True)
    target_path = backup_path
    if target_path.exists():
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        target_path = target_path.with_name(f"{target_path.stem}__reintento_{stamp}{target_path.suffix}")
    shutil.copy2(source_path, target_path)


def append_retake_audit(backup_dir: Path, record: PhotoRecord, note: str = "reintento") -> None:
    backup_dir.mkdir(parents=True, exist_ok=True)
    audit_path = backup_dir / RETAKE_AUDIT_FILENAME
    write_header = not audit_path.exists()
    with audit_path.open("a", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        if write_header:
            writer.writerow(["timestamp", "action", "id", "filename", "student_name", "course", "rut", "note"])
        writer.writerow([
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "retake",
            record.id,
            record.filename,
            record.student_name,
            record.course,
            record.rut,
            note,
        ])


def ask_mode() -> str:
    while True:
        print("\nSelecciona el modo de trabajo:")
        print("  1. Modo prueba")
        print("  2. Modo curso")
        choice = input("Opcion [1/2]: ").strip()
        if choice == "1":
            return "test"
        if choice == "2":
            return "course"
        print("Opcion invalida. Escribe 1 o 2.")


def load_existing_records(csv_path: Path) -> List[PhotoRecord]:
    if not csv_path.exists():
        return []

    records: List[PhotoRecord] = []
    with csv_path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            try:
                records.append(
                    PhotoRecord(
                        id=int(row["id"]),
                        filename=row["filename"],
                        student_name=row["student_name"],
                        course=row["course"],
                        timestamp=row["timestamp"],
                        rut=row.get("rut", ""),
                    )
                )
            except (KeyError, TypeError, ValueError):
                continue
    deduped: List[PhotoRecord] = []
    seen_keys: set[tuple[str, str, str, str, str]] = set()
    for record in records:
        key = _photo_record_key(record)
        if key in seen_keys:
            continue
        seen_keys.add(key)
        deduped.append(record)
    deduped.sort(key=lambda item: item.id)
    return deduped


def image_signature(frame: np.ndarray) -> int:
    if frame is None or getattr(frame, "size", 0) == 0:
        return 0
    if len(frame.shape) == 3:
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    else:
        gray = frame.copy()
    small = cv2.resize(gray, (9, 8), interpolation=cv2.INTER_AREA)
    diff = small[:, 1:] > small[:, :-1]
    signature = 0
    for value in diff.flatten():
        signature = (signature << 1) | int(bool(value))
    return signature


def image_signature_from_path(image_path: Path) -> Optional[int]:
    if not image_path.exists():
        return None
    image = cv2.imread(str(image_path))
    if image is None:
        return None
    return image_signature(image)


def image_signature_distance(left: int, right: int) -> int:
    return (left ^ right).bit_count()


def image_fingerprint(frame: np.ndarray) -> Optional[str]:
    if frame is None or getattr(frame, "size", 0) == 0:
        return None
    ok, encoded = cv2.imencode(".jpg", frame)
    if not ok:
        return None
    return hashlib.sha256(encoded.tobytes()).hexdigest()


def image_fingerprint_from_path(image_path: Path) -> Optional[str]:
    if not image_path.exists():
        return None
    try:
        return hashlib.sha256(image_path.read_bytes()).hexdigest()
    except OSError:
        return None


def find_similar_record(
    frame: np.ndarray,
    records: List[PhotoRecord],
    session_dir: Path,
) -> Optional[PhotoRecord]:
    target_fingerprint = image_fingerprint(frame)
    if target_fingerprint is None:
        return None
    for record in records:
        image_path = session_dir / record.filename
        record_fingerprint = image_fingerprint_from_path(image_path)
        if record_fingerprint is None:
            continue
        if record_fingerprint == target_fingerprint:
            return record
    return None


def record_identity_key(student_name: str, course: str, rut: str = "") -> tuple[str, str, str]:
    return (
        sanitize_file_component(student_name).casefold(),
        sanitize_file_component(course).casefold(),
        rut_no_hyphen(rut),
    )


def has_record_for_student(records: List[PhotoRecord], student_name: str, course: str, rut: str = "") -> bool:
    target_key = record_identity_key(student_name, course, rut)
    for record in records:
        if record_identity_key(record.student_name, record.course, record.rut) == target_key:
            return True
    return False


def ensure_csv_exists(csv_path: Path) -> None:
    if csv_path.exists():
        return
    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["id", "filename", "student_name", "course", "rut", "timestamp"])


def append_csv_record(csv_path: Path, record: PhotoRecord) -> None:
    ensure_csv_exists(csv_path)
    with csv_path.open("a", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow([record.id, record.filename, record.student_name, record.course, record.rut, record.timestamp])


def rewrite_csv(csv_path: Path, records: List[PhotoRecord]) -> None:
    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["id", "filename", "student_name", "course", "rut", "timestamp"])
        for record in records:
            writer.writerow([record.id, record.filename, record.student_name, record.course, record.rut, record.timestamp])


def initialize_session(app_dir: Path) -> SessionContext:
    mode = ask_mode()
    photos_root = app_dir / PHOTOS_DIRNAME
    photos_root.mkdir(parents=True, exist_ok=True)
    backup_root = app_dir / BACKUP_PHOTOS_DIRNAME
    backup_root.mkdir(parents=True, exist_ok=True)

    if mode == "test":
        course_display = "PRUEBA"
        course_slug = "PRUEBA"
        session_dir = photos_root / TEST_FOLDER_NAME
        backup_dir = backup_root / TEST_FOLDER_NAME
    else:
        while True:
            course_input = input("Nombre del curso: ").strip()
            if course_input:
                break
            print("Debes escribir un nombre de curso.")
        course_display = course_input
        course_slug = sanitize_folder_name(course_input)
        session_dir = photos_root / course_slug
        backup_dir = backup_root / course_slug

    session_dir.mkdir(parents=True, exist_ok=True)
    backup_dir.mkdir(parents=True, exist_ok=True)
    csv_path = session_dir / CSV_FILENAME
    ensure_csv_exists(csv_path)
    try:
        shutil.copy2(csv_path, backup_dir / CSV_FILENAME)
    except Exception:
        pass
    records = load_existing_records(csv_path)

    print("\nSesion lista:")
    print(f"  Modo: {'Prueba' if mode == 'test' else 'Curso'}")
    print(f"  Curso: {course_display}")
    print(f"  Carpeta: {session_dir}")
    print(f"  Siguiente numero: {len(records) + 1:03d}")
    open_folder(photos_root)

    return SessionContext(
        mode=mode,
        course_display=course_display,
        course_slug=course_slug,
        photos_root=photos_root,
        backup_root=backup_root,
        session_dir=session_dir,
        backup_dir=backup_dir,
        csv_path=csv_path,
        records=records,
        session_started_at=datetime.now(),
    )


def open_camera(index: int, backend: int = cv2.CAP_ANY) -> cv2.VideoCapture:
    with suppress_native_stderr():
        return cv2.VideoCapture(index, backend)


def configure_capture(
    capture: cv2.VideoCapture,
    preferred_resolution: Optional[tuple[int, int]] = None,
) -> tuple[int, int]:
    if sys.platform.startswith("win"):
        try:
            capture.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"MJPG"))
        except Exception:
            pass

    preferred_sequence = list(PREFERRED_CAMERA_RESOLUTIONS)
    if preferred_resolution is not None:
        preferred_sequence = [preferred_resolution] + [item for item in preferred_sequence if item != preferred_resolution]

    actual_width = 0
    actual_height = 0
    for target_width, target_height in preferred_sequence:
        capture.set(cv2.CAP_PROP_FRAME_WIDTH, target_width)
        capture.set(cv2.CAP_PROP_FRAME_HEIGHT, target_height)
        capture.set(cv2.CAP_PROP_CONVERT_RGB, 1)
        try:
            capture.set(cv2.CAP_PROP_FPS, 30)
        except Exception:
            pass

        actual_width = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH) or 0)
        actual_height = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0)
        if actual_width == target_width and actual_height == target_height:
            break

    capture.set(cv2.CAP_PROP_CONVERT_RGB, 1)
    try:
        capture.set(cv2.CAP_PROP_BUFFERSIZE, 1)
    except Exception:
        pass
    return actual_width, actual_height


def frame_stats(frame) -> Tuple[float, float]:
    mean_value = float(frame.mean())
    std_value = float(frame.std())
    return mean_value, std_value


def frame_looks_usable(frame) -> bool:
    mean_value, std_value = frame_stats(frame)
    if mean_value < 1.0 and std_value < 1.0:
        return False
    if std_value < MIN_FRAME_STD:
        return False
    return True


@lru_cache(maxsize=1)
def _autoframe_face_cascades() -> tuple[cv2.CascadeClassifier, ...]:
    """Reuse face classifiers while postprocessing a photo batch."""
    return (
        cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml"),
        cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_alt2.xml"),
        cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_alt.xml"),
        cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_profileface.xml"),
    )


def _autoframe_score_face(
    box: tuple[int, int, int, int],
    width: int,
    height: int,
    eye_count: int = 0,
) -> float:
    x, y, w, h = box
    area = float(w * h)
    cx = x + w / 2
    cy = y + h / 2
    center_bias = 1.0 - min(
        1.0,
        (abs(cx - width / 2) / max(1, width)) * 1.05 + (abs(cy - height * 0.42) / max(1, height)) * 0.55,
    )
    aspect = w / max(1, h)
    aspect_penalty = 1.0 - min(0.32, abs(aspect - 0.78) * 0.15)
    eye_bonus = 1.0 + (0.20 * min(2, eye_count))
    size_bonus = min(1.8, 0.55 + (area / max(1, width * height)) * 5.0)
    return area * max(0.2, center_bias) * aspect_penalty * eye_bonus * size_bonus


@lru_cache(maxsize=1)
def _autoframe_eye_cascades() -> tuple[cv2.CascadeClassifier, ...]:
    """Reuse eye classifiers while one postprocess job evaluates candidates."""
    return (
        cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_eye_tree_eyeglasses.xml"),
        cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_eye.xml"),
    )


def _autoframe_detect_eyes(gray: np.ndarray, face_box: tuple[int, int, int, int]) -> list[tuple[int, int]]:
    x, y, w, h = face_box
    roi = gray[y : y + h, x : x + w]
    if roi.size == 0:
        return []

    detected_eyes: list[tuple[int, int, int, int]] = []
    for cascade in _autoframe_eye_cascades():
        if cascade.empty():
            continue
        eyes = cascade.detectMultiScale(
            roi,
            scaleFactor=1.06,
            minNeighbors=4,
            minSize=(max(AUTOFRAME_MIN_EYE_W, w // 12), max(AUTOFRAME_MIN_EYE_H, h // 14)),
        )
        for ex, ey, ew, eh in eyes:
            detected_eyes.append((int(x + ex + ew // 2), int(y + ey + eh // 2), int(ew), int(eh)))

    unique: list[tuple[int, int, int, int]] = []
    for candidate in sorted(detected_eyes, key=lambda pt: (pt[0], pt[1], -pt[2])):
        if not any(abs(existing[0] - candidate[0]) <= 12 and abs(existing[1] - candidate[1]) <= 12 for existing in unique):
            unique.append(candidate)

    valid_pairs: list[tuple[float, tuple[int, int], tuple[int, int]]] = []
    for left, right in itertools.combinations(unique, 2):
        first, second = sorted((left, right), key=lambda pt: pt[0])
        separation_ratio = (second[0] - first[0]) / max(1, w)
        level_delta_ratio = abs(second[1] - first[1]) / max(1, h)
        eye_line_ratio = (((first[1] + second[1]) / 2) - y) / max(1, h)
        if not AUTOFRAME_MIN_EYE_SEPARATION_RATIO <= separation_ratio <= AUTOFRAME_MAX_EYE_SEPARATION_RATIO:
            continue
        if level_delta_ratio > AUTOFRAME_MAX_EYE_LEVEL_DELTA_RATIO:
            continue
        if not 0.18 <= eye_line_ratio <= 0.62:
            continue
        pair_score = level_delta_ratio + abs(eye_line_ratio - 0.40) * 0.30
        valid_pairs.append((pair_score, (first[0], first[1]), (second[0], second[1])))

    if not valid_pairs:
        return []
    _score, left_eye, right_eye = min(valid_pairs, key=lambda pair: pair[0])
    return [left_eye, right_eye]


def _autoframe_box_iou(left: tuple[int, int, int, int], right: tuple[int, int, int, int]) -> float:
    """Measure overlap to collapse repeated Haar detections of one region."""
    lx, ly, lw, lh = left
    rx, ry, rw, rh = right
    ix1 = max(lx, rx)
    iy1 = max(ly, ry)
    ix2 = min(lx + lw, rx + rw)
    iy2 = min(ly + lh, ry + rh)
    intersection = max(0, ix2 - ix1) * max(0, iy2 - iy1)
    if intersection <= 0:
        return 0.0
    union = lw * lh + rw * rh - intersection
    return intersection / max(1, union)


def _autoframe_unique_candidates(
    candidates: list[tuple[int, int, int, int]],
    width: int,
    height: int,
) -> list[tuple[int, int, int, int]]:
    """Keep distinct face hypotheses ordered by their initial relevance."""
    clipped: list[tuple[int, int, int, int]] = []
    for x, y, w, h in candidates:
        x = max(0, min(x, width - 1))
        y = max(0, min(y, height - 1))
        w = max(1, min(w, width - x))
        h = max(1, min(h, height - y))
        clipped.append((x, y, w, h))

    unique: list[tuple[int, int, int, int]] = []
    for candidate in sorted(clipped, key=lambda box: _autoframe_score_face(box, width, height), reverse=True):
        if any(_autoframe_box_iou(candidate, selected) >= 0.48 for selected in unique):
            continue
        unique.append(candidate)
    return unique


def _autoframe_collect_candidates(
    frame: np.ndarray,
    max_detect_width: int,
    cascades: tuple[cv2.CascadeClassifier, ...],
    profiles: tuple[tuple[float, int, tuple[int, int]], ...],
    include_mirror: bool,
) -> list[tuple[int, int, int, int]]:
    """Detect possible faces for either the cheap first pass or exhaustive fallback."""
    height, width = frame.shape[:2]
    detect_frame = frame
    scale = 1.0
    if width > max_detect_width:
        scale = max_detect_width / width
        detect_frame = cv2.resize(frame, (max_detect_width, max(1, int(height * scale))), interpolation=cv2.INTER_AREA)

    gray = cv2.equalizeHist(cv2.cvtColor(detect_frame, cv2.COLOR_BGR2GRAY))
    search_frames = [(gray, False)]
    if include_mirror:
        search_frames.append((cv2.flip(gray, 1), True))

    candidates: list[tuple[int, int, int, int]] = []
    for cascade in cascades:
        if cascade.empty():
            continue
        for search_frame, mirrored in search_frames:
            for scale_factor, min_neighbors, min_size in profiles:
                faces = cascade.detectMultiScale(
                    search_frame,
                    scaleFactor=scale_factor,
                    minNeighbors=min_neighbors,
                    minSize=min_size,
                )
                for fx, fy, fw, fh in faces:
                    if mirrored:
                        fx = search_frame.shape[1] - fx - fw
                    if scale != 1.0:
                        fx = int(fx / scale)
                        fy = int(fy / scale)
                        fw = int(fw / scale)
                        fh = int(fh / scale)
                    candidates.append((fx, fy, fw, fh))
    return candidates


def _autoframe_select_verified_face(
    frame: np.ndarray,
    candidates: list[tuple[int, int, int, int]],
    diagnostic_logger: Optional[logging.Logger],
    phase: str,
    max_candidates: int,
) -> Optional[tuple[int, int, int, int]]:
    """Return only a face backed by a plausible two-eye detection."""
    height, width = frame.shape[:2]
    if not candidates:
        if diagnostic_logger is not None:
            diagnostic_logger.info("Autoframe phase=%s: candidatos=0.", phase)
        return None

    detection_gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    unique_candidates = _autoframe_unique_candidates(candidates, width, height)
    
    # Filtro robusto de tamaño y centrado para descartar falsos positivos en el postprocesado
    filtered_candidates = []
    for box in unique_candidates:
        x, y, w, h = box
        cx = x + w / 2
        cy = y + h / 2
        if w < width * 0.07 or w > width * 0.35:
            continue
        if cx < width * 0.30 or cx > width * 0.70:
            continue
        if cy < height * 0.15 or cy > height * 0.65:
            continue
        filtered_candidates.append(box)

    candidates_to_verify = filtered_candidates[:max_candidates]
    evaluated = [(candidate, _autoframe_detect_eyes(detection_gray, candidate)) for candidate in candidates_to_verify]
    verified = [candidate for candidate in evaluated if len(candidate[1]) >= 2]
    if diagnostic_logger is not None:
        diagnostic_logger.info(
            "Autoframe phase=%s: crudos=%s unicos=%s evaluados=%s confirmados_por_ojos=%s.",
            phase,
            len(candidates),
            len(unique_candidates),
            len(candidates_to_verify),
            len(verified),
        )
    if not verified:
        return None

    (x, y, w, h), eyes = max(
        verified,
        key=lambda candidate: _autoframe_score_face(candidate[0], width, height, len(candidate[1])),
    )
    raw_best_box, raw_best_eyes = max(
        evaluated,
        key=lambda candidate: _autoframe_score_face(candidate[0], width, height, len(candidate[1])),
    )
    if diagnostic_logger is not None and raw_best_box != (x, y, w, h):
        diagnostic_logger.info(
            "Autoframe rejection: fase=%s candidato_mayor=%s ojos=%s descartado_por=no_confirmar_ojos; elegido=%s.",
            phase,
            raw_best_box,
            len(raw_best_eyes),
            (x, y, w, h),
        )
    if diagnostic_logger is not None:
        diagnostic_logger.info(
            "Autoframe decision: fase=%s rostro=%s motivo=ojos_confirmados ojos=%s score=%.1f.",
            phase,
            (x, y, w, h),
            len(eyes),
            _autoframe_score_face((x, y, w, h), width, height, len(eyes)),
        )
    return x, y, w, h


def _autoframe_detect_face(
    frame: np.ndarray,
    diagnostic_logger: Optional[logging.Logger] = None,
) -> Optional[tuple[int, int, int, int]]:
    if frame.size == 0:
        if diagnostic_logger is not None:
            diagnostic_logger.warning("Autoframe decision: frame vacio, se omite deteccion.")
        return None

    cascades = _autoframe_face_cascades()
    fast_candidates = _autoframe_collect_candidates(
        frame,
        AUTOFRAME_FAST_DETECT_WIDTH,
        cascades[:3],
        ((1.06, 4, (30, 30)),),
        include_mirror=False,
    )
    face_box = _autoframe_select_verified_face(
        frame,
        fast_candidates,
        diagnostic_logger,
        "rapida",
        AUTOFRAME_FAST_MAX_UNIQUE_CANDIDATES,
    )
    if face_box is not None:
        return face_box

    fallback_candidates = _autoframe_collect_candidates(
        frame,
        AUTOFRAME_MAX_DETECT_WIDTH,
        cascades,
        ((1.03, 3, (28, 28)), (1.05, 4, (36, 36)), (1.08, 5, (52, 52))),
        include_mirror=True,
    )
    face_box = _autoframe_select_verified_face(
        frame,
        fallback_candidates,
        diagnostic_logger,
        "exhaustiva",
        AUTOFRAME_MAX_UNIQUE_CANDIDATES,
    )
    if face_box is None and diagnostic_logger is not None:
        diagnostic_logger.warning(
            "Autoframe decision: ningun pase confirmo un rostro; se preservara la imagen sin recorte adicional."
        )
    return face_box


def _autoframe_build_crop_box(
    width: int,
    height: int,
    face_box: Optional[tuple[int, int, int, int]],
    eye_centers: Optional[list[tuple[int, int]]] = None,
) -> tuple[int, int, int, int]:
    target_ratio = 3 / 4
    max_crop_h = min(height, int(width / target_ratio))
    max_crop_w = int(max_crop_h * target_ratio)

    if face_box is None:
        crop_h = max(220, int(max_crop_h * AUTOFRAME_FALLBACK_HEIGHT_RATIO))
        crop_w = int(crop_h * target_ratio)
        x1 = (width - crop_w) // 2
        y1 = (height - crop_h) // 2
    else:
        fx, fy, fw, fh = face_box
        face_cx = fx + fw / 2
        face_cy = fy + fh / 2

        crop_h = max(int(fh * AUTOFRAME_FACE_EXPANSION), int(height * AUTOFRAME_FACE_HEIGHT_RATIO))
        crop_h = min(crop_h, max(220, int(height * 0.88)))
        crop_h = min(crop_h, max_crop_h)
        crop_w = int(crop_h * target_ratio)

        x1 = int(face_cx - crop_w / 2)
        y1 = int(face_cy - crop_h * 0.40)

        if fx < width * 0.30:
            x1 = int(face_cx - crop_w * 0.38)
        elif fx > width * 0.70:
            x1 = int(face_cx - crop_w * 0.62)

        if eye_centers:
            eye_y = sum(pt[1] for pt in eye_centers) / len(eye_centers)
            y1 = int(eye_y - crop_h * AUTOFRAME_EYE_TOP_RATIO)
        elif fy < height * 0.28:
            y1 = int(face_cy - crop_h * 0.32)
        else:
            y1 = int(face_cy - crop_h * 0.30)

        # Haar commonly starts inside the hairline; always reserve visible headroom.
        headroom_y1 = int(fy - fh * AUTOFRAME_HEADROOM_RATIO)
        y1 = min(y1, headroom_y1)
        chest_margin = max(18, int(fh * AUTOFRAME_CHEST_MARGIN_RATIO))
        y1 = min(y1, height - crop_h + chest_margin)
        x1 = min(x1, width - crop_w + max(12, int(fw * 0.18)))

        # Pequeña búsqueda alrededor del rostro para centrar mejor cuando la detección
        # cae corrida a un lado. Esto ayuda mucho con fotos de aula y encuadres apurados.
        search_offsets = (-0.16, -0.08, 0.0, 0.08, 0.16)
        best_box = (x1, y1, x1 + crop_w, y1 + crop_h)
        best_score = -1.0
        for dx in search_offsets:
            for dy in (-0.08, 0.0, 0.08):
                cand_x1 = int(face_cx - crop_w / 2 + crop_w * dx)
                cand_y1 = min(int(y1 + crop_h * dy), headroom_y1)
                cand_x1 = max(0, min(cand_x1, width - crop_w))
                cand_y1 = max(0, min(cand_y1, height - crop_h))
                cand_box = (cand_x1, cand_y1, cand_x1 + crop_w, cand_y1 + crop_h)
                face_left = fx
                face_top = fy
                face_right = fx + fw
                face_bottom = fy + fh
                margin_left = max(0, face_left - cand_x1)
                margin_top = max(0, face_top - cand_y1)
                margin_right = max(0, (cand_x1 + crop_w) - face_right)
                margin_bottom = max(0, (cand_y1 + crop_h) - face_bottom)
                face_center_bias = 1.0 - min(
                    1.0,
                    (abs((face_cx - cand_x1) - crop_w * 0.5) / max(1, crop_w)) * 1.2
                    + (abs((face_cy - cand_y1) - crop_h * 0.32) / max(1, crop_h)) * 0.9,
                )
                room_bonus = min(1.6, (margin_top + margin_bottom * 1.2 + margin_left * 0.7 + margin_right * 0.7) / max(1, crop_h))
                score = face_center_bias + room_bonus
                if score > best_score:
                    best_score = score
                    best_box = cand_box
        x1, y1, x2, y2 = best_box

    crop_w = min(crop_w, max_crop_w)
    crop_h = min(crop_h, height)
    x1 = max(0, min(x1, width - crop_w))
    y1 = max(0, min(y1, height - crop_h))
    return x1, y1, x1 + crop_w, y1 + crop_h


def _autoframe_crop_frame(frame: np.ndarray, crop_box: tuple[int, int, int, int], output_size: tuple[int, int] = AUTOFRAME_TARGET_SIZE) -> np.ndarray:
    x1, y1, x2, y2 = crop_box
    crop = frame[y1:y2, x1:x2]
    if crop.size == 0:
        return frame.copy()
    crop_h, crop_w = crop.shape[:2]
    target_w, target_h = output_size
    interpolation = cv2.INTER_AREA if target_w < crop_w or target_h < crop_h else cv2.INTER_CUBIC
    return cv2.resize(crop, output_size, interpolation=interpolation)


def autoframe_photo_file(
    image_path: Path,
    backup_path: Optional[Path] = None,
    diagnostic_logger: Optional[logging.Logger] = None,
) -> tuple[bool, str]:
    try:
        image = cv2.imread(str(image_path))
        if image is None:
            if diagnostic_logger is not None:
                diagnostic_logger.error("Autoframe error: no se pudo leer %s.", image_path)
            return False, f"No se pudo leer {image_path}"

        if diagnostic_logger is not None:
            diagnostic_logger.info(
                "Autoframe input: archivo=%s dimensiones=%sx%s backup=%s.",
                image_path,
                image.shape[1],
                image.shape[0],
                backup_path or "-",
            )
        if backup_path is not None and not backup_path.exists():
            backup_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(image_path, backup_path)
            if diagnostic_logger is not None:
                diagnostic_logger.info("Autoframe backup: creado %s.", backup_path)

        face_box = _autoframe_detect_face(image, diagnostic_logger)
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        eye_centers = _autoframe_detect_eyes(gray, face_box) if face_box is not None else []
        if face_box is None or len(eye_centers) < 2:
            if diagnostic_logger is not None:
                diagnostic_logger.warning(
                    "Autoframe guard: imagen preservada sin cambios; no hay rostro con par de ojos confiable. rostro=%s ojos=%s.",
                    face_box or "-",
                    eye_centers or "-",
                )
            return True, f"Sin reencuadre para {image_path.name}: rostro no confirmado"
        crop_box = _autoframe_build_crop_box(image.shape[1], image.shape[0], face_box, eye_centers)
        if diagnostic_logger is not None:
            diagnostic_logger.info(
                "Autoframe crop: caja=%s salida=%s motivo=%s rostro=%s ojos=%s.",
                crop_box,
                AUTOFRAME_TARGET_SIZE,
                "rostro_con_margen_superior_y_par_de_ojos_validado",
                face_box or "-",
                eye_centers or "-",
            )
        framed = _autoframe_crop_frame(image, crop_box)
        if framed.size == 0:
            if diagnostic_logger is not None:
                diagnostic_logger.error("Autoframe error: crop vacio para %s.", image_path.name)
            return False, f"Crop vacio para {image_path.name}"

        tmp_main = image_path.with_name(f"{image_path.stem}.__autoframe_tmp{image_path.suffix}")
        if not cv2.imwrite(str(tmp_main), framed):
            if diagnostic_logger is not None:
                diagnostic_logger.error("Autoframe error: no se pudo escribir %s.", tmp_main)
            return False, f"No se pudo escribir temporal {tmp_main.name}"
        tmp_main.replace(image_path)

        if diagnostic_logger is not None:
            diagnostic_logger.info("Autoframe result: reencuadre aplicado a %s.", image_path.name)
        return True, f"Reencuadre aplicado a {image_path.name}"
    except Exception as exc:
        if diagnostic_logger is not None:
            diagnostic_logger.exception("Autoframe exception: %s.", exc)
        return False, f"Error de reencuadre en {image_path.name}: {exc}"


def try_open_camera(
    index: int,
    backend_id: Optional[int] = None,
) -> Tuple[Optional[cv2.VideoCapture], Optional[str], Optional[int]]:
    if backend_id is None:
        attempts = CAMERA_BACKENDS if sys.platform.startswith("win") else [("Automatico", cv2.CAP_ANY)]
    else:
        attempts = [(backend_name_from_id(backend_id), backend_id)]
    for backend_name, backend_id in attempts:
        capture = open_camera(index, backend_id)
        if not capture.isOpened():
            capture.release()
            continue

        actual_width, actual_height = configure_capture(capture)
        frame = None
        ok = False
        for _ in range(6):
            with suppress_native_stderr():
                ok, frame = capture.read()
            if ok and frame is not None and frame_looks_usable(frame):
                if actual_width <= 0 or actual_height <= 0:
                    actual_width = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH) or 0)
                    actual_height = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0)
                if frame.shape[1] != actual_width or frame.shape[0] != actual_height:
                    actual_width = frame.shape[1]
                    actual_height = frame.shape[0]
                return capture, backend_name, backend_id

        capture.release()
    return None, None, None


def list_available_cameras(
    aliases: dict[tuple[int, str], str],
    max_index: int = MAX_CAMERA_INDEX,
) -> List[Tuple[int, str, int, str, str]]:
    cameras: List[Tuple[int, str, int, str, str]] = []
    for index in range(max_index):
        attempts = CAMERA_BACKENDS if sys.platform.startswith("win") else [("Automatico", cv2.CAP_ANY)]
        for backend_name, backend_id in attempts:
            capture, detected_backend_name, detected_backend_id = try_open_camera(index, backend_id)
            if capture is None or detected_backend_name is None or detected_backend_id is None:
                continue

            width = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH) or 0)
            height = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0)
            alias = get_camera_alias(aliases, index, detected_backend_id)
            capture.release()
            cameras.append((index, f"{alias} ({width}x{height})", detected_backend_id, detected_backend_name, alias))
    cameras.sort(key=lambda item: (camera_priority(item[4], item[3]), item[0]))
    return cameras


def select_camera(
    aliases: dict[tuple[int, str], str],
    app_dir: Path,
    preferred_index: Optional[int] = None,
    preferred_backend: Optional[str] = None,
) -> Tuple[int, int, str, str]:
    cameras = list_available_cameras(aliases)
    if not cameras:
        raise RuntimeError("No se encontro ninguna camara disponible en Windows/OpenCV.")

    camera_by_index: dict[int, list[tuple[int, str, str]]] = {}
    for index, _label, backend_id, backend_name, alias in cameras:
        camera_by_index.setdefault(index, []).append((backend_id, backend_name, alias))

    remembered_index, remembered_backend = load_last_camera(app_dir)
    if preferred_index is None and remembered_index is not None:
        preferred_index = remembered_index
        preferred_backend = remembered_backend

    if preferred_index is not None:
        matches = camera_by_index.get(preferred_index, [])
        if preferred_backend:
            backend_key = preferred_backend.lower()
            expected = BACKEND_LOOKUP.get(backend_key)
            if expected is not None:
                for backend_id, backend_name, alias in matches:
                    if backend_id == expected[1]:
                        print(f"\nUsando camara preseleccionada: {alias} | indice {preferred_index} | backend: {backend_name}")
                        return preferred_index, backend_id, backend_name, alias
        if matches:
            backend_id, backend_name, alias = matches[0]
            print(f"\nUsando camara preseleccionada: {alias} | indice {preferred_index} | backend: {backend_name}")
            return preferred_index, backend_id, backend_name, alias

    print("\nCamaras detectadas:")
    for index, label, _backend_id, backend_name, _alias in cameras:
        print(f"  {index}. {label} | backend: {backend_name}")

    default_index = cameras[0][0]
    default_backend_id, default_backend_name, default_alias = camera_by_index[default_index][0]

    while True:
        raw = input(f"Selecciona camara [{default_index}]: ").strip()
        if not raw:
            return default_index, default_backend_id, default_backend_name, default_alias
        try:
            value = int(raw)
        except ValueError:
            print("Debes escribir un numero de camara valido.")
            continue
        matches = camera_by_index.get(value, [])
        if matches:
            if len(matches) > 1:
                print(f"El indice {value} tiene varias fuentes; se usara {matches[0][2]} ({matches[0][1]}).")
            backend_id, backend_name, alias = matches[0]
            return value, backend_id, backend_name, alias
        print("Ese indice no aparece como disponible.")


def draw_guides(frame) -> None:
    height, width = frame.shape[:2]
    center_x = width // 2
    center_y = height // 2
    guide_w = int(width * 0.26)
    guide_h = int(height * 0.46)
    left = max(20, center_x - guide_w // 2)
    right = min(width - 20, center_x + guide_w // 2)
    top = max(130, center_y - guide_h // 2)
    bottom = min(height - 30, center_y + guide_h // 2)

    cv2.rectangle(frame, (left, top), (right, bottom), (0, 200, 255), 2)
    cv2.line(frame, (center_x, top), (center_x, bottom), (0, 200, 255), 1)
    cv2.line(frame, (left, center_y), (right, center_y), (0, 200, 255), 1)
    cv2.putText(
        frame,
        "Guia de encuadre",
        (left, top - 10),
        TEXT_FONT,
        0.48,
        (0, 200, 255),
        1,
        cv2.LINE_AA,
    )


def draw_overlay(
    frame,
    session: SessionContext,
    student_name: str,
    typed_name: str = "",
    status_line: str = "",
    camera_label: str = "",
):
    overlay = frame.copy()
    panel_height = 102
    cv2.rectangle(overlay, (0, 0), (frame.shape[1], panel_height), (0, 0, 0), -1)
    cv2.addWeighted(overlay, 0.38, frame, 0.62, 0, frame)
    draw_guides(frame)

    lines = [
        f"Curso: {session.course_display} | Foto: {session.next_id:03d} | Guardadas: {len(session.records)}",
        f"Estudiante: {student_name or '-'}",
        f"Ingreso: {typed_name or '_'}",
        "Escribe nombre aqui | Enter confirma | Espacio/P captura | Q salir",
    ]
    if camera_label:
        lines.append(camera_label)
    if status_line:
        lines.append(status_line)

    y = 22
    for line in lines:
        cv2.putText(frame, line, (14, y), TEXT_FONT, TEXT_SCALE, (255, 255, 255), TEXT_THICKNESS, cv2.LINE_AA)
        y += TEXT_LINE
    return frame


def save_image(image, destination: Path) -> None:
    if not cv2.imwrite(str(destination), image):
        raise RuntimeError(f"No se pudo guardar la imagen en {destination}")


def remove_last_record(session: SessionContext) -> Optional[PhotoRecord]:
    if not session.records:
        return None

    last_record = session.records.pop()
    image_path = session.session_dir / last_record.filename
    if image_path.exists():
        image_path.unlink()
    append_retake_audit(session.backup_dir, last_record, note="reintento")
    rewrite_csv(session.csv_path, session.records)
    try:
        shutil.copy2(session.csv_path, session.backup_dir / CSV_FILENAME)
    except Exception:
        pass
    return last_record


def build_record(session: SessionContext, student_name: str) -> PhotoRecord:
    photo_id = session.next_id
    filename = build_photo_filename(student_name, session.course_display, "")
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    return PhotoRecord(
        id=photo_id,
        filename=filename,
        student_name=student_name,
        course=session.course_display,
        timestamp=timestamp,
    )


def open_folder(path: Path) -> None:
    if sys.platform.startswith("win"):
        os.startfile(path)  # type: ignore[attr-defined]
        return
    print(f"Carpeta: {path}")


def show_post_capture_review(session: SessionContext, frame, record: PhotoRecord, camera_label: str) -> str:
    review = frame.copy()
    review = draw_overlay(
        review,
        session,
        record.student_name,
        typed_name=record.student_name,
        status_line="Guardada. Enter/espacio=siguiente | r=rehacer esta foto | q=salir",
        camera_label=camera_label,
    )

    while True:
        cv2.imshow(WINDOW_NAME, review)
        key = cv2.waitKey(0) & 0xFF
        if key in (13, 32):
            return "next"
        if key == ord("r"):
            return "retake"
        if key == ord("q"):
            return "quit"


def capture_photo(
    capture: cv2.VideoCapture,
    session: SessionContext,
    camera_label: str,
) -> str:
    typed_name = ""
    active_student_name = ""
    while True:
        ok, frame = capture.read()
        if not ok or frame is None:
            blank = draw_overlay(
                np.zeros((720, 1280, 3), dtype=np.uint8),
                session,
                active_student_name,
                typed_name=typed_name,
                status_line="No se pudo leer la camara. Revisa la conexion o cambia de indice.",
                camera_label=camera_label,
            )
            cv2.imshow(WINDOW_NAME, blank)
            key = cv2.waitKey(200) & 0xFF
            if key == ord("q"):
                return "quit"
            continue

        preview = draw_overlay(
            frame.copy(),
            session,
            active_student_name,
            typed_name=typed_name,
            camera_label=camera_label,
        )
        cv2.imshow(WINDOW_NAME, preview)
        key = cv2.waitKey(30) & 0xFF

        if key == ord("q"):
            return "quit"
        if key in (8, 127):
            typed_name = typed_name[:-1]
            continue
        if key == 13:
            candidate = typed_name.strip()
            if candidate:
                active_student_name = candidate
            continue
        if 32 <= key <= 126 and key not in (ord("p"), ord("q")):
            if len(typed_name) < 60:
                typed_name += chr(key)
            continue
        if key not in (ord("p"), 32):
            continue
        student_name = active_student_name or typed_name.strip()
        if not student_name:
            continue
        if has_record_for_student(session.records, student_name, session.course_display):
            print(f"Ya existe una foto de {student_name} en {session.course_display}. No se guarda duplicado.")
            continue
        similar_record = find_similar_record(frame, session.records, session.session_dir)
        if similar_record is not None:
            print(
                "La foto ya coincide con "
                f"{similar_record.student_name} en {similar_record.course}. No se guarda duplicado."
            )
            continue

        record = build_record(session, student_name)
        image_path = session.session_dir / record.filename
        backup_path = session.backup_dir / record.filename
        save_image(frame, image_path)
        append_csv_record(session.csv_path, record)
        try:
            shutil.copy2(image_path, backup_path)
            shutil.copy2(session.csv_path, session.backup_dir / CSV_FILENAME)
        except Exception:
            pass
        session.records.append(record)

        action = show_post_capture_review(session, frame, record, camera_label)
        if action == "next":
            return "captured"
        if action == "quit":
            return "quit"

        removed = remove_last_record(session)
        if removed:
            print(f"Foto eliminada para rehacer: {removed.filename}")


def warm_up_camera(capture: cv2.VideoCapture) -> None:
    for _ in range(WARMUP_FRAMES):
        capture.read()
        cv2.waitKey(1)


def write_session_report(session: SessionContext, camera_index: int, backend_name: str) -> Path:
    report_name = f"session_{session.session_started_at.strftime('%Y%m%d_%H%M%S')}.txt"
    report_path = session.session_dir / report_name
    lines = [
        APP_TITLE,
        f"Inicio: {session.session_started_at.strftime('%Y-%m-%d %H:%M:%S')}",
        f"Modo: {'Prueba' if session.mode == 'test' else 'Curso'}",
        f"Curso: {session.course_display}",
        f"Carpeta: {session.session_dir}",
        f"Camara: {camera_index}",
        f"Backend: {backend_name}",
        f"Total fotos en carpeta al cierre: {len(session.records)}",
        "",
        "Ultimos registros:",
    ]
    for record in session.records[-10:]:
        lines.append(f"{record.id:03d} | {record.filename} | {record.student_name} | {record.timestamp}")

    report_path.write_text("\n".join(lines), encoding="utf-8")
    return report_path


def run_capture_loop(
    camera_index: int,
    backend_id: int,
    backend_name: str,
    camera_alias: str,
    session: SessionContext,
) -> Path:
    capture = open_camera(camera_index, backend_id)
    if not capture.isOpened():
        raise RuntimeError(f"No se pudo abrir la camara con indice {camera_index}.")

    requested_width, requested_height = configure_capture(capture)
    warm_up_camera(capture)
    actual_width = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH) or requested_width or 0)
    actual_height = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT) or requested_height or 0)
    camera_label = f"Camara: {camera_alias} | indice {camera_index} | backend: {backend_name}"
    print(f"Resolucion activa: {actual_width}x{actual_height}")

    cv2.namedWindow(WINDOW_NAME, cv2.WINDOW_NORMAL)
    cv2.resizeWindow(WINDOW_NAME, 1280, 720)
    cv2.setWindowProperty(WINDOW_NAME, cv2.WND_PROP_TOPMOST, 1)

    try:
        while True:
            print("Preview activo. Escribe el nombre dentro de la ventana, Enter confirma, P o espacio captura.")
            result = capture_photo(capture, session, camera_label)
            if result == "captured":
                print("Foto guardada.")
                continue
            if result == "quit":
                print("Sesion cerrada desde la ventana de captura.")
                break
    finally:
        capture.release()
        cv2.destroyAllWindows()

    return write_session_report(session, camera_index, backend_name)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Captura local de fotos tipo credencial para cursos.")
    parser.add_argument("--camera-index", type=int, default=None, help="Indice de camara a usar directamente.")
    parser.add_argument(
        "--backend",
        choices=sorted(BACKEND_LOOKUP.keys()),
        default=None,
        help="Backend de OpenCV a usar con --camera-index.",
    )
    return parser.parse_args()


def main() -> None:
    app_dir = Path(__file__).resolve().parent
    silence_opencv_logs()
    logger, log_path = setup_logging(app_dir, "cli")
    logger.info("=== CastelCredCam CLI start ===")
    logger.info("Log file: %s", log_path)
    logger.info("Python: %s", sys.version.replace("\n", " "))
    logger.info("Executable: %s", sys.executable)
    logger.info("CWD: %s", Path.cwd())
    logger.info("Args: %s", sys.argv[1:])
    session: Optional[SessionContext] = None
    session_report_path: Optional[Path] = None
    args = parse_args()
    camera_aliases = load_camera_aliases(app_dir)
    print(f"{APP_TITLE} - Captura local de fotos tipo credencial")
    print("-" * 56)

    try:
        session = initialize_session(app_dir)
        logger.info("Session initialized at %s", session.session_dir)
        camera_index, backend_id, backend_name, camera_alias = select_camera(
            camera_aliases, app_dir, args.camera_index, args.backend
        )
        logger.info(
            "Selected camera index=%s backend=%s alias=%s",
            camera_index,
            backend_name,
            camera_alias,
        )
        save_last_camera(app_dir, camera_index, backend_key_from_id(backend_id))
        session_report_path = run_capture_loop(camera_index, backend_id, backend_name, camera_alias, session)
    except KeyboardInterrupt:
        logger.info("Session interrupted by keyboard.")
        print("\nSesion interrumpida por teclado.")
    except Exception as exc:
        logger.exception("Unhandled exception in CLI run: %s", exc)
        print(f"\n[ERROR] {exc}")
        sys.exit(1)

    if session is not None:
        logger.info("Session finished. records=%s csv=%s", len(session.records), session.csv_path)
        print("\nSesion finalizada.")
        print(f"Fotos: {session.session_dir}")
        print(f"CSV:   {session.csv_path}")
        if session_report_path is not None:
            logger.info("Session report: %s", session_report_path)
            print(f"Reporte: {session_report_path}")
        print(f"Total en esta carpeta: {len(session.records)}")
    logger.info("=== CastelCredCam CLI end ===")


if __name__ == "__main__":
    main()
