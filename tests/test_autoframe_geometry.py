"""Pruebas de la geometria pura del reencuadre automatico.

Estas funciones deciden el recorte final de cada credencial. Un fallo aqui no
lanza excepcion: produce una tanda completa de fotos mal encuadradas que solo
se detecta al imprimirlas. Por eso se validan sus invariantes, no su salida
exacta: los umbrales son ajustables, pero las invariantes no deben romperse.
"""
from __future__ import annotations

import pytest

from castel_credcam import (
    _autoframe_box_iou,
    _autoframe_build_crop_box,
    _autoframe_score_face,
    _autoframe_unique_candidates,
)

# Resolucion de trabajo habitual de la camara.
ANCHO, ALTO = 1920, 1080
RATIO_RETRATO = 3 / 4


class TestBoxIou:
    """Solape entre cajas: alimenta la deduplicacion de detecciones Haar."""

    def test_caja_identica_da_uno(self):
        caja = (10, 10, 100, 100)
        assert _autoframe_box_iou(caja, caja) == pytest.approx(1.0)

    def test_cajas_disjuntas_dan_cero(self):
        assert _autoframe_box_iou((0, 0, 50, 50), (500, 500, 50, 50)) == 0.0

    def test_cajas_que_solo_se_tocan_dan_cero(self):
        # Bordes adyacentes sin area comun: no deben contar como solape.
        assert _autoframe_box_iou((0, 0, 50, 50), (50, 0, 50, 50)) == 0.0

    def test_solape_parcial_conocido(self):
        # Dos cuadrados de 100x100 desplazados 50 px: interseccion 50x100=5000,
        # union 10000+10000-5000=15000 -> 1/3.
        valor = _autoframe_box_iou((0, 0, 100, 100), (50, 0, 100, 100))
        assert valor == pytest.approx(1 / 3, abs=1e-6)

    def test_es_simetrico(self):
        a, b = (0, 0, 100, 100), (40, 30, 90, 120)
        assert _autoframe_box_iou(a, b) == pytest.approx(_autoframe_box_iou(b, a))


class TestScoreFace:
    """Puntuacion de candidatos: decide que rostro se considera el del alumno."""

    def test_rostro_centrado_supera_a_uno_en_esquina(self):
        centrado = (860, 400, 200, 260)
        esquina = (20, 20, 200, 260)
        assert _autoframe_score_face(centrado, ANCHO, ALTO) > _autoframe_score_face(esquina, ANCHO, ALTO)

    def test_rostro_grande_supera_a_uno_pequeno_igual_de_centrado(self):
        grande = (810, 340, 300, 390)
        pequeno = (930, 460, 60, 78)
        assert _autoframe_score_face(grande, ANCHO, ALTO) > _autoframe_score_face(pequeno, ANCHO, ALTO)

    def test_confirmar_ojos_aumenta_la_puntuacion(self):
        caja = (860, 400, 200, 260)
        sin_ojos = _autoframe_score_face(caja, ANCHO, ALTO, eye_count=0)
        con_ojos = _autoframe_score_face(caja, ANCHO, ALTO, eye_count=2)
        assert con_ojos > sin_ojos

    def test_el_bono_de_ojos_se_satura_en_dos(self):
        # Mas de dos ojos es ruido de deteccion; no debe premiarse mas.
        caja = (860, 400, 200, 260)
        assert _autoframe_score_face(caja, ANCHO, ALTO, eye_count=2) == pytest.approx(
            _autoframe_score_face(caja, ANCHO, ALTO, eye_count=5)
        )

    def test_siempre_positiva(self):
        assert _autoframe_score_face((0, 0, 10, 10), ANCHO, ALTO) > 0


class TestUniqueCandidates:
    """Deduplicacion: varias pasadas Haar devuelven la misma cara repetida."""

    def test_colapsa_detecciones_casi_iguales(self):
        base = (800, 400, 200, 260)
        casi = (804, 403, 198, 258)
        assert len(_autoframe_unique_candidates([base, casi], ANCHO, ALTO)) == 1

    def test_conserva_rostros_realmente_distintos(self):
        izquierda = (200, 400, 200, 260)
        derecha = (1400, 400, 200, 260)
        assert len(_autoframe_unique_candidates([izquierda, derecha], ANCHO, ALTO)) == 2

    def test_ordena_por_relevancia_descendente(self):
        pequeno_lateral = (60, 700, 70, 90)
        grande_centrado = (810, 340, 300, 390)
        resultado = _autoframe_unique_candidates([pequeno_lateral, grande_centrado], ANCHO, ALTO)
        assert resultado[0] == grande_centrado

    def test_recorta_cajas_que_se_salen_del_encuadre(self):
        # Una caja desbordada nunca debe propagarse fuera de la imagen.
        for x, y, w, h in _autoframe_unique_candidates([(1800, 1000, 400, 400)], ANCHO, ALTO):
            assert x >= 0 and y >= 0
            assert x + w <= ANCHO
            assert y + h <= ALTO

    def test_lista_vacia_devuelve_vacio(self):
        assert _autoframe_unique_candidates([], ANCHO, ALTO) == []


