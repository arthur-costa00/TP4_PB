"""Arthur Costa — PB TP3 — API independente do agente 1."""
import asyncio
import json
import os
import sqlite3
import uuid
from contextlib import asynccontextmanager
from pathlib import Path
from dotenv import load_dotenv
from fastapi import BackgroundTasks, FastAPI, HTTPException, Response
from .models import Pedido
from .pipeline import execute, ROOT
from .jobs import JobStore
from .api_models import Accepted, TaskStatus

load_dotenv(ROOT/".env")

def make_app(state_dir=None,executor=None):
    state=Path(state_dir or os.getenv("AGENT_STATE_DIR",ROOT/"runtime"))
    if not state.is_absolute(): state=ROOT/state
    store=JobStore(state/"jobs.sqlite")
    run_pipeline=executor or execute

    @asynccontextmanager
    async def lifespan(app):
        store.recover()
        yield

    app=FastAPI(title="Arthur Costa — PB TP3 — Agente 1",version="0.3.0",lifespan=lifespan)
    app.state.store=store

    def work(task_id,pedido):
        # Starlette executa esta função separadamente após enviar o HTTP 202.
        try:
            if executor is None and not os.getenv("OPENAI_API_KEY"):
                raise RuntimeError("Configuração ausente")
            async def process():
                return await run_pipeline(pedido,state_dir=state)
            timeout = int(os.getenv("AGENT_TASK_TIMEOUT_SECONDS", "120"))
            if timeout <= 0:
                raise ValueError("AGENT_TASK_TIMEOUT_SECONDS deve ser positivo")
            result,evidence=asyncio.run(asyncio.wait_for(process(),timeout=timeout))
            evidence_dir=state/"evidence";evidence_dir.mkdir(exist_ok=True)
            (evidence_dir/f"{task_id}.json").write_text(json.dumps(evidence,ensure_ascii=False,indent=2),encoding="utf-8")
            if evidence.get("erro_validacao"): raise ValueError(evidence["erro_validacao"])
            store.finish(task_id,result=result.model_dump())
        except Exception as exc:
            code="VALIDATION_ERROR" if isinstance(exc,ValueError) else "TIMEOUT" if isinstance(exc,TimeoutError) else "EXECUTION_ERROR"
            store.finish(task_id,error=dict(code=code,message="A execução não foi concluída. Verifique o pedido e a configuração do serviço."))

    @app.post("/run",status_code=202,response_model=Accepted,summary="Solicitar execução")
    def run(pedido:Pedido,background_tasks:BackgroundTasks,response:Response):
        try:task_id=store.create(f"{pedido.usuario}:{pedido.sessao}")
        except sqlite3.IntegrityError: raise HTTPException(409,"Já há uma tarefa pendente para esta sessão") from None
        background_tasks.add_task(work,task_id,pedido)
        response.headers["Location"]=f"/status/{task_id}"
        return Accepted(task_id=task_id,status_url=f"/status/{task_id}")

    @app.get("/status/{task_id}",response_model=TaskStatus,summary="Consultar andamento")
    def status(task_id:str):
        data=store.get(task_id)
        if data is None:raise HTTPException(404,"Tarefa não encontrada")
        return data

    return app

app=make_app()
