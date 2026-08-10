"""Audita fotos tipo credencial y marca tomas candidatas a retoque con IA.

El script no intenta juzgar atractivo ni identidad. Solo revisa senales tecnicas
que suelen hacer que una foto salga desfavorecida: ojos no confirmados,
desenfoque, cara cortada, encuadre raro, baja luz o exposicion extrema.
"""

from __future__ import annotations

import argparse
import csv
import html
import json
from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

import cv2
import numpy as np

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png"}
DEFAULT_PHOTOS_DIR = "fotos"
DEFAULT_OUTPUT_DIR = "auditoria_fotos"


@dataclass
class AuditFinding:
    code: str
    severity: int
    message: str


@dataclass
class PhotoAudit:
    path: Path
    course: str
    student: str
    width: int = 0
    height: int = 0
    blur_score: float = 0.0
    brightness: float = 0.0
    contrast: float = 0.0
    face_box: tuple[int, int, int, int] | None = None
    face_count: int = 0
    profile_count: int = 0
    eye_count: int = 0
    eye_centers: list[tuple[int, int]] = field(default_factory=list)
    findings: list[AuditFinding] = field(default_factory=list)

    @property
    def severity(self) -> int:
        return max((finding.severity for finding in self.findings), default=0)

    @property
    def action(self) -> str:
        if self.severity >= 3:
            return "REVISAR / RETOQUE IA PRIORITARIO"
        if self.severity == 2:
            return "REVISAR ANTES DE ENTREGAR"
        if self.severity == 1:
            return "OBSERVACION LEVE"
        return "OK"

    @property
    def reasons(self) -> str:
        return "; ".join(f"{item.code}: {item.message}" for item in self.findings) or "sin alertas"


def load_cascades(names: Iterable[str]) -> tuple[cv2.CascadeClassifier, ...]:
    """Carga cascadas Haar incluidas con OpenCV y descarta las vacias."""
    cascades: list[cv2.CascadeClassifier] = []
    for name in names:
        cascade = cv2.CascadeClassifier(cv2.data.haarcascades + name)
        if not cascade.empty():
            cascades.append(cascade)
    return tuple(cascades)


FAST_FACE_CASCADES = load_cascades(("haarcascade_frontalface_default.xml", "haarcascade_frontalface_alt2.xml"))
FALLBACK_FACE_CASCADES = load_cascades(("haarcascade_frontalface_alt.xml",))
PROFILE_FACE_CASCADES = load_cascades(("haarcascade_profileface.xml",))
EYE_CASCADES = load_cascades(("haarcascade_eye_tree_eyeglasses.xml", "haarcascade_eye.xml"))


def normalize_name_from_filename(path: Path) -> str:
    """Obtiene un nombre legible desde el archivo sin exponer nada externo."""
    stem = path.stem
    if "-" in stem:
        return stem.split("-")[0].strip()
    return stem.strip()


def find_images(root: Path) -> list[Path]:
    """Lista imagenes activas de manera acotada, evitando respaldos y basura."""
    return sorted(
        path
        for path in root.rglob("*")
        if path.is_file() and path.suffix.lower() in IMAGE_EXTENSIONS and not path.name.startswith(".")
    )


def detect_faces(image: np.ndarray, deep_scan: bool = False) -> list[tuple[int, int, int, int]]:
    """Busca rostros en escala reducida para mantener la auditoria liviana."""
    height, width = image.shape[:2]
    max_width = 720
    scale = 1.0
    work = image
    if width > max_width:
        scale = max_width / width
        work = cv2.resize(image, (max_width, max(1, int(height * scale))), interpolation=cv2.INTER_AREA)

    gray = cv2.equalizeHist(cv2.cvtColor(work, cv2.COLOR_BGR2GRAY))
    candidates = run_face_pass(gray, FAST_FACE_CASCADES[:1], scale, ((1.12, 5),))
    if deep_scan and not candidates:
        candidates = run_face_pass(gray, FAST_FACE_CASCADES[1:], scale, ((1.12, 4),))
    if deep_scan and not candidates:
        candidates = run_face_pass(gray, FALLBACK_FACE_CASCADES, scale, ((1.08, 4), (1.14, 3)))
    return unique_boxes(candidates, width, height)


