from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional

import cv2
import tkinter as tk
from PIL import Image, ImageTk
from tkinter import messagebox, ttk

APP_ROOT = Path(__file__).resolve().parent.parent
if str(APP_ROOT) not in sys.path:
    sys.path.insert(0, str(APP_ROOT))

from castel_credcam import (  # noqa: E402
    CSV_FILENAME,
    PHOTOS_DIRNAME,
    TEST_FOLDER_NAME,
    PhotoRecord,
    append_csv_record,
    configure_capture,
    list_available_cameras,
    load_camera_aliases,
    load_existing_records,
    open_camera,
    open_folder,
    rewrite_csv,
    sanitize_folder_name,
)


APP_TITLE = "CastelCredCam Studio"
WINDOW_BG = "#14061E"
PANEL_BG = "#241033"
CARD_BG = "#31164A"
ACCENT_PURPLE = "#8B4DFF"
ACCENT_GOLD = "#F4C95D"
TEXT_PRIMARY = "#F7F1FF"
TEXT_MUTED = "#D8C8F2"
SUCCESS = "#6EE7B7"
DANGER = "#FF7A90"


@dataclass
class GuiSession:
    mode: str
    course_display: str
    course_slug: str
    photos_root: Path
    session_dir: Path
    csv_path: Path
    records: list[PhotoRecord]
    started_at: datetime

    @property
    def next_id(self) -> int:
        return len(self.records) + 1

    def filename_for(self, photo_id: int) -> str:
        prefix = "PRUEBA" if self.mode == "test" else self.course_slug
        return f"{prefix}_{photo_id:03d}.jpg"