class TestBuildCropBox:
    """Caja de recorte final: define la credencial impresa."""

    @staticmethod
    def _caso(face_box, eyes=None, ancho=ANCHO, alto=ALTO):
        return _autoframe_build_crop_box(ancho, alto, face_box, eyes)

    @pytest.mark.parametrize(
        "face_box",
        [
            None,                       # sin rostro: recorte centrado de respaldo
            (860, 300, 200, 260),       # rostro centrado
            (100, 300, 200, 260),       # rostro pegado al borde izquierdo
            (1620, 300, 200, 260),      # rostro pegado al borde derecho
            (860, 20, 200, 260),        # rostro muy alto en el encuadre
            (860, 700, 200, 260),       # rostro muy bajo en el encuadre
            (700, 200, 500, 650),       # primer plano
            (940, 500, 40, 52),         # rostro lejano y pequeno
        ],
    )
    def test_la_caja_nunca_se_sale_de_la_imagen(self, face_box):
        x1, y1, x2, y2 = self._caso(face_box)
        assert 0 <= x1 < x2 <= ANCHO
        assert 0 <= y1 < y2 <= ALTO

    @pytest.mark.parametrize(
        "face_box",
        [None, (860, 300, 200, 260), (100, 300, 200, 260), (860, 20, 200, 260), (700, 200, 500, 650)],
    )
    def test_conserva_proporcion_de_retrato(self, face_box):
        x1, y1, x2, y2 = self._caso(face_box)
        # Tolerancia de 1 px por el redondeo entero de ancho/alto.
        assert (x2 - x1) / (y2 - y1) == pytest.approx(RATIO_RETRATO, abs=0.01)

    def test_sin_rostro_el_recorte_queda_centrado(self):
        x1, y1, x2, y2 = self._caso(None)
        centro_x = (x1 + x2) / 2
        assert centro_x == pytest.approx(ANCHO / 2, abs=1.0)

    @pytest.mark.parametrize(
        "face_box",
        [(860, 300, 200, 260), (700, 250, 400, 520), (940, 400, 120, 156)],
    )
    def test_el_rostro_queda_dentro_del_recorte(self, face_box):
        fx, fy, fw, fh = face_box
        x1, y1, x2, y2 = self._caso(face_box)
        assert x1 <= fx and fx + fw <= x2, "el rostro se sale horizontalmente"
        assert y1 <= fy and fy + fh <= y2, "el rostro se sale verticalmente"

    def test_reserva_espacio_sobre_la_cabeza(self):
        # Haar suele empezar bajo el nacimiento del pelo: el recorte debe abrir
        # margen por encima, nunca cortar a la altura de la ceja.
        fx, fy, fw, fh = 860, 300, 200, 260
        _x1, y1, _x2, _y2 = self._caso((fx, fy, fw, fh))
        assert y1 < fy, "no se reservo margen superior sobre el rostro"

    def test_los_ojos_quedan_dentro_del_recorte(self):
        # Cuando la deteccion aporta el par de ojos, ambos deben quedar visibles
        # en la credencial final: son la referencia de altura del encuadre.
        face_box = (860, 300, 200, 260)
        ojos = [(900, 380), (1020, 384)]
        x1, y1, x2, y2 = self._caso(face_box, eyes=ojos)
        for ex, ey in ojos:
            assert x1 <= ex <= x2, f"ojo {ex},{ey} fuera del recorte horizontalmente"
            assert y1 <= ey <= y2, f"ojo {ex},{ey} fuera del recorte verticalmente"

    def test_el_recorte_con_ojos_respeta_el_margen_superior(self):
        # Aunque los ojos reposicionen la caja, nunca deben eliminar el margen
        # sobre la cabeza que Haar no incluye en su deteccion.
        fx, fy, fw, fh = 860, 300, 200, 260
        _x1, y1, _x2, _y2 = self._caso((fx, fy, fw, fh), eyes=[(900, 380), (1020, 384)])
        assert y1 < fy, "el reencuadre por ojos elimino el margen superior"

    def test_es_determinista(self):
        face_box = (860, 300, 200, 260)
        assert self._caso(face_box) == self._caso(face_box)

    @pytest.mark.parametrize("ancho,alto", [(640, 480), (1280, 720), (1920, 1080), (3840, 2160)])
    def test_funciona_en_distintas_resoluciones(self, ancho, alto):
        face_box = (int(ancho * 0.45), int(alto * 0.28), int(ancho * 0.10), int(alto * 0.24))
        x1, y1, x2, y2 = self._caso(face_box, ancho=ancho, alto=alto)
        assert 0 <= x1 < x2 <= ancho
        assert 0 <= y1 < y2 <= alto
