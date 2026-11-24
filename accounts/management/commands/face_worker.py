import logging
import signal
import threading

from django.core.management.base import BaseCommand
from django.db import close_old_connections

from accounts.face_jobs import process_next_face_job


class Command(BaseCommand):
    help = 'Process queued face images and embeddings without blocking web requests.'

    def add_arguments(self, parser):
        parser.add_argument('--once', action='store_true', help='Process at most one job, then exit.')

    def handle(self, *args, **options):
        stopping = threading.Event()
        if threading.current_thread() is threading.main_thread() and not options['once']:
            for sig in (signal.SIGINT, signal.SIGTERM):
                signal.signal(sig, lambda *_: stopping.set())
        while not stopping.is_set():
            close_old_connections()
            try:
                worked = process_next_face_job()
            except Exception:
                logging.getLogger(__name__).exception('Face worker iteration failed')
                worked = False
                if options['once']:
                    raise
            finally:
                close_old_connections()
            if options['once']:
                break
            if not worked:
                stopping.wait(3)
