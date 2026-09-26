"""Nonblocking per-job execution locks. PostgreSQL locks span short transactions."""

import hashlib
import threading
from contextlib import contextmanager

from django.db import connection

_local_locks = {}
_mutex = threading.Lock()


def advisory_lock_id(job_id):
    return int.from_bytes(hashlib.sha256(str(job_id).encode()).digest()[:8], signed=True)


@contextmanager
def execution_lock(job_id):
    # Also prevent PostgreSQL's reentrant session locks within this process.
    key = str(job_id)
    with _mutex:
        entry = _local_locks.setdefault(key, [threading.Lock(), 0])
        entry[1] += 1
    local_acquired = entry[0].acquire(blocking=False)
    pg_acquired = False
    lock_id = advisory_lock_id(key)
    try:
        if not local_acquired:
            yield False
            return
        if connection.vendor == "postgresql":
            with connection.cursor() as cursor:
                cursor.execute("SELECT pg_try_advisory_lock(%s)", [lock_id])
                pg_acquired = cursor.fetchone()[0]
            yield pg_acquired
        else:
            # SQLite development supports one worker process only.
            yield True
    finally:
        try:
            if pg_acquired:
                with connection.cursor() as cursor:
                    cursor.execute("SELECT pg_advisory_unlock(%s)", [lock_id])
        finally:
            if local_acquired:
                entry[0].release()
            with _mutex:
                entry[1] -= 1
                if entry[1] == 0:
                    del _local_locks[key]
