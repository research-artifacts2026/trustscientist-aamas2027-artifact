"""Counterfactual branch revalidation with persistent, content-bound receipts.
Linux single-writer store; no rollback of external jobs or unregistered effects.
"""
from pathlib import Path
import copy, hashlib, inspect, json, os, uuid, fcntl
from contextlib import contextmanager

ACTIONS = {"proceed", "refine", "pivot"}
def canonical(x): return json.dumps(x,sort_keys=True,separators=(",",":"),ensure_ascii=False)
def digest(x): return hashlib.sha256(x if isinstance(x,bytes) else canonical(x).encode()).hexdigest()
def atomic(path,value):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    tmp=path.with_name(path.name+"."+uuid.uuid4().hex+".tmp")
    with tmp.open("w") as f:
        f.write(json.dumps(value,indent=2));f.flush();os.fsync(f.fileno())
    os.replace(tmp,path)
def safe(root,relative):
    p=Path(relative)
    if p.is_absolute() or ".." in p.parts: raise ValueError("relative in-workspace path required")
    target=(root/p).resolve()
    if not target.is_relative_to(root.resolve()): raise ValueError("path escapes workspace")
    return target
def file_hash(root,relative):
    p=safe(root,relative)
    return digest(p.read_bytes()) if p.is_file() else None

def requirements_action(verdict,retry_count,max_retries):
    """Exact branch rule extracted from the existing Stage-15 requirements gate."""
    return "refine" if verdict=="reject" and retry_count<max_retries else "proceed"

def version_contract_policy(root,bindings,context):
    """Controlled version-contract adapter, not a scientific truth predicate."""
    passed=context["base_pass"] and all(
        file_hash(root,p)==context["expected"][p] for p in bindings)
    return requirements_action("accept" if passed else "reject",
                               context["retry_count"],context["max_retries"])

def verdict_policy(root,bindings,context):
    """Replay Stage-15 branch routing after its judge verdict has been refreshed."""
    value=json.loads(safe(root,bindings[0]).read_text())
    verdict=value.get("verdict")
    if verdict not in {"proceed","partial","reject"}: raise ValueError("unknown judge verdict")
    return requirements_action(verdict,context["retry_count"],context["max_retries"])

