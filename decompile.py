"""Safe unzip and wrappers around the decompiler tools (ILSpy for C#, jadx for Java/Android)."""
import shutil
import subprocess
import zipfile
from pathlib import Path


class ToolMissing(Exception):
    pass


def safe_extract(zip_path, dest, max_total=3 * 1024 ** 3):
    """Unzip, but refuse zips that write outside dest or are huge when unpacked."""
    dest = Path(dest).resolve()
    dest.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_path) as z:
        if sum(m.file_size for m in z.infolist()) > max_total:
            raise ValueError('The zip is too large when unpacked.')
        for m in z.infolist():
            if not (dest / m.filename).resolve().is_relative_to(dest):
                raise ValueError('The zip contains an unsafe path.')
        z.extractall(dest)


def ilspy(src, outdir):
    tool = shutil.which('ilspycmd') or str(Path.home() / '.dotnet' / 'tools' / 'ilspycmd')
    if not Path(tool).exists():
        raise ToolMissing('ilspycmd is not installed on the server.')
    Path(outdir).mkdir(parents=True, exist_ok=True)
    subprocess.run([tool, '-p', '-o', str(outdir), str(src)], check=True, timeout=900, capture_output=True, text=True)


def jadx(src, outdir):
    tool = shutil.which('jadx') or '/opt/jadx/bin/jadx'
    if not Path(tool).exists():
        raise ToolMissing('jadx is not installed on the server (needed for Java and Android apps). See the setup guide.')
    Path(outdir).mkdir(parents=True, exist_ok=True)
    res = subprocess.run([tool, '--no-res', '-d', str(outdir), str(src)], timeout=1800, capture_output=True, text=True)
    # jadx exits with an error code when a few classes fail; that is fine if it produced sources
    if res.returncode != 0 and not any(Path(outdir).rglob('*.java')):
        raise RuntimeError('jadx failed: ' + (res.stderr or res.stdout)[-300:])


def decompile_target(src, outdir, language):
    (ilspy if language == 'csharp' else jadx)(src, outdir)
