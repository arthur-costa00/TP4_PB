"""Arthur Costa — PB TP3 — estados de tarefas persistentes (um worker por serviço)."""
import json
import sqlite3
import uuid
from datetime import datetime, timezone

def now(): return datetime.now(timezone.utc).isoformat()

class JobStore:
    def __init__(self,path):
        self.path=path;path.parent.mkdir(parents=True,exist_ok=True)
        with self.connect() as db:
            db.execute("PRAGMA journal_mode=WAL")
            db.execute("CREATE TABLE IF NOT EXISTS jobs (task_id TEXT PRIMARY KEY,scope TEXT,status TEXT,result TEXT,error TEXT,created_at TEXT,updated_at TEXT)")
            db.execute("CREATE UNIQUE INDEX IF NOT EXISTS active_scope ON jobs(scope) WHERE status='pending'")
    def connect(self): return sqlite3.connect(self.path,timeout=10)
    def recover(self):
        with self.connect() as db:
            db.execute("UPDATE jobs SET status='error',error=?,updated_at=? WHERE status='pending'",
                (json.dumps(dict(code="PROCESS_RESTARTED",message="Execução interrompida por reinício; envie novamente.")),now()))
    def create(self,scope):
        task=uuid.uuid4().hex;date=now()
        with self.connect() as db:
            db.execute("INSERT INTO jobs VALUES (?,?, 'pending',NULL,NULL,?,?)",(task,scope,date,date))
        return task
    def finish(self,task,result=None,error=None):
        with self.connect() as db:
            db.execute("UPDATE jobs SET status=?,result=?,error=?,updated_at=? WHERE task_id=?",
                ("error" if error else "done",json.dumps(result,ensure_ascii=False) if result is not None else None,
                 json.dumps(error,ensure_ascii=False) if error else None,now(),task))
    def get(self,task):
        with self.connect() as db:
            db.row_factory=sqlite3.Row
            row=db.execute("SELECT task_id,status,result,error,created_at,updated_at FROM jobs WHERE task_id=?",(task,)).fetchone()
        if row is None:return None
        data=dict(row)
        for field in ("result","error"):
            data[field]=json.loads(data[field]) if data[field] else None
        return data
