import os
import sys
import threading
import time

from django.apps import AppConfig


class FixturesConfig(AppConfig):
    """Only keeps fixtures/scores fresh under `manage.py runserver` (local
    dev) - gunicorn never triggers this `ready()` path with "runserver" in
    sys.argv, so this is a no-op in production. Production relies on a
    separate scheduled job (a Render Cron Job) running `sync_fixtures` and
    `score_gameweeks` instead - see README.md's Deployment section."""

    name = 'backend.fixtures'
    label = 'fixtures'

    def ready(self):
        if "runserver" not in sys.argv:
            return
        # runserver's autoreloader spawns a watcher process and a worker
        # process; RUN_MAIN is only set in the worker, so this avoids
        # starting two competing background schedulers.
        if os.environ.get("RUN_MAIN") != "true":
            return

        from django.conf import settings

        if not settings.AUTO_SYNC_INTERVAL_SECONDS:
            return

        thread = threading.Thread(target=_sync_loop, daemon=True)
        thread.start()


def _sync_loop():
    from django.conf import settings
    from django.core.management import call_command

    interval = settings.AUTO_SYNC_INTERVAL_SECONDS
    while True:
        try:
            call_command("sync_fixtures")
            call_command("score_gameweeks")
        except Exception as exc:  # keep the loop alive across transient API/network errors
            print(f"[auto-sync] fixtures sync failed, will retry in {interval}s: {exc}")
        time.sleep(interval)
