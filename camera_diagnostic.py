from __future__ import annotations

from pathlib import Path

import cv2


BACKENDS = [
    ("DSHOW", cv2.CAP_DSHOW),
    ("MSMF", cv2.CAP_MSMF),
    ("ANY", cv2.CAP_ANY),
]


def main() -> None:
    output_dir = Path(__file__).resolve().parent / "camera_diagnostic"
    output_dir.mkdir(exist_ok=True)

    print("Diagnostico de camaras OpenCV\n")
    for index in range(6):
        for backend_name, backend_id in BACKENDS:
            cap = cv2.VideoCapture(index, backend_id)
            opened = cap.isOpened()
            ok = False
            details = ""
            if opened:
                cap.set(cv2.CAP_PROP_CONVERT_RGB, 1)
                for _ in range(6):
                    ok, frame = cap.read()
                    if ok and frame is not None:
                        mean = float(frame.mean())
                        std = float(frame.std())
                        details = f"shape={frame.shape} mean={mean:.1f} std={std:.1f}"
                        out = output_dir / f"camera_{index}_{backend_name}.jpg"
                        cv2.imwrite(str(out), frame)
                        break
            print(f"idx={index} backend={backend_name} opened={opened} ok={ok} {details}")
            cap.release()

    print(f"\nImagenes de prueba: {output_dir}")


if __name__ == "__main__":
    main()
