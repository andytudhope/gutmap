"""Update Songflight's app code from a bundle; preserve the live database and secrets."""
import argparse,shutil,subprocess,tarfile,tempfile,time
from pathlib import Path

p=argparse.ArgumentParser();p.add_argument('archive',nargs='?',default='/tmp/gut-atlas-deploy.tar.gz');args=p.parse_args()
root=Path('/opt/gut-atlas')
if not (root/'hub/app.py').exists():raise SystemExit('This updater expects the existing Songflight deployment')
backup=Path('/var/backups/gut-atlas')/time.strftime('%Y%m%d-%H%M%S',time.gmtime())
backup.mkdir(parents=True)
with tempfile.TemporaryDirectory() as tmp:
    stage=Path(tmp)
    with tarfile.open(args.archive) as archive:archive.extractall(stage,filter='data')
    if not (stage/'hub/app.py').exists():raise SystemExit('Bundle is missing the app')
    for name in ('hub','content','static','scripts','tests','deploy'):
        if (root/name).exists():shutil.copytree(root/name,backup/name,ignore=shutil.ignore_patterns('__pycache__'))
    db=Path('/var/lib/gut-atlas/atlas.sqlite')
    import sqlite3
    source=sqlite3.connect(db);dest=sqlite3.connect(backup/'atlas.sqlite');source.backup(dest);source.close();dest.close()
    subprocess.run(['systemctl','stop','gut-atlas'],check=True)
    try:
        for name in ('hub','content','static','scripts','tests','deploy'):
            if (stage/name).exists():
                if (root/name).exists():shutil.rmtree(root/name)
                shutil.copytree(stage/name,root/name)
        for name in ('README.md','CONTRIBUTING.md','LICENSE'):
            if (stage/name).exists():shutil.copy2(stage/name,root/name)
        if (root/'docs').exists():shutil.rmtree(root/'docs')
    finally:subprocess.run(['systemctl','start','gut-atlas'],check=True)
print('Updated code; database, review history and credentials preserved. Backup:',backup)
