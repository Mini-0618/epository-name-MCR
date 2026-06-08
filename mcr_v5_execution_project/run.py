from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SRC = ROOT / "src"

if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from mcr_v5.unified_loop import UnifiedLoopV5


def main() -> None:
    loop = UnifiedLoopV5()
    report = loop.run_once()

    print("MCR v5.0 unified loop finished")
    print(f"steps: {len(report['steps'])}")
    print(f"events: {len(report['events'])}")
    print(f"status: {report['status']}")


if __name__ == "__main__":
    main()
