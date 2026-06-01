# Guia operativa de CastelCredCam

Este documento explica como funciona el proyecto por dentro, como operarlo en una jornada real y que revisar cuando algo falla.

## Idea general

CastelCredCam existe para tomar fotos tipo credencial de estudiantes en una jornada de curso, con tres prioridades:

1. rapidez para el operador
2. orden de archivos y trazabilidad
3. respaldo local para no perder material si algo se borra por error

Hay dos caminos principales:

- `castel_credcam.py`, que es el flujo por consola
- `GUI/castel_credcam_qt.py`, que es la interfaz principal para operar con roster y progreso visual

## Flujo recomendado

La forma mas segura de trabajar es esta:

1. preparar la nomina del curso en Excel o CSV
2. abrir la GUI
3. cargar la nomina
4. verificar el curso correcto
5. confirmar camara y backend
6. avanzar alumno por alumno con captura, rehacer si hace falta y continuar
7. cerrar la sesion y revisar que quedaron `fotos/`, `fotos_respaldo/` e `index.csv`

## Estructura de carpetas

La salida local esperada es parecida a esto:

```text
CastelCredCam/
|-- fotos/
|   `-- 1 BASICO A/
|       |-- Nombre Alumno-1 BASICO A-12345678.jpg
|       |-- index.csv
|       `-- session_YYYYMMDD_HHMMSS.txt
|-- fotos_respaldo/
|   `-- 1 BASICO A/
|       |-- Nombre Alumno-1 BASICO A-12345678.jpg
|       `-- index.csv
`-- logs/
    |-- gui_qt_YYYYMMDD_HHMMSS_PID.log
    `-- cli_YYYYMMDD_HHMMSS_PID.log
```

Reglas clave:

- la carpeta principal del curso vive en `fotos/<curso>/`
- el respaldo fuente vive en `fotos_respaldo/<curso>/` y conserva la toma completa sin recorte de credencial
- cada captura actualiza el `index.csv`
- cada arranque genera un log nuevo

## Formato de nombres

Cuando hay roster cargado, el nombre del archivo usa:

- nombre normalizado del alumno
- curso
- RUT sin guion

Ejemplo:

```text
Arancibia Zuniga Carmen Luz-PRE KINDER A-276719157.jpg
```

Si no hay RUT, se usa `SIN_RUT`.

## Que hace cada parte de la app

### Consola

La version por consola sirve para:

- sesiones simples
- pruebas rapidas
- diagnostico si la GUI falla
- usos donde no interesa una interfaz grande

### GUI Qt

La GUI principal sirve para:

- operar con roster
- ver el curso completo y su progreso
- avanzar entre alumnos
- revisar el ultimo capture y rehacerlo
- mantener respaldo espejo

## Logs

Cada arranque deja trazabilidad en `logs/`.

Los logs guardan:

- version de Python
- ejecutable y directorio actual
- carga de roster
- apertura y cierre de camara
- capturas
- errores con traceback completo

### Que log mirar

- GUI: el ultimo `logs/gui_qt_*.log`
- consola: el ultimo `logs/cli_*.log`

## Checklist antes de una jornada

1. verificar que la camara responda
2. abrir `camera_diagnostic.py` si hay dudas
3. confirmar que la nomina tenga el curso correcto
4. comprobar que el espacio en disco alcance para fotos y respaldos
5. revisar que la carpeta `logs/` exista y este escribible

## Problemas comunes

### La GUI dice que no responde

Suele pasar por:

- una camara que no devuelve frames
- un backend que se queda pegado
- una vista que intenta refrescar demasiado pesado

Qué revisar:

- el log mas reciente
- si otra app esta usando la camara
- si el curso cargado tiene muchos alumnos y el equipo esta muy justo de recursos

### La camara abre pero no se ve imagen

Puede ser:

- la camara esta ocupada por otra aplicacion
- el backend elegido no le sienta bien al dispositivo
- la camara virtual esta entregando frames tarde

Accion recomendada:

- cerrar otras apps
- volver a abrir la GUI
- probar otro backend con `camera_diagnostic.py`

### No carga la nomina

Revisar:

- que el archivo sea `.xlsx` o `.csv`
- que exista la columna de curso
- que el curso seleccionado coincida con la escritura exacta de la hoja
- que el archivo no tenga celdas fusionadas extrañas o encabezados cambiados

### Falta una foto

Revisar:

- `fotos/<curso>/`
- `fotos_respaldo/<curso>/`
- `index.csv`
- el log de la sesion

## Recuperacion manual

Si alguien borra una foto por error o el recorte automatico corta mal una cara:

- buscar en `fotos_respaldo/<curso>/`
- copiar el archivo de vuelta a `fotos/<curso>/` o recortarlo manualmente desde esa fuente completa
- si hace falta, reconstruir el `index.csv` a partir del respaldo

Por eso el proyecto guarda la copia fuente: para que una perdida accidental o un recorte fallido no implique rehacer toda la jornada.

## Modo prueba vs modo curso

### Modo prueba

Sirve para:

- probar camara
- validar encuadre
- verificar logs y respaldos
- ensayar sin afectar un curso real

### Modo curso

Sirve para:

- capturar una nomina real
- avanzar alumno por alumno
- mantener orden de curso
- guardar nombres y RUT

## Buenas practicas

- no mover manualmente los archivos mientras la sesion esta abierta
- no usar la misma camara en otra app al mismo tiempo
- no borrar `logs/` hasta haber revisado un problema
- si algo raro pasa, probar primero con una sesion de prueba

## Archivos que casi nunca conviene tocar

- `camera_aliases.json` solo si se quiere cambiar un alias local
- `last_camera.json` solo como cache local
- `requirements.txt` solo al sumar dependencias nuevas

## Si vas a seguir el proyecto

Antes de cambiar codigo, probar esta secuencia minima:

1. abrir la GUI
2. cargar roster
3. entrar a la pestaña `Curso`
4. cambiar de alumno
5. capturar
6. rehacer ultima
7. cerrar la sesion

Si cualquiera de esos pasos rompe, el log debe mostrar el punto exacto.
