"""Lab packager: do not fabricate an Ignition project export."""
import hashlib
import json
from pathlib import Path
import zipfile

ROOT = Path(__file__).resolve().parents[1]
EXPORT = ROOT / 'exports' / 'ManufacturingSCADA.zip'
OUT = ROOT / 'out'

def validate():
    manifest = json.loads((ROOT / 'manifests/release.json').read_text())
    assert manifest['production_approved'] is False
    assert manifest['project_export'] == 'exports/ManufacturingSCADA.zip'
    if not EXPORT.exists():
        return False
    with zipfile.ZipFile(EXPORT) as z:
        names = z.namelist()
        assert names, 'Empty project export'
        for name in names:
            parts = Path(name).parts
            assert not name.startswith('/') and '..' not in parts, 'Unsafe zip entry'
        bad = [n for n in names if any(word in n.lower() for word in ('secret','password','private-key','.env'))]
        assert not bad, 'Possible sensitive content in export: ' + str(bad[:5])
    return True

def main():
    real_export = validate()
    OUT.mkdir(exist_ok=True)
    if not real_export:
        print('NO_REAL_PROJECT_EXPORT: release not built. Export a real Ignition project first.')
        return
    package = OUT / 'ManufacturingSCADA-LAB-0.1.0-release.zip'
    paths = [EXPORT, ROOT / 'manifests/release.json', ROOT / 'README.md']
    checksums = '\n'.join(hashlib.sha256(p.read_bytes()).hexdigest() + '  ' + str(p.relative_to(ROOT)) for p in paths) + '\n'
    with zipfile.ZipFile(package, 'w', zipfile.ZIP_DEFLATED) as z:
        for p in paths:
            z.write(p, p.relative_to(ROOT).as_posix())
        z.writestr('SHA256SUMS.txt', checksums)
    print('RELEASE_CREATED:', package)
    print('WARNING: Gateway runtime and EAM transfer NOT tested.')

if __name__ == '__main__':
    main()
