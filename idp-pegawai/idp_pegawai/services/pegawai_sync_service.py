import hashlib
from datetime import datetime

def row_hash(p):
    ou = getattr(p, "primary_org_unit", None)
    parts = [
        str(getattr(p, "uuid", "")),
        str(getattr(p, "nip", "")),
        str(getattr(p, "nama_lengkap", "")),
        str(getattr(p, "email_google", "") or ""),
        str(getattr(p, "email_dinas", "") or ""),
        str(getattr(ou, "code", "") or "") if ou else "",
    ]
    return hashlib.sha256("|".join(parts).encode()).hexdigest()

def snapshot_hash(rows):
    hashes = sorted(row_hash(r) for r in rows)
    return hashlib.sha256("|".join(hashes).encode()).hexdigest() if hashes else hashlib.sha256(b"").hexdigest()

class PegawaiSyncService:
    def __init__(self, repository):
        self.repository = repository

    def snapshot(self, *, updated_since=None, page=1, per_page=100):
        all_rows = self.repository.list_active_snapshot_scope()
        # filter updated_since
        if updated_since:
            try:
                dt = datetime.fromisoformat(updated_since.replace("Z","+00:00"))
                all_rows = [r for r in all_rows if getattr(r,"updated_at",None) and r.updated_at >= dt]
            except Exception:
                all_rows = []
        all_rows = sorted(all_rows, key=lambda x: str(getattr(x,"uuid","")))
        total = len(all_rows)
        snap_hash = snapshot_hash(all_rows)
        # pagination
        page = max(1,int(page))
        per_page = min(500,max(1,int(per_page)))
        start = (page-1)*per_page
        page_rows = all_rows[start:start+per_page]
        data=[]
        for p in page_rows:
            ou = getattr(p,"primary_org_unit",None)
            data.append({
                "uuid": str(getattr(p,"uuid","")),
                "nama": getattr(p,"nama_lengkap",""),
                "nip": getattr(p,"nip",""),
                "email_google": getattr(p,"email_google",None),
                "email_dinas": getattr(p,"email_dinas",None),
                "org_units": [{"code": getattr(ou,"code",""), "name": getattr(ou,"name",""), "path": getattr(ou,"path","")}] if ou else [],
                "updated_at": getattr(p,"updated_at",None).isoformat() if getattr(p,"updated_at",None) else None,
            })
        return {"data": data, "meta": {"total": total, "page": page, "per_page": per_page, "snapshot_hash": snap_hash, "generated_at": datetime.utcnow().isoformat()+"Z", "contract_version": "pegawai-sync.v1"}}
