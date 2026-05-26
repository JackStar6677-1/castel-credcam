from __future__ import annotations

import argparse
import sys
from pathlib import Path

from castel_credcam import autoframe_photo_file, setup_logging


def main() -> int:
    parser = argparse.ArgumentParser(description="Reencuadra una foto de CastelCredCam centrando el rostro.")
    parser.add_argument("image", type=Path, help="Ruta del JPG a reencuadrar.")
    parser.add_argument("--backup", type=Path, default=None, help="Ruta opcional del respaldo espejo.")
    args = parser.parse_args()

    logger, log_path = setup_logging(Path(__file__).resolve().parent, "autoframe")
    logger.info("=== Photo autoframe start ===")
    logger.info("Diagnostic log: %s", log_path)
    ok, message = autoframe_photo_file(args.image, args.backup, diagnostic_logger=logger)
    logger.info("Photo autoframe end: ok=%s message=%s", ok, message)
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