class CastelCredCamGUI:
    def __init__(self) -> None:
        self.root = tk.Tk()
        self.root.title(APP_TITLE)
        self.root.geometry("1460x900")
        self.root.minsize(1240, 760)
        self.root.configure(bg=WINDOW_BG)

        self.aliases = load_camera_aliases(APP_ROOT)
        self.available_cameras = list_available_cameras(self.aliases)
        self.current_camera_index: Optional[int] = None
        self.current_backend_id: Optional[int] = None
        self.current_backend_name: str = ""
        self.current_camera_alias: str = ""
        self.capture: Optional[cv2.VideoCapture] = None
        self.preview_job: Optional[str] = None
        self.current_frame = None
        self.tk_image = None
        self.session: Optional[GuiSession] = None
        self.face_cascade = cv2.CascadeClassifier(
            cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
        )

        self.mode_var = tk.StringVar(value="test")
        self.course_var = tk.StringVar(value="")
        self.student_var = tk.StringVar(value="")
        self.camera_var = tk.StringVar(value="")
        self.status_var = tk.StringVar(value="Listo para iniciar. Selecciona camara y sesion.")
        self.face_guide_var = tk.BooleanVar(value=True)
        self.mirror_var = tk.BooleanVar(value=False)
        self.recent_var = tk.StringVar(value="Sin capturas aun.")
        self.session_var = tk.StringVar(value="Sesion no iniciada")
        self.preview_camera_var = tk.StringVar(value="")

        self._configure_style()
        self._build_layout()
        self._load_camera_choices()
        self._bind_shortcuts()
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

    def _configure_style(self) -> None:
        style = ttk.Style(self.root)
        style.theme_use("clam")
        style.configure("Panel.TFrame", background=PANEL_BG)
        style.configure("Card.TFrame", background=CARD_BG)
        style.configure("Title.TLabel", background=PANEL_BG, foreground=TEXT_PRIMARY, font=("Segoe UI", 22, "bold"))
        style.configure("Body.TLabel", background=CARD_BG, foreground=TEXT_PRIMARY, font=("Segoe UI", 10))
        style.configure("Muted.TLabel", background=CARD_BG, foreground=TEXT_MUTED, font=("Segoe UI", 9))
        style.configure("Accent.TButton", background=ACCENT_PURPLE, foreground=TEXT_PRIMARY, font=("Segoe UI", 10, "bold"), padding=8)
        style.map("Accent.TButton", background=[("active", "#9C68FF")])
        style.configure("Gold.TButton", background=ACCENT_GOLD, foreground="#2B1700", font=("Segoe UI", 10, "bold"), padding=8)
        style.map("Gold.TButton", background=[("active", "#FFD87A")])
        style.configure("Danger.TButton", background=DANGER, foreground=TEXT_PRIMARY, font=("Segoe UI", 10, "bold"), padding=8)
        style.configure("TEntry", fieldbackground="#FFF9FE", foreground="#1B102A", padding=6)
        style.configure("TCombobox", fieldbackground="#FFF9FE", foreground="#1B102A", padding=4)
        style.configure("TRadiobutton", background=CARD_BG, foreground=TEXT_PRIMARY, font=("Segoe UI", 10))
        style.map("TRadiobutton", background=[("active", CARD_BG)])
        style.configure("TCheckbutton", background=CARD_BG, foreground=TEXT_PRIMARY, font=("Segoe UI", 10))

    def _build_layout(self) -> None:
        self.root.grid_columnconfigure(1, weight=1)
        self.root.grid_rowconfigure(0, weight=1)

        left = ttk.Frame(self.root, style="Panel.TFrame", width=360)
        left.grid(row=0, column=0, sticky="nsew")
        left.grid_propagate(False)

        right = ttk.Frame(self.root, style="Panel.TFrame")
        right.grid(row=0, column=1, sticky="nsew", padx=(0, 16), pady=16)
        right.grid_rowconfigure(1, weight=1)
        right.grid_columnconfigure(0, weight=1)

        title = ttk.Label(left, text=APP_TITLE, style="Title.TLabel")
        title.pack(anchor="w", padx=18, pady=(18, 4))
        subtitle = tk.Label(
            left,
            text="Captura por curso con estilo morado/dorado",
            bg=PANEL_BG,
            fg=ACCENT_GOLD,
            font=("Segoe UI", 10, "bold"),
        )
        subtitle.pack(anchor="w", padx=20, pady=(0, 14))

        self._make_session_card(left)
        self._make_camera_card(left)
        self._make_student_card(left)
        self._make_recent_card(left)

        header = tk.Label(
            right,
            textvariable=self.session_var,
            bg=WINDOW_BG,
            fg=TEXT_PRIMARY,
            anchor="w",
            font=("Segoe UI", 13, "bold"),
            padx=8,
            pady=6,
        )
        header.grid(row=0, column=0, sticky="ew", pady=(0, 10))

        preview_card = tk.Frame(right, bg=CARD_BG, highlightbackground="#4F2B74", highlightthickness=1)
        preview_card.grid(row=1, column=0, sticky="nsew")
        preview_card.grid_rowconfigure(1, weight=1)
        preview_card.grid_columnconfigure(0, weight=1)

        preview_toolbar = tk.Frame(preview_card, bg="#20102F", padx=10, pady=8)
        preview_toolbar.grid(row=0, column=0, sticky="ew")
        preview_toolbar.grid_columnconfigure(1, weight=1)

        tk.Label(
            preview_toolbar,
            text="Camara",
            bg="#20102F",
            fg=ACCENT_GOLD,
            font=("Segoe UI", 10, "bold"),
        ).grid(row=0, column=0, sticky="w", padx=(0, 8))

        self.preview_camera_combo = ttk.Combobox(
            preview_toolbar,
            textvariable=self.preview_camera_var,
            state="readonly",
            width=42,
        )
        self.preview_camera_combo.grid(row=0, column=1, sticky="ew", padx=(0, 10))
        self.preview_camera_combo.bind("<<ComboboxSelected>>", lambda _event: self.change_camera(from_preview=True))

        ttk.Checkbutton(preview_toolbar, text="Voltear", variable=self.mirror_var).grid(row=0, column=2, sticky="w", padx=(0, 10))
        ttk.Checkbutton(preview_toolbar, text="Rostro", variable=self.face_guide_var).grid(row=0, column=3, sticky="w", padx=(0, 10))
        ttk.Button(preview_toolbar, text="Siguiente cam", style="Gold.TButton", command=self.cycle_camera).grid(row=0, column=4, sticky="e")

        self.preview_label = tk.Label(
            preview_card,
            bg="#0D0914",
            fg=TEXT_MUTED,
            text="Selecciona una camara y comienza una sesion.",
            font=("Segoe UI", 16, "bold"),
        )
        self.preview_label.grid(row=1, column=0, sticky="nsew")

        status_bar = tk.Label(
            right,
            textvariable=self.status_var,
            bg="#1B0F2A",
            fg=SUCCESS,
            anchor="w",
            padx=10,
            pady=8,
            font=("Segoe UI", 10, "bold"),
        )
        status_bar.grid(row=2, column=0, sticky="ew", pady=(10, 0))

    def _make_card(self, parent: tk.Widget, title: str) -> ttk.Frame:
        card = ttk.Frame(parent, style="Card.TFrame")
        card.pack(fill="x", padx=16, pady=8)
        tk.Label(card, text=title, bg=CARD_BG, fg=ACCENT_GOLD, font=("Segoe UI", 11, "bold")).pack(
            anchor="w", padx=14, pady=(12, 8)
        )
        return card

    def _make_session_card(self, parent: tk.Widget) -> None:
        card = self._make_card(parent, "Sesion")
        ttk.Radiobutton(card, text="Modo prueba", variable=self.mode_var, value="test").pack(anchor="w", padx=14, pady=2)
        ttk.Radiobutton(card, text="Modo curso", variable=self.mode_var, value="course").pack(anchor="w", padx=14, pady=2)
        ttk.Label(card, text="Curso", style="Muted.TLabel").pack(anchor="w", padx=14, pady=(10, 2))
        ttk.Entry(card, textvariable=self.course_var).pack(fill="x", padx=14, pady=(0, 10))
        ttk.Button(card, text="Iniciar sesion", style="Accent.TButton", command=self.start_session).pack(
            fill="x", padx=14, pady=(0, 14)
        )

    def _make_camera_card(self, parent: tk.Widget) -> None:
        card = self._make_card(parent, "Camara")
        ttk.Label(card, text="Fuente detectada", style="Muted.TLabel").pack(anchor="w", padx=14, pady=(0, 2))
        self.camera_combo = ttk.Combobox(card, textvariable=self.camera_var, state="readonly")
        self.camera_combo.pack(fill="x", padx=14, pady=(0, 10))
        self.camera_combo.bind("<<ComboboxSelected>>", lambda _event: self.change_camera())
        ttk.Checkbutton(card, text="Ayuda visual de rostro", variable=self.face_guide_var).pack(anchor="w", padx=14, pady=2)
        ttk.Checkbutton(card, text="Espejo horizontal", variable=self.mirror_var).pack(anchor="w", padx=14, pady=2)
        ttk.Button(card, text="Abrir carpeta fotos", style="Gold.TButton", command=self.open_photos_root).pack(
            fill="x", padx=14, pady=(10, 14)
        )

    def _make_student_card(self, parent: tk.Widget) -> None:
        card = self._make_card(parent, "Estudiante y captura")
        ttk.Label(card, text="Nombre actual", style="Muted.TLabel").pack(anchor="w", padx=14, pady=(0, 2))
        entry = ttk.Entry(card, textvariable=self.student_var)
        entry.pack(fill="x", padx=14, pady=(0, 10))
        entry.bind("<Return>", lambda _event: self.capture_photo())

        buttons = tk.Frame(card, bg=CARD_BG)
        buttons.pack(fill="x", padx=14, pady=(0, 6))
        ttk.Button(buttons, text="Capturar", style="Accent.TButton", command=self.capture_photo).pack(
            side="left", fill="x", expand=True
        )
        ttk.Button(buttons, text="Limpiar", style="Gold.TButton", command=lambda: self.student_var.set("")).pack(
            side="left", fill="x", expand=True, padx=(8, 0)
        )

        buttons2 = tk.Frame(card, bg=CARD_BG)
        buttons2.pack(fill="x", padx=14, pady=(0, 14))
        ttk.Button(buttons2, text="Rehacer ultima", style="Gold.TButton", command=self.retake_last).pack(
            side="left", fill="x", expand=True
        )
        ttk.Button(buttons2, text="Cerrar sesion", style="Danger.TButton", command=self.close_session).pack(
            side="left", fill="x", expand=True, padx=(8, 0)
        )

    def _make_recent_card(self, parent: tk.Widget) -> None:
        card = self._make_card(parent, "Recientes")
        label = tk.Label(
            card,
            textvariable=self.recent_var,
            justify="left",
            anchor="w",
            bg=CARD_BG,
            fg=TEXT_MUTED,
            font=("Consolas", 9),
            wraplength=300,
        )
        label.pack(fill="x", padx=14, pady=(0, 14))

    def _load_camera_choices(self) -> None:
        values = []
        for index, label, backend_id, backend_name, alias in self.available_cameras:
            backend_key = self._backend_key_from_id(backend_id)
            values.append(f"{alias} | idx {index} | {backend_name} | {backend_key}")

        self.camera_combo["values"] = values
        self.preview_camera_combo["values"] = values
        if values:
            self.camera_combo.current(0)
            self.preview_camera_combo.current(0)
            self.change_camera()
        else:
            self.status_var.set("No se detectaron camaras compatibles.")

    def _backend_key_from_id(self, backend_id: int) -> str:
        for key, value in {
            "dshow": cv2.CAP_DSHOW,
            "msmf": cv2.CAP_MSMF,
            "any": cv2.CAP_ANY,
        }.items():
            if value == backend_id:
                return key
        return "any"

    def change_camera(self, from_preview: bool = False) -> None:
        selection = self.preview_camera_combo.current() if from_preview else self.camera_combo.current()
        if selection < 0 or selection >= len(self.available_cameras):
            return

        index, _label, backend_id, backend_name, alias = self.available_cameras[selection]
        self.camera_combo.current(selection)
        self.preview_camera_combo.current(selection)
        self.current_camera_index = index
        self.current_backend_id = backend_id
        self.current_backend_name = backend_name
        self.current_camera_alias = alias
        self._open_selected_camera()

    def cycle_camera(self) -> None:
        if not self.available_cameras:
            return
        current = self.preview_camera_combo.current()
        next_index = 0 if current < 0 else (current + 1) % len(self.available_cameras)
        self.preview_camera_combo.current(next_index)
        self.change_camera(from_preview=True)

    def _open_selected_camera(self) -> None:
        self._release_capture()
        if self.current_camera_index is None or self.current_backend_id is None:
            return

        cap = open_camera(self.current_camera_index, self.current_backend_id)
        if not cap.isOpened():
            self.status_var.set("No se pudo abrir la camara seleccionada.")
            return

        configure_capture(cap)
        self.capture = cap
        self.status_var.set(f"Camara activa: {self.current_camera_alias}")
        self._schedule_preview()

    def _schedule_preview(self) -> None:
        if self.preview_job is not None:
            self.root.after_cancel(self.preview_job)
        self.preview_job = self.root.after(30, self._update_preview)

    def _update_preview(self) -> None:
        self.preview_job = None
        frame = None

        if self.capture is not None:
            ok, frame = self.capture.read()
            if ok and frame is not None:
                if self.mirror_var.get():
                    frame = cv2.flip(frame, 1)
                frame = self._decorate_frame(frame)
                self.current_frame = frame.copy()
                rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                image = Image.fromarray(rgb)
                self.tk_image = ImageTk.PhotoImage(image=image)
                self.preview_label.configure(image=self.tk_image, text="")
            else:
                self.preview_label.configure(
                    image="",
                    text="No se pudo leer la camara.\nRevisa la conexion o cambia de fuente.",
                )
        else:
            self.preview_label.configure(image="", text="Selecciona una camara para empezar.")

        self._schedule_preview()

    def _decorate_frame(self, frame):
        height, width = frame.shape[:2]

        # Header translucent strip
        overlay = frame.copy()
        cv2.rectangle(overlay, (0, 0), (width, 110), (35, 14, 51), -1)
        cv2.addWeighted(overlay, 0.68, frame, 0.32, 0, frame)

        guide_w = int(width * 0.24)
        guide_h = int(height * 0.46)
        cx = width // 2
        cy = height // 2 + 20
        x1 = max(30, cx - guide_w // 2)
        y1 = max(130, cy - guide_h // 2)
        x2 = min(width - 30, cx + guide_w // 2)
        y2 = min(height - 30, cy + guide_h // 2)

        cv2.rectangle(frame, (x1, y1), (x2, y2), (93, 201, 244), 2)
        cv2.line(frame, (cx, y1), (cx, y2), (93, 201, 244), 1)
        cv2.line(frame, (x1, cy), (x2, cy), (93, 201, 244), 1)
        cv2.putText(frame, "Guia credencial", (x1, y1 - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.52, (93, 201, 244), 1, cv2.LINE_AA)

        if self.face_guide_var.get() and not self.face_cascade.empty():
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            faces = self.face_cascade.detectMultiScale(gray, scaleFactor=1.15, minNeighbors=5, minSize=(70, 70))
            for (fx, fy, fw, fh) in faces[:1]:
                cv2.rectangle(frame, (fx, fy), (fx + fw, fy + fh), (244, 201, 93), 2)
                cv2.putText(frame, "Rostro detectado", (fx, max(24, fy - 8)), cv2.FONT_HERSHEY_SIMPLEX, 0.48, (244, 201, 93), 1, cv2.LINE_AA)

        course = self.session.course_display if self.session else "Sin sesion"
        photo_no = self.session.next_id if self.session else 1
        saved = len(self.session.records) if self.session else 0
        typed_name = self.student_var.get().strip() or "-"
        camera = self.current_camera_alias or "Sin camara"

        lines = [
            f"Curso: {course}  |  Foto: {photo_no:03d}  |  Guardadas: {saved}",
            f"Estudiante: {typed_name}",
            f"Camara: {camera}",
            "Enter captura | C cambia camara | V voltea | R rostro",
        ]

        y = 24
        for text in lines:
            cv2.putText(frame, text, (16, y), cv2.FONT_HERSHEY_SIMPLEX, 0.58, (247, 241, 255), 1, cv2.LINE_AA)
            y += 22

        return frame

    def start_session(self) -> None:
        mode = self.mode_var.get()
        photos_root = APP_ROOT / PHOTOS_DIRNAME
        photos_root.mkdir(parents=True, exist_ok=True)

        if mode == "test":
            course_display = "PRUEBA"
            course_slug = "PRUEBA"
            session_dir = photos_root / TEST_FOLDER_NAME
        else:
            course_display = self.course_var.get().strip()
            if not course_display:
                messagebox.showwarning(APP_TITLE, "Escribe el nombre del curso antes de iniciar.")
                return
            course_slug = sanitize_folder_name(course_display)
            session_dir = photos_root / course_slug

        session_dir.mkdir(parents=True, exist_ok=True)
        csv_path = session_dir / CSV_FILENAME
        if not csv_path.exists():
            csv_path.write_text("id,filename,student_name,course,timestamp\n", encoding="utf-8")
        records = load_existing_records(csv_path)

        self.session = GuiSession(
            mode=mode,
            course_display=course_display,
            course_slug=course_slug,
            photos_root=photos_root,
            session_dir=session_dir,
            csv_path=csv_path,
            records=records,
            started_at=datetime.now(),
        )
        self.session_var.set(f"Sesion activa: {course_display} | Carpeta: {session_dir.name}")
        self.status_var.set(f"Sesion iniciada en {session_dir}")
        self._refresh_recent()
        open_folder(photos_root)

    def capture_photo(self) -> None:
        if self.session is None:
            messagebox.showinfo(APP_TITLE, "Primero inicia una sesion.")
            return
        if self.current_frame is None:
            messagebox.showwarning(APP_TITLE, "Todavia no hay un frame valido de camara.")
            return

        student_name = self.student_var.get().strip()
        if not student_name:
            messagebox.showwarning(APP_TITLE, "Escribe el nombre del estudiante.")
            return

        photo_id = self.session.next_id
        filename = self.session.filename_for(photo_id)
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        image_path = self.session.session_dir / filename

        if not cv2.imwrite(str(image_path), self.current_frame):
            messagebox.showerror(APP_TITLE, f"No se pudo guardar la imagen en {image_path}")
            return

        record = PhotoRecord(
            id=photo_id,
            filename=filename,
            student_name=student_name,
            course=self.session.course_display,
            timestamp=timestamp,
        )
        append_csv_record(self.session.csv_path, record)
        self.session.records.append(record)
        self.student_var.set("")
        self.status_var.set(f"Guardada: {filename} | {student_name}")
        self._refresh_recent()

    def retake_last(self) -> None:
        if self.session is None or not self.session.records:
            messagebox.showinfo(APP_TITLE, "No hay capturas para rehacer.")
            return

        record = self.session.records.pop()
        image_path = self.session.session_dir / record.filename
        if image_path.exists():
            image_path.unlink()
        rewrite_csv(self.session.csv_path, self.session.records)
        self.student_var.set(record.student_name)
        self.status_var.set(f"Rehecha la ultima captura. Nombre restaurado: {record.student_name}")
        self._refresh_recent()

    def close_session(self) -> None:
        if self.session is None:
            return
        self.status_var.set(f"Sesion cerrada: {self.session.course_display}")
        self.session_var.set("Sesion no iniciada")
        self.session = None
        self.student_var.set("")
        self._refresh_recent()

    def _bind_shortcuts(self) -> None:
        self.root.bind("<Return>", lambda _event: self.capture_photo())
        self.root.bind("<KeyPress-c>", lambda _event: self.cycle_camera())
        self.root.bind("<KeyPress-C>", lambda _event: self.cycle_camera())
        self.root.bind("<KeyPress-v>", lambda _event: self._toggle_mirror())
        self.root.bind("<KeyPress-V>", lambda _event: self._toggle_mirror())
        self.root.bind("<KeyPress-r>", lambda _event: self._toggle_face_guide())
        self.root.bind("<KeyPress-R>", lambda _event: self._toggle_face_guide())

    def _toggle_mirror(self) -> None:
        self.mirror_var.set(not self.mirror_var.get())
        state = "activado" if self.mirror_var.get() else "desactivado"
        self.status_var.set(f"Volteo {state}")

    def _toggle_face_guide(self) -> None:
        self.face_guide_var.set(not self.face_guide_var.get())
        state = "activada" if self.face_guide_var.get() else "desactivada"
        self.status_var.set(f"Guia de rostro {state}")

    def open_photos_root(self) -> None:
        photos_root = APP_ROOT / PHOTOS_DIRNAME
        photos_root.mkdir(parents=True, exist_ok=True)
        open_folder(photos_root)

    def _refresh_recent(self) -> None:
        if self.session is None or not self.session.records:
            self.recent_var.set("Sin capturas aun.")
            return

        lines = []
        for record in self.session.records[-6:]:
            lines.append(f"{record.id:03d}  {record.filename}  {record.student_name}")
        self.recent_var.set("\n".join(lines))

    def _release_capture(self) -> None:
        if self.capture is not None:
            self.capture.release()
            self.capture = None

    def on_close(self) -> None:
        if self.preview_job is not None:
            self.root.after_cancel(self.preview_job)
        self._release_capture()
        self.root.destroy()

    def run(self) -> None:
        self.root.mainloop()


def main() -> None:
    app = CastelCredCamGUI()
    app.run()


if __name__ == "__main__":
    main()
