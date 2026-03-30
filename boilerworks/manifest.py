"""Pydantic models for boilerworks.yaml manifest."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, Field, field_validator, model_validator

_SLUG_RE = re.compile(r"^[a-z][a-z0-9-]*$")


class ServicesConfig(BaseModel):
    email: Literal["ses", "sendgrid", "mailgun", "none"] | None = None
    storage: Literal["s3", "gcs", "azure-blob", "none"] | None = None
    search: Literal["opensearch", "meilisearch", "none"] | None = None
    cache: Literal["redis", "memcached", "none"] | None = "redis"


class DataConfig(BaseModel):
    database: Literal["postgres", "mysql", "sqlite"] = "postgres"
    migrations: bool = True
    seed_data: bool = True


class TestingConfig(BaseModel):
    e2e: Literal["playwright", "cypress", "none"] | None = None
    unit: bool = True
    integration: bool = True


class BoilerworksManifest(BaseModel):
    project: str
    family: str
    size: Literal["full", "micro", "edge"]
    topology: Literal["standard", "omni", "api-only"] = "standard"
    cloud: Literal["aws", "gcp", "azure"] | None = None
    ops: bool = False
    region: str | None = None
    domain: str | None = None
    mobile: bool = False
    web_presence: bool = False
    compliance: list[str] = Field(default_factory=list)
    services: ServicesConfig = Field(default_factory=ServicesConfig)
    data: DataConfig = Field(default_factory=DataConfig)
    testing: TestingConfig = Field(default_factory=TestingConfig)
    template_versions: dict[str, str] = Field(default_factory=dict)

    @field_validator("project")
    @classmethod
    def validate_project_slug(cls, v: str) -> str:
        if not _SLUG_RE.match(v):
            raise ValueError(
                f"project name '{v}' must be lowercase, start with a letter, "
                "and contain only letters, digits, and hyphens"
            )
        return v

    @model_validator(mode="after")
    def validate_family_in_registry(self) -> BoilerworksManifest:
        from boilerworks.registry import Registry

        registry = Registry()
        if registry.get_by_name(self.family) is None:
            valid = ", ".join(sorted(registry.names()))
            raise ValueError(f"unknown template family '{self.family}'. Valid families: {valid}")
        return self

    def to_yaml(self) -> str:
        """Serialise the manifest to a YAML string."""
        data = self.model_dump(exclude_none=False)
        return yaml.dump(data, default_flow_style=False, sort_keys=False, allow_unicode=True)

    @classmethod
    def from_yaml(cls, text: str) -> BoilerworksManifest:
        """Parse a manifest from a YAML string."""
        data = yaml.safe_load(text)
        return cls(**data)

    @classmethod
    def from_file(cls, path: str | Path) -> BoilerworksManifest:
        """Load a manifest from a file path."""
        return cls.from_yaml(Path(path).read_text())

    def to_file(self, path: str | Path) -> None:
        """Write the manifest to a file."""
        Path(path).write_text(self.to_yaml())
