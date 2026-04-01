# CastelCredCam

MVP local en Python para sacar fotos tipo credencial a estudiantes por curso, pensado para Windows y uso real en jornadas de colegio.

## Que hace

- Pregunta si la sesion es `prueba` o `curso`
- Permite elegir camara por indice (`0`, `1`, `2`, etc.)
- Prueba apertura con backends de Windows para mejorar compatibilidad
- Muestra preview en vivo con overlay
- Dibuja una guia de encuadre centrada para foto tipo credencial
- Captura con la tecla `p`
- Cierra con la tecla `q`
- Guarda JPG numerados en carpetas por curso
- Guarda un `index.csv` por carpeta
- Permite rehacer la ultima foto desde la pantalla de revision con `r`
- Deja un reporte simple de sesion al terminar

## Estructura

```text
CastelCredCam/
|-- castel_credcam.py
|-- requirements.txt
`-- fotos/
    |-- _pruebas/
    |-- 7A/
    |-- 8B/
    `-- 2MedioA/
```

Las carpetas dentro de `fotos/` se crean solas cuando inicias una sesion.

## Instalacion

En PowerShell, dentro de esta carpeta:

```powershell
py -m pip install -r requirements.txt
```

Si `py` no funciona en tu Windows:

```powershell
python -m pip install -r requirements.txt
```

## Ejecucion

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

## Flujo de uso

1. Elegir `modo prueba` o `modo curso`.
2. Si es curso, escribir el nombre del curso.
3. Elegir el indice de camara.
4. Escribir el nombre del estudiante.
5. En la ventana:
   - `p` toma y guarda la foto
   - `Enter` o `espacio` avanza al siguiente estudiante
   - `r` borra la ultima captura y permite repetirla
   - `q` sale de la sesion

En la consola:

- `revisar` abre la carpeta del curso en el Explorador
- `ultimo` muestra el ultimo registro guardado
- `q` termina el curso

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

## Sugerencias para la toma

- Usa buena luz frontal.
- Mantén la camara fija en tripode.
- Si usas Iriun, DroidCam o similar, comprueba antes que aparezca como camara en Windows.
- Haz una sesion de prueba antes de empezar con el curso real.
- Coloca ojos y hombros dentro de la guia amarilla del preview.

## Version 2 sugerida

- Recorte automatico opcional para exportacion
- Plantilla de exportacion para MySchool
- Atajo para abrir automaticamente la carpeta del curso
- Deteccion de rostro solo como ayuda visual, sin auto-captura
