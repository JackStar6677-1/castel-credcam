from GUI.castel_credcam_qt import CastelCredCamQt


def test_legacy_three_column_student_name_is_preserved() -> None:
    """Legacy rosters split surnames and given names under one merged header."""
    header = (None, "Nº", "NOMBRE ESTUDIANTES", None, None, "RUT")
    row = (None, 1, "Araneda", "Espinoza", "Mia Ignacia Isabella", "27.291.696-9")

    header_map = CastelCredCamQt._header_map_from_sequence(None, header)
    student = CastelCredCamQt._student_from_sequence(None, row, header_map)

    assert student is not None
    assert student.display_name == "Araneda Espinoza Mia Ignacia Isabella"
    assert student.rut == "27.291.696-9"


def test_structured_castel_roster_keeps_all_name_parts() -> None:
    """Current Castel rosters expose each name component explicitly."""
    header = ("Orden", "N° Original", "Rut", "Apellido Paterno", "Apellido Materno", "Segundo Nombre", "Primer Nombre")
    row = (1, 1, "27.671.915-7", "Arancibia", "Zuñiga", "Luz", "Carmen")

    header_map = CastelCredCamQt._header_map_from_sequence(None, header)
    student = CastelCredCamQt._student_from_sequence(None, row, header_map)

    assert student is not None
    assert student.display_name == "Arancibia Zuñiga Luz Carmen"
    assert student.rut == "27.671.915-7"
