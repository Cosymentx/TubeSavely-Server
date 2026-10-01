"""Copy Deno from the build environment into the Vercel function bundle."""

from pathlib import Path
import os
import shutil
import subprocess
import sysconfig


def main():
    root = Path(__file__).resolve().parents[1]
    executable = 'deno.exe' if os.name == 'nt' else 'deno'
    candidates = []
    try:
        from deno import find_deno_bin
        candidates.append(Path(find_deno_bin()))
    except (ImportError, FileNotFoundError):
        pass
    candidates.extend([
        root / '_vendor' / 'bin' / executable,
        root / '.venv' / 'bin' / executable,
        Path(sysconfig.get_path('scripts')) / executable,
        Path(sysconfig.get_path('scripts', scheme=sysconfig.get_preferred_scheme('user'))) / executable,
    ])
    if shutil.which('deno'):
        candidates.append(Path(shutil.which('deno')))
    source = next((path.resolve() for path in candidates if path.is_file()), None)
    if source is None:
        raise SystemExit('Deno was not installed during the build. Check requirements.txt and dependency installation.')
    destination = root / 'app' / 'runtime_bin' / executable
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, destination)
    destination.chmod(destination.stat().st_mode | 0o111)
    result = subprocess.run([str(destination), '--version'], check=True, capture_output=True, text=True)
    print('Packaged JavaScript runtime:', result.stdout.splitlines()[0])


if __name__ == '__main__':
    main()