class Store:
    def __init__(self,root,policies):
        self.root=Path(root).resolve();self.home=self.root/".cbr"
        self.home.mkdir(parents=True,exist_ok=True)
        self.policies=policies
        self.state_path=self.home/"state.json"
    @contextmanager
    def locked(self):
        with (self.home/"lock").open("a") as lock:
            fcntl.flock(lock,fcntl.LOCK_EX)
            try: yield
            finally: fcntl.flock(lock,fcntl.LOCK_UN)
    def state(self):
        if self.state_path.exists():return json.loads(self.state_path.read_text())
        return {"schema":"trustscientist.cbr.v1","active":[],"receipts":{},
                "events":[],"generation":0,"blocked":False}
    def fingerprint(self,name):
        fn=self.policies[name]
        return digest({"name":name,"module":Path(inspect.getfile(fn)).read_text()})
    def receipt(self,rid):
        p=self.home/"receipts"/(rid+".json")
        r=json.loads(p.read_text())
        if digest(r)!=rid:raise ValueError("tampered receipt")
        return r
    def evaluate(self,r):
        if r["policy"] not in self.policies:raise ValueError("unregistered replay policy")
        if self.fingerprint(r["policy"])!=r["policy_hash"]:raise ValueError("policy version changed")
        action=self.policies[r["policy"]](self.root,r["bindings"],copy.deepcopy(r["context"]))
        if action not in ACTIONS:raise ValueError("unknown decision")
        return action
    def save_receipt(self,r):
        rid=digest(r);p=self.home/"receipts"/(rid+".json")
        if not p.exists():atomic(p,r)
        return rid
    def record(self,policy,bindings,context,old_action,outputs=(),checkpoint_before=None):
        with self.locked():
            s=self.state()
            if s["blocked"]:raise RuntimeError("blocked history requires resolution")
            bindings=sorted(set(bindings))
            for p in list(bindings)+list(outputs):safe(self.root,p)
            witnesses={p:file_hash(self.root,p) for p in bindings}
            if any(v is None for v in witnesses.values()):raise ValueError("missing initial witness")
            # Binding completeness is the caller's obligation, not inferred here.
            for p,h in witnesses.items():
                blob=self.home/"witnesses"/h
                if not blob.exists():
                    blob.parent.mkdir(parents=True,exist_ok=True);blob.write_bytes(safe(self.root,p).read_bytes())
            r={"policy":policy,"policy_hash":self.fingerprint(policy),
               "bindings":bindings,"context":copy.deepcopy(context),"witnesses":witnesses,
               "old_action":old_action,"parent":s["active"][-1] if s["active"] else None,
               "sequence":len(s["events"]),"outputs":list(outputs),
               "checkpoint_before":checkpoint_before or {}}
            if self.evaluate(r)!=old_action:raise ValueError("receipt does not reproduce original action")
            rid=self.save_receipt(r)
            s["active"].append(rid);s["receipts"][rid]={"status":"valid","certificate":rid}
            s["events"].append({"type":"decision","receipt":rid})
            atomic(self.state_path,s);return rid
    def _finish_pending(self,s):
        plan=s.get("pending_rollback")
        if not plan:return s
        for relative in plan["outputs"]:
            source=safe(self.root,relative)
            destination=safe(self.home/"quarantine"/plan["id"],relative)
            destination.parent.mkdir(parents=True,exist_ok=True)
            if source.exists():
                if destination.exists():raise RuntimeError("rollback destination collision")
                os.rename(source,destination)
        atomic(self.root/"checkpoint.json",plan["checkpoint"])
        s["events"].append({"type":"rollback_applied","plan":plan})
        s["pending_rollback"]=None;s["blocked"]=False
        atomic(self.state_path,s);return s
    def revalidate(self,mode="cbr",budget=None):
        if mode not in {"cbr","full","tracker","none"}:raise ValueError(mode)
        with self.locked():
            s=self._finish_pending(self.state())
            active=list(s["active"]);receipts=[self.receipt(s["receipts"][x]["certificate"]) for x in active]
            # Read once per registered file; changed-file notifications are not trusted.
            observed={p:file_hash(self.root,p) for r in receipts for p in r["bindings"]}
            changed={p for r in receipts for p in r["bindings"] if observed[p]!=r["witnesses"][p]}
            affected=[i for i,r in enumerate(receipts) if changed.intersection(r["bindings"])
                      or r["policy"] not in self.policies
                      or self.fingerprint(r["policy"])!=r["policy_hash"]]
            selected=list(range(len(active))) if mode=="full" and affected else affected
            report={"mode":mode,"changed":sorted(changed),"affected":affected,
                    "replayed":[],"flips":[],"rollback_index":None,"blocked":False,
                    "witness_files_read":len(observed)}
            if mode=="none":return report
            if mode=="tracker":
                for i in affected:s["receipts"][active[i]]["status"]="stale"
                report["blocked"]=bool(affected);s["blocked"]=bool(affected)
                s["events"].append({"type":"dependency_invalidation","report":report})
                atomic(self.state_path,s);return report
            refresh=[]
            for i in selected:
                if budget is not None and len(report["replayed"])>=budget:
                    report["blocked"]=True;report["reason"]="replay_budget_exhausted";break
                r=receipts[i]
                try:new_action=self.evaluate(r)
                except Exception as exc:
                    report["blocked"]=True;report["reason"]=type(exc).__name__+": "+str(exc);break
                report["replayed"].append({"index":i,"old":r["old_action"],"new":new_action})
                if new_action!=r["old_action"]:
                    report["flips"].append(i);report["rollback_index"]=i;break
                refresh.append(i)
            if report["blocked"]:
                s["blocked"]=True
                for i in affected:s["receipts"][active[i]]["status"]="stale"
            elif report["rollback_index"] is not None:
                i=report["rollback_index"]
                invalidated=active[i:]
                outputs=sorted({p for r in receipts[i:] for p in r["outputs"]})
                # Refuse overlapping output paths; replay evidence must remain outside outputs.
                for a in outputs:
                    for b in outputs:
                        if a!=b and Path(a) in Path(b).parents:raise ValueError("overlapping outputs")
                    if any(Path(a)==Path(p) or Path(a) in Path(p).parents for r in receipts for p in r["bindings"]):
                        raise ValueError("rollback output contains evidence")
                for rid in invalidated:s["receipts"][rid]["status"]="invalidated_branch"
                s["active"]=active[:i];s["generation"]+=1;s["blocked"]=True
                checkpoint=dict(receipts[i]["checkpoint_before"])
                checkpoint.update({"cbr_rollback_receipt":active[i],"cbr_generation":s["generation"]})
                s["pending_rollback"]={"id":uuid.uuid4().hex,"outputs":outputs,"checkpoint":checkpoint,
                                       "earliest_receipt":active[i],"invalidated":invalidated}
                report["invalidated"]=invalidated
            else:s["blocked"]=False
            if not report["blocked"]:
                for i in refresh:
                    r=copy.deepcopy(receipts[i]);r["witnesses"]={p:observed[p] for p in r["bindings"]}
                    r["supersedes"]=active[i]
                    newrid=self.save_receipt(r)
                    # Preserve decision identity; store new version certificate as its attestation.
                    s["receipts"][active[i]]["certificate"]=newrid
                    # Future change detection uses current attestation, without rewriting history.
            s["events"].append({"type":"revalidation","report":report})
            atomic(self.state_path,s)
            if s.get("pending_rollback"):self._finish_pending(s)
            return report

def snapshot_requirements_decision(run_dir,verdict,retry_before,max_retries,action):
    root=Path(run_dir);binding=".cbr_inputs/verdict_"+uuid.uuid4().hex+".json"
    atomic(safe(root,binding),verdict)
    outputs=[p.name for p in root.glob("stage-*") if p.name[6:].isdigit() and int(p.name[6:])>=15]
    # Future downstream stage directories are also registered.
    outputs=sorted(set(outputs)|{f"stage-{i:02d}" for i in range(15,31)})
    store=Store(root,{"stage15_requirements":verdict_policy})
    return store.record("stage15_requirements",[binding],
        {"retry_count":retry_before,"max_retries":max_retries},action,outputs,
        {"last_completed_stage":14,"last_completed_name":"RESULT_ANALYSIS","run_id":root.name})
