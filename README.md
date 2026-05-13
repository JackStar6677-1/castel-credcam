# CastelCredCam

> Herramienta local en Python para tomar fotos tipo credencial de estudiantes con orden, respaldo y trazabilidad por curso.

CastelCredCam esta pensada para jornadas reales de captura escolar. Permite abrir una camara, avanzar alumno por alumno, guardar cada foto con nombre claro, mantener un respaldo espejo y dejar registro en CSV y logs para que nada se pierda si hay que retomar el trabajo despues.

## Lo esencial

- Captura local en Windows, sin depender de servicios externos.
- Flujo por consola para uso rapido y diagnostico.
- GUI principal en PySide6 para operacion real con roster de alumnos.
- Carga de nominas desde Excel o CSV.
- Guardado por curso con `index.csv` y carpeta espejo en `fotos_respaldo/`.
- Reintento de la ultima foto con historial de respaldo.
- Logs detallados para revisar fallas tecnicas.
- Versiones separadas para flujo principal y compatibilidad historica.

## Que resuelve

El problema que intenta resolver es simple:

1. abrir una camara funcional.
2. cargar una lista de alumnos cuando exista.
3. capturar fotos de forma ordenada.
4. guardar todo con nombres legibles.
5. dejar respaldo por si se borra algo o se repite una toma.

La idea no es reemplazar un estudio fotografico profesional. La idea es hacer una herramienta practica, liviana y confiable para sesiones largas de curso.

## Flujo recomendado

La forma mas segura de trabajar es esta:

1. preparar la nomina del curso en Excel o CSV.
2. abrir la GUI principal.
3. cargar la lista.
4. verificar que el curso detectado sea el correcto.
5. confirmar camara y backend.
6. capturar alumno por alumno.
7. usar `Volver atras y reintentar` si una foto quedo mala.
8. cerrar la sesion y revisar `fotos/`, `fotos_respaldo/` y `index.csv`.

## Componentes del proyecto

### `castel_credcam.py`

Flujo principal por consola. Sirve para:

- capturas rapidas.
- pruebas de hardware.
- diagnostico simple.
- sesiones livianas sin interfaz grande.

### `GUI/castel_credcam_qt.py`

GUI principal del proyecto. Incluye:

- panel visual mas comodo para operador.
- preview en vivo.
- carga de roster por curso.
- avance secuencial de alumnos.
- tabla de progreso.
- control de reintentos.
- respaldo espejo por curso.

### `GUI/castel_credcam_gui.py`

Variante legacy mantenida por compatibilidad interna. No es la interfaz recomendada para trabajo diario.

### `camera_diagnostic.py`

Ayuda a verificar camaras, indices y backends antes de una jornada.

## Funciones principales

- preguntar si la sesion es de prueba o de curso real.
- crear carpetas por curso.
- generar nombres de archivo del tipo `Nombre Alumno-Curso-RUT.jpg`.
- registrar metadatos en `index.csv`.
- cargar roster desde Excel o CSV.
- avanzar automaticamente al siguiente alumno cuando hay lista cargada.
- crear copia espejo en `fotos_respaldo/<curso>/`.
- guardar auditoria de reintentos en `retakes.csv`.
- recordar la ultima camara usada.
- trabajar con camara integrada, USB o virtual.
- dejar logs de arranque, captura, errores y cierre.

## Regla de nombres

Cuando hay roster cargado, el archivo se guarda con este formato:

```text
Nombre Alumno-Curso-RUT.jpg
```

Si no hay RUT, la app usa `SIN_RUT`.

Esto ayuda a recuperar archivos manualmente aunque el CSV se pierda o se necesite reconstruir una carpeta.

## Salida esperada

Una sesion normal deja una estructura parecida a esta:

```text
CastelCredCam/
|-- fotos/
|   `-- 7BASICOA/
|       |-- Nombre Alumno-7 BASICO A-12345678.jpg
|       |-- index.csv
|       `-- session_YYYYMMDD_HHMMSS.txt
|-- fotos_respaldo/
|   `-- 7BASICOA/
|       |-- Nombre Alumno-7 BASICO A-12345678.jpg
|       |-- index.csv
|       `-- retakes.csv
`-- logs/
    |-- gui_qt_YYYYMMDD_HHMMSS_PID.log
    `-- cli_YYYYMMDD_HHMMSS_PID.log
```

## Instalacion

