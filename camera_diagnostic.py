from __future__ import annotations

from pathlib import Path

import cv2

from castel_credcam import (
    backend_key_from_id,
    camera_priority,
    get_camera_alias,
    load_camera_aliases,
    save_last_camera,
    silence_opencv_logs,
    suppress_native_stderr,
)


BACKENDS = [
    ("DSHOW", cv2.CAP_DSHOW),
    ("MSMF", cv2.CAP_MSMF),
    ("ANY", cv2.CAP_ANY),
]


def main() -> None:
    silence_opencv_logs()
    app_dir = Path(__file__).resolve().parent
    output_dir = app_dir / "camera_diagnostic"
    output_dir.mkdir(exist_ok=True)
    aliases = load_camera_aliases(app_dir)
    usable: list[tuple[int, int, str, str, str, float]] = []

    print("Diagnostico de camaras OpenCV\n")
    for index in range(12):
        for backend_name, backend_id in BACKENDS:
            with suppress_native_stderr():
                cap = cv2.VideoCapture(index, backend_id)
            opened = cap.isOpened()
            ok = False
            details = ""
            if opened:
                cap.set(cv2.CAP_PROP_CONVERT_RGB, 1)
                for _ in range(6):
                    with suppress_native_stderr():
                        ok, frame = cap.read()
                    if ok and frame is not None:
                        mean = float(frame.mean())
                        std = float(frame.std())
                        details = f"shape={frame.shape} mean={mean:.1f} std={std:.1f}"
                        out = output_dir / f"camera_{index}_{backend_name}.jpg"
                        cv2.imwrite(str(out), frame)
                        alias = get_camera_alias(aliases, index, backend_id)
                        usable.append((index, backend_id, backend_name, alias, details, std))
                        break
            print(f"idx={index} backend={backend_name} opened={opened} ok={ok} {details}")
            cap.release()

    print(f"\nImagenes de prueba: {output_dir}")
    if usable:
        usable.sort(
            key=lambda item: (
                camera_priority(item[3], item[2])[0],
                -item[5],
                camera_priority(item[3], item[2])[1],
                item[0],
            )
        )
        index, backend_id, backend_name, alias, details, _std = usable[0]
        save_last_camera(app_dir, index, backend_key_from_id(backend_id))
        print(
            "\nCamara recomendada guardada: "
            f"{alias} | idx={index} | backend={backend_name} | {details}"
        )
    else:
        print("\nNo se detecto ninguna camara con frames usables.")


if __name__ == "__main__":
    main()
