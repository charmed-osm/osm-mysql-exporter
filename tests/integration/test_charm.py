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
MYSQL_CHARM = "mysql-k8s"
MYSQL_APP = "mysql"
INGRESS_CHARM = "nginx-ingress-integrator"
INGRESS_APP = "ingress"
APPS = [INGRESS_APP, MYSQL_APP, APP_NAME]


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
        ops_test.model.deploy(
            MYSQL_CHARM,
            application_name=MYSQL_APP,
            channel="edge",
            series="jammy",
        ),
    )

    async with ops_test.fast_forward():
        await ops_test.model.wait_for_idle(
            apps=APPS,
        )
    assert ops_test.model.applications[APP_NAME].status == "blocked"
    unit = ops_test.model.applications[APP_NAME].units[0]
    assert (
        unit.workload_status_message
        == "No MySQL uri added. MySQL uri needs to be added via relation or via config"
    )

    logger.info("Adding relations")
    await ops_test.model.applications[APP_NAME].set_config(APP_CONFIG)
    await ops_test.model.add_relation(APP_NAME, MYSQL_APP)
    await ops_test.model.add_relation(APP_NAME, INGRESS_APP)

    async with ops_test.fast_forward():
        await ops_test.model.wait_for_idle(
            apps=APPS,
            status="active",
        )


@pytest.mark.abort_on_fail
async def test_mysql_exporter_blocks_without_mysql(ops_test: OpsTest):
    await asyncio.gather(ops_test.model.applications[MYSQL_APP].remove())
    async with ops_test.fast_forward():
        await ops_test.model.wait_for_idle(apps=[APP_NAME])
    assert ops_test.model.applications[APP_NAME].status == "blocked"
    for unit in ops_test.model.applications[APP_NAME].units:
        assert (
            unit.workload_status_message
            == "No MySQL uri added. MySQL uri needs to be added via relation or via config"
        )
