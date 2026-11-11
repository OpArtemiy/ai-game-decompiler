"""Jobs are stored as jobs/<id>/job.json so they survive a server restart."""
import copy
import json
import os
import threading
from datetime import datetime, timezone
from pathlib import Path

ACTIVE = {'queued', 'decompiling', 'cleaning'}


class JobStore:
    def __init__(self, root):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.lock = threading.RLock()
        self.jobs = {}
        self.cancels = {}
        self._load()

    def base(self, job_id):
        return self.root / job_id

    def _write(self, job):
        p = self.base(job['id']) / 'job.json'
        p.parent.mkdir(parents=True, exist_ok=True)
        tmp = p.with_suffix('.tmp')
        tmp.write_text(json.dumps(job), encoding='utf-8')
        os.replace(tmp, p)

    def _load(self):
        for f in self.root.glob('*/job.json'):
            try:
                job = json.loads(f.read_text(encoding='utf-8'))
            except Exception:
                continue
            if job.get('state') in ACTIVE:
                job['state'] = 'interrupted'
                job['message'] = 'The server restarted while this job was running.'
                self._write(job)
            self.jobs[job['id']] = job

    def create(self, job_id, filename):
        job = {
            'id': job_id, 'filename': filename, 'created': datetime.now(timezone.utc).isoformat(timespec='seconds'),
            'state': 'queued', 'message': 'Queued...', 'game_type': '', 'language': 'csharp', 'files': [],
            'usage': {'input': 0, 'output': 0, 'calls': 0},
        }
        with self.lock:
            self.jobs[job_id] = job
            self._write(job)
        return copy.deepcopy(job)

    def get(self, job_id):
        with self.lock:
            job = self.jobs.get(job_id)
            return copy.deepcopy(job) if job else None

    def update(self, job_id, **fields):
        with self.lock:
            job = self.jobs[job_id]
            job.update(fields)
            self._write(job)

    def update_file(self, job_id, path, **fields):
        with self.lock:
            job = self.jobs[job_id]
            for f in job['files']:
                if f['path'] == path:
                    f.update(fields)
                    break
            self._write(job)

    def add_usage(self, job_id, tokens_in, tokens_out, path=None):
        with self.lock:
            job = self.jobs[job_id]
            u = job['usage']
            u['input'] += tokens_in
            u['output'] += tokens_out
            u['calls'] += 1
            if path:
                for f in job['files']:
                    if f['path'] == path:
                        f['tokens_in'] += tokens_in
                        f['tokens_out'] += tokens_out
                        break
            self._write(job)

    def list(self, limit=20):
        with self.lock:
            jobs = sorted(self.jobs.values(), key=lambda j: j['created'], reverse=True)[:limit]
            return [{k: j.get(k) for k in ('id', 'filename', 'created', 'state', 'game_type', 'message')} for j in jobs]

    # cancel flags are kept in memory only
    def request_cancel(self, job_id):
        self.cancels[job_id] = True

    def clear_cancel(self, job_id):
        self.cancels.pop(job_id, None)

    def is_cancelled(self, job_id):
        return self.cancels.get(job_id, False)
