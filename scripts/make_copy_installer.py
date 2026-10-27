"""Create a copy/paste transfer file from the previously verified source ZIP.

No public hosting, Git push, or external file-transfer service is involved.
"""
import base64
import hashlib
import io
import tarfile
import textwrap
from pathlib import Path
from zipfile import ZipFile

source = Path('/workspace/artifacts/jakji-joeykorea.zip')
dest = Path('/workspace/artifacts/install_jakji.py')
buffer = io.BytesIO()
with ZipFile(source) as z, tarfile.open(fileobj=buffer, mode='w:xz', preset=6) as archive:
    assert z.testzip() is None
    for name in sorted(z.namelist()):
        path = Path(name)
        assert path.parts[0] == 'jakji'
        assert not any(part in {'.local', '.venv', '.git', '..'} for part in path.parts)
        assert not name.endswith('.sqlite3')
        data = z.read(name)
        item = tarfile.TarInfo(name)
        item.size = len(data)
        item.mode = 0o644
        archive.addfile(item, io.BytesIO(data))
payload = buffer.getvalue()
header = '''#!/usr/bin/env python3
# 작지의나라: ZIP 다운로드 대신 소스 전체를 복사해서 옮기는 설치 파일입니다.
# PythonAnywhere Files에서 /home/joeykorea/install_jakji.py로 저장하고
# Bash 콘솔에서 python3 /home/joeykorea/install_jakji.py 를 실행합니다.
# 내장된 소스의 체크섬을 확인하고 /home/joeykorea/jakji에 설치합니다.
# 기존 jakji 디렉터리가 있으면 덮어쓰지 않습니다. 비밀키/회원 DB는 포함하지 않습니다.
import argparse
import base64
import hashlib
import io
import os
from pathlib import Path, PurePosixPath
import shutil
import subprocess
import sys
import tarfile
import tempfile

'''
body = '''
def main():
    parser = argparse.ArgumentParser(description='Install the jakji source without downloading a ZIP.')
    parser.add_argument('--extract-only', action='store_true', help='Verify/extract source only; skip dependency installation.')
    parser.add_argument('--destination', type=Path, default=Path.home() / 'jakji')
    args = parser.parse_args()
    try:
        payload = base64.b64decode(''.join(PAYLOAD.split()), validate=True)
    except (ValueError, TypeError) as exc:
        raise SystemExit('Copy error: please copy the complete file, from its first line through main().') from exc
    if hashlib.sha256(payload).hexdigest() != EXPECTED_SHA256:
        raise SystemExit('Copy error: checksum mismatch. No files were installed. Copy the complete file again.')
    target = args.destination.expanduser().absolute()
    if target.exists() or target.is_symlink():
        raise SystemExit('The jakji directory already exists. Nothing was overwritten. Ask for update instructions.')
    if not target.parent.is_dir():
        raise SystemExit('The destination parent directory does not exist.')
    staging = Path(tempfile.mkdtemp(prefix='.jakji-transfer-', dir=target.parent))
    try:
        with tarfile.open(fileobj=io.BytesIO(payload), mode='r:xz') as archive:
            members = archive.getmembers()
            for member in members:
                parts = PurePosixPath(member.name).parts
                if not member.isfile() or len(parts) < 2 or parts[0] != 'jakji' or '..' in parts:
                    raise SystemExit('Unsafe source member. Installation stopped.')
            for member in members:
                path = staging.joinpath(*PurePosixPath(member.name).parts)
                path.parent.mkdir(parents=True, exist_ok=True)
                with archive.extractfile(member) as src, path.open('xb') as dst:
                    shutil.copyfileobj(src, dst)
                path.chmod(0o644)
        if target.exists() or target.is_symlink():
            raise SystemExit('The target directory was created by another process; nothing was overwritten.')
        (staging / 'jakji').rename(target)
    finally:
        shutil.rmtree(staging)
    print('Source integrity verified; installed to:', target, flush=True)
    if args.extract_only:
        return 0
    python_bin = shutil.which('python3.12') or sys.executable
    env = os.environ.copy()
    env['PYTHON_BIN'] = python_bin
    env['WEBSITE_HOST'] = 'joeykorea.pythonanywhere.com'
    print('Installing dependencies with:', python_bin, flush=True)
    try:
        subprocess.run(['bash', 'scripts/setup.sh'], cwd=target, env=env, check=True)
    except subprocess.CalledProcessError as exc:
        print('Source was preserved. To retry, run from the jakji directory:')
        print('PYTHON_BIN=' + python_bin + ' WEBSITE_HOST=joeykorea.pythonanywhere.com bash scripts/setup.sh')
        return exc.returncode
    subprocess.run([str(target / '.venv/bin/python'), '--version'], check=True)
    print('INSTALL COMPLETE. Next: configure the operator contact, administrator, and PythonAnywhere Web tab.')
    print('The public website has NOT been enabled by this script.')
    return 0

if __name__ == '__main__':
    sys.exit(main())
'''
encoded = '\n'.join(textwrap.wrap(base64.b64encode(payload).decode('ascii'), 96))
dest.write_text(header + f'EXPECTED_SHA256 = "{hashlib.sha256(payload).hexdigest()}"\nPAYLOAD = """\n' + encoded + '\n"""\n' + body)
dest.chmod(0o644)
compile(dest.read_text(), str(dest), 'exec')
print('Prepared copyable Python installer:', dest)
print('Size:', dest.stat().st_size, 'bytes. Source files:', len(z.namelist()))
