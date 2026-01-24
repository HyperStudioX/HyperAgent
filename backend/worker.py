#!/usr/bin/env python3
"""
Background Worker CLI

Usage:
    python worker.py                    # Start worker with defaults
    python worker.py --concurrency 5    # Start with 5 concurrent jobs
    python worker.py --watch            # Watch for code changes (development)
"""

import argparse
import asyncio
import sys


def main():
    parser = argparse.ArgumentParser(description="HyperAgent Background Worker")
    parser.add_argument(
        "--concurrency",
        "-c",
        type=int,
        default=10,
        help="Number of concurrent jobs (default: 10)",
    )
    parser.add_argument(
        "--burst",
        action="store_true",
        help="Exit after processing all available jobs",
    )
    parser.add_argument(
        "--watch",
        action="store_true",
        help="Watch for code changes and reload (development)",
    )

    args = parser.parse_args()

    # Import here to avoid loading everything for --help
    from app.workers.main import WorkerSettings

    # Override settings from CLI
    WorkerSettings.max_jobs = args.concurrency

    if args.watch:
        # Use watchdog for development
        try:
            from watchdog.events import FileSystemEventHandler
            from watchdog.observers import Observer

            class RestartHandler(FileSystemEventHandler):
                def __init__(self):
                    self.process = None
                    self.start_worker()

                def start_worker(self):
                    import subprocess

                    if self.process:
                        self.process.terminate()
                    self.process = subprocess.Popen(
                        [
                            sys.executable,
                            "-c",
                            "from arq import run_worker; from app.workers.main import WorkerSettings; import asyncio; asyncio.run(run_worker(WorkerSettings))",
                        ]
                    )

                def on_modified(self, event):
                    if event.src_path.endswith(".py"):
                        print(f"\nFile changed: {event.src_path}, restarting worker...")
                        self.start_worker()

            handler = RestartHandler()
            observer = Observer()
            observer.schedule(handler, path="app", recursive=True)
            observer.start()

            try:
                while True:
                    import time

                    time.sleep(1)
            except KeyboardInterrupt:
                observer.stop()
                if handler.process:
                    handler.process.terminate()
            observer.join()

        except ImportError:
            print("Install watchdog for --watch support: pip install watchdog")
            sys.exit(1)
    else:
        from arq.worker import run_worker

        # run_worker is a sync function that manages the event loop internally
        # It returns a Worker object after completion
        worker = run_worker(WorkerSettings)
        if args.burst:
            # In burst mode, worker exits after processing all jobs
            print(f"Burst mode complete: {worker}")


if __name__ == "__main__":
    main()
