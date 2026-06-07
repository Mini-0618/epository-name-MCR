"""
test_concept_map.py -- Tests for Concept Map v0.1

Run: python -m pytest tests/test_concept_map.py -v
"""
import json
import sys
from pathlib import Path

import pytest

ECOSYSTEM_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ECOSYSTEM_ROOT / "runtime" / "agi"))

from importlib.machinery import SourceFileLoader

cm_module = SourceFileLoader(
    "concept_map",
    str(ECOSYSTEM_ROOT / "runtime" / "agi" / "concept_map.py")
).load_module()

ConceptMap = cm_module.ConceptMap
DEFAULT_CONCEPT_MAP = cm_module.DEFAULT_CONCEPT_MAP


@pytest.fixture
def tmp_ecosystem(tmp_path):
    """Create a temporary ecosystem directory."""
    config_dir = tmp_path / "config"
    config_dir.mkdir(parents=True)
    agi_dir = tmp_path / "runtime" / "agi"
    agi_dir.mkdir(parents=True)
    return tmp_path


@pytest.fixture
def cm(tmp_ecosystem):
    """Create a ConceptMap instance with temp paths."""
    config_path = tmp_ecosystem / "config" / "concept_map.json"
    return ConceptMap(ecosystem_root=tmp_ecosystem, config_path=config_path)


class TestResolve:
    """Test observation → concept resolution."""

    def test_resolve_jenkins(self, cm):
        r = cm.resolve("jenkins_detected")
        assert r is not None
        assert r["concept"] == "web_admin_interface"
        assert r["confidence"] > 0.5

    def test_resolve_pacs(self, cm):
        r = cm.resolve("pacs_detected")
        assert r is not None
        assert r["concept"] == "web_admin_interface"

    def test_resolve_router_admin(self, cm):
        r = cm.resolve("router_admin_detected")
        assert r is not None
        assert r["concept"] == "web_admin_interface"

    def test_resolve_static_site(self, cm):
        r = cm.resolve("static_http_site")
        assert r is not None
        assert r["concept"] == "static_content"
        assert r["concept"] != "web_admin_interface"

    def test_resolve_unknown(self, cm):
        r = cm.resolve("unknown_thing")
        assert r is None

    def test_resolve_api_endpoint(self, cm):
        r = cm.resolve("api_endpoint")
        assert r is not None
        assert r["concept"] == "api_service"


class TestInfer:
    """Test concept → risk inference."""

    def test_pacs_with_full_context(self, cm):
        results = cm.infer("pacs_detected", ["exposed_port", "credential_surface"])
        risks = [r["risk"] for r in results]
        assert "weak_password_risk" in risks

    def test_pacs_missing_credential_surface(self, cm):
        results = cm.infer("pacs_detected", ["exposed_port"])
        risks = [r["risk"] for r in results]
        assert "weak_password_risk" not in risks

    def test_static_site_excluded(self, cm):
        results = cm.infer("static_http_site", ["exposed_port", "credential_surface"])
        risks = [r["risk"] for r in results]
        assert "weak_password_risk" not in risks

    def test_jenkins_with_context(self, cm):
        results = cm.infer("jenkins_detected", ["exposed_port", "credential_surface"])
        risks = [r["risk"] for r in results]
        assert "weak_password_risk" in risks

    def test_pacs_inference_uses_concept(self, cm):
        """PACS should infer through web_admin_interface, not directly."""
        results = cm.infer("pacs_detected", ["exposed_port", "credential_surface"])
        assert len(results) > 0
        assert results[0]["concept"] == "web_admin_interface"

    def test_pacs_does_not_memorize_risk(self, cm):
        """PACS should not have a direct mapping to weak_password_risk."""
        # The resolve should give concept, not risk
        r = cm.resolve("pacs_detected")
        assert "risk" not in r  # resolve returns concept, not risk

    def test_router_admin_inference(self, cm):
        results = cm.infer("router_admin_detected", ["exposed_port", "credential_surface"])
        risks = [r["risk"] for r in results]
        assert "weak_password_risk" in risks

    def test_default_creds_without_credential_surface(self, cm):
        """default_credentials_risk should work with just exposed_port."""
        results = cm.infer("jenkins_detected", ["exposed_port"])
        risks = [r["risk"] for r in results]
        assert "default_credentials_risk" in risks

    def test_unknown_observation_no_risk(self, cm):
        results = cm.infer("unknown_thing", ["exposed_port", "credential_surface"])
        assert results == []


class TestExclusions:
    """Test exclusion rules."""

    def test_static_content_excludes_weak_password(self, cm):
        exclusions = cm.get_exclusions()
        assert "weak_password_risk" in exclusions.get("static_content", [])

    def test_static_content_excludes_default_creds(self, cm):
        exclusions = cm.get_exclusions()
        assert "default_credentials_risk" in exclusions.get("static_content", [])


class TestValidation:
    """Test concept map validation."""

    def test_valid_config(self, cm):
        result = cm.validate()
        assert result["valid"] is True

    def test_counts(self, cm):
        result = cm.validate()
        assert result["mappings_count"] == 9  # 9 observations mapped
        assert result["rules_count"] == 2      # 2 inference rules


class TestListConcepts:
    """Test concept listing."""

    def test_list_concepts(self, cm):
        concepts = cm.list_concepts()
        assert "web_admin_interface" in concepts
        assert "static_content" in concepts
        assert "jenkins_detected" in concepts["web_admin_interface"]

    def test_list_rules(self, cm):
        rules = cm.list_rules()
        assert len(rules) == 2
        rule_ids = [r["rule_id"] for r in rules]
        assert "R001" in rule_ids
        assert "R002" in rule_ids


class TestCrossDomainTransfer:
    """Test the core cross-domain transfer scenario."""

    def test_pacs_transfers_through_concept(self, cm):
        """
        Core test: PACS (medical) should get weak_password_risk
        through web_admin_interface concept, not through direct memorization.
        """
        # Step 1: PACS resolves to web_admin_interface
        resolution = cm.resolve("pacs_detected")
        assert resolution["concept"] == "web_admin_interface"

        # Step 2: web_admin_interface + context → weak_password_risk
        inference = cm.infer("pacs_detected", ["exposed_port", "credential_surface"])
        assert len(inference) > 0
        assert inference[0]["risk"] == "weak_password_risk"
        assert inference[0]["concept"] == "web_admin_interface"

        # Step 3: Confidence is lower than Jenkins (because PACS confidence is 0.85 vs 0.95)
        jenkins_inference = cm.infer("jenkins_detected", ["exposed_port", "credential_surface"])
        assert inference[0]["confidence"] < jenkins_inference[0]["confidence"]

    def test_static_site_does_not_transfer(self, cm):
        """
        static_http_site should NOT get weak_password_risk
        even with the same context.
        """
        resolution = cm.resolve("static_http_site")
        assert resolution["concept"] != "web_admin_interface"

        inference = cm.infer("static_http_site", ["exposed_port", "credential_surface"])
        risks = [r["risk"] for r in inference]
        assert "weak_password_risk" not in risks


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
