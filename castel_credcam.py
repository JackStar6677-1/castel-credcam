from __future__ import annotations

import argparse
import csv
import json
import os
import re
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Tuple

import cv2
import numpy as np


APP_TITLE = "CastelCredCam"
WINDOW_NAME = "CastelCredCam Preview"
PHOTOS_DIRNAME = "fotos"
TEST_FOLDER_NAME = "_pruebas"
CSV_FILENAME = "index.csv"
MAX_CAMERA_INDEX = 8
WARMUP_FRAMES = 12
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
CAMERA_ALIASES_FILENAME = "camera_aliases.json"


@dataclass
class PhotoRecord:
    id: int
    filename: str
    student_name: str
    course: str
    timestamp: str


@dataclass
class SessionContext:
    mode: str
    course_display: str
    course_slug: str
    photos_root: Path
    session_dir: Path
    csv_path: Path
    records: List[PhotoRecord]
    session_started_at: datetime

    @property
    def next_id(self) -> int:
        return len(self.records) + 1

    def filename_for(self, photo_id: int) -> str:
        prefix = "PRUEBA" if self.mode == "test" else self.course_slug
        return f"{prefix}_{photo_id:03d}.jpg"


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


def sanitize_folder_name(value: str) -> str:
    cleaned = re.sub(r"\s+", "", value.strip())
    cleaned = re.sub(r"[^A-Za-z0-9_-]", "", cleaned)
    return cleaned or "Curso"


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
                    )
                )
            except (KeyError, TypeError, ValueError):
                continue
    records.sort(key=lambda item: item.id)
    return records


def ensure_csv_exists(csv_path: Path) -> None:
    if csv_path.exists():
        return
    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["id", "filename", "student_name", "course", "timestamp"])


def append_csv_record(csv_path: Path, record: PhotoRecord) -> None:
    ensure_csv_exists(csv_path)
    with csv_path.open("a", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow([record.id, record.filename, record.student_name, record.course, record.timestamp])


def rewrite_csv(csv_path: Path, records: List[PhotoRecord]) -> None:
    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["id", "filename", "student_name", "course", "timestamp"])
        for record in records:
            writer.writerow([record.id, record.filename, record.student_name, record.course, record.timestamp])


def initialize_session(app_dir: Path) -> SessionContext:
    mode = ask_mode()
    photos_root = app_dir / PHOTOS_DIRNAME
    photos_root.mkdir(parents=True, exist_ok=True)

    if mode == "test":
        course_display = "PRUEBA"
        course_slug = "PRUEBA"
        session_dir = photos_root / TEST_FOLDER_NAME
    else:
        while True:
            course_input = input("Nombre del curso: ").strip()
            if course_input:
                break
            print("Debes escribir un nombre de curso.")
        course_display = course_input
        course_slug = sanitize_folder_name(course_input)
        session_dir = photos_root / course_slug

    session_dir.mkdir(parents=True, exist_ok=True)
    csv_path = session_dir / CSV_FILENAME
    ensure_csv_exists(csv_path)
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
        session_dir=session_dir,
        csv_path=csv_path,
        records=records,
        session_started_at=datetime.now(),
    )


def open_camera(index: int, backend: int = cv2.CAP_ANY) -> cv2.VideoCapture:
    return cv2.VideoCapture(index, backend)


def configure_capture(capture: cv2.VideoCapture) -> None:
    capture.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
    capture.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
    capture.set(cv2.CAP_PROP_CONVERT_RGB, 1)
    try:
        capture.set(cv2.CAP_PROP_BUFFERSIZE, 1)
    except Exception:
        pass


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


def try_open_camera(index: int) -> Tuple[Optional[cv2.VideoCapture], Optional[str], Optional[int]]:
    attempts = CAMERA_BACKENDS if sys.platform.startswith("win") else [("Automatico", cv2.CAP_ANY)]
    for backend_name, backend_id in attempts:
        capture = open_camera(index, backend_id)
        if not capture.isOpened():
            capture.release()
            continue

        configure_capture(capture)
        frame = None
        ok = False
        for _ in range(6):
            ok, frame = capture.read()
            if ok and frame is not None and frame_looks_usable(frame):
                return capture, backend_name, backend_id

        capture.release()
    return None, None, None