def detect_profile_faces(image: np.ndarray) -> list[tuple[int, int, int, int]]:
    """Busca perfiles para marcar miradas o cabezas giradas sin confundirlo con identidad."""
    height, width = image.shape[:2]
    max_width = 720
    scale = 1.0
    work = image
    if width > max_width:
        scale = max_width / width
        work = cv2.resize(image, (max_width, max(1, int(height * scale))), interpolation=cv2.INTER_AREA)

    gray = cv2.equalizeHist(cv2.cvtColor(work, cv2.COLOR_BGR2GRAY))
    candidates: list[tuple[int, int, int, int]] = []
    for search_frame, mirrored in ((gray, False), (cv2.flip(gray, 1), True)):
        for cascade in PROFILE_FACE_CASCADES:
            faces = cascade.detectMultiScale(search_frame, scaleFactor=1.10, minNeighbors=5, minSize=(58, 58))
            for x, y, w, h in faces:
                if mirrored:
                    x = search_frame.shape[1] - x - w
                if scale != 1.0:
                    x, y, w, h = (int(x / scale), int(y / scale), int(w / scale), int(h / scale))
                candidates.append((x, y, w, h))
    return unique_boxes(candidates, width, height)


def run_face_pass(
    gray: np.ndarray,
    cascades: tuple[cv2.CascadeClassifier, ...],
    scale: float,
    profiles: tuple[tuple[float, int], ...],
) -> list[tuple[int, int, int, int]]:
    """Ejecuta una pasada Haar acotada para no castigar CPU en auditorias masivas."""
    candidates: list[tuple[int, int, int, int]] = []
    for cascade in cascades:
        for scale_factor, neighbors in profiles:
            faces = cascade.detectMultiScale(
                gray,
                scaleFactor=scale_factor,
                minNeighbors=neighbors,
                minSize=(56, 56),
            )
            for x, y, w, h in faces:
                if scale != 1.0:
                    x, y, w, h = (int(x / scale), int(y / scale), int(w / scale), int(h / scale))
                candidates.append((x, y, w, h))
    return candidates


def unique_boxes(boxes: list[tuple[int, int, int, int]], width: int, height: int) -> list[tuple[int, int, int, int]]:
    """Fusiona detecciones repetidas y prioriza las mas utiles para credencial."""
    filtered: list[tuple[int, int, int, int]] = []
    for box in sorted(boxes, key=lambda item: item[2] * item[3], reverse=True):
        x, y, w, h = box
        if w <= 0 or h <= 0:
            continue
        cx, cy = x + w / 2, y + h / 2
        duplicate = False
        for ox, oy, ow, oh in filtered:
            ocx, ocy = ox + ow / 2, oy + oh / 2
            if abs(cx - ocx) < max(w, ow) * 0.35 and abs(cy - ocy) < max(h, oh) * 0.35:
                duplicate = True
                break
        if not duplicate:
            filtered.append((max(0, x), max(0, y), min(w, width), min(h, height)))
    return filtered[:5]


def score_face(box: tuple[int, int, int, int], width: int, height: int) -> float:
    """Prefiere rostro grande, centrado y ubicado cerca del tercio superior."""
    x, y, w, h = box
    cx = x + w / 2
    cy = y + h / 2
    center_penalty = abs(cx - width / 2) / max(1, width) + abs(cy - height * 0.42) / max(1, height)
    return (w * h) * (1.0 - min(0.85, center_penalty))


def count_competing_faces(
    faces: list[tuple[int, int, int, int]],
    main_face: tuple[int, int, int, int],
    image_height: int,
    gray: np.ndarray,
) -> int:
    """Cuenta solo rostros secundarios con ojos; evita falsos positivos en ropa, pelo o insignias."""
    main_area = main_face[2] * main_face[3]
    count = 1
    for face in faces:
        if face == main_face:
            continue
        x, y, w, h = face
        cy = y + h / 2
        area_ratio = (w * h) / max(1, main_area)
        aspect = w / max(1, h)
        if area_ratio >= 0.45 and 0.58 <= aspect <= 1.25 and (cy / max(1, image_height)) < 0.72 and len(detect_eyes(gray, face)) >= 2:
            count += 1
    return count


