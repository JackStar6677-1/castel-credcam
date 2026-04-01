# CastelCredCam

Aplicacion local en Python para sacar fotos tipo credencial a estudiantes por curso, pensada para Windows y jornadas reales de colegio.

El foco es simple: abrir, escribir el nombre dentro del preview, capturar rapido y dejar todo ordenado por curso.

## Licencia

Este codigo base queda publicado con licencia MIT para que puedas reutilizarlo, adaptarlo o ampliarlo libremente.

Revisa el archivo [LICENSE](LICENSE).

## Que hace

- Pregunta si la sesion es `prueba` o `curso`
- Permite elegir camara por indice, backend y alias legible
- Muestra preview en vivo con overlay compacto
- Permite escribir el nombre del estudiante directamente en el preview
- `Enter` confirma el nombre actual
- `p` o `espacio` toman la foto
- `q` sale de la sesion
- `r` rehace la ultima captura desde la pantalla de revision
- Guarda JPG numerados en carpetas por curso
- Guarda un `index.csv` por carpeta
- Abre automaticamente la carpeta `fotos/` al iniciar la sesion
- Genera un reporte simple de sesion al terminar

## Requisitos

- Windows 10 u 11
- Python 3.10 o superior recomendado
- Una camara disponible en Windows:
  - webcam integrada
  - webcam USB
  - celular usando camara virtual como Iriun, DroidCam, iVCam o Camo

## Instalacion

Clona o descarga el proyecto y abre PowerShell dentro de la carpeta del repositorio:

```powershell
cd CastelCredCam
```

Instala dependencias:

```powershell
py -m pip install -r requirements.txt
```

Si `py` no funciona:

```powershell
python -m pip install -r requirements.txt
```

## Ejecucion

Modo normal:

```powershell
py .\castel_credcam.py
```

o

```powershell
python .\castel_credcam.py
```

Tambien puedes abrir:

```text
run_castel_credcam.bat
```

## GUI nueva

Se agrego una version mas completa dentro de:

```text
GUI/
```

Incluye:

- interfaz completa en Tkinter
- tema morado/dorado
- panel lateral con sesion, camara y acciones
- preview grande
- selector de camara dentro del propio preview
- opcion de voltear la imagen dentro del preview
- escritura del nombre dentro de la misma interfaz
- ayuda visual de rostro opcional
- lista de capturas recientes

Para abrirla:

```powershell
cd GUI
py .\castel_credcam_gui.py
```

o con doble clic:

```text
GUI\run_castel_credcam_gui.bat
```

## Ejecucion con una camara preseleccionada

Si ya sabes que combinacion de camara y backend quieres usar, puedes lanzar la app con argumentos:

```powershell
py .\castel_credcam.py --camera-index 3 --backend dshow
```

Tambien puedes crear o editar un lanzador `.bat` para tu equipo, por ejemplo:

```text
run_castel_credcam_iriun.bat
```

En la configuracion actual del proyecto, el lanzador de Iriun apunta a:

- alias: `Iriun Webcam (celular)`
- indice: `3`
- backend: `DirectShow`

## Nombres de camara

La app usa aliases legibles desde:

```text
camera_aliases.json
```

Ejemplos de aliases:

- `Camara laptop`
- `Iriun Webcam (celular)`
- `DroidCam Video`
- `iVCam`

Si cambia el orden de las camaras en Windows, puedes editar ese archivo y cambiar:

- `index`
- `backend`
- `label`

## Flujo de uso

1. Elegir `modo prueba` o `modo curso`.
2. Si es curso, escribir el nombre del curso.
3. Elegir la camara, o usar un lanzador preparado para una camara concreta.
4. En la ventana, escribir el nombre del estudiante directamente sobre el preview.
5. En la ventana:
   - haz clic dentro del preview si el teclado no responde
   - escribe el nombre del estudiante
   - `Enter` confirma el nombre actual
   - `p` toma y guarda la foto
   - `espacio` tambien toma la foto
   - `Enter` o `espacio` avanzan al siguiente estudiante en la revision
   - `r` borra la ultima captura y permite repetirla
   - `q` sale de la sesion

Al iniciar la sesion, la app abre automaticamente la carpeta `fotos/` para que puedas ir revisando que los cursos y archivos se esten guardando bien.

## Estructura

```text
CastelCredCam/
|-- castel_credcam.py
|-- camera_aliases.json
|-- camera_diagnostic.py
|-- GUI/
|   |-- castel_credcam_gui.py
|   `-- run_castel_credcam_gui.bat
|-- requirements.txt
|-- run_castel_credcam.bat
|-- run_castel_credcam_iriun.bat
`-- fotos/
    |-- _pruebas/
    |-- 7A/
    |-- 8B/
    `-- 2MedioA/
```

Las carpetas dentro de `fotos/` se crean solas cuando inicias una sesion.

## Salida

Ejemplo de archivos:

```text
fotos/7A/7A_001.jpg
fotos/7A/7A_002.jpg
fotos/7A/index.csv
fotos/7A/session_20260401_110000.txt
```

Ejemplo de `index.csv`:

```csv
id,filename,student_name,course,timestamp
1,7A_001.jpg,Juan Perez,7A,2026-04-01 10:45:10
```

## Diagnostico rapido

Para revisar que camaras detecta OpenCV:

```powershell
py .\camera_diagnostic.py
```

Las imagenes de prueba quedaran en:

```text
camera_diagnostic\
```

## Apps de camara recomendadas

Recomendacion practica para este proyecto:

1. Iriun Webcam
2. DroidCam
3. iVCam
4. Camo

Links oficiales:

- Iriun Webcam: https://iriun.com/
- DroidCam: https://www.dev47apps.com/
- iVCam: https://www.e2esoft.com/ivcam/
- Camo: https://camo.com/

Notas rapidas:

- Iriun suele ser facil de hacer andar como camara virtual simple.
- DroidCam soporta Wi-Fi y USB.
- iVCam soporta Wi-Fi y USB y tiene muchas opciones de camara.
- Camo suele verse muy bien, pero es mas "producto premium".

## Sugerencias de uso real

- Usa buena luz frontal.
- Manten la camara fija en tripode.
- Si usas celular, abre primero la app del telefono y luego el cliente de Windows.
- Haz una sesion de prueba antes del curso real.
- Coloca ojos y hombros dentro de la guia amarilla del preview.
- Si el preview no responde al teclado, haz clic dentro de la ventana una vez.

## Archivos ignorados por Git

El repo ignora por defecto:

- `fotos/`
- `camera_diagnostic/`
- imagenes de diagnostico temporales
- cache de Python
- entornos virtuales
- archivos tipicos de Windows

Eso permite mantener el repo publico sin subir fotos de estudiantes ni salidas locales.

## Version 2 sugerida

- Recorte automatico opcional para exportacion
- Plantilla de exportacion para MySchool
- Selector visual de camaras con mini-preview
- Atajo para abrir la carpeta del curso activo
- Deteccion de rostro solo como ayuda visual, sin auto-captura
