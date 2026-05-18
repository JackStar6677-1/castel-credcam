from __future__ import annotations

import argparse
import sys
from pathlib import Path

from castel_credcam import autoframe_photo_file


def main() -> int:
    parser = argparse.ArgumentParser(description="Reencuadra una foto de CastelCredCam centrando el rostro.")
    parser.add_argument("image", type=Path, help="Ruta del JPG a reencuadrar.")
    parser.add_argument("--backup", type=Path, default=None, help="Ruta opcional del respaldo espejo.")
    args = parser.parse_args()

    ok, message = autoframe_photo_file(args.image, args.backup)
    print(message)
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
