"""python -m kaaran.api [--host 127.0.0.1] [--port 8000]"""

from __future__ import annotations

import argparse
import os
import sys


def main(argv: list[str] | None = None) -> int:
    import uvicorn

    from .app import create_app

    p = argparse.ArgumentParser(prog="python -m kaaran.api", description="Kaaran web demo + WhatsApp webhook.")
    p.add_argument("--host", default=os.environ.get("KAARAN_HOST", "127.0.0.1"),
                   help="use 0.0.0.0 only in a container or behind a tunnel you control")
    p.add_argument("--port", type=int, default=int(os.environ.get("PORT", "8000")))  # hosts such as Render set PORT
    args = p.parse_args(argv)
    print(f"Kaaran demo: http://{args.host}:{args.port}/  (WhatsApp simulator: /whatsapp, webhook: /whatsapp/webhook)")
    uvicorn.run(create_app(), host=args.host, port=args.port, log_level="info")
    return 0


if __name__ == "__main__":
    sys.exit(main())
