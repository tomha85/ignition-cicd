import sys
from pathlib import Path

def validate(path):
    p = Path(path)
    if not p.is_dir() or not (p / 'project.json').exists():
        raise SystemExit('FAIL: authentic Ignition 8.3 source project missing project.json at ' + str(p))
    files = [x for x in p.rglob('*') if x.is_file()]
    if len(files) < 2:
        raise SystemExit('FAIL: project has no real resources')
    for f in files:
        rel = f.relative_to(p)
        if any(x in str(rel).lower() for x in ('password', 'private-key', '.env', 'certificates')):
            raise SystemExit('FAIL: suspected sensitive file ' + str(rel))
    return len(files)

if __name__ == '__main__':
    print('VALID_PROJECT_FILES', validate(sys.argv[1]))
