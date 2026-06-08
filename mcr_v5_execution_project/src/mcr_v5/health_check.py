from __future__ import annotations

from mcr_v5.unified_loop import UnifiedLoopV5


def main() -> None:
    loop = UnifiedLoopV5()
    report = loop.run_once()

    assert report["status"] == "ok"
    assert len(report["steps"]) == 15

    print("health_check: PASS")
    print(f"cycle_id: {report['cycle_id']}")
    print(f"steps: {len(report['steps'])}")
    print(f"events: {len(report['events'])}")


if __name__ == "__main__":
    main()
