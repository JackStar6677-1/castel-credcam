# CastelCredCam

CastelCredCam es una herramienta local en Python para tomar fotos tipo credencial de estudiantes de forma rapida, ordenada y repetible durante jornadas reales de curso.

El problema que intenta resolver es muy concreto: tener una app sencilla para abrir una camara, escribir el nombre del estudiante, capturar la foto y dejar todo guardado por curso sin depender de un flujo pesado de estudio fotografico ni de software complejo.

## Objetivo del repositorio

Este repo guarda el experimento completo de captura local, incluyendo:

- una version principal por consola con preview de OpenCV
- una version GUI en Tkinter con mas controles
- scripts de arranque para flujos comunes
- archivos de configuracion local para aliases de camaras
- utilidades de diagnostico

## Que hace la aplicacion

Funciones principales:

- pregunta si la sesion es de prueba o de curso real
- crea y organiza carpetas por curso
- guarda las capturas numeradas automaticamente
- mantiene un `index.csv` con metadatos de cada foto
- puede cargar una lista de alumnos desde Excel o CSV y avanzar secuencialmente
- crea una carpeta espejo `fotos_respaldo/` por curso con copia de cada foto y del `index.csv`
- nombra cada archivo como `Nombre Alumno-Curso-RUT.jpg` cuando hay lista cargada
- crea logs detallados de arranque, errores y cierre en `logs/`
- recuerda la ultima camara valida usada
- permite elegir backend y camara por indice
- muestra preview en vivo con overlay informativo
- deja la captura final limpia aunque el overlay se vea en pantalla
- ofrece una etapa de revision inmediata para repetir la ultima foto si hace falta
- genera un reporte de sesion al terminar

## Casos de uso pensados

- fotografiar estudiantes para credenciales o fichas internas
- jornadas donde se necesita capturar muchas fotos seguidas
- escenarios con webcam integrada, webcam USB o camara virtual desde celular
- equipos Windows donde interesa una herramienta local y simple

## Stack

- Python
- OpenCV para captura y preview
- Tkinter para la GUI incluida en `GUI/`
- archivos CSV y JSON para persistencia local ligera

## Estructura del repositorio

```text
CastelCredCam/
|-- castel_credcam.py
|-- camera_aliases.json
|-- camera_diagnostic.py
|-- requirements.txt
|-- run_castel_credcam.bat
|-- run_castel_credcam_iriun.bat
|-- logs/
|-- README.md
|-- LICENSE
`-- GUI/
    |-- castel_credcam_gui.py
    `-- run_castel_credcam_gui.bat
```

## Archivo por archivo

- `castel_credcam.py`
  Flujo principal de captura. Maneja seleccion de camara, sesion, overlay, captura, revision, guardado y CSV.
- `camera_aliases.json`
  Alias legibles para indices y backends de camara del equipo.
- `camera_diagnostic.py`
  Script para revisar que camaras detecta OpenCV y generar una salida de diagnostico local.
- `GUI/castel_credcam_gui.py`
  Variante con interfaz grafica mas completa para operar sin depender tanto de teclado en consola.
- `run_castel_credcam.bat`
  Lanzador rapido del flujo principal.
- `run_castel_credcam_iriun.bat`
  Lanzador preparado para una configuracion concreta de Iriun Webcam.

## Requisitos

- Windows 10 u 11
- Python 3.10 o superior recomendado
- una camara funcional en Windows

Tipos de camara viables:

- webcam integrada
- webcam USB
- camara virtual desde celular con apps como Iriun, DroidCam, iVCam o Camo

## Instalacion

```powershell
cd C:\Users\Jack\Documents\GitHub\Experimentos\CastelCredCam
py -m pip install -r requirements.txt
```

Si tu entorno no usa `py`, puedes usar:

```powershell
python -m pip install -r requirements.txt
```

## Ejecucion del flujo principal

```powershell
py .\castel_credcam.py
```

O con:

```text
run_castel_credcam.bat
```

## Ejecucion con camara preseleccionada

La app admite argumentos para saltarse parte de la seleccion manual:

```powershell
py .\castel_credcam.py --camera-index 3 --backend dshow
```

