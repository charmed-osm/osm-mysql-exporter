# Copyright 2023 Canonical Ltd.
# See LICENSE file for licensing details.
#
# Learn more about testing at: https://juju.is/docs/sdk/testing

import unittest

import ops.testing
from charm import MysqlExporterCharm
from ops.model import ActiveStatus, BlockedStatus, WaitingStatus
from ops.testing import Harness


class TestCharm(unittest.TestCase):
    """Class to test the charm."""

    def setUp(self):
        # Enable more accurate simulation of container networking.
        # For more information, see https://juju.is/docs/sdk/testing#heading--simulate-can-connect
        ops.testing.SIMULATE_CAN_CONNECT = True
        self.addCleanup(setattr, ops.testing, "SIMULATE_CAN_CONNECT", False)

        self.harness = Harness(MysqlExporterCharm)
        self.addCleanup(self.harness.cleanup)
        self.harness.begin()

    def test_mysql_exporter_pebble_ready(self):
        """Test to check the plan created is the expected one."""
        # Expected plan after Pebble ready with default config
        expected_plan = {
            "services": {
                "mysql-exporter": {
                    "override": "replace",
                    "summary": "mysql-exporter service",
                    "command": "/bin/mysqld_exporter",
                    "startup": "enabled",
                    "environment": {"DATA_SOURCE_NAME": "username:password@(endpoints)/"},
                },
            },
        }
        self.harness.update_config({"mysql-uri": "mysql://username:password@endpoints/"})
        self.harness.container_pebble_ready("mysql-exporter")
        updated_plan = self.harness.get_container_pebble_plan("mysql-exporter").to_dict()
        self.assertEqual(expected_plan, updated_plan)
        service = self.harness.model.unit.get_container("mysql-exporter").get_service(
            "mysql-exporter"
        )
        self.assertTrue(service.is_running())
        self.assertEqual(self.harness.model.unit.status, ActiveStatus())

    def test_mysql_exporter_pebble_not_ready(self):
        """Test to check the plan created is the expected one."""
        # Expected plan after Pebble ready with default config
        expected_plan = {}
        error_message = "No MySQL uri added. MySQL uri needs to be added via config"
        self.harness.container_pebble_ready("mysql-exporter")
        updated_plan = self.harness.get_container_pebble_plan("mysql-exporter").to_dict()
        self.assertEqual(expected_plan, updated_plan)
        self.assertEqual(self.harness.model.unit.status, BlockedStatus(error_message))

    def test_config_changed_valid_can_connect(self):
        """Valid config change for mysql-uri parameter."""
        self.harness.set_can_connect("mysql-exporter", True)
        self.harness.update_config({"mysql-uri": "mysql://username:password@endpoints/"})
        updated_plan = self.harness.get_container_pebble_plan("mysql-exporter").to_dict()
        updated_env = updated_plan["services"]["mysql-exporter"]["environment"]
        self.assertEqual(updated_env, {"DATA_SOURCE_NAME": "username:password@(endpoints)/"})
        self.assertEqual(self.harness.model.unit.status, ActiveStatus())

    def test_config_changed_valid_cannot_connect(self):
        """Test cannot connect to Pebble."""
        self.harness.update_config({"mysql-uri": "mysql://username:password@endpoints/"})
        self.assertIsInstance(self.harness.model.unit.status, WaitingStatus)

    def test_config_mysql_uri_changed_invalid(self):
        """Invalid config change for mysql-uri parameter."""
        self.harness.set_can_connect("mysql-exporter", True)
        self.harness.update_config({"mysql-uri": "foobar"})
        self.assertIsInstance(self.harness.model.unit.status, BlockedStatus)

    def test_no_config(self):
        """No database configured in the charm."""
        self.harness.set_can_connect("mysql-exporter", True)
        self.harness.charm.on.config_changed.emit()
        self.assertIsInstance(self.harness.model.unit.status, BlockedStatus)

    def test_update_status_no_mysql(self):
        """update_status test Blocked because no MySQL."""
        self.harness.set_can_connect("mysql-exporter", True)
        self.harness.charm.on.update_status.emit()
        self.assertIsInstance(self.harness.model.unit.status, BlockedStatus)

    def test_update_status_success(self):
        """update_status test successful."""
        self.harness.set_can_connect("mysql-exporter", True)
        self.harness.update_config({"mysql-uri": "mysql://username:password@endpoints/"})
        self.harness.charm.on.update_status.emit()
        self.assertIsInstance(self.harness.model.unit.status, ActiveStatus)
