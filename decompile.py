import shutil
import subprocess
import zipfile
from pathlib import Path
class UnsupportedGame(Exception):
    pass
def safe_extract(zip_path: Path, dest: Path, max_total=2 * 1024**3):
    """Unzip, but refuse zips that try to write outside dest or are huge."""
    dest = dest.resolve()
    dest.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_path) as z:
        if sum(m.file_size for m in z.infolist()) > max_total:
            raise ValueError("The zip file is too large when unpacked.")
        for m in z.infolist():
            if not (dest / m.filename).resolve().is_relative_to(dest):
                raise ValueError("The zip file contains an unsafe path.")
        z.extractall(dest)
def find_target_dll(upload_dir: Path) -> Path:
    # 1. A Unity (Mono) game's main code library
    hits = list(upload_dir.rglob("Assembly-CSharp.dll"))
    if hits:
        return hits[0]
    # 2. IL2CPP games can't be decompiled with ILSpy
    if list(upload_dir.rglob("GameAssembly.dll")):
        raise UnsupportedGame(
            "This looks like an IL2CPP game, which is not supported yet. "
            "Only Unity games built with the Mono backend work."
        )
    # 3. A single plain .dll uploaded directly (handy for testing)
    dlls = list(upload_dir.rglob("*.dll"))
    if len(dlls) == 1:
        return dlls[0]
    raise UnsupportedGame(
        "Could not find Assembly-CSharp.dll. Upload the game folder as a .zip "
        "(it should contain <GameName>_Data/Managed/Assembly-CSharp.dll)."
    )

def ilspy_path() -> str:
    found = shutil.which("ilspycmd")
    if found:
        return found
    fallback = Path.home() / ".dotnet" / "tools" / "ilspycmd"
    if fallback.exists():
        return str(fallback)
    raise RuntimeError("ilspycmd was not found on this server.")

def decompile(dll: Path, outdir: Path):
    outdir.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [ilspy_path(), "-p", "-o", str(outdir), str(dll)],
        check=True, timeout=900, capture_output=True, text=True,
    )