def detect_eyes(gray: np.ndarray, face_box: tuple[int, int, int, int]) -> list[tuple[int, int]]:
    """Busca ojos plausibles dentro del tercio superior del rostro."""
    x, y, w, h = face_box
    roi_top = y + int(h * 0.12)
    roi_bottom = y + int(h * 0.66)
    roi = gray[roi_top:roi_bottom, x : x + w]
    if roi.size == 0:
        return []

    candidates: list[tuple[int, int, int, int]] = []
    for cascade in EYE_CASCADES:
        eyes = cascade.detectMultiScale(
            roi,
            scaleFactor=1.05,
            minNeighbors=4,
            minSize=(max(10, w // 12), max(8, h // 18)),
        )
        for ex, ey, ew, eh in eyes:
            candidates.append((x + int(ex), roi_top + int(ey), int(ew), int(eh)))

    centers: list[tuple[int, int]] = []
    for ex, ey, ew, eh in sorted(candidates, key=lambda item: item[2] * item[3], reverse=True):
        center = (ex + ew // 2, ey + eh // 2)
        if not any(abs(center[0] - old[0]) < 14 and abs(center[1] - old[1]) < 12 for old in centers):
            centers.append(center)
    return centers[:4]


def add_finding(audit: PhotoAudit, code: str, severity: int, message: str) -> None:
    audit.findings.append(AuditFinding(code=code, severity=severity, message=message))


def audit_photo(path: Path, photos_root: Path, deep_scan: bool = False, pose_check: bool = False) -> PhotoAudit:
    """Calcula metricas y motivos de revision para una foto."""
    course = path.parent.name
    audit = PhotoAudit(path=path, course=course, student=normalize_name_from_filename(path))
    image = cv2.imread(str(path))
    if image is None:
        add_finding(audit, "no_lee", 3, "OpenCV no pudo leer la imagen")
        return audit

    height, width = image.shape[:2]
    audit.width = width
    audit.height = height
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    audit.blur_score = float(cv2.Laplacian(gray, cv2.CV_64F).var())
    audit.brightness = float(np.mean(gray))
    audit.contrast = float(np.std(gray))

    faces = detect_faces(image, deep_scan=deep_scan)
    if not faces:
        add_finding(
            audit,
            "rostro_no_confirmado",
            1,
            "el detector no confirmo rostro; revisar visualmente, sobre todo si hay lentes, cara pequena o pelo en la frente",
        )
        assess_global_quality(audit)
        return audit

    face_box = max(faces, key=lambda box: score_face(box, width, height))
    audit.face_box = face_box
    audit.face_count = count_competing_faces(faces, face_box, height, gray)
    if audit.face_count > 1:
        add_finding(audit, "varios_rostros", 1, f"se detectaron {audit.face_count} rostros plausibles")

    audit.eye_centers = detect_eyes(gray, face_box)
    audit.eye_count = len(audit.eye_centers)
    profile_faces = detect_profile_faces(image) if pose_check else []
    audit.profile_count = len(profile_faces)
    assess_global_quality(audit)
    assess_framing(audit)
    assess_eyes(audit)
    if pose_check:
        assess_pose(audit, profile_faces)
    return audit


def assess_global_quality(audit: PhotoAudit) -> None:
    """Marca problemas generales de nitidez y exposicion."""
    if audit.blur_score < 0.85:
        add_finding(audit, "muy_borrosa", 3, f"nitidez baja ({audit.blur_score:.0f})")
    elif audit.blur_score < 1.35:
        add_finding(audit, "algo_borrosa", 1, f"nitidez justa ({audit.blur_score:.0f})")

    if audit.brightness < 62:
        add_finding(audit, "oscura", 2, f"brillo bajo ({audit.brightness:.0f})")
    elif audit.brightness > 205:
        add_finding(audit, "sobreexpuesta", 2, f"brillo alto ({audit.brightness:.0f})")

    if audit.contrast < 32:
        add_finding(audit, "bajo_contraste", 1, f"contraste bajo ({audit.contrast:.0f})")


def assess_framing(audit: PhotoAudit) -> None:
    """Marca encuadres que suelen requerir retoque o reencuadre."""
    if audit.face_box is None or audit.width <= 0 or audit.height <= 0:
        return
    x, y, w, h = audit.face_box
    face_ratio = (w * h) / max(1, audit.width * audit.height)
    cx = (x + w / 2) / audit.width
    cy = (y + h / 2) / audit.height
    top_margin = y / audit.height
    side_margin = min(x, audit.width - (x + w)) / audit.width

    if face_ratio < 0.035:
        add_finding(audit, "rostro_pequeno", 1, f"rostro ocupa poco espacio ({face_ratio:.2f})")
    elif face_ratio > 0.62:
        add_finding(audit, "rostro_muy_cerca", 1, f"rostro demasiado grande ({face_ratio:.2f})")

    if abs(cx - 0.50) > 0.17:
        add_finding(audit, "descentrada", 1, f"rostro corrido del centro (x={cx:.2f})")
    if cy < 0.30:
        add_finding(audit, "cara_alta", 1, f"rostro muy arriba (y={cy:.2f})")
    elif cy > 0.58:
        add_finding(audit, "cara_baja", 1, f"rostro muy abajo (y={cy:.2f})")
    if top_margin < 0.015 or side_margin < 0.015:
        add_finding(audit, "posible_corte", 3, "rostro demasiado cerca del borde")


def assess_eyes(audit: PhotoAudit) -> None:
    """Marca ojos no confirmados o inclinados, senal tipica de parpadeo/mala toma."""
    if audit.face_box is None:
        return
    x, y, w, h = audit.face_box
    if audit.eye_count == 0:
        add_finding(audit, "ojos_no_detectados", 1, "no se confirmaron ojos; revisar si hay parpadeo, sombra o lentes")
        return
    if audit.eye_count == 1:
        add_finding(audit, "un_ojo", 1, "solo se confirmo un ojo; posible lente, sombra o giro leve")
        return

    eyes = sorted(audit.eye_centers[:2], key=lambda item: item[0])
    separation = (eyes[1][0] - eyes[0][0]) / max(1, w)
    level_delta = abs(eyes[1][1] - eyes[0][1]) / max(1, h)
    eye_line = (((eyes[0][1] + eyes[1][1]) / 2) - y) / max(1, h)

    if separation < 0.22 or separation > 0.62:
        add_finding(audit, "ojos_raros", 1, f"separacion ocular fuera de rango ({separation:.2f})")
    if level_delta > 0.14:
        add_finding(audit, "cabeza_inclinada", 1, f"ojos desnivelados ({level_delta:.2f})")
    if eye_line < 0.18 or eye_line > 0.55:
        add_finding(audit, "linea_ojos_rara", 1, f"altura de ojos sospechosa ({eye_line:.2f})")


def assess_pose(audit: PhotoAudit, profile_faces: list[tuple[int, int, int, int]]) -> None:
    """Marca posible mirada lateral solo si el perfil compite con el rostro frontal."""
    if audit.face_box is None or len(profile_faces) < 2:
        return
    frontal_score = score_face(audit.face_box, audit.width, audit.height)
    profile_score = max(score_face(face, audit.width, audit.height) for face in profile_faces)
    if profile_score >= frontal_score * 0.70:
        add_finding(audit, "mirada_lateral", 2, "rostro/perfil sugiere cabeza o mirada girada")


def write_csv(audits: list[PhotoAudit], output_path: Path, photos_root: Path) -> None:
    """Escribe un CSV simple para filtrar en Excel."""
    with output_path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(
            [
                "severity",
                "action",
                "course",
                "student",
                "file",
                "reasons",
                "eye_count",
                "face_count",
                "profile_count",
                "blur_score",
                "brightness",
                "contrast",
                "width",
                "height",
            ]
        )
        for audit in audits:
            writer.writerow(
                [
                    audit.severity,
                    audit.action,
                    audit.course,
                    audit.student,
                    str(audit.path.relative_to(photos_root.parent)),
                    audit.reasons,
                    audit.eye_count,
                    audit.face_count,
                    audit.profile_count,
                    f"{audit.blur_score:.1f}",
                    f"{audit.brightness:.1f}",
                    f"{audit.contrast:.1f}",
                    audit.width,
                    audit.height,
                ]
            )


def write_html(audits: list[PhotoAudit], output_path: Path) -> None:
    """Genera una galeria local con miniaturas enlazadas al archivo real."""
    rows = []
    for audit in audits:
        if audit.severity == 0:
            continue
        color = "#ffdddd" if audit.severity >= 3 else "#fff1bf" if audit.severity == 2 else "#e9f3ff"
        image_uri = audit.path.resolve().as_uri()
        rows.append(
            f"""
            <tr style="background:{color}">
              <td>{audit.severity}</td>
              <td>{html.escape(audit.action)}</td>
              <td>{html.escape(audit.course)}</td>
              <td>{html.escape(audit.student)}</td>
              <td><a href="{image_uri}"><img src="{image_uri}" loading="lazy"></a></td>
              <td>{html.escape(audit.reasons)}</td>
              <td><code>{html.escape(str(audit.path))}</code></td>
            </tr>
            """
        )

    output_path.write_text(
        f"""<!doctype html>
<html lang="es">
<head>
  <meta charset="utf-8">
  <title>Auditoria de fotos CastelCredCam</title>
  <style>
    body {{ font-family: Segoe UI, Arial, sans-serif; margin: 24px; background: #14121a; color: #f7f1ff; }}
    table {{ border-collapse: collapse; width: 100%; background: #fff; color: #1d1826; }}
    th, td {{ border: 1px solid #d7cce3; padding: 8px; vertical-align: top; }}
    th {{ position: sticky; top: 0; background: #4f2b74; color: #fff; }}
    img {{ width: 96px; height: 128px; object-fit: cover; border-radius: 6px; }}
    code {{ font-size: 11px; }}
  </style>
</head>
<body>
  <h1>Auditoria de fotos CastelCredCam</h1>
  <p>Generado: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}. Este reporte marca problemas tecnicos; la decision final es visual.</p>
  <table>
    <thead>
      <tr><th>Sev.</th><th>Accion</th><th>Curso</th><th>Estudiante</th><th>Foto</th><th>Motivos</th><th>Ruta</th></tr>
    </thead>
    <tbody>
      {''.join(rows)}
    </tbody>
  </table>
</body>
</html>
""",
        encoding="utf-8",
    )


def write_summary(audits: list[PhotoAudit], output_path: Path, csv_path: Path, html_path: Path) -> None:
    """Deja un resumen legible sin tener que abrir el CSV completo."""
    by_severity = {level: sum(1 for audit in audits if audit.severity == level) for level in range(4)}
    by_course: dict[str, int] = {}
    for audit in audits:
        if audit.severity >= 2:
            by_course[audit.course] = by_course.get(audit.course, 0) + 1

    payload = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "total_photos": len(audits),
        "ok": by_severity[0],
        "minor": by_severity[1],
        "review": by_severity[2],
        "priority_ai_retouch": by_severity[3],
        "review_by_course": dict(sorted(by_course.items())),
        "csv": str(csv_path),
        "html": str(html_path),
    }
    output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Audita calidad tecnica de fotos de estudiantes.")
    parser.add_argument("--photos-root", default=DEFAULT_PHOTOS_DIR, help="Carpeta raiz de fotos activas.")
    parser.add_argument("--output-root", default=DEFAULT_OUTPUT_DIR, help="Carpeta local de reportes ignorada por Git.")
    parser.add_argument("--limit", type=int, default=0, help="Limita cantidad de fotos para pruebas.")
    parser.add_argument("--deep", action="store_true", help="Usa cascadas extra; mas lento, util para confirmar casos puntuales.")
    parser.add_argument(
        "--pose-check",
        action="store_true",
        help="Activa deteccion experimental de mirada lateral; apagada por defecto por falsos positivos.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    app_root = Path(__file__).resolve().parents[1]
    photos_root = Path(args.photos_root)
    if not photos_root.is_absolute():
        photos_root = app_root / photos_root
    output_root = Path(args.output_root)
    if not output_root.is_absolute():
        output_root = app_root / output_root

    try:
        images = find_images(photos_root)
        if args.limit > 0:
            images = images[: args.limit]
        output_root.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        csv_path = output_root / f"auditoria_fotos_{stamp}.csv"
        html_path = output_root / f"auditoria_fotos_{stamp}.html"
        summary_path = output_root / f"auditoria_fotos_{stamp}.json"

        cv2.setNumThreads(1)
        print(f"[INFO] Fotos a auditar: {len(images)}")
        audits: list[PhotoAudit] = []
        for index, path in enumerate(images, start=1):
            if index % 50 == 0:
                print(f"[INFO] Progreso: {index}/{len(images)}", flush=True)
            audits.append(audit_photo(path, photos_root, deep_scan=args.deep, pose_check=args.pose_check))

        audits.sort(key=lambda item: (-item.severity, item.course, item.student, str(item.path)))
        write_csv(audits, csv_path, photos_root)
        write_html(audits, html_path)
        write_summary(audits, summary_path, csv_path, html_path)

        priority = sum(1 for audit in audits if audit.severity >= 3)
        review = sum(1 for audit in audits if audit.severity == 2)
        print(f"[SUCCESS] Reporte CSV: {csv_path}")
        print(f"[SUCCESS] Reporte HTML: {html_path}")
        print(f"[SUCCESS] Resumen JSON: {summary_path}")
        print(f"[SUMMARY] Prioridad IA: {priority} | Revisar: {review} | OK/leves: {len(audits) - priority - review}")
        return 0
    except Exception as exc:
        print(f"[ERROR] Auditoria fallida: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
