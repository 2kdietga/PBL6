"""Exercise the process supervisor with real, lightweight Python children."""
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path
from unittest import TestCase

from run_services import Services


class ServiceTests(TestCase):
    def test_web_exit_stops_worker_and_propagates_failure(self):
        services = Services(
            [sys.executable, '-c', 'import time; time.sleep(.4); raise SystemExit(7)'],
            [sys.executable, '-c', 'import time; time.sleep(30)'], shutdown_timeout=2,
            face_command=[sys.executable, '-c', 'import time; time.sleep(30)'])
        self.assertEqual(services.run(), 7)
        self.assertTrue(all(child.poll() is not None for child in services.children))

    def test_worker_restarts_and_stop_reaps_both_children(self):
        self.check_worker_restart()

    def test_face_worker_restarts_without_mqtt(self):
        self.check_worker_restart(face=True)

    def check_worker_restart(self, face=False):
        with tempfile.TemporaryDirectory() as directory:
            marker = Path(directory) / 'started.txt'
            worker = 'from pathlib import Path; import sys; p=Path(sys.argv[1]); p.write_text(p.read_text()+"x" if p.exists() else "x")'
            services = Services(
                [sys.executable, '-c', 'import time; time.sleep(30)'],
                None if face else [sys.executable, '-c', worker, str(marker)], restart_delay=.1, shutdown_timeout=2,
                face_command=[sys.executable, '-c', worker, str(marker)] if face else None)
            outcome = []
            thread = threading.Thread(target=lambda: outcome.append(services.run()))
            thread.start()
            try:
                deadline = time.monotonic() + 8
                while time.monotonic() < deadline:
                    if marker.exists() and len(marker.read_text()) >= 2:
                        break
                    time.sleep(.05)
                self.assertTrue(marker.exists() and len(marker.read_text()) >= 2)
            finally:
                services.stop()
                thread.join(timeout=5)
            self.assertFalse(thread.is_alive())
            self.assertEqual(outcome, [0])
            self.assertTrue(all(child.poll() is not None for child in services.children))