```powershell
cd C:\Users\Jack\Documents\GitHub\Experimentos\Castel\CastelCredCam
py -m pip install -r requirements.txt
```

Si tu entorno no usa `py`:

```powershell
python -m pip install -r requirements.txt
```

## Ejecucion

### Flujo por consola

```powershell
py .\castel_credcam.py
```

Tambien puedes usar:

```text
run_castel_credcam.bat
```

### GUI principal

```powershell
cd C:\Users\Jack\Documents\GitHub\Experimentos\Castel\CastelCredCam\GUI
py .\castel_credcam_qt.py
```

O con:

```text
GUI\run_castel_credcam_gui.bat
```

### Con camara preseleccionada

```powershell
py .\castel_credcam.py --camera-index 3 --backend dshow
```

Para una configuracion concreta de Iriun existe:

```text
run_castel_credcam_iriun.bat
```

## Que guarda cada sesion

- `fotos/<curso>/` guarda las fotos principales.
- `fotos_respaldo/<curso>/` guarda la copia espejo.
- `index.csv` guarda `id`, `filename`, `student_name`, `course`, `rut` y `timestamp`.
- `retakes.csv` registra cuando una captura se rehace.
- `logs/` guarda trazabilidad tecnica con fecha y hora.

## Roster de alumnos

La GUI puede cargar una nomina desde Excel o CSV y trabajar con captura secuencial.

Cuando la lista esta cargada:

- completa nombre, curso y RUT desde la nomina.
- marca alumnos como `Hecho`, `Actual` o `Pendiente`.
- avanza sola al siguiente alumno despues de guardar.
- salta registros ya completados si vuelves a abrir la sesion.

## Reintentos y respaldo

El proyecto esta preparado para jornadas donde una foto se repite porque el alumno quiere otra toma o la imagen anterior no quedo bien.

Cuando pasa eso:

- la ultima captura puede rehacerse desde la GUI.
- la copia anterior se conserva en el respaldo.
- si existe una version previa del archivo, se guarda con sufijo `__reintento_YYYYMMDD_HHMMSS`.
- el respaldo escribe una entrada en `retakes.csv` con nota `reintento`.

## Diagnostico rapido

Si tienes dudas con la camara:

```powershell
py .\camera_diagnostic.py
```

Esto ayuda a revisar indices, backends y estabilidad antes de una jornada real.

## Estructura del repositorio

```text
CastelCredCam/
|-- castel_credcam.py
|-- camera_diagnostic.py
|-- camera_aliases.json
|-- requirements.txt
|-- run_castel_credcam.bat
|-- run_castel_credcam_iriun.bat
|-- README.md
|-- LICENSE
|-- docs/
|   `-- OPERACION.md
|-- GUI/
|   |-- castel_credcam_qt.py
|   `-- castel_credcam_gui.py
|-- fotos/
|-- fotos_respaldo/
`-- logs/
```

## Requisitos

- Windows 10 u 11.
- Python 3.10 o superior recomendado.
- una camara funcional en Windows.

Tipos de camara viables:

- webcam integrada.
- webcam USB.
- camara virtual desde celular con apps como Iriun, DroidCam, iVCam o Camo.

## Seguridad y privacidad

El repo esta pensado para trabajar con datos locales y no publicar material sensible por accidente.

En general se ignoran:

- `fotos/`
- `fotos_respaldo/`
- `logs/`
- caches de Python
- entornos virtuales
- archivos locales de editor y sistema

Eso ayuda a mantener el codigo publico sin subir fotos de estudiantes ni salidas de uso diario.

## Documentacion util

- [Guia operativa](docs/OPERACION.md)

## Estado actual del proyecto

Hoy la ruta recomendada es:

- `GUI/castel_credcam_qt.py` como interfaz principal.
- `castel_credcam.py` como flujo de respaldo por consola.
- `docs/OPERACION.md` como guia tecnica y de soporte.

La GUI legacy de Tkinter sigue en el repo por compatibilidad, pero no es la opcion principal de uso.

## Posibles mejoras futuras

- recorte automatico opcional para exportacion final.
- exportadores para sistemas escolares concretos.
- selector visual de camaras con mini preview.
- validacion mas estricta de nombres y roster.
- empaquetado como ejecutable de Windows.

## Licencia

Este repositorio se publica con licencia MIT. Revisa `LICENSE` para el texto completo.
