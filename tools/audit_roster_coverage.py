from __future__ import annotations

import argparse
import csv
import sys
from dataclasses import dataclass
from pathlib import Path

APP_ROOT = Path(__file__).resolve().parent.parent
if str(APP_ROOT) not in sys.path:
    sys.path.insert(0, str(APP_ROOT))

from castel_credcam import load_existing_records, sanitize_folder_name  # noqa: E402
from GUI.castel_credcam_qt import CastelCredCamQt, RosterStudent, _student_key  # noqa: E402


class RosterParser:
    """Reuse the production roster parser without constructing the Qt window."""

    _load_roster_from_workbook = CastelCredCamQt._load_roster_from_workbook
    _parse_table_rows = CastelCredCamQt._parse_table_rows
    _header_map_from_sequence = CastelCredCamQt._header_map_from_sequence
    _student_from_sequence = CastelCredCamQt._student_from_sequence


@dataclass(frozen=True)
class CoverageRow:
    course: str
    roster_total: int
    captured: int
    pending: int
    status: str
    pending_students: str


def audit_coverage(roster_path: Path, photos_root: Path) -> list[CoverageRow]:
    """Compare every roster student with the recoverable course index."""
    roster_map: dict[str, list[RosterStudent]] = RosterParser()._load_roster_from_workbook(roster_path)
    rows: list[CoverageRow] = []
    for course, students in roster_map.items():
        course_dir = photos_root / sanitize_folder_name(course)
        records = load_existing_records(course_dir / "index.csv") if course_dir.is_dir() else []
        completed_keys = {_student_key(record.student_name, record.rut) for record in records}
        missing = [student for student in students if student.key not in completed_keys]
        if not course_dir.is_dir():
            status = "SIN CARPETA"
        elif not missing:
            status = "COMPLETO"
        else:
            status = "PARCIAL"
        rows.append(
            CoverageRow(
                course=course,
                roster_total=len(students),
                captured=len(students) - len(missing),
                pending=len(missing),
                status=status,
                pending_students=" | ".join(f"{student.display_name} [{student.rut}]" for student in missing),
            )
        )
    return rows


def write_report(rows: list[CoverageRow], output_path: Path) -> None:
    """Write an Excel-friendly UTF-8 CSV with one row per course."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["curso", "total_nomina", "capturados", "pendientes", "estado", "estudiantes_pendientes"])
        for row in rows:
            writer.writerow([row.course, row.roster_total, row.captured, row.pending, row.status, row.pending_students])


def main() -> int:
    parser = argparse.ArgumentParser(description="Audita cobertura de fotos contra la nomina oficial.")
    parser.add_argument("roster", type=Path, help="Archivo XLSX de nomina")
    parser.add_argument("photos_root", type=Path, help="Carpeta fotos que contiene un directorio por curso")
    parser.add_argument("output", type=Path, help="CSV de salida")
    args = parser.parse_args()

    try:
        rows = audit_coverage(args.roster, args.photos_root)
        write_report(rows, args.output)
    except Exception as exc:
        print(f"[ERROR] No se pudo completar la auditoria: {exc}", file=sys.stderr)
        return 1

    print(f"[SUCCESS] Informe creado: {args.output}")
    print(f"[INFO] Cursos: {len(rows)} | alumnos: {sum(row.roster_total for row in rows)}")
    print(f"[INFO] Capturados: {sum(row.captured for row in rows)} | pendientes: {sum(row.pending for row in rows)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