El repo trae un ejemplo listo para Iriun:

```text
run_castel_credcam_iriun.bat
```

## Flujo de una sesion

1. elegir modo `prueba` o `curso`
2. si vas a trabajar con roster, cargar el Excel o CSV de alumnos
3. elegir el curso en el campo correspondiente
4. seleccionar camara y backend
5. capturar con Enter
6. la GUI avanza automaticamente al siguiente alumno si hay roster cargado
7. revisar rapidamente la foto o rehacer la ultima si hace falta

## Salida generada

Durante una sesion, la app crea una estructura local parecida a esta:

```text
fotos/
`-- 7A/
    |-- Nombre Alumno-7A-276719157.jpg
    |-- Nombre Alumno-7A-274886543.jpg
    |-- index.csv
    `-- session_YYYYMMDD_HHMMSS.txt

fotos_respaldo/
`-- 7A/
    |-- Nombre Alumno-7A-276719157.jpg
    |-- Nombre Alumno-7A-274886543.jpg
    `-- index.csv
```

`index.csv` guarda columnas como:

- id
- filename
- student_name
- course
- rut
- timestamp

Si cargas una lista de alumnos, la GUI completa `student_name` y `rut` automaticamente mientras avanza por el curso.
Las fotos quedan con formato `Nombre Alumno-Curso-RUT.jpg`, usando el RUT sin guion. Si no hay RUT disponible, la app usa `SIN_RUT`.

## Logs y diagnostico

Cada arranque genera un archivo nuevo dentro de `logs/` con timestamp y PID. Ahí se guardan:

- eventos de inicio y cierre
- excepciones no controladas con traceback completo
- errores de carga de roster, captura, backup o rehacer
- contexto tecnico de la ejecucion, como version de Python y ruta de trabajo

Si la GUI se congela o arroja un error inesperado, revisa el archivo mas reciente de `logs/gui_*.log`.
Para ejecucion por consola, usa `logs/cli_*.log`.

## GUI incluida

La carpeta `GUI/` contiene una variante con interfaz grafica mas elaborada.

Incluye:

- preview grande
- controles mas visibles
- panel lateral de acciones
- lista de capturas recientes
- carga de roster de alumnos para captura secuencial con nombre y RUT
- respaldo espejo por curso en `fotos_respaldo/`
- archivos nombrados de forma legible para recuperación manual
- flujo mas amigable para operadores no tecnicos

Ejecucion:

```powershell
cd C:\Users\Jack\Documents\GitHub\Experimentos\CastelCredCam\GUI
py .\castel_credcam_gui.py
```

O con:

```text
GUI\run_castel_credcam_gui.bat
```

## Diagnostico

Si necesitas comprobar deteccion de camaras:

```powershell
py .\camera_diagnostic.py
```

Esto sirve para validar indices, backends y estabilidad antes de una jornada real.

## Persistencia local y archivos auxiliares

El proyecto usa persistencia ligera:

- `camera_aliases.json` para nombres legibles de camaras
- `last_camera.json` para recordar la ultima camara valida
- `index.csv` por curso para registrar capturas

`last_camera.json` es local y no se sube al repo.
Los logs se guardan en `logs/` y tampoco se versionan.

## Seguridad y privacidad

Este punto es importante: el repo esta configurado para no subir datos sensibles de uso real.

Se ignoran por defecto:

- `fotos/`
- `fotos_respaldo/`
- `camera_diagnostic/`
- `last_camera.json`
- caches de Python
- entornos virtuales
- archivos locales de editor y sistema

Eso permite tener el codigo publico sin publicar fotos de estudiantes ni salidas locales.

## Licencia

El repositorio se publica con licencia MIT. Revisa `LICENSE` para el texto completo.

## Estado del proyecto

CastelCredCam es una herramienta practica y funcional, pero sigue siendo un experimento orientado a un flujo concreto. No intenta reemplazar suites fotograficas profesionales ni sistemas escolares completos.

## Posibles mejoras futuras

- recorte automatico opcional para exportacion final
- exportadores a formatos de sistemas escolares concretos
- selector visual de camaras con mini preview
- etiquetado o validacion mas estricta de nombres
- empaquetado como ejecutable de Windows
