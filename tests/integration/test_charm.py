#!/usr/bin/env python3
# Copyright 2023 Guillermo
# See LICENSE file for licensing details.

import asyncio
import logging
from pathlib import Path

import pytest
import yaml
from pytest_operator.plugin import OpsTest

logger = logging.getLogger(__name__)

METADATA = yaml.safe_load(Path("./metadata.yaml").read_text())
APP_NAME = METADATA["name"]
APP_CONFIG = {"external-hostname": "mysql-exporter.127.0.0.1.nip.io"}
INGRESS_CHARM = "nginx-ingress-integrator"
INGRESS_APP = "ingress"
APPS = [INGRESS_APP, APP_NAME]


@pytest.mark.abort_on_fail
async def test_build_and_deploy(ops_test: OpsTest):
    """Build the charm-under-test and deploy it together with related charms.

    Assert on the unit status before any relations/configurations take place.
    """
    # Build and deploy charm from local source folder
    charm = await ops_test.build_charm(".")
    resources = {"image": METADATA["resources"]["image"]["upstream-source"]}

    await asyncio.gather(
        ops_test.model.deploy(
            charm, resources=resources, application_name=APP_NAME, series="jammy"
        ),
        ops_test.model.deploy(INGRESS_CHARM, application_name=INGRESS_APP, channel="stable"),
    )

    async with ops_test.fast_forward():
        await ops_test.model.wait_for_idle(
            apps=APPS,
        )
    assert ops_test.model.applications[APP_NAME].status == "blocked"
    unit = ops_test.model.applications[APP_NAME].units[0]
    assert (
        unit.workload_status_message
        == "No MySQL uri added. MySQL uri needs to be added via config"
    )

    logger.info("Adding relations")
    await ops_test.model.applications[APP_NAME].set_config(APP_CONFIG)
    await ops_test.model.add_relation(APP_NAME, INGRESS_APP)

    async with ops_test.fast_forward():
        await ops_test.model.wait_for_idle(
            apps=APPS,
            status="active",
        )
