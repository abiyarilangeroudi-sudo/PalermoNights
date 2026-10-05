"""Stage only application Python sources; never package local environments or tests."""
from pathlib import Path
import shutil
root=Path(__file__).resolve().parents[1]
target=root/'.worker-build'
target.mkdir(exist_ok=True)
shutil.copy2(root/'worker.py',target/'worker.py')
if (target/'app').exists(): shutil.rmtree(target/'app')
shutil.copytree(root/'app',target/'app',ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