def list_available_cameras(
    aliases: dict[tuple[int, str], str],
    max_index: int = MAX_CAMERA_INDEX,
) -> List[Tuple[int, str, int, str, str]]:
    cameras: List[Tuple[int, str, int, str, str]] = []
    for index in range(max_index):
        capture, backend_name, backend_id = try_open_camera(index)
        if capture is None or backend_name is None or backend_id is None:
            continue

        width = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH) or 0)
        height = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0)
        alias = get_camera_alias(aliases, index, backend_id)
        capture.release()
        cameras.append((index, f"{alias} ({width}x{height})", backend_id, backend_name, alias))
    return cameras


def select_camera(
    aliases: dict[tuple[int, str], str],
    preferred_index: Optional[int] = None,
    preferred_backend: Optional[str] = None,
) -> Tuple[int, int, str, str]:
    cameras = list_available_cameras(aliases)
    if not cameras:
        raise RuntimeError("No se encontro ninguna camara disponible en Windows/OpenCV.")

    if preferred_index is not None:
        for index, _label, backend_id, backend_name, alias in cameras:
            if index != preferred_index:
                continue
            if preferred_backend:
                backend_key = preferred_backend.lower()
                expected = BACKEND_LOOKUP.get(backend_key)
                if expected and backend_id != expected[1]:
                    continue
            print(f"\nUsando camara preseleccionada: {alias} | indice {index} | backend: {backend_name}")
            return index, backend_id, backend_name, alias

    print("\nCamaras detectadas:")
    for index, label, _backend_id, backend_name, _alias in cameras:
        print(f"  {index}. {label} | backend: {backend_name}")

    camera_by_index = {
        index: (backend_id, backend_name, alias)
        for index, _label, backend_id, backend_name, alias in cameras
    }
    default_index = cameras[0][0]
    default_backend_id, default_backend_name, default_alias = camera_by_index[default_index]

    while True:
        raw = input(f"Selecciona camara [{default_index}]: ").strip()
        if not raw:
            return default_index, default_backend_id, default_backend_name, default_alias
        try:
            value = int(raw)
        except ValueError:
            print("Debes escribir un numero de camara valido.")
            continue
        if value in camera_by_index:
            backend_id, backend_name, alias = camera_by_index[value]
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
    rewrite_csv(session.csv_path, session.records)
    return last_record


def build_record(session: SessionContext, student_name: str) -> PhotoRecord:
    photo_id = session.next_id
    filename = session.filename_for(photo_id)
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

        record = build_record(session, student_name)
        image_path = session.session_dir / record.filename
        save_image(frame, image_path)
        append_csv_record(session.csv_path, record)
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

    configure_capture(capture)
    warm_up_camera(capture)
    camera_label = f"Camara: {camera_alias} | indice {camera_index} | backend: {backend_name}"

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
    session: Optional[SessionContext] = None
    session_report_path: Optional[Path] = None
    args = parse_args()
    camera_aliases = load_camera_aliases(app_dir)
    print(f"{APP_TITLE} - Captura local de fotos tipo credencial")
    print("-" * 56)

    try:
        session = initialize_session(app_dir)
        camera_index, backend_id, backend_name, camera_alias = select_camera(camera_aliases, args.camera_index, args.backend)
        session_report_path = run_capture_loop(camera_index, backend_id, backend_name, camera_alias, session)
    except KeyboardInterrupt:
        print("\nSesion interrumpida por teclado.")
    except Exception as exc:
        print(f"\n[ERROR] {exc}")
        sys.exit(1)

    if session is not None:
        print("\nSesion finalizada.")
        print(f"Fotos: {session.session_dir}")
        print(f"CSV:   {session.csv_path}")
        if session_report_path is not None:
            print(f"Reporte: {session_report_path}")
        print(f"Total en esta carpeta: {len(session.records)}")


if __name__ == "__main__":
    main()
