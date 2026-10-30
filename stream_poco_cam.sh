#!/usr/bin/env bash
set -Eeuo pipefail

echo "========================================================="
echo "   📷 Conexión Automática Cámara POCO X8 Pro a Nova      "
echo "========================================================="

# 1. Asegurar módulo de cámara virtual
if [ ! -e /dev/video10 ]; then
    echo "[1/4] Creando cámara virtual /dev/video10..."
    sudo modprobe v4l2loopback video_nr=10 card_label="POCO_Cam" exclusive_caps=1 max_buffers=2
    sudo chmod 666 /dev/video10
fi

# 2. Descubrimiento y conexión automática por mDNS / puerto dinámico
echo "[2/4] Buscando POCO X8 Pro en la red local..."
PHONE_IP="192.168.0.211"

# Verificar si ya está conectado
CONNECTED_DEV=$(adb devices | grep -E "${PHONE_IP}|klee" | awk '{print $1}' | head -n 1)

if [ -z "$CONNECTED_DEV" ]; then
    # Intentar descubrimiento automático mDNS de Android 11+
    echo ">> Intentando autodetección de servicio inalámbrico ADB..."
    DISCOVERED=$(adb mdns services 2>/dev/null | grep -iE "_adb-tls-connect._tcp|_adb._tcp" | awk '{print $3}' | head -n 1 || true)
    
    if [ -n "$DISCOVERED" ]; then
        echo ">> Dispositivo detectado vía mDNS en: $DISCOVERED"
        adb connect "$DISCOVERED" || true
    fi
    
    # Si sigue sin conectar, probar escaneo rápido de puertos comunes de depuración
    CONNECTED_DEV=$(adb devices | grep "device$" | awk '{print $1}' | head -n 1 || true)
    if [ -z "$CONNECTED_DEV" ]; then
        echo ">> Verificando puerto de depuración en $PHONE_IP..."
        for port in 42957 5555 37000 38000 39000 40000 41000 42000 43000 44000 45000; do
            if nc -z -w 1 "$PHONE_IP" "$port" 2>/dev/null; then
                echo ">> Puerto abierto encontrado: $port. Conectando..."
                adb connect "$PHONE_IP:$port" && break
            fi
        done
    fi
fi

# 3. Validar si el dispositivo está listo
CURRENT_DEVICE=$(adb devices | grep "device$" | awk '{print $1}' | head -n 1 || true)

if [ -z "$CURRENT_DEVICE" ]; then
    echo ""
    echo "⚠️  [AVISO]: No se pudo conectar automáticamente."
    echo "Por favor verifica en tu POCO X8 Pro:"
    echo "1. Que 'Depuración inalámbrica' esté ACTIVADA."
    echo "2. Revisa la pantalla de 'Depuración inalámbrica' y dime el puerto si cambió."
    echo ""
    read -rp "Ingresa el puerto que muestra el celular (ej. 39123) o presiona ENTER para reintentar: " USER_PORT
    if [ -n "$USER_PORT" ]; then
        adb connect "$PHONE_IP:$USER_PORT"
    fi
fi

echo "[3/4] Dispositivo confirmado: $(adb devices | grep 'device$' | tr '\n' ' ')"
echo "[4/4] Transmitiendo cámara principal (1080p @ 30 FPS) a /dev/video10..."
echo "---------------------------------------------------------"
echo ">> Abre CastelCredCam y selecciona 'POCO_Cam (/dev/video10)'."
echo ">> Presiona Ctrl+C en esta terminal para detener la cámara."
echo "---------------------------------------------------------"

exec scrcpy \
    --video-source=camera \
    --camera-id=0 \
    --camera-size=1920x1080 \
    --camera-fps=30 \
    --no-audio \
    --no-playback \
    --v4l2-sink=/dev/video10
