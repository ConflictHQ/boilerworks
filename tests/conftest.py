"""Shared pytest fixtures."""

from __future__ import annotations

import pytest

from boilerworks.manifest import BoilerworksManifest, DataConfig, ServicesConfig
from boilerworks.manifest import TestingConfig as TestingCfg


@pytest.fixture()
def valid_manifest() -> BoilerworksManifest:
    return BoilerworksManifest(
        project="my-app",
        family="django-nextjs",
        size="full",
        topology="standard",
        cloud="aws",
        region="us-east-1",
        domain="myapp.com",
        mobile=False,
        web_presence=False,
        compliance=["soc2"],
        services=ServicesConfig(email="ses"),
        data=DataConfig(),
        testing=TestingCfg(e2e="playwright"),
    )
