"""Pre-build what a slow host would otherwise make on the first request: the demo dataset's packs, briefs and one-page
PDFs (both languages). Used at Docker build time so a 0.1-CPU free host serves PDFs instantly.

    python -m kaaran.warm --dataset blocks
"""

from __future__ import annotations

import argparse
import sys
import time

from .brief.pdf import PdfUnavailable
from .service import Service


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="python -m kaaran.warm")
    p.add_argument("--dataset", default="blocks")
    args = p.parse_args(argv)
    t0 = time.monotonic()
    ws = Service().workspace(args.dataset).prepare()
    n = 0
    for focus in ws.analyses:
        ws.brief(focus)
        for lang in ("mr", "en"):
            try:
                ws.pdf(focus, lang)
                n += 1
            except PdfUnavailable as e:
                print(f"no PDF browser ({e}); skipping PDFs")
                return 0
    if hasattr(ws, "save_prepared"):
        path = ws.save_prepared()
        print(f"prepared state saved: {path.name} ({path.stat().st_size // 1_000_000} MB)")
    print(f"warm: {len(ws.analyses)} briefs, {n} PDFs in {time.monotonic() - t0:.0f} s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
