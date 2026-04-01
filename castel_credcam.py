from __future__ import annotations

import csv
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


def try_open_camera(index: int) -> Tuple[Optional[cv2.VideoCapture], Optional[str], Optional[int]]:
    attempts = CAMERA_BACKENDS if sys.platform.startswith("win") else [("Automatico", cv2.CAP_ANY)]
    for backend_name, backend_id in attempts:
        capture = open_camera(index, backend_id)
        if not capture.isOpened():
            capture.release()
            continue

        ok, frame = capture.read()
        if ok and frame is not None:
            return capture, backend_name, backend_id

        capture.release()
    return None, None, None


def list_available_cameras(max_index: int = MAX_CAMERA_INDEX) -> List[Tuple[int, str, int, str]]:
    cameras: List[Tuple[int, str, int, str]] = []
    for index in range(max_index):
        capture, backend_name, backend_id = try_open_camera(index)
        if capture is None or backend_name is None or backend_id is None:
            continue

        width = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH) or 0)
        height = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0)
        capture.release()
        cameras.append((index, f"Camara {index} ({width}x{height})", backend_id, backend_name))
    return cameras


def select_camera() -> Tuple[int, int, str]:
    cameras = list_available_cameras()
    if not cameras:
        raise RuntimeError("No se encontro ninguna camara disponible en Windows/OpenCV.")

    print("\nCamaras detectadas:")
    for index, label, _backend_id, backend_name in cameras:
        print(f"  {index}. {label} | backend: {backend_name}")

    camera_by_index = {index: (backend_id, backend_name) for index, _label, backend_id, backend_name in cameras}
    default_index = cameras[0][0]
    default_backend_id, default_backend_name = camera_by_index[default_index]

    while True:
        raw = input(f"Selecciona camara [{default_index}]: ").strip()
        if not raw:
            return default_index, default_backend_id, default_backend_name
        try:
            value = int(raw)
        except ValueError:
            print("Debes escribir un numero de camara valido.")
            continue
        if value in camera_by_index:
            backend_id, backend_name = camera_by_index[value]
            return value, backend_id, backend_name
        print("Ese indice no aparece como disponible.")


def draw_guides(frame) -> None:
    height, width = frame.shape[:2]
    center_x = width // 2
    center_y = height // 2
    guide_w = int(width * 0.30)
    guide_h = int(height * 0.55)
    left = max(20, center_x - guide_w // 2)
    right = min(width - 20, center_x + guide_w // 2)
    top = max(160, center_y - guide_h // 2)
    bottom = min(height - 30, center_y + guide_h // 2)

    cv2.rectangle(frame, (left, top), (right, bottom), (0, 200, 255), 2)
    cv2.line(frame, (center_x, top), (center_x, bottom), (0, 200, 255), 1)
    cv2.line(frame, (left, center_y), (right, center_y), (0, 200, 255), 1)
    cv2.putText(
        frame,
        "Guia de encuadre",
        (left, top - 10),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.6,
        (0, 200, 255),
        2,
        cv2.LINE_AA,
    )


def draw_overlay(
    frame,
    session: SessionContext,
    student_name: str,
    status_line: str = "",
    camera_label: str = "",
):
    overlay = frame.copy()
    panel_height = 160
    cv2.rectangle(overlay, (0, 0), (frame.shape[1], panel_height), (0, 0, 0), -1)
    cv2.addWeighted(overlay, 0.5, frame, 0.5, 0, frame)
    draw_guides(frame)

    lines = [
        f"Curso: {session.course_display}",
        f"Estudiante: {student_name}",
        f"Proxima foto: {session.next_id:03d}",
        f"Fotos guardadas: {len(session.records)}",
        "Teclas: p=tomar foto | q=salir | r=rehacer desde revision",
    ]
    if camera_label:
        lines.append(camera_label)
    if status_line:
        lines.append(status_line)

    y = 28
    for line in lines:
        cv2.putText(frame, line, (16, y), cv2.FONT_HERSHEY_SIMPLEX, 0.68, (255, 255, 255), 2, cv2.LINE_AA)
        y += 26
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
    student_name: str,
    camera_label: str,
) -> str:
    while True:
        ok, frame = capture.read()
        if not ok or frame is None:
            blank = draw_overlay(
                np.zeros((720, 1280, 3), dtype=np.uint8),
                session,
                student_name,
                status_line="No se pudo leer la camara. Revisa la conexion o cambia de indice.",
                camera_label=camera_label,
            )
            cv2.imshow(WINDOW_NAME, blank)
            key = cv2.waitKey(200) & 0xFF
            if key == ord("q"):
                return "quit"
            continue

        preview = draw_overlay(frame.copy(), session, student_name, camera_label=camera_label)
        cv2.imshow(WINDOW_NAME, preview)
        key = cv2.waitKey(1) & 0xFF

        if key == ord("q"):
            return "quit"
        if key != ord("p"):
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


def ask_student_name(session: SessionContext) -> Optional[str]:
    print(f"\nCurso actual: {session.course_display}")
    print(f"Siguiente numero: {session.next_id:03d}")
    print("Escribe el nombre del estudiante.")
    print("Comandos: q=terminar curso | revisar=abrir carpeta | ultimo=ver ultimo registro")

    while True:
        value = input("Estudiante: ").strip()
        if not value:
            print("Debes escribir un nombre o un comando.")
            continue
        if value.lower() == "q":
            return None
        if value.lower() == "revisar":
            open_folder(session.session_dir)
            continue
        if value.lower() == "ultimo":
            if session.records:
                last = session.records[-1]
                print(f"Ultimo: {last.id:03d} | {last.filename} | {last.student_name} | {last.timestamp}")
            else:
                print("Aun no hay fotos guardadas en esta carpeta.")
            continue
        return value


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


def run_capture_loop(camera_index: int, backend_id: int, backend_name: str, session: SessionContext) -> Path:
    capture = open_camera(camera_index, backend_id)
    if not capture.isOpened():
        raise RuntimeError(f"No se pudo abrir la camara con indice {camera_index}.")

    capture.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
    capture.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
    warm_up_camera(capture)
    camera_label = f"Camara: {camera_index} | backend: {backend_name}"

    cv2.namedWindow(WINDOW_NAME, cv2.WINDOW_NORMAL)
    cv2.resizeWindow(WINDOW_NAME, 1280, 720)

    try:
        while True:
            student_name = ask_student_name(session)
            if student_name is None:
                break

            print("Abriendo preview. En la ventana usa p para capturar y q para salir.")
            result = capture_photo(capture, session, student_name, camera_label)
            if result == "captured":
                print(f"Foto guardada para {student_name}.")
                continue
            if result == "quit":
                print("Sesion cerrada desde la ventana de captura.")
                break
    finally:
        capture.release()
        cv2.destroyAllWindows()

    return write_session_report(session, camera_index, backend_name)


def main() -> None:
    app_dir = Path(__file__).resolve().parent
    session: Optional[SessionContext] = None
    session_report_path: Optional[Path] = None
    print(f"{APP_TITLE} - Captura local de fotos tipo credencial")
    print("-" * 56)

    try:
        session = initialize_session(app_dir)
        camera_index, backend_id, backend_name = select_camera()
        session_report_path = run_capture_loop(camera_index, backend_id, backend_name, session)
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
