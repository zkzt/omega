import io
import os
import unittest
from unittest import mock

import cfg4py
from omega import cli
from ruamel.yaml import YAML
from tests import init_test_env


class TestCLI(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self.cfg = init_test_env()

    def yaml_dumps(self, settings):
        stream = io.StringIO()
        yaml = YAML()
        yaml.indent(sequence=4, offset=2)
        try:
            yaml.dump(settings, stream)
            return stream.getvalue()
        finally:
            stream.close()

    def _count_configured_sessions(self):
        count = 0
        for group in self.cfg.quotes_fetchers:
            workers = group.get("workers", None)
            if not workers:
                continue

            for worker in workers:
                count += worker.get("sessions", 1)

        return count

    def test_omega_lifecycle(self):
        cli.start("omega")
        procs = cli.find_fetcher_processes()
        self.assertTrue(len(procs) >= 1)

        cli.restart("omega")
        cli.status()

        cli.stop("omega")
        procs = cli.find_fetcher_processes()
        self.assertEqual(0, len(procs))

    def test_omega_jobs(self):
        cli.start("jobs")
        cli.status()
        cli.stop("jobs")

    def test_sync_sec_list(self):
        cli.sync_sec_list()

    def test_sync_calendar(self):
        cli.sync_calendar()

    def test_sync_bars(self):
        cli.sync_bars("1d", codes="000001.XSHE")

    def test_load_factory_settings(self):
        settings = cli.load_factory_settings()
        self.assertTrue(len(settings) > 0)
        self.assertEqual("Asia/Shanghai", settings.get("tz"))

    def test_update_config(self):
        settings = cli.load_factory_settings()

        key = "postgres.dsn"
        value = "postgres://blah"
        cli.update_config(settings, key, value)
        self.assertEqual(settings["postgres"]["dsn"], value)

        key = "tz"
        value = "shanghai"
        cli.update_config(settings, key, value)
        self.assertEqual(settings[key], value)

    def test_config_fetcher(self):
        settings = {}
        with mock.patch(
            "builtins.input", side_effect=["account", "password", "1", "n", "c"]
        ):
            cli.config_fetcher(settings)

        impl = settings["quotes_fetchers"][0]["impl"]
        worker = settings["quotes_fetchers"][0]["workers"][0]
        self.assertEqual("jqadaptor", impl)
        self.assertEqual("account", worker["account"])

    def test_check_environment(self):
        os.environ[cfg4py.envar] = ""

        with mock.patch("sh.contrib.sudo.mkdir"):
            cli.check_environment()

        with mock.patch("builtins.input", side_effect=["C"]):
            os.environ[cfg4py.envar] = "PRODUCTION"
            self.assertTrue(cli.check_environment())

    def _test_config_syslog(self):
        # this test is from debug only. Need interact manually.
        cli.config_syslog()

    async def test_config_postgres(self):
        settings = {}
        with mock.patch(
            "builtins.input",
            side_effect=["R", "127.0.0.1", "6380", "account", "password"],
        ):
            with mock.patch("omega.cli.check_postgres", side_effect=[True]):
                await cli.config_postgres(settings)
                expected = "postgres://account:password@127.0.0.1:6380/zillionare"
                self.assertEqual(expected, settings["postgres"]["dsn"])

        with mock.patch(
            "builtins.input",
            side_effect=["R", "127.0.0.1", "6380", "account", "password", "C"],
        ):
            await cli.config_postgres(settings)
            expected = "postgres://account:password@127.0.0.1:6380/zillionare"
            self.assertEqual(expected, settings["postgres"]["dsn"])

    async def test_config_redis(self):
        settings = {}
        with mock.patch("builtins.input", side_effect=["local", "6380", "", "C"]):
            expected = "redis://local:6380"
            await cli.config_redis(settings)
            self.assertDictEqual({}, settings)

        with mock.patch("builtins.input", side_effect=["local", "6380", ""]):
            with mock.patch("omega.cli.check_redis"):
                expected = "redis://local:6380"
                await cli.config_redis(settings)
                self.assertEqual(expected, settings["redis"]["dsn"])

    def _test_setup(self):
        def save_config(settings):
            with open("/tmp/omega_test_setup.yaml", "w") as f:
                f.writelines(self.yaml_dumps(settings))

        with mock.patch("omega.cli.save_config", save_config):
            cli.setup()

    def test_main(self):
        cli.main()
