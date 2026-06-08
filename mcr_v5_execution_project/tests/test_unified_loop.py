from mcr_v5.unified_loop import UnifiedLoopV5


def test_unified_loop_runs_15_steps() -> None:
    loop = UnifiedLoopV5()
    report = loop.run_once()

    assert report["status"] == "ok"
    assert len(report["steps"]) == 15
    assert len(report["events"]) >= 15
