"""Find out what kind of game was uploaded and which file(s) can be decompiled."""
import zipfile
from pathlib import Path


def _result(kind, language='csharp', targets=None, message=''):
    return {'type': kind, 'language': language, 'targets': targets or [], 'message': message}


def _has(upload_dir, pattern):
    return any(True for _ in Path(upload_dir).rglob(pattern))


def _managed_dlls(names):
    """Assembly-CSharp*.dll entries in a list of zip entry names (Unity Mono layout)."""
    return [n for n in names if '/Managed/' in '/' + n and Path(n).name.startswith('Assembly-CSharp') and n.lower().endswith('.dll')]


def _order(paths):
    """Main game assembly first, plugin assemblies (firstpass) after it."""
    return sorted(paths, key=lambda p: ('firstpass' in Path(p).name.lower(), Path(p).name))


def detect(upload_dir, work_dir):
    upload_dir, work_dir = Path(upload_dir), Path(work_dir)

    # 1. IL2CPP games have no readable code in the managed DLLs
    if _has(upload_dir, 'GameAssembly.dll') or _has(upload_dir, 'libil2cpp.so') or _has(upload_dir, 'global-metadata.dat'):
        return _result('unity-il2cpp', message='This is a Unity IL2CPP game. Only Unity games built with the Mono '
                       'backend are supported right now (IL2CPP needs a different tool).')

    # 2. Android packages
    for apk in sorted(upload_dir.rglob('*.apk')):
        try:
            with zipfile.ZipFile(apk) as z:
                names = z.namelist()
                if any(n.endswith('libil2cpp.so') or n.endswith('global-metadata.dat') for n in names):
                    return _result('unity-il2cpp', message='This APK is a Unity IL2CPP build, which is not supported yet.')
                managed = _managed_dlls(names)
                if managed:
                    out = work_dir / apk.stem
                    out.mkdir(parents=True, exist_ok=True)
                    targets = []
                    for n in managed:
                        dest = out / Path(n).name
                        dest.write_bytes(z.read(n))
                        targets.append(dest)
                    return _result('unity-apk-mono', targets=_order(targets))
                if 'classes.dex' in names:
                    return _result('android-java', language='java', targets=[apk])
        except zipfile.BadZipFile:
            return _result('unknown', message=f'{apk.name} is not a valid APK file.')
        return _result('unknown', message=f'No code found in {apk.name}.')

    # 3. Java archives
    jars = sorted(upload_dir.rglob('*.jar'))
    if jars:
        return _result('java', language='java', targets=jars[:1])

    # 4. Unity (Mono) assemblies
    unity = sorted(upload_dir.rglob('Assembly-CSharp*.dll'))
    if unity:
        return _result('unity-mono', targets=_order(unity))

    # 5. Any single .NET library
    dlls = sorted(upload_dir.rglob('*.dll'))
    if len(dlls) == 1:
        return _result('dotnet', targets=dlls)

    return _result('unknown', message='Could not find Assembly-CSharp.dll. Upload the file itself, an APK, or a zip '
                   'of the game folder (it contains <Name>_Data/Managed/Assembly-CSharp.dll).')
