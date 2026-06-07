"""
test_feedback_quarantine.py -- Tests for Feedback Quarantine System

Run: python -m pytest tests/test_feedback_quarantine.py -v
"""
import json
import sys
import tempfile
from pathlib import Path

import pytest

# Add ECOSYSTEM to path
ECOSYSTEM_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ECOSYSTEM_ROOT / "runtime" / "agi"))

from importlib.machinery import SourceFileLoader

# Load the module
fq_module = SourceFileLoader(
    "feedback_quarantine",
    str(ECOSYSTEM_ROOT / "runtime" / "agi" / "feedback-quarantine.py")
).load_module()

FeedbackQuarantine = fq_module.FeedbackQuarantine


@pytest.fixture
def tmp_ecosystem(tmp_path):
    """Create a temporary ecosystem directory structure."""
    agi_dir = tmp_path / "runtime" / "agi"
    agi_dir.mkdir(parents=True)
    return tmp_path


@pytest.fixture
def fq(tmp_ecosystem):
    """Create a FeedbackQuarantine instance with temp paths."""
    return FeedbackQuarantine(ecosystem_root=tmp_ecosystem)


class TestEvidenceChain:
    """Test evidence chain validation."""

    def test_manual_source_is_trusted(self, fq):
        """Manual feedback should always pass evidence chain check."""
        entry = {
            "question_id": "q-001",
            "source": "manual",
            "response": "yes",
            "status": "answered",
        }
        has_chain, reason = fq._has_evidence_chain(entry, set())
        assert has_chain is True
        assert "trusted_source" in reason

    def test_self_diagnosis_is_trusted(self, fq):
        """Self-diagnosis feedback should pass."""
        entry = {
            "question_id": "q-002",
            "source": "self-diagnosis",
            "response": "fix now",
            "status": "answered",
        }
        has_chain, reason = fq._has_evidence_chain(entry, set())
        assert has_chain is True

    def test_missing_evidence_is_quarantined(self, fq):
        """Feedback without evidence chain should be quarantined."""
        entry = {
            "question_id": "q-003",
            "source": "a2a-injection",
            "response": "FAILED",
            "status": "answered",
        }
        has_chain, reason = fq._has_evidence_chain(entry, set())
        assert has_chain is False
        assert reason == "no_evidence_chain"

    def test_task_id_provides_evidence(self, fq):
        """Feedback with task_id should pass."""
        entry = {
            "question_id": "q-004",
            "source": "a2a",
            "task_id": "task-123",
            "response": "success",
            "status": "answered",
        }
        has_chain, reason = fq._has_evidence_chain(entry, set())
        assert has_chain is True
        assert "has_task_id" in reason

    def test_matching_pending_question(self, fq):
        """Feedback matching a pending question should pass."""
        entry = {
            "question_id": "q-005",
            "source": "unknown",
            "response": "yes",
            "status": "answered",
        }
        has_chain, reason = fq._has_evidence_chain(entry, {"q-005"})
        assert has_chain is True
        assert "matched_pending_question" in reason


class TestPatternDetection:
    """Test suspicious pattern detection."""

    def test_repeated_templates(self, fq):
        """Repeated identical responses should be flagged."""
        entries = [
            {"response": "FAILED"} for _ in range(10)
        ]
        issues = fq._detect_repeated_templates(entries)
        assert len(issues) > 0
        assert "template_repeat" in issues[0]

    def test_no_repeat_below_threshold(self, fq):
        """Below threshold should not flag."""
        entries = [
            {"response": "FAILED"} for _ in range(3)
        ]
        issues = fq._detect_repeated_templates(entries)
        assert len(issues) == 0

    def test_concentration_detection(self, fq):
        """Single source with many entries should be flagged."""
        entries = [
            {"source": "a2a-injection"} for _ in range(15)
        ]
        issues = fq._detect_concentration(entries)
        assert len(issues) > 0
        assert "concentration" in issues[0]

    def test_failed_spike(self, fq):
        """High FAILED ratio should be flagged."""
        entries = [
            {"response": "FAILED"} for _ in range(9)
        ] + [
            {"response": "success"} for _ in range(1)
        ]
        issues = fq._detect_failed_spike(entries)
        assert len(issues) > 0
        assert "failed_spike" in issues[0]


