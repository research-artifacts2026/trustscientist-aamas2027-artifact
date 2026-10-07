"""Restore and hash-check the complete recorded trajectory artifact."""
from pathlib import Path,PurePosixPath
import hashlib,json,zipfile
root=Path(__file__).resolve().parent
dest=root/'long_trajectory_artifact'
with zipfile.ZipFile(root/'long-trajectory-artifact.zip') as archive:
    files=json.loads(archive.read('manifest.json'))['files']
    for name,entry in files.items():
        rel=PurePosixPath(name)
        if rel.is_absolute() or '..' in rel.parts or '\\' in name: raise ValueError('Invalid path')
        target=dest.joinpath(*rel.parts)
        if not target.resolve().is_relative_to(dest.resolve()): raise ValueError('Outside output')
        data=archive.read('blobs/'+entry['sha256'])
        if len(data)!=entry['bytes'] or hashlib.sha256(data).hexdigest()!=entry['sha256']: raise ValueError('Hash mismatch')
        if target.exists() and target.read_bytes()!=data: raise FileExistsError('Refusing overwrite: '+name)
        target.parent.mkdir(parents=True,exist_ok=True)
        target.write_bytes(data)
print('Restored and verified',len(files),'files in',dest.name)
