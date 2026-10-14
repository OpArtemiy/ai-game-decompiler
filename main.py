import os
import re
import shutil
import subprocess
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed

from pathlib import Path


from fastapi import BackgroundTasks, FastAPI, HTTPException, UploadFile

from fastapi.responses import FileResponse

from fastapi.staticfiles import StaticFiles


from ai import clean_code, make_overview

from decompile import UnsupportedGame, decompile, find_target_dll, safe_extract


BASE = Path(__file__).resolve().parent

JOBS = BASE / "jobs"

JOBS.mkdir(exist_ok=True)


MAX_UPLOAD = 300 * 1024 * 1024                    # 300 MB

MAX_FILES = int(os.environ.get("MAX_FILES", "20"))  # cost cap while testing

MAX_CHARS = 15000                                  # skip files bigger than this

MIN_LINES = 8                                      # skip tiny files

WORKERS = 1                                        # parallel AI calls


app = FastAPI()

STATUS = {}  # job_id -> {"state": ..., "message": ...}

def set_status(job_id, state, message):
    STATUS[job_id] = {"state": state, "message": message}
def process(job_id: str):
    job = JOBS / job_id
    try:
        set_status(job_id, "running", "Unpacking upload...")
        up = job / "upload"
        for z in list(up.glob("*.zip")):
            safe_extract(z, up / "unzipped")

        set_status(job_id, "running", "Finding the game code...")
        dll = find_target_dll(up)


        set_status(job_id, "running", f"Decompiling {dll.name}...")
        raw = job / "raw"
        decompile(dll, raw)

        candidates = [
            f for f in sorted(raw.rglob("*.cs"))
            if "Properties" not in f.relative_to(raw).parts
            and len(f.read_text(errors="ignore").splitlines()) >= MIN_LINES
        ]
        chosen = candidates[:MAX_FILES]
        if not chosen:
            raise UnsupportedGame("No source files were produced from this file.")

        def clean_one(f: Path):
            code = f.read_text(errors="ignore")
            if len(code) > MAX_CHARS:
                return f, "skipped (file too large)"
            try:
                f.write_text(clean_code(code))
                return f, "cleaned"
            except Exception as e:
                return f, f"unchanged ({e})"


        results = []
        with ThreadPoolExecutor(max_workers=WORKERS) as pool:
            futures = [pool.submit(clean_one, f) for f in chosen]
            for i, fut in enumerate(as_completed(futures), 1):
                results.append(fut.result())
                set_status(job_id, "running", f"AI cleanup {i}/{len(chosen)}")

        set_status(job_id, "running", "Writing project overview...")
        parts = []
        for f in chosen:
            decl = [
                ln.strip() for ln in f.read_text(errors="ignore").splitlines()
                if re.search(r"\b(class|interface|enum|struct)\b", ln)
                or re.search(r"\b(public|protected|internal)\b.*\(", ln)
            ]
            parts.append(f"## {f.name}\n" + "\n".join(decl[:25]))
        summary = "\n\n".join(parts)[:40000]
        (raw / "OVERVIEW.md").write_text(make_overview(summary))

        notes = "\n".join(f"{f.name}: {r}" for f, r in sorted(results, key=lambda x: x[0].name))
        (raw / "NOTES.txt").write_text("AI cleanup results\n\n" + notes + "\n")

        shutil.make_archive(str(job / "result"), "zip", raw)
        cleaned = sum(1 for _, r in results if r == "cleaned")
        set_status(job_id, "done", f"Done. {cleaned} of {len(chosen)} files cleaned by AI.")


    except UnsupportedGame as e:
        set_status(job_id, "error", str(e))
    except subprocess.CalledProcessError as e:
        set_status(job_id, "error", f"Decompiler failed: {(e.stderr or '')[:300]}")
    except Exception as e:
        set_status(job_id, "error", f"{type(e).__name__}: {e}")


@app.post("/upload")
async def upload(file: UploadFile, bg: BackgroundTasks):
    name = Path(file.filename or "").name
    if not name.lower().endswith((".zip", ".dll")):
        raise HTTPException(400, "Upload a .zip of the game folder or a .dll file.")

    job_id = uuid.uuid4().hex
    up = JOBS / job_id / "upload"
    up.mkdir(parents=True)
    size, too_big = 0, False
    with open(up / name, "wb") as out:
        while chunk := await file.read(1024 * 1024):
            size += len(chunk)
            if size > MAX_UPLOAD:
                too_big = True
                break
            out.write(chunk)
    if too_big:
        shutil.rmtree(JOBS / job_id, ignore_errors=True)
        raise HTTPException(413, "File is too large (limit 300 MB).")


    set_status(job_id, "queued", "Queued...")
    bg.add_task(process, job_id)
    return {"job_id": job_id}


@app.get("/status/{job_id}")
def status(job_id: str):
    return STATUS.get(job_id, {"state": "unknown", "message": "Unknown job"})


@app.get("/download/{job_id}")
def download(job_id: str):
    if not re.fullmatch(r"[0-9a-f]{32}", job_id):
        raise HTTPException(404)
    z = JOBS / job_id / "result.zip"
    if not z.exists():
        raise HTTPException(404, "Result not ready")
    return FileResponse(z, filename="decompiled.zip")



# Must be last: serves the web page
app.mount("/", StaticFiles(directory=BASE / "static", html=True), name="static")
