# Copyright 2023 Guillermo
# See LICENSE file for licensing details.
#
# Learn more about testing at: https://juju.is/docs/sdk/testing

import unittest

import ops.testing
from charm import MysqlExporterCharm
from charms.data_platform_libs.v0.data_interfaces import DatabaseCreatedEvent
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
        error_message = (
            "No MySQL uri added. MySQL uri needs to be added via relation or via config"
        )
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

    def test_config_log_changed_invalid(self):
        """Invalid config change for log-level parameter."""
        self.harness.set_can_connect("mysql-exporter", True)
        # Trigger a config-changed event with an updated value
        self.harness.update_config({"log-level": "foobar"})
        # Check the charm is in BlockedStatus
        self.assertIsInstance(self.harness.model.unit.status, BlockedStatus)

    def test_config_log_changed_no_mysql(self):
        """Valid config change for log-level parameter."""
        error_message = (
            "No MySQL uri added. MySQL uri needs to be added via relation or via config"
        )
        self.harness.set_can_connect("mysql-exporter", True)
        self.harness.update_config({"log-level": "INFO"})
        self.assertEqual(self.harness.model.unit.status, BlockedStatus(error_message))

    def test_no_config(self):
        """No database related or configured in the charm."""
        self.harness.set_can_connect("mysql-exporter", True)
        self.harness.charm.on.config_changed.emit()
        self.assertIsInstance(self.harness.model.unit.status, BlockedStatus)

    def test_mysql_relation(self):
        """Database related in the charm."""
        self.harness.set_can_connect("mysql-exporter", True)
        relation_id = self.harness.add_relation("mysql", "mysql")
        self.harness.add_relation_unit(relation_id, "mysql/0")
        self.harness.update_relation_data(
            relation_id,
            "mysql",
            {
                "endpoints": "mysql-k8s-primary.testing.svc.cluster.local:3306",
                "username": "username",
                "password": "password",
            },
        )
        self.harness.charm.on.config_changed.emit()
        self.assertIsInstance(self.harness.model.unit.status, ActiveStatus)

    def test_mysql_relation_broken(self):
        """Remove relation of the database, no database in config."""
        self.harness.set_can_connect("mysql-exporter", True)
        relation_id = self.harness.add_relation("mysql", "mysql")
        self.harness.add_relation_unit(relation_id, "mysql/0")
        self.harness.update_relation_data(
            relation_id,
            "mysql",
            {
                "endpoints": "mysql-k8s-primary.testing.svc.cluster.local:3306",
                "username": "username",
                "password": "password",
            },
        )
        self.harness.charm.on.config_changed.emit()
        self.assertIsInstance(self.harness.model.unit.status, ActiveStatus)
        self.harness.remove_relation(relation_id)
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

    def test_db_creation(self):
        """DB creation test successful."""
        self.harness.set_can_connect("mysql-exporter", True)
        relation_id = self.harness.add_relation("mysql", "mysql")
        self.harness.add_relation_unit(relation_id, "mysql/0")
        self.harness.update_relation_data(
            relation_id,
            "mysql",
            {
                "endpoints": "mysql-k8s-primary.testing.svc.cluster.local:3306",
                "username": "username",
                "password": "password",
                "database": "osm-mysql-exporter",
            },
        )
        self.harness.charm._on_database_created(DatabaseCreatedEvent)
        self.assertIsInstance(self.harness.model.unit.status, ActiveStatus)

    def test_db_creation_failed(self):
        """DB creation failedtest."""
        error_message = (
            "No MySQL uri added. MySQL uri needs to be added via relation or via config"
        )
        self.harness.set_can_connect("mysql-exporter", True)
        self.harness.charm._on_database_created(DatabaseCreatedEvent)
        self.assertEqual(self.harness.model.unit.status, BlockedStatus(error_message))

    def test_db_duplicated(self):
        """Connected to MySQL through config and relation."""
        error_message = "MySQL cannot added via relation and via config at the same time"
        self.harness.set_can_connect("mysql-exporter", True)
        relation_id = self.harness.add_relation("mysql", "mysql")
        self.harness.add_relation_unit(relation_id, "mysql/0")
        self.harness.update_relation_data(
            relation_id,
            "mysql",
            {
                "endpoints": "mysql-k8s-primary.testing.svc.cluster.local:3306",
                "username": "username",
                "password": "password",
            },
        )
        self.harness.update_config({"mysql-uri": "mysql://username:password@endpoints/"})
        self.assertEqual(self.harness.model.unit.status, BlockedStatus(error_message))

    def test_db_duplicated_and_relation_broken(self):
        """Connected to MySQL through config and relation and then remove the relation."""
        error_message = "MySQL cannot added via relation and via config at the same time"
        self.harness.set_can_connect("mysql-exporter", True)
        relation_id = self.harness.add_relation("mysql", "mysql")
        self.harness.add_relation_unit(relation_id, "mysql/0")
        self.harness.update_relation_data(
            relation_id,
            "mysql",
            {
                "endpoints": "mysql-k8s-primary.testing.svc.cluster.local:3306",
                "username": "username",
                "password": "password",
            },
        )
        self.harness.update_config({"mysql-uri": "mysql://username:password@endpoints/"})
        self.assertEqual(self.harness.model.unit.status, BlockedStatus(error_message))
        self.harness.remove_relation(relation_id)
        self.assertIsInstance(self.harness.model.unit.status, ActiveStatus)
