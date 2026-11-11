"""The two phases of a job:  prepare() unpacks and decompiles, clean() runs the AI on the chosen files."""
import re
import shutil
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import ai
import config
import decompile
import detect
import scan
from chunking import header_context, split_code
from textutil import fit_ends, strip_fences, strip_noise
from validate import validate_clean

_RUN_LOCK = threading.Lock()   # only one cleaning run at a time, so rate limits are not multiplied


class Cancelled(Exception):
    pass


# ---------------------------------------------------------------- phase 1
def prepare(store, job_id, decompiler=None):
    base = store.base(job_id)
    try:
        store.update(job_id, state='decompiling', message='Unpacking the upload...')
        upload = base / 'upload'
        for z in list(upload.glob('*.zip')):
            decompile.safe_extract(z, upload / 'unzipped')

        info = detect.detect(upload, base / 'work')
        store.update(job_id, game_type=info['type'], language=info['language'])
        if not info['targets']:
            store.update(job_id, state='error', message=info['message'])
            return

        run = decompiler or decompile.decompile_target
        raw = base / 'raw'
        for target in info['targets']:
            store.update(job_id, message=f'Decompiling {target.name}...')
            run(target, raw / target.stem, info['language'])

        files = scan.scan_sources(raw, info['language'])
        if not files:
            store.update(job_id, state='error', message='The decompiler produced no source files.')
            return
        shutil.copytree(raw, base / 'result', dirs_exist_ok=True)
        files = scan.mark_suggested(files)
        n_sug = sum(1 for f in files if f['suggested'])
        store.update(job_id, state='ready', files=files,
                     message=f'Decompiled {len(files)} files. {n_sug} are suggested for AI cleanup.')
    except decompile.ToolMissing as e:
        store.update(job_id, state='error', message=str(e))
    except Exception as e:
        store.update(job_id, state='error', message=f'{type(e).__name__}: {str(e)[:300]}')


# ---------------------------------------------------------------- phase 2
def pick_model(chars):
    if config.MODEL_SMALL and chars < config.SMALL_FILE_CHARS:
        return config.MODEL_SMALL
    return config.MODEL


def max_tokens_for(chars):
    return min(16000, int(chars / 2.5) + 1200)


def clean_file(src, dst, language, ask_fn, stop, on_usage):
    """Clean one file part by part. Returns the fields to store for the file."""
    text = Path(src).read_text(encoding='utf-8', errors='ignore')
    chunks = split_code(text, config.MAX_CHUNK_CHARS)
    header = header_context(text)
    out, notes, ok_parts = [], [], 0
    for i, ch in enumerate(chunks, 1):
        if stop():
            raise Cancelled()
        prompt = ai.build_prompt(language, Path(src).name, ch, i, len(chunks), header if i > 1 else '')
        try:
            reply, usage = ask_fn(prompt, model=pick_model(len(ch)), max_tokens=max_tokens_for(len(ch)))
        except Exception as e:
            out.append(ch)
            notes.append(f'part {i}/{len(chunks)}: AI call failed ({type(e).__name__}: {str(e)[:80]})')
            continue
        on_usage(usage.get('input', 0), usage.get('output', 0))
        cleaned = strip_fences(reply)
        ok, why = validate_clean(ch, cleaned)
        if ok:
            out.append(fit_ends(cleaned, ch))
            ok_parts += 1
        else:
            out.append(ch)
            notes.append(f'part {i}/{len(chunks)}: kept original ({why})')
    status = 'cleaned' if ok_parts == len(chunks) else ('partial' if ok_parts else 'unchanged')
    if ok_parts:
        Path(dst).write_text(''.join(out), encoding='utf-8')
    return {'status': status, 'note': '; '.join(notes), 'parts': len(chunks)}


def declarations(text, limit=25):
    lines = []
    for ln in strip_noise(text).split('\n'):
        s = ln.strip()
        if re.search(r'\b(class|interface|enum|struct)\b', s) or re.match(r'(public|protected|internal)\b.*\(', s):
            lines.append(s)
        if len(lines) >= limit:
            break
    return '\n'.join(lines)


def clean(store, job_id, selected, ask_fn=None):
    ask_fn = ask_fn or ai.ask
    base = store.base(job_id)
    job = store.get(job_id)
    language = job['language']
    chosen = set(selected)
    paths = [f['path'] for f in job['files'] if f['path'] in chosen]

    store.clear_cancel(job_id)
    for p in paths:
        store.update_file(job_id, p, status='queued', note='')
    store.update(job_id, state='queued', message='Waiting for other jobs to finish...')

    def stop():
        return store.is_cancelled(job_id)

    def one(p):
        if stop():
            store.update_file(job_id, p, status='pending', note='cancelled')
            return
        store.update_file(job_id, p, status='cleaning')
        try:
            res = clean_file(base / 'raw' / p, base / 'result' / p, language, ask_fn, stop,
                             lambda i, o: store.add_usage(job_id, i, o, p))
            store.update_file(job_id, p, **res)
        except Cancelled:
            store.update_file(job_id, p, status='pending', note='cancelled')
        except Exception as e:
            store.update_file(job_id, p, status='failed', note=f'{type(e).__name__}: {str(e)[:120]}')

    with _RUN_LOCK:
        store.update(job_id, state='cleaning', message=f'Cleaning {len(paths)} files...')
        done = [0]

        def tracked(p):
            one(p)
            done[0] += 1
            store.update(job_id, message=f'Cleaning files: {done[0]}/{len(paths)} done')

        with ThreadPoolExecutor(max_workers=max(1, config.WORKERS)) as pool:
            list(pool.map(tracked, paths))
        finalize(store, job_id, ask_fn)


def finalize(store, job_id, ask_fn):
    base = store.base(job_id)
    job = store.get(job_id)
    result = base / 'result'
    cleaned = [f for f in job['files'] if f['status'] in ('cleaned', 'partial')]

    if store.is_cancelled(job_id):
        state, message = 'cancelled', 'Cancelled. Files already cleaned are kept in the download.'
    else:
        state, message = 'done', f'Done. {len(cleaned)} files cleaned.'
        if cleaned:
            try:
                store.update(job_id, message='Writing the project overview...')
                summary = '\n\n'.join(
                    f"## {f['path']}\n" + declarations((result / f['path']).read_text(encoding='utf-8', errors='ignore'))
                    for f in cleaned[:60])[:40000]
                text, usage = ai.make_overview(summary, ask_fn)
                store.add_usage(job_id, usage.get('input', 0), usage.get('output', 0))
                (result / 'OVERVIEW.md').write_text(text, encoding='utf-8')
            except Exception as e:
                (result / 'OVERVIEW.md').write_text(f'# Overview unavailable\n\n{type(e).__name__}: {e}\n', encoding='utf-8')

    job = store.get(job_id)
    lines = ['AI cleanup results', '']
    for f in job['files']:
        if f['status'] != 'pending' or f['note']:
            lines.append(f"{f['path']}: {f['status']} (tokens in/out {f['tokens_in']}/{f['tokens_out']})"
                         + (f" - {f['note']}" if f['note'] else ''))
    u = job['usage']
    lines += ['', f"Total tokens: input {u['input']}, output {u['output']}, calls {u['calls']}"]
    (result / 'NOTES.txt').write_text('\n'.join(lines) + '\n', encoding='utf-8')
    shutil.make_archive(str(base / 'decompiled'), 'zip', result)
    store.update(job_id, state=state, message=message)
