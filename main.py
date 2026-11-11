import re
import shutil
import uuid
from pathlib import Path

from fastapi import BackgroundTasks, FastAPI, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles

import config
import pipeline
from store import JobStore

app = FastAPI()
store = JobStore(config.JOBS_DIR)
ALLOWED = ('.zip', '.dll', '.apk', '.jar')
ID_RE = re.compile(r'[0-9a-f]{32}')


def get_job(job_id):
    job = store.get(job_id) if ID_RE.fullmatch(job_id) else None
    if not job:
        raise HTTPException(404, 'Unknown job')
    return job


@app.get('/api/config')
def get_config():
    return {
        'model': config.MODEL, 'price_in': config.PRICE_IN_PER_M, 'price_out': config.PRICE_OUT_PER_M,
        'max_run_tokens': config.MAX_RUN_TOKENS, 'max_upload_mb': config.MAX_UPLOAD_MB,
    }


@app.post('/api/upload')
async def upload(file: UploadFile, bg: BackgroundTasks):
    name = Path(file.filename or '').name
    if not name.lower().endswith(ALLOWED):
        raise HTTPException(400, 'Upload Assembly-CSharp.dll, an .apk, a .jar or a .zip of the game folder.')
    job_id = uuid.uuid4().hex
    up = store.base(job_id) / 'upload'
    up.mkdir(parents=True)
    limit = config.MAX_UPLOAD_MB * 1024 * 1024
    size = 0
    with open(up / name, 'wb') as out:
        while chunk := await file.read(1024 * 1024):
            size += len(chunk)
            if size > limit:
                break
            out.write(chunk)
    if size > limit:
        shutil.rmtree(store.base(job_id), ignore_errors=True)
        raise HTTPException(413, f'File is too large (limit {config.MAX_UPLOAD_MB} MB). '
                                 'Upload only Assembly-CSharp.dll or the APK instead of the whole game.')
    store.create(job_id, name)
    bg.add_task(pipeline.prepare, store, job_id)
    return {'job_id': job_id}


@app.get('/api/jobs')
def list_jobs():
    return store.list()


@app.get('/api/jobs/{job_id}')
def job_info(job_id: str):
    return get_job(job_id)


@app.post('/api/jobs/{job_id}/clean')
async def clean_job(job_id: str, request: Request, bg: BackgroundTasks):
    job = get_job(job_id)
    if job['state'] not in ('ready', 'done', 'cancelled', 'interrupted') or not job['files']:
        raise HTTPException(409, 'This job cannot be cleaned right now.')
    body = await request.json()
    known = {f['path']: f for f in job['files']}
    selected = [p for p in body.get('files', []) if p in known]
    if not selected:
        raise HTTPException(400, 'No files selected.')
    estimate = sum(known[p]['est_tokens'] for p in selected)
    if estimate > config.MAX_RUN_TOKENS:
        raise HTTPException(400, f'The selection is estimated at {estimate:,} tokens, above the limit of '
                                 f'{config.MAX_RUN_TOKENS:,} per run. Select fewer files.')
    bg.add_task(pipeline.clean, store, job_id, selected)
    store.update(job_id, state='queued', message='Starting...')
    return {'ok': True, 'files': len(selected), 'estimated_tokens': estimate}


@app.post('/api/jobs/{job_id}/cancel')
def cancel_job(job_id: str):
    get_job(job_id)
    store.request_cancel(job_id)
    return {'ok': True}


@app.get('/api/jobs/{job_id}/file')
def job_file(job_id: str, path: str, version: str = 'raw'):
    get_job(job_id)
    folder = (store.base(job_id) / ('result' if version == 'clean' else 'raw')).resolve()
    target = (folder / path).resolve()
    if not target.is_relative_to(folder) or not target.is_file():
        raise HTTPException(404, 'File not found')
    return PlainTextResponse(target.read_text(encoding='utf-8', errors='ignore'))


@app.get('/api/jobs/{job_id}/download')
def download(job_id: str):
    job = get_job(job_id)
    base = store.base(job_id)
    if not (base / 'result').exists():
        raise HTTPException(404, 'Nothing to download yet')
    if not (base / 'decompiled.zip').exists() or job['state'] not in ('done', 'cancelled'):
        shutil.make_archive(str(base / 'decompiled'), 'zip', base / 'result')
    return FileResponse(base / 'decompiled.zip', filename='decompiled.zip')


# Must be last: serves the web page
app.mount('/', StaticFiles(directory=config.BASE / 'static', html=True), name='static')
