"""Calls the API functions of main.py directly (works even without FastAPI installed).  Run: python tests/smoke_main.py"""
import asyncio
import os
import sys
import tempfile
import types
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'tests'))
TMP = tempfile.mkdtemp()
os.environ['JOBS_DIR'] = TMP

try:
    import fastapi  # noqa: F401
except ImportError:   # minimal stand-ins so the handlers can be imported and called
    class HTTPException(Exception):
        def __init__(self, status_code, detail=''):
            self.status_code, self.detail = status_code, detail

    class FastAPI:
        def get(self, *a, **k):
            return lambda f: f
        post = get

        def mount(self, *a, **k):
            pass

    class BackgroundTasks:
        def __init__(self):
            self.tasks = []

        def add_task(self, fn, *args):
            self.tasks.append((fn, args))

    class Simple:
        def __init__(self, *a, **k):
            self.args = a

    fa = types.ModuleType('fastapi')
    fa.FastAPI, fa.HTTPException, fa.BackgroundTasks, fa.Request, fa.UploadFile = FastAPI, HTTPException, BackgroundTasks, Simple, Simple
    fr = types.ModuleType('fastapi.responses')
    fr.FileResponse = fr.PlainTextResponse = Simple
    fs = types.ModuleType('fastapi.staticfiles')
    fs.StaticFiles = Simple
    sys.modules.update({'fastapi': fa, 'fastapi.responses': fr, 'fastapi.staticfiles': fs})

from fastapi import BackgroundTasks, HTTPException  # noqa: E402

import ai  # noqa: E402
import config  # noqa: E402
import decompile  # noqa: E402
import main  # noqa: E402
import run_tests as helpers  # noqa: E402  (re-runs the unit tests, then gives us the fakes)


class FakeUpload:
    def __init__(self, name, data):
        self.filename, self._data, self._pos = name, data, 0

    async def read(self, n):
        chunk = self._data[self._pos:self._pos + n]
        self._pos += n
        return chunk


class FakeRequest:
    def __init__(self, body):
        self._body = body

    async def json(self):
        return self._body


def run_tasks(bg):
    for fn, args in bg.tasks:
        fn(*args)
    bg.tasks.clear()


def expect_error(code, fn, *args, **kwargs):
    try:
        r = fn(*args, **kwargs)
        if asyncio.iscoroutine(r):
            asyncio.run(r)
    except HTTPException as e:
        assert e.status_code == code, (code, e.status_code, e.detail)
        return
    raise AssertionError(f'expected HTTP {code}')


decompile.decompile_target = helpers.fake_decompiler
ai.ask = helpers.fake_ask
config.MAX_CHUNK_CHARS = 3000
config.SUGGEST_TOKEN_BUDGET = 10 ** 9

bg = BackgroundTasks()
expect_error(400, main.upload, FakeUpload('notes.txt', b'x'), bg)
job_id = asyncio.run(main.upload(FakeUpload('Assembly-CSharp.dll', b'MZ'), bg))['job_id']
run_tasks(bg)
job = main.job_info(job_id)
assert job['state'] == 'ready', job
assert main.list_jobs()[0]['id'] == job_id
assert main.get_config()['model']

chosen = [f['path'] for f in job['files'] if f['suggested']]
assert chosen, 'nothing suggested'
old_limit, config.MAX_RUN_TOKENS = config.MAX_RUN_TOKENS, 1
expect_error(400, main.clean_job, job_id, FakeRequest({'files': chosen}), bg)
config.MAX_RUN_TOKENS = old_limit
expect_error(400, main.clean_job, job_id, FakeRequest({'files': ['nope.cs']}), bg)
r = asyncio.run(main.clean_job(job_id, FakeRequest({'files': chosen}), bg))
assert r['ok'] and r['files'] == len(chosen)
run_tasks(bg)
job = main.job_info(job_id)
assert job['state'] == 'done', job
assert any(f['status'] == 'cleaned' for f in job['files'])

first = chosen[0]
raw = main.job_file(job_id, first, 'raw')
clean = main.job_file(job_id, first, 'clean')
assert raw.args[0] != clean.args[0]
expect_error(404, main.job_file, job_id, '../../etc/passwd', 'raw')
expect_error(404, main.job_info, 'x' * 32)
assert main.download(job_id).args
assert main.cancel_job(job_id)['ok']
print('API smoke test passed.')
