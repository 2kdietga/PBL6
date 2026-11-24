"""Run the web server and one MQTT worker inside a single Render service."""
import logging
import os
import signal
import subprocess
import sys
import threading
import time

logger = logging.getLogger('savelife.services')


class Services:
    def __init__(self, web_command, mqtt_command, restart_delay=5, shutdown_timeout=20, face_command=None):
        self.web_command = web_command
        self.mqtt_command = mqtt_command
        self.face_command = face_command
        self.restart_delay = restart_delay
        self.shutdown_timeout = shutdown_timeout
        self.stopping = threading.Event()
        self.children = []

    def stop(self, *_):
        self.stopping.set()

    def start(self, command):
        # Inherit stdout/stderr so both services appear in Render Logs.
        process = subprocess.Popen(command, start_new_session=(os.name == 'posix'))
        self.children.append(process)
        return process

    def shutdown(self):
        live = [process for process in self.children if process.poll() is None]
        for process in live:
            try:
                if os.name == 'posix':
                    os.killpg(process.pid, signal.SIGTERM)
                else:
                    process.terminate()
            except ProcessLookupError:
                pass
        deadline = time.monotonic() + self.shutdown_timeout
        for process in live:
            try:
                process.wait(timeout=max(0, deadline - time.monotonic()))
            except subprocess.TimeoutExpired:
                if os.name == 'posix':
                    os.killpg(process.pid, signal.SIGKILL)
                else:
                    process.kill()
                process.wait()

    def run(self):
        try:
            web = self.start(self.web_command)
            mqtt = self.start(self.mqtt_command) if self.mqtt_command else None
            face = self.start(self.face_command) if self.face_command else None
            face_retry_at = None
            retry_at = None
            while not self.stopping.wait(0.25):
                if web.poll() is not None:
                    logger.error('Web server exited (%s); stopping service.', web.returncode)
                    return web.returncode or 1
                if mqtt is not None and mqtt.poll() is not None:
                    logger.warning('MQTT worker exited (%s); retrying in %ss.', mqtt.returncode, self.restart_delay)
                    self.children.remove(mqtt)
                    mqtt = None
                    retry_at = time.monotonic() + self.restart_delay
                if retry_at is not None and time.monotonic() >= retry_at:
                    mqtt = self.start(self.mqtt_command)
                    retry_at = None
                if face is not None and face.poll() is not None:
                    logger.warning('Face worker exited (%s); retrying in %ss.', face.returncode, self.restart_delay)
                    self.children.remove(face)
                    face = None
                    face_retry_at = time.monotonic() + self.restart_delay
                if face_retry_at is not None and time.monotonic() >= face_retry_at:
                    face = self.start(self.face_command)
                    face_retry_at = None
            return 0
        finally:
            self.shutdown()


def main():
    logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(name)s %(message)s')
    mqtt_enabled = os.getenv('RUN_MQTT', 'true').lower() == 'true'
    if mqtt_enabled and not all(os.getenv(key) for key in ('MQTT_HOST', 'MQTT_USERNAME', 'MQTT_PASSWORD')):
        logger.error('Set MQTT_HOST, MQTT_USERNAME and MQTT_PASSWORD, or RUN_MQTT=false for web-only mode.')
        return 1
    web = [sys.executable, '-m', 'gunicorn', 'config.wsgi:application',
           '--bind', f"0.0.0.0:{os.getenv('PORT', '8000')}",
           '--workers', '1', '--threads', '4', '--timeout', '180',
           '--access-logfile', '-', '--error-logfile', '-']
    mqtt = [sys.executable, '-u', 'manage.py', 'mqtt_worker'] if mqtt_enabled else None
    face = [sys.executable, '-u', 'manage.py', 'face_worker']
    services = Services(web, mqtt, face_command=face)
    for sig in (signal.SIGTERM, signal.SIGINT):
        signal.signal(sig, services.stop)
    logger.info('Starting web, face worker%s.', ' and MQTT worker' if mqtt_enabled else '')
    return services.run()


if __name__ == '__main__':
    sys.exit(main())
