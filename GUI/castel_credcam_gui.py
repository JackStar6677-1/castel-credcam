from __future__ import annotations

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
    backend_key_from_id,
    configure_capture,
    list_available_cameras,
    load_camera_aliases,
    load_existing_records,
    load_last_camera,
    open_camera,
    open_folder,
    rewrite_csv,
    sanitize_folder_name,
    save_last_camera,
    silence_opencv_logs,
)


APP_TITLE = "CastelCredCam Studio"
WINDOW_BG = "#14061E"
PANEL_BG = "#241033"
CARD_BG = "#31164A"
INFO_BG = "#1A0D28"
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
        silence_opencv_logs()
        self.root = tk.Tk()
        self.root.title(APP_TITLE)
        self.root.geometry("1500x920")
        self.root.minsize(1200, 760)
        self.root.configure(bg=WINDOW_BG)

        self.aliases = load_camera_aliases(APP_ROOT)
        self.available_cameras = list_available_cameras(self.aliases)
        self.current_camera_index: Optional[int] = None
        self.current_backend_id: Optional[int] = None
        self.current_backend_name = ""
        self.current_camera_alias = ""
        self.capture: Optional[cv2.VideoCapture] = None
        self.preview_job: Optional[str] = None
        self.current_frame = None
        self.tk_image = None
        self.session: Optional[GuiSession] = None
        self.student_entry: Optional[ttk.Entry] = None
        self.current_face_box: Optional[tuple[int, int, int, int]] = None
        self.current_crop_box: Optional[tuple[int, int, int, int]] = None
        self.stable_crop_box: Optional[tuple[int, int, int, int]] = None
        self.face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")

        self.mode_var = tk.StringVar(value="test")
        self.course_var = tk.StringVar(value="")
        self.student_var = tk.StringVar(value="")
        self.camera_var = tk.StringVar(value="")
        self.preview_camera_var = tk.StringVar(value="")
        self.status_var = tk.StringVar(value="Listo para iniciar. Selecciona camara y sesion.")
        self.session_var = tk.StringVar(value="Sesion no iniciada")
        self.recent_var = tk.StringVar(value="Sin capturas aun.")

        self.face_guide_var = tk.BooleanVar(value=True)
        self.frame_guide_var = tk.BooleanVar(value=True)
        self.mirror_var = tk.BooleanVar(value=False)
        self.crop_portrait_var = tk.BooleanVar(value=True)
        self.zoom_var = tk.DoubleVar(value=1.0)
        self.rotation_var = tk.StringVar(value="0 deg")
        self.countdown_var = tk.StringVar(value="0 s")

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
        style.configure("Muted.TLabel", background=CARD_BG, foreground=TEXT_MUTED, font=("Segoe UI", 9))
        style.configure("Accent.TButton", background=ACCENT_PURPLE, foreground=TEXT_PRIMARY, font=("Segoe UI", 10, "bold"), padding=8)
        style.map("Accent.TButton", background=[("active", "#A56CFF")])
        style.configure("Gold.TButton", background=ACCENT_GOLD, foreground="#291600", font=("Segoe UI", 10, "bold"), padding=8)
        style.map("Gold.TButton", background=[("active", "#FFD97F")])
        style.configure("Danger.TButton", background=DANGER, foreground=TEXT_PRIMARY, font=("Segoe UI", 10, "bold"), padding=8)
        style.configure("TEntry", fieldbackground="#FFF9FE", foreground="#180E24", padding=6)
        style.configure("TCombobox", fieldbackground="#FFF9FE", foreground="#180E24", padding=4)
        style.configure("TRadiobutton", background=CARD_BG, foreground=TEXT_PRIMARY, font=("Segoe UI", 10))
        style.map("TRadiobutton", background=[("active", CARD_BG)])
        style.configure("TCheckbutton", background=CARD_BG, foreground=TEXT_PRIMARY, font=("Segoe UI", 10))

    def _build_layout(self) -> None:
        self.root.grid_columnconfigure(1, weight=1)
        self.root.grid_rowconfigure(0, weight=1)

        left = ttk.Frame(self.root, style="Panel.TFrame", width=320)
        left.grid(row=0, column=0, sticky="nsew")
        left.grid_propagate(False)

        right = ttk.Frame(self.root, style="Panel.TFrame")
        right.grid(row=0, column=1, sticky="nsew", padx=(0, 16), pady=16)
        right.grid_rowconfigure(0, weight=1)
        right.grid_columnconfigure(0, weight=1)

        ttk.Label(left, text=APP_TITLE, style="Title.TLabel").pack(anchor="w", padx=18, pady=(18, 4))
        tk.Label(
            left,
            text="Captura por curso con estilo morado y dorado",
            bg=PANEL_BG,
            fg=ACCENT_GOLD,
            font=("Segoe UI", 10, "bold"),
        ).pack(anchor="w", padx=20, pady=(0, 14))

        self._make_session_card(left)
        self._make_camera_card(left)
        self._make_student_card(left)
        self._make_recent_card(left)

        notebook = ttk.Notebook(right)
        notebook.grid(row=0, column=0, sticky="nsew")

        capture_page = tk.Frame(notebook, bg=WINDOW_BG)
        capture_page.grid_rowconfigure(1, weight=1)
        capture_page.grid_columnconfigure(0, weight=1)
        notebook.add(capture_page, text="Captura")

        info_page = tk.Frame(notebook, bg=INFO_BG)
        notebook.add(info_page, text="Info")

        tk.Label(
            capture_page,
            textvariable=self.session_var,
            bg=WINDOW_BG,
            fg=TEXT_PRIMARY,
            anchor="w",
            font=("Segoe UI", 13, "bold"),
            padx=8,
            pady=6,
        ).grid(row=0, column=0, sticky="ew", pady=(0, 10))

        preview_card = tk.Frame(capture_page, bg=CARD_BG, highlightbackground="#4F2B74", highlightthickness=1)
        preview_card.grid(row=1, column=0, sticky="nsew")
        preview_card.grid_rowconfigure(1, weight=1)
        preview_card.grid_columnconfigure(0, weight=1)

        toolbar = tk.Frame(preview_card, bg="#20102F", padx=10, pady=8)
        toolbar.grid(row=0, column=0, sticky="ew")
        toolbar.grid_columnconfigure(1, weight=1)

        tk.Label(toolbar, text="Camara", bg="#20102F", fg=ACCENT_GOLD, font=("Segoe UI", 10, "bold")).grid(
            row=0, column=0, sticky="w", padx=(0, 8)
        )
        self.preview_camera_combo = ttk.Combobox(toolbar, textvariable=self.preview_camera_var, state="readonly", width=34)
        self.preview_camera_combo.grid(row=0, column=1, sticky="ew", padx=(0, 10))
        self.preview_camera_combo.bind("<<ComboboxSelected>>", lambda _event: self.change_camera(from_preview=True))

        ttk.Checkbutton(toolbar, text="Voltear", variable=self.mirror_var).grid(row=0, column=2, sticky="w", padx=(0, 6))
        ttk.Checkbutton(toolbar, text="Rostro", variable=self.face_guide_var).grid(row=0, column=3, sticky="w", padx=(0, 6))
        ttk.Checkbutton(toolbar, text="Guia", variable=self.frame_guide_var).grid(row=0, column=4, sticky="w", padx=(0, 6))
        ttk.Checkbutton(toolbar, text="Recortar", variable=self.crop_portrait_var).grid(row=0, column=5, sticky="w", padx=(0, 6))
        ttk.Button(toolbar, text="Sig. cam", style="Gold.TButton", command=self.cycle_camera).grid(row=0, column=6, sticky="e")

        tool_row = tk.Frame(preview_card, bg="#180B25", padx=10, pady=6)
        tool_row.grid(row=2, column=0, sticky="ew")

        tk.Label(tool_row, text="Zoom", bg="#180B25", fg=TEXT_MUTED, font=("Segoe UI", 9, "bold")).pack(side="left")
        tk.Scale(
            tool_row,
            from_=1.0,
            to=2.5,
            resolution=0.1,
            orient="horizontal",
            variable=self.zoom_var,
            bg="#180B25",
            fg=TEXT_PRIMARY,
            troughcolor="#5F34A8",
            highlightthickness=0,
            length=120,
        ).pack(side="left", padx=(8, 12))

        tk.Label(tool_row, text="Rotacion", bg="#180B25", fg=TEXT_MUTED, font=("Segoe UI", 9, "bold")).pack(side="left")
        rotation_combo = ttk.Combobox(tool_row, textvariable=self.rotation_var, state="readonly", width=7)
        rotation_combo["values"] = ("0 deg", "90 deg", "180 deg", "270 deg")
        rotation_combo.pack(side="left", padx=(8, 12))

        tk.Label(tool_row, text="Temporizador", bg="#180B25", fg=TEXT_MUTED, font=("Segoe UI", 9, "bold")).pack(side="left")
        countdown_combo = ttk.Combobox(tool_row, textvariable=self.countdown_var, state="readonly", width=6)
        countdown_combo["values"] = ("0 s", "3 s", "5 s")
        countdown_combo.pack(side="left", padx=(8, 12))

        ttk.Button(tool_row, text="Abrir fotos", style="Gold.TButton", command=self.open_photos_root).pack(side="right")

        self.preview_canvas = tk.Canvas(preview_card, bg="#0D0914", highlightthickness=0, bd=0)
        self.preview_canvas.grid(row=1, column=0, sticky="nsew")
        self.preview_canvas.bind("<Button-1>", lambda _event: self._focus_student())

        tk.Label(
            capture_page,
            textvariable=self.status_var,
            bg="#1B0F2A",
            fg=SUCCESS,
            anchor="w",
            padx=10,
            pady=8,
            font=("Segoe UI", 10, "bold"),
        ).grid(row=2, column=0, sticky="ew", pady=(10, 0))

        self._build_info_page(info_page)

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
        ttk.Button(card, text="Iniciar sesion", style="Accent.TButton", command=self.start_session).pack(fill="x", padx=14, pady=(0, 14))

    def _make_camera_card(self, parent: tk.Widget) -> None:
        card = self._make_card(parent, "Camara")
        ttk.Label(card, text="Fuente detectada", style="Muted.TLabel").pack(anchor="w", padx=14, pady=(0, 2))
        self.camera_combo = ttk.Combobox(card, textvariable=self.camera_var, state="readonly")
        self.camera_combo.pack(fill="x", padx=14, pady=(0, 10))
        self.camera_combo.bind("<<ComboboxSelected>>", lambda _event: self.change_camera())
        ttk.Checkbutton(card, text="Ayuda visual de rostro", variable=self.face_guide_var).pack(anchor="w", padx=14, pady=2)
        ttk.Checkbutton(card, text="Espejo horizontal", variable=self.mirror_var).pack(anchor="w", padx=14, pady=2)
        ttk.Checkbutton(card, text="Mostrar guia", variable=self.frame_guide_var).pack(anchor="w", padx=14, pady=2)
        ttk.Checkbutton(card, text="Recortar tipo credencial 3:4", variable=self.crop_portrait_var).pack(anchor="w", padx=14, pady=2)
        ttk.Button(card, text="Abrir carpeta fotos", style="Gold.TButton", command=self.open_photos_root).pack(fill="x", padx=14, pady=(10, 14))

    def _make_student_card(self, parent: tk.Widget) -> None:
        card = self._make_card(parent, "Estudiante y captura")
        ttk.Label(card, text="Nombre actual", style="Muted.TLabel").pack(anchor="w", padx=14, pady=(0, 2))
        self.student_entry = ttk.Entry(card, textvariable=self.student_var)
        self.student_entry.pack(fill="x", padx=14, pady=(0, 10))
        self.student_entry.bind("<Return>", lambda _event: self.capture_photo())

        buttons = tk.Frame(card, bg=CARD_BG)
        buttons.pack(fill="x", padx=14, pady=(0, 6))
        ttk.Button(buttons, text="Capturar", style="Accent.TButton", command=self.capture_photo).pack(side="left", fill="x", expand=True)
        ttk.Button(buttons, text="Limpiar", style="Gold.TButton", command=lambda: self.student_var.set("")).pack(side="left", fill="x", expand=True, padx=(8, 0))

        buttons2 = tk.Frame(card, bg=CARD_BG)
        buttons2.pack(fill="x", padx=14, pady=(0, 14))
        ttk.Button(buttons2, text="Rehacer ultima", style="Gold.TButton", command=self.retake_last).pack(side="left", fill="x", expand=True)
        ttk.Button(buttons2, text="Cerrar sesion", style="Danger.TButton", command=self.close_session).pack(side="left", fill="x", expand=True, padx=(8, 0))

    def _make_recent_card(self, parent: tk.Widget) -> None:
        card = self._make_card(parent, "Recientes")
        tk.Label(
            card,
            textvariable=self.recent_var,
            justify="left",
            anchor="w",
            bg=CARD_BG,
            fg=TEXT_MUTED,
            font=("Consolas", 9),
            wraplength=300,
        ).pack(fill="x", padx=14, pady=(0, 14))

    def _build_info_page(self, parent: tk.Widget) -> None:
        parent.grid_rowconfigure(0, weight=1)
        parent.grid_columnconfigure(0, weight=1)
        info = tk.Text(
            parent,
            wrap="word",
            bg=INFO_BG,
            fg=TEXT_PRIMARY,
            font=("Segoe UI", 11),
            relief="flat",
            padx=18,
            pady=18,
            insertbackground=ACCENT_GOLD,
        )
        info.grid(row=0, column=0, sticky="nsew")
        info.insert(
            "1.0",
            (
                "CastelCredCam Studio\n\n"
                "Flujo recomendado\n"
                "1. Inicia una sesion en modo prueba o curso.\n"
                "2. Elige una camara desde la izquierda o desde la barra del preview.\n"
                "3. Escribe el nombre del estudiante.\n"
                "4. Usa Enter o el boton Capturar.\n"
                "5. Revisa la carpeta fotos mientras avanzas.\n\n"
                "Atajos\n"
                "- Enter: capturar foto\n"
                "- C: siguiente camara\n"
                "- V: voltear horizontalmente\n"
                "- R: activar o desactivar ayuda de rostro\n"
                "- G: activar o desactivar guia de encuadre\n"
                "- X: activar o desactivar recorte automatico\n"
                "- O: abrir carpeta de fotos\n"
                "- F: enfocar nombre del estudiante\n"
                "- Escape: limpiar nombre actual\n\n"
                "Funciones utiles de camara\n"
                "- Zoom digital\n"
                "- Rotacion 0, 90, 180 y 270 grados\n"
                "- Temporizador de captura 0, 3 o 5 segundos\n"
                "- Guia de encuadre\n"
                "- Ayuda visual de rostro\n"
                "- Recorte automatico tipo credencial 3:4\n"
                "- Preview del recorte siguiendo el rostro cuando esta disponible\n"
                "- Selector rapido de camara dentro del preview\n\n"
                "Consejos\n"
                "- Usa buena luz frontal.\n"
                "- Manten la camara fija en tripode.\n"
                "- Si usas Recortar, procura que el rostro quede visible y centrado.\n"
                "- Haz una sesion de prueba antes de un curso real.\n"
                "- Verifica que el nombre este correcto antes de capturar.\n"
            ),
        )
        info.configure(state="disabled")

    def _load_camera_choices(self) -> None:
        values = []
        for index, label, backend_id, backend_name, alias in self.available_cameras:
            values.append(f"{alias} | idx {index} | {backend_name} | {backend_key_from_id(backend_id)}")

        self.camera_combo["values"] = values
        self.preview_camera_combo["values"] = values
        if not values:
            self.status_var.set("No se detectaron camaras compatibles.")
            return

        preferred = 0
        remembered_index, remembered_backend = load_last_camera(APP_ROOT)
        if remembered_index is not None and remembered_backend is not None:
            for pos, (index, _label, backend_id, _backend_name, _alias) in enumerate(self.available_cameras):
                if index == remembered_index and backend_key_from_id(backend_id) == remembered_backend:
                    preferred = pos
                    break

        self.camera_combo.current(preferred)
        self.preview_camera_combo.current(preferred)
        self.change_camera()

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
        save_last_camera(APP_ROOT, index, backend_key_from_id(backend_id))
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
        if self.capture is None:
            self._show_placeholder("Selecciona una camara para empezar.")
            self._schedule_preview()
            return

        ok, frame = self.capture.read()
        if not ok or frame is None:
            self._show_placeholder("No se pudo leer la camara.\nRevisa la conexion o cambia de fuente.")
            self._schedule_preview()
            return

        if self.mirror_var.get():
            frame = cv2.flip(frame, 1)
        transformed = self._apply_transformations(frame)
        self.current_face_box = self._detect_primary_face(transformed)
        if self.crop_portrait_var.get():
            next_crop_box = self._compute_portrait_crop_box(
                transformed.shape[1], transformed.shape[0], self.current_face_box
            )
            smoothed_box = self._smooth_crop_box(next_crop_box)
            self.current_crop_box = self._constrain_crop_box(
                smoothed_box,
                transformed.shape[1],
                transformed.shape[0],
            )
            portrait_frame = self._crop_frame_with_box(transformed, self.current_crop_box)
            self.current_frame = portrait_frame.copy()
            preview_frame = self._decorate_frame(portrait_frame.copy())
        else:
            self.current_crop_box = None
            self.stable_crop_box = None
            self.current_frame = transformed.copy()
            preview_frame = self._decorate_frame(transformed.copy())
        display_frame = self._fit_frame_to_preview(preview_frame)

        rgb = cv2.cvtColor(display_frame, cv2.COLOR_BGR2RGB)
        image = Image.fromarray(rgb)
        self.tk_image = ImageTk.PhotoImage(image=image)
        self.preview_canvas.delete("all")
        canvas_w = max(320, self.preview_canvas.winfo_width())
        canvas_h = max(240, self.preview_canvas.winfo_height())
        self.preview_canvas.create_image(canvas_w // 2, canvas_h // 2, image=self.tk_image, anchor="center")
        self._schedule_preview()

    def _fit_frame_to_preview(self, frame):
        target_w = max(320, self.preview_canvas.winfo_width() - 20)
        target_h = max(240, self.preview_canvas.winfo_height() - 20)
        src_h, src_w = frame.shape[:2]
        scale = min(target_w / src_w, target_h / src_h)
        new_w = max(1, int(src_w * scale))
        new_h = max(1, int(src_h * scale))
        return cv2.resize(frame, (new_w, new_h), interpolation=cv2.INTER_AREA)

    def _show_placeholder(self, text: str) -> None:
        self.preview_canvas.delete("all")
        canvas_w = max(320, self.preview_canvas.winfo_width())
        canvas_h = max(240, self.preview_canvas.winfo_height())
        self.preview_canvas.create_text(
            canvas_w // 2,
            canvas_h // 2,
            text=text,
            fill=TEXT_MUTED,
            font=("Segoe UI", 16, "bold"),
            justify="center",
        )

    def _apply_transformations(self, frame):
        zoom = max(1.0, float(self.zoom_var.get()))
        if zoom > 1.01:
            height, width = frame.shape[:2]
            crop_w = int(width / zoom)
            crop_h = int(height / zoom)
            x1 = max(0, (width - crop_w) // 2)
            y1 = max(0, (height - crop_h) // 2)
            frame = cv2.resize(frame[y1:y1 + crop_h, x1:x1 + crop_w], (width, height), interpolation=cv2.INTER_LINEAR)

        if self.rotation_var.get() == "90 deg":
            frame = cv2.rotate(frame, cv2.ROTATE_90_CLOCKWISE)
        elif self.rotation_var.get() == "180 deg":
            frame = cv2.rotate(frame, cv2.ROTATE_180)
        elif self.rotation_var.get() == "270 deg":
            frame = cv2.rotate(frame, cv2.ROTATE_90_COUNTERCLOCKWISE)

        return frame

    def _detect_primary_face(self, frame) -> Optional[tuple[int, int, int, int]]:
        if self.face_cascade.empty():
            return None
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        faces = self.face_cascade.detectMultiScale(gray, scaleFactor=1.08, minNeighbors=7, minSize=(90, 90))
        if len(faces) == 0:
            return None
        fx, fy, fw, fh = sorted(faces, key=lambda f: f[2] * f[3], reverse=True)[0]
        return int(fx), int(fy), int(fw), int(fh)

    def _compute_portrait_crop_box(
        self,
        width: int,
        height: int,
        face_box: Optional[tuple[int, int, int, int]],
    ) -> tuple[int, int, int, int]:
        target_ratio = 3 / 4
        max_crop_h = min(height, int(width / target_ratio))
        max_crop_w = int(max_crop_h * target_ratio)

        if face_box is not None:
            fx, fy, fw, fh = face_box
            face_cx = fx + fw / 2
            face_cy = fy + fh / 2
            crop_h = max(int(fh * 2.45), int(height * 0.58))
            crop_h = min(crop_h, max_crop_h)
            crop_w = int(crop_h * target_ratio)
            x1 = int(face_cx - crop_w / 2)
            y1 = int(face_cy - crop_h * 0.36)
        else:
            crop_h = int(max_crop_h * 0.9)
            crop_w = int(crop_h * target_ratio)
            x1 = (width - crop_w) // 2
            y1 = (height - crop_h) // 2

        x1 = max(0, min(x1, width - crop_w))
        y1 = max(0, min(y1, height - crop_h))
        x2 = x1 + crop_w
        y2 = y1 + crop_h
        return x1, y1, x2, y2

    def _smooth_crop_box(self, next_box: tuple[int, int, int, int]) -> tuple[int, int, int, int]:
        if self.stable_crop_box is None:
            self.stable_crop_box = next_box
            return next_box

        prev_x1, prev_y1, prev_x2, prev_y2 = self.stable_crop_box
        next_x1, next_y1, next_x2, next_y2 = next_box
        prev_w = prev_x2 - prev_x1
        prev_h = prev_y2 - prev_y1
        next_w = next_x2 - next_x1
        next_h = next_y2 - next_y1
        move_threshold_x = max(10, int(prev_w * 0.06))
        move_threshold_y = max(10, int(prev_h * 0.06))
        size_threshold_w = max(12, int(prev_w * 0.08))
        size_threshold_h = max(12, int(prev_h * 0.08))

        if (
            abs(next_x1 - prev_x1) < move_threshold_x
            and abs(next_y1 - prev_y1) < move_threshold_y
            and abs(next_w - prev_w) < size_threshold_w
            and abs(next_h - prev_h) < size_threshold_h
        ):
            return self.stable_crop_box

        alpha = 0.12
        prev_cx = (prev_x1 + prev_x2) / 2
        prev_cy = (prev_y1 + prev_y2) / 2
        next_cx = (next_x1 + next_x2) / 2
        next_cy = (next_y1 + next_y2) / 2

        blended_cx = prev_cx + (next_cx - prev_cx) * alpha
        blended_cy = prev_cy + (next_cy - prev_cy) * alpha
        blended_h = prev_h + (next_h - prev_h) * alpha
        blended_h = max(240, blended_h)
        blended_w = blended_h * (3 / 4)

        x1 = int(blended_cx - blended_w / 2)
        y1 = int(blended_cy - blended_h / 2)
        x2 = int(x1 + blended_w)
        y2 = int(y1 + blended_h)
        blended = (x1, y1, x2, y2)
        self.stable_crop_box = blended
        return blended

    def _crop_frame_with_box(self, frame, crop_box: tuple[int, int, int, int], output_size: tuple[int, int] = (900, 1200)):
        x1, y1, x2, y2 = crop_box
        crop = frame[y1:y2, x1:x2]
        if crop.size == 0:
            return frame
        return cv2.resize(crop, output_size, interpolation=cv2.INTER_CUBIC)

    def _constrain_crop_box(
        self,
        crop_box: tuple[int, int, int, int],
        width: int,
        height: int,
    ) -> tuple[int, int, int, int]:
        x1, y1, x2, y2 = crop_box
        crop_w = x2 - x1
        crop_h = y2 - y1
        crop_w = min(crop_w, width)
        crop_h = min(crop_h, height)
        crop_w = int(crop_h * (3 / 4))
        x1 = max(0, min(x1, width - crop_w))
        y1 = max(0, min(y1, height - crop_h))
        return x1, y1, x1 + crop_w, y1 + crop_h

    def _decorate_frame(self, frame):
        height, width = frame.shape[:2]
        overlay = frame.copy()
        cv2.rectangle(overlay, (0, 0), (width, 72), (35, 14, 51), -1)
        cv2.addWeighted(overlay, 0.52, frame, 0.48, 0, frame)
        is_portrait_preview = self.crop_portrait_var.get() and width < height

        if self.frame_guide_var.get():
            if is_portrait_preview:
                pad_x = int(width * 0.11)
                pad_top = int(height * 0.12)
                pad_bottom = int(height * 0.08)
                x1 = pad_x
                y1 = pad_top
                x2 = width - pad_x
                y2 = height - pad_bottom
                cx = (x1 + x2) // 2
                eye_y = y1 + int((y2 - y1) * 0.38)
                cv2.rectangle(frame, (x1, y1), (x2, y2), (93, 201, 244), 2)
                cv2.line(frame, (cx, y1), (cx, y2), (93, 201, 244), 1)
                cv2.line(frame, (x1, eye_y), (x2, eye_y), (93, 201, 244), 1)
                cv2.putText(
                    frame,
                    "Credencial auto 3:4",
                    (x1, max(88, y1 - 10)),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.48,
                    (93, 201, 244),
                    1,
                    cv2.LINE_AA,
                )
            else:
                guide_w = int(width * 0.22)
                guide_h = int(height * 0.42)
                cx = width // 2
                cy = height // 2 + 18
                x1 = max(30, cx - guide_w // 2)
                y1 = max(96, cy - guide_h // 2)
                x2 = min(width - 30, cx + guide_w // 2)
                y2 = min(height - 30, cy + guide_h // 2)
                cv2.rectangle(frame, (x1, y1), (x2, y2), (93, 201, 244), 2)
                cv2.line(frame, (cx, y1), (cx, y2), (93, 201, 244), 1)
                cv2.line(frame, (x1, cy), (x2, cy), (93, 201, 244), 1)
                cv2.putText(
                    frame,
                    "Guia credencial",
                    (x1, max(88, y1 - 10)),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.48,
                    (93, 201, 244),
                    1,
                    cv2.LINE_AA,
                )

        if self.face_guide_var.get():
            preview_face_box = self._detect_primary_face(frame)
            if preview_face_box is not None:
                fx, fy, fw, fh = preview_face_box
                cv2.rectangle(frame, (fx, fy), (fx + fw, fy + fh), (244, 201, 93), 2)
                cv2.putText(frame, "Rostro", (fx, max(88, fy - 8)), cv2.FONT_HERSHEY_SIMPLEX, 0.46, (244, 201, 93), 1, cv2.LINE_AA)

        course = self.session.course_display if self.session else "Sin sesion"
        photo_no = self.session.next_id if self.session else 1
        saved = len(self.session.records) if self.session else 0
        typed_name = self.student_var.get().strip() or "-"
        camera = self.current_camera_alias or "Sin camara"

        crop_mode = "ON" if self.crop_portrait_var.get() else "OFF"
        lines = [
            f"{course} | Foto {photo_no:03d} | Guardadas {saved}",
            f"Estudiante: {typed_name} | Cam: {camera}",
            f"Enter captura | Auto credencial {'ON' if self.crop_portrait_var.get() else 'OFF'} | X cambia",
        ]

        y = 22
        for text in lines:
            cv2.putText(frame, text, (14, y), cv2.FONT_HERSHEY_SIMPLEX, 0.48, (247, 241, 255), 1, cv2.LINE_AA)
            y += 17
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

        countdown = int(self.countdown_var.get().split()[0])
        for remaining in range(countdown, 0, -1):
            self.status_var.set(f"Capturando en {remaining}...")
            self.root.update()
            self.root.after(1000)

        photo_id = self.session.next_id
        filename = self.session.filename_for(photo_id)
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        image_path = self.session.session_dir / filename

        if not cv2.imwrite(str(image_path), self.current_frame.copy()):
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

    def open_photos_root(self) -> None:
        photos_root = APP_ROOT / PHOTOS_DIRNAME
        photos_root.mkdir(parents=True, exist_ok=True)
        open_folder(photos_root)

    def _refresh_recent(self) -> None:
        if self.session is None or not self.session.records:
            self.recent_var.set("Sin capturas aun.")
            return
        self.recent_var.set("\n".join(f"{r.id:03d}  {r.filename}  {r.student_name}" for r in self.session.records[-6:]))

    def _bind_shortcuts(self) -> None:
        self.root.bind("<Return>", lambda _event: self.capture_photo())
        self.root.bind("<KeyPress-c>", lambda _event: self.cycle_camera())
        self.root.bind("<KeyPress-C>", lambda _event: self.cycle_camera())
        self.root.bind("<KeyPress-v>", lambda _event: self._toggle_mirror())
        self.root.bind("<KeyPress-V>", lambda _event: self._toggle_mirror())
        self.root.bind("<KeyPress-r>", lambda _event: self._toggle_face())
        self.root.bind("<KeyPress-R>", lambda _event: self._toggle_face())
        self.root.bind("<KeyPress-g>", lambda _event: self._toggle_guide())
        self.root.bind("<KeyPress-G>", lambda _event: self._toggle_guide())
        self.root.bind("<KeyPress-x>", lambda _event: self._toggle_crop())
        self.root.bind("<KeyPress-X>", lambda _event: self._toggle_crop())
        self.root.bind("<KeyPress-o>", lambda _event: self.open_photos_root())
        self.root.bind("<KeyPress-O>", lambda _event: self.open_photos_root())
        self.root.bind("<KeyPress-f>", lambda _event: self._focus_student())
        self.root.bind("<KeyPress-F>", lambda _event: self._focus_student())
        self.root.bind("<Escape>", lambda _event: self.student_var.set(""))

    def _toggle_mirror(self) -> None:
        self.mirror_var.set(not self.mirror_var.get())
        self.status_var.set(f"Volteo {'activado' if self.mirror_var.get() else 'desactivado'}")

    def _toggle_face(self) -> None:
        self.face_guide_var.set(not self.face_guide_var.get())
        self.status_var.set(f"Guia de rostro {'activada' if self.face_guide_var.get() else 'desactivada'}")

    def _toggle_guide(self) -> None:
        self.frame_guide_var.set(not self.frame_guide_var.get())
        self.status_var.set(f"Guia de encuadre {'activada' if self.frame_guide_var.get() else 'desactivada'}")

    def _toggle_crop(self) -> None:
        self.crop_portrait_var.set(not self.crop_portrait_var.get())
        self.status_var.set(f"Recorte automatico {'activado' if self.crop_portrait_var.get() else 'desactivado'}")

    def _focus_student(self) -> None:
        if self.student_entry is not None:
            self.student_entry.focus_set()

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

