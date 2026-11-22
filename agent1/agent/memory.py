"""RAG persistente: chunks de Markdown e interações, embeddings e cosseno."""
import hashlib
import json
import math
import os
import sqlite3
from pathlib import Path
from openai import OpenAI

def cosine(a, b):
    if len(a) != len(b):
        raise ValueError("Dimensões de embeddings incompatíveis")
    den = math.sqrt(sum(x*x for x in a) * sum(x*x for x in b))
    return sum(x*y for x, y in zip(a, b)) / den if den else 0.0

class SemanticMemory:
    def __init__(self, path: Path, model: str = "text-embedding-3-small", client=None):
        self.path, self.model = path, model
        embedding_url = os.getenv("EMBEDDING_BASE_URL")
        self.client = client or (
            OpenAI(base_url=embedding_url, api_key="ollama")
            if embedding_url else OpenAI()
        )
        path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as db:
            db.execute("CREATE TABLE IF NOT EXISTS chunks (id TEXT PRIMARY KEY, owner TEXT NOT NULL, source TEXT NOT NULL, text TEXT NOT NULL, model TEXT NOT NULL, vector TEXT NOT NULL)")

    def connect(self):
        return sqlite3.connect(self.path)

    def embed(self, text):
        return self.client.embeddings.create(model=self.model, input=text).data[0].embedding

    def add(self, owner, source, text):
        key = hashlib.sha256((owner + source + text + self.model).encode()).hexdigest()
        with self.connect() as db:
            if db.execute("SELECT 1 FROM chunks WHERE id=?", (key,)).fetchone():
                return key
        vector = self.embed(text)
        with self.connect() as db:
            db.execute("INSERT OR IGNORE INTO chunks VALUES (?,?,?,?,?,?)", (key, owner, source, text, self.model, json.dumps(vector)))
        return key

    def index_guide(self, path):
        for i, chunk in enumerate(path.read_text(encoding="utf-8").split("\n\n")):
            if len(chunk.strip()) > 80:
                self.add("*", f"guia_estudos.md#trecho-{i}", chunk)

    def search(self, owner, query, limit=4, previous_only=False):
        vector = self.embed(query)
        with self.connect() as db:
            rows = db.execute("SELECT id,source,text,vector FROM chunks WHERE model=? AND (owner=? OR owner='*')", (self.model, owner)).fetchall()
        ranked = []
        for key, source, text, stored in rows:
            if previous_only and not source.startswith("interacao:"):
                continue
            score = cosine(vector, json.loads(stored))
            if score >= 0.18:
                ranked.append(dict(id=key, fonte=source, texto=text, similaridade=round(score, 4)))
        return sorted(ranked, key=lambda x: x["similaridade"], reverse=True)[:limit]
