"""Bootstrap checks without package downloads, GUI windows or radio hardware."""

from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

import launch_app
import setup_venv


class SetupTests(unittest.TestCase):
    def test_missing_environment_is_not_ready(self):
        with tempfile.TemporaryDirectory() as directory:
            with patch.object(setup_venv, "ENVIRONMENT", Path(directory) / ".venv"):
                self.assertFalse(setup_venv.check_environment("rx"))

    def test_new_environment_is_created_before_installing_missing_dependencies(self):
        with tempfile.TemporaryDirectory() as directory:
            environment = Path(directory) / ".venv"
            calls = []

            def run(command, **kwargs):
                calls.append(command)
                # PySerial is missing; other probes succeed.
                code = 1 if command[-1] == "import serial" and "-c" in command else 0
                return subprocess.CompletedProcess(command, code)

            with patch.object(setup_venv, "ENVIRONMENT", environment), \
                    patch.object(setup_venv.venv, "EnvBuilder") as builder, \
                    patch.object(setup_venv.subprocess, "run", side_effect=run):
                setup_venv.install_environment("ris")
            builder.assert_called_once_with(with_pip=True, system_site_packages=True)
            builder.return_value.create.assert_called_once_with(environment)
            self.assertTrue(any(command[-3:] == ["pip", "install", "pyserial"] for command in calls))
            self.assertFalse(any("uhd" in command for command in calls))

    def test_existing_environment_is_preserved_and_completed(self):
        with tempfile.TemporaryDirectory() as directory:
            python = Path(directory) / "python"
            python.touch()
            with patch.object(setup_venv, "environment_python", return_value=python), \
                    patch.object(setup_venv.venv, "EnvBuilder") as builder, \
                    patch.object(setup_venv.subprocess, "run") as run:
                run.return_value.returncode = 0
                setup_venv.install_environment("tx")
            builder.assert_not_called()
            self.assertFalse(any("install" in call.args[0] for call in run.call_args_list))


class LauncherTests(unittest.TestCase):
    def run_launch(self, component, readiness):
        with patch.object(launch_app.sys, "platform", "win32"), \
                patch.object(setup_venv, "check_environment", side_effect=readiness), \
                patch.object(setup_venv, "environment_python", return_value=Path(".venv/Scripts/python.exe")), \
                patch.object(launch_app.subprocess, "CREATE_NEW_CONSOLE", 16, create=True), \
                patch.object(launch_app.subprocess, "run") as install, \
                patch.object(launch_app.subprocess, "Popen") as start:
            launch_app.launch(component)
        return install, start

    def test_ready_apps_skip_setup_and_use_correct_entrypoint(self):
        for component, (folder, script) in launch_app.APPLICATIONS.items():
            with self.subTest(component=component):
                install, start = self.run_launch(component, [True])
                install.assert_not_called()
                command = start.call_args.args[0]
                self.assertEqual(Path(command[1]), launch_app.ROOT / folder / script)
                self.assertEqual(Path(command[0]).name, "python.exe" if component == "tx" else "pythonw.exe")
                self.assertEqual(start.call_args.kwargs.get("creationflags"), 16 if component == "tx" else None)

    def test_missing_or_incomplete_environment_runs_installer_then_app(self):
        for component in launch_app.APPLICATIONS:
            with self.subTest(component=component):
                install, start = self.run_launch(component, [False, True])
                command = install.call_args.args[0]
                self.assertEqual(command[1:4], [str(launch_app.ROOT / "setup_venv.py"), component, "--pause-on-error"])
                self.assertEqual(install.call_args.kwargs["creationflags"], 16)
                start.assert_called_once()

    def test_failed_setup_never_starts_app(self):
        with patch.object(setup_venv, "check_environment", return_value=False), \
                patch.object(launch_app.subprocess, "run", side_effect=subprocess.CalledProcessError(1, "setup")), \
                patch.object(launch_app.subprocess, "Popen") as start:
            with self.assertRaises(subprocess.CalledProcessError):
                launch_app.launch("tx")
            start.assert_not_called()

    def test_incomplete_setup_never_starts_app(self):
        with patch.object(setup_venv, "check_environment", return_value=False), \
                patch.object(launch_app.subprocess, "run"), \
                patch.object(launch_app.subprocess, "Popen") as start:
            with self.assertRaises(RuntimeError):
                launch_app.launch("rx")
            start.assert_not_called()


if __name__ == "__main__":
    unittest.main()
