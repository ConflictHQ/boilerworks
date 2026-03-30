"""Tests for boilerworks.manifest."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from boilerworks.manifest import BoilerworksManifest, DataConfig, ServicesConfig
from boilerworks.manifest import TestingConfig as TestingCfg


def _make_manifest(**kwargs) -> BoilerworksManifest:
    defaults = {
        "project": "my-app",
        "family": "django-nextjs",
        "size": "full",
    }
    defaults.update(kwargs)
    return BoilerworksManifest(**defaults)


class TestValidManifest:
    def test_minimal_manifest_passes(self) -> None:
        m = _make_manifest()
        assert m.project == "my-app"
        assert m.family == "django-nextjs"
        assert m.size == "full"

    def test_defaults_are_correct(self) -> None:
        m = _make_manifest()
        assert m.topology == "standard"
        assert m.cloud is None
        assert m.region is None
        assert m.domain is None
        assert m.mobile is False
        assert m.web_presence is False
        assert m.compliance == []
        assert m.template_versions == {}

    def test_full_manifest_passes(self, valid_manifest: BoilerworksManifest) -> None:
        assert valid_manifest.project == "my-app"
        assert valid_manifest.cloud == "aws"
        assert valid_manifest.region == "us-east-1"

    def test_micro_template(self) -> None:
        m = _make_manifest(family="fastapi-micro", size="micro")
        assert m.size == "micro"

    def test_edge_template(self) -> None:
        m = _make_manifest(family="astro-site", size="edge")
        assert m.size == "edge"


class TestProjectSlugValidation:
    def test_valid_slugs(self) -> None:
        for slug in ["my-app", "app", "my-app-v2", "a1b2c3"]:
            m = _make_manifest(project=slug)
            assert m.project == slug

    def test_spaces_fail(self) -> None:
        with pytest.raises(ValidationError, match="project name"):
            _make_manifest(project="my app")

    def test_uppercase_fails(self) -> None:
        with pytest.raises(ValidationError, match="project name"):
            _make_manifest(project="MyApp")

    def test_leading_digit_fails(self) -> None:
        with pytest.raises(ValidationError, match="project name"):
            _make_manifest(project="1app")

    def test_underscore_fails(self) -> None:
        with pytest.raises(ValidationError, match="project name"):
            _make_manifest(project="my_app")

    def test_empty_fails(self) -> None:
        with pytest.raises(ValidationError):
            _make_manifest(project="")


class TestFamilyValidation:
    def test_unknown_family_fails(self) -> None:
        with pytest.raises(ValidationError, match="unknown template family"):
            _make_manifest(family="not-a-real-template")

    def test_all_known_families_pass(self) -> None:
        from boilerworks.registry import Registry

        registry = Registry()
        for t in registry.list_all():
            m = _make_manifest(family=t.name, size=t.size)
            assert m.family == t.name


class TestYamlRoundtrip:
    def test_to_yaml_and_back(self, valid_manifest: BoilerworksManifest) -> None:
        yaml_str = valid_manifest.to_yaml()
        assert "my-app" in yaml_str
        assert "django-nextjs" in yaml_str

        restored = BoilerworksManifest.from_yaml(yaml_str)
        assert restored.project == valid_manifest.project
        assert restored.family == valid_manifest.family
        assert restored.size == valid_manifest.size
        assert restored.cloud == valid_manifest.cloud
        assert restored.region == valid_manifest.region

    def test_to_yaml_is_valid_yaml(self, valid_manifest: BoilerworksManifest) -> None:
        import yaml

        yaml_str = valid_manifest.to_yaml()
        parsed = yaml.safe_load(yaml_str)
        assert isinstance(parsed, dict)
        assert parsed["project"] == "my-app"

    def test_from_file(self, valid_manifest: BoilerworksManifest, tmp_path) -> None:
        yaml_file = tmp_path / "boilerworks.yaml"
        valid_manifest.to_file(yaml_file)

        loaded = BoilerworksManifest.from_file(yaml_file)
        assert loaded.project == valid_manifest.project
        assert loaded.family == valid_manifest.family


class TestNestedModels:
    def test_services_config_defaults(self) -> None:
        s = ServicesConfig()
        assert s.email is None
        assert s.cache == "redis"

    def test_data_config_defaults(self) -> None:
        d = DataConfig()
        assert d.database == "postgres"
        assert d.migrations is True
        assert d.seed_data is True

    def test_testing_config_defaults(self) -> None:
        t = TestingCfg()
        assert t.e2e is None
        assert t.unit is True
        assert t.integration is True

    def test_services_email_options(self) -> None:
        for provider in ("ses", "sendgrid", "mailgun"):
            s = ServicesConfig(email=provider)
            assert s.email == provider
