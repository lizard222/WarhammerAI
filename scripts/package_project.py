"""Build a portable archive; assert real credentials are absent from every member."""
import hashlib
import json
import zipfile
from pathlib import Path
from check_cloudflare import settings

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT.parent / 'Результат'
SKIP_DIRS = {'.venv', 'venv', '__pycache__', '.git', 'node_modules', '.wrangler'}


def project_files():
    for path in sorted(ROOT.rglob('*')):
        if not path.is_file():
            continue
        relative = path.relative_to(ROOT)
        if any(part in SKIP_DIRS for part in relative.parts):
            continue
        if path.name == '.env' or (path.name.startswith('.env.') and path.name != '.env.example'):
            continue
        if path.name in {'db.sqlite3', 'db.sqlite3-journal'} or path.suffix in {'.pyc', '.pyo', '.log'}:
            continue
        if path.name.startswith('report_contact_') or path.name.startswith('report_preview_'):
            continue
        yield path, relative


def main():
    OUT.mkdir(exist_ok=True)
    path = OUT / 'WarhammerAI_проект.zip'
    values = settings()
    secrets = [values[k].encode() for k in ['CLOUDFLARE_API_TOKEN', 'RECOMMENDATIONS_API_KEY'] if values.get(k)]
    count = 0
    with zipfile.ZipFile(path, 'w', zipfile.ZIP_DEFLATED, compresslevel=8) as archive:
        for source, relative in project_files():
            data = source.read_bytes()
            assert all(secret not in data for secret in secrets), 'Secret detected in ' + str(relative)
            archive.writestr('WarhammerAI/' + relative.as_posix(), data)
            count += 1
    with zipfile.ZipFile(path) as archive:
        assert archive.testzip() is None
        assert not any(n.endswith('/.env') or '/.venv/' in n or n.endswith('/db.sqlite3') for n in archive.namelist())
    manifest = {'archive': path.name, 'files': count, 'bytes': path.stat().st_size,
                'sha256': hashlib.sha256(path.read_bytes()).hexdigest(), 'credentials_excluded': True,
                'database_excluded': True, 'environment_excluded': True}
    (OUT / 'Комплект.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf-8')
    print('Archive ready:', count, 'files;', path.stat().st_size, 'bytes; secret scan passed')


if __name__ == '__main__':
    main()
