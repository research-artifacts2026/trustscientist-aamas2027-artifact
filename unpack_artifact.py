from pathlib import Path
import hashlib,zipfile
ROOT=Path(__file__).resolve().parent
ARCHIVES={'artifact-code.zip': '09e971a05cad3ec7a9f36eea2894447aeb7d3aca53c52bcf61f1359911e105eb', 'artifact-cbr-inputs.zip': '2b6feca46acb9cccdc302eefd20ae425cf30a4c8a856bdb55a092288bb243287', 'artifact-recorded-evidence.zip': 'ace3e3a44436cd6d89da7c81b25fa0fc5b44292fcad309b2ca40a7d76b21ac2f'}
for name,expected in ARCHIVES.items():
 p=ROOT/name
 assert hashlib.sha256(p.read_bytes()).hexdigest()==expected, "Archive integrity failure: "+name
 with zipfile.ZipFile(p) as z:
  for item in z.infolist():
   target=(ROOT/item.filename).resolve()
   assert target.is_relative_to(ROOT.resolve()) and ".git" not in target.relative_to(ROOT).parts
  z.extractall(ROOT)
print("Artifact unpacked. Linux/Python 3.10+: python test_cbr.py; python run_branch_experiment.py prepare; python run_branch_experiment.py; python validate_branch_results.py")