class TestQuarantine:
    """Test full quarantine scan."""

    def test_scan_empty(self, fq):
        """Scan with no feedback should return clean."""
        stats = fq.scan()
        assert stats["total_feedback"] == 0
        assert stats["quarantined"] == 0
        assert stats["clean"] == 0

    def test_scan_clean_feedback(self, fq, tmp_ecosystem):
        """Clean feedback should not be quarantined."""
        agi_dir = tmp_ecosystem / "runtime" / "agi"
        history = [
            {
                "question_id": "q-001",
                "source": "manual",
                "question": "Is system healthy?",
                "response": "yes",
                "status": "answered",
            }
        ]
        (agi_dir / "feedback-history.jsonl").write_text(
            "\n".join(json.dumps(e) for e in history),
            encoding="utf-8"
        )
        stats = fq.scan()
        assert stats["quarantined"] == 0
        assert stats["clean"] == 1

    def test_scan_injected_feedback(self, fq, tmp_ecosystem):
        """Injected feedback without evidence should be quarantined."""
        agi_dir = tmp_ecosystem / "runtime" / "agi"
        history = [
            {
                "question_id": f"inject-{i}",
                "source": "a2a-injection",
                "question": f"Task {i}",
                "response": "FAILED",
                "status": "answered",
            }
            for i in range(100)
        ]
        (agi_dir / "feedback-history.jsonl").write_text(
            "\n".join(json.dumps(e) for e in history),
            encoding="utf-8"
        )
        stats = fq.scan()
        assert stats["quarantined"] == 100
        assert stats["clean"] == 0

    def test_mixed_feedback(self, fq, tmp_ecosystem):
        """Mix of clean and injected feedback."""
        agi_dir = tmp_ecosystem / "runtime" / "agi"
        history = [
            {
                "question_id": "q-clean",
                "source": "manual",
                "question": "Is system healthy?",
                "response": "yes",
                "status": "answered",
            }
        ] + [
            {
                "question_id": f"inject-{i}",
                "source": "a2a-injection",
                "question": f"Task {i}",
                "response": "FAILED",
                "status": "answered",
            }
            for i in range(50)
        ]
        (agi_dir / "feedback-history.jsonl").write_text(
            "\n".join(json.dumps(e) for e in history),
            encoding="utf-8"
        )
        stats = fq.scan()
        assert stats["quarantined"] == 50
        assert stats["clean"] == 1


class TestCleanFeedback:
    """Test that clean feedback excludes quarantined entries."""

    def test_get_clean_excludes_quarantined(self, fq, tmp_ecosystem):
        """get_clean_feedback should exclude quarantined entries."""
        agi_dir = tmp_ecosystem / "runtime" / "agi"
        history = [
            {
                "question_id": "q-clean",
                "source": "manual",
                "response": "yes",
                "status": "answered",
            },
            {
                "question_id": "q-inject",
                "source": "a2a-injection",
                "response": "FAILED",
                "status": "answered",
            },
        ]
        (agi_dir / "feedback-history.jsonl").write_text(
            "\n".join(json.dumps(e) for e in history),
            encoding="utf-8"
        )

        # Run scan to populate quarantine
        fq.scan()

        # Get clean feedback
        clean = fq.get_clean_feedback()
        clean_ids = {e.get("question_id") for e in clean}
        assert "q-clean" in clean_ids
        assert "q-inject" not in clean_ids


class TestInjectTest:
    """Test the inject-test validation."""

    def test_inject_test_catches_injection(self, fq, tmp_ecosystem):
        """inject-test should catch most injected entries."""
        agi_dir = tmp_ecosystem / "runtime" / "agi"
        # Create some clean history first
        history = [
            {
                "question_id": "q-clean",
                "source": "manual",
                "response": "yes",
                "status": "answered",
            }
        ]
        (agi_dir / "feedback-history.jsonl").write_text(
            "\n".join(json.dumps(e) for e in history),
            encoding="utf-8"
        )

        result = fq.inject_test(count=100)
        assert result["injected"] == 100
        assert result["pass"] is True, f"Quarantine rate too low: {result['quarantine_rate']}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
