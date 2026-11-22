import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from fastapi import BackgroundTasks
from fastapi.testclient import TestClient
from agent.api import make_app
from agent.jobs import JobStore
from agent.models import PlanoEstudos

def output():
    return PlanoEstudos(assunto="Python",objetivo="Praticar",sessoes=[dict(dia=1,topico="Variáveis",atividade="Exercícios",duracao_minutos=30,recurso_id="py-01")],tempo_total_planejado_minutos=30,fontes=["data/catalogo.json"],contexto_anterior_utilizado=[],justificativa_resumida="Teste")

class ApiTests(unittest.TestCase):
    def test_background_scheduling_and_pending(self):
        with tempfile.TemporaryDirectory() as tmp:
            app=make_app(tmp,executor=lambda *a,**k:None)
            with TestClient(app) as client, patch.object(BackgroundTasks,"add_task") as add:
                r=client.post("/run",json=dict(usuario="teste",sessao="api",minutos=30,dias=1))
                self.assertEqual(r.status_code,202)
                add.assert_called_once()
                task=r.json()["task_id"]
                self.assertEqual(client.get("/status/"+task).json()["status"],"pending")
                self.assertEqual(client.post("/run",json=dict(usuario="teste",sessao="api",minutos=30,dias=1)).status_code,409)
    def test_done_and_error(self):
        async def ok(*args,**kwargs):return output(),{"erro_validacao":None}
        async def fail(*args,**kwargs):raise ValueError("detalhe interno não deve aparecer")
        for worker,expected in [(ok,"done"),(fail,"error")]:
            with tempfile.TemporaryDirectory() as tmp,TestClient(make_app(tmp,worker)) as client:
                r=client.post("/run",json=dict(usuario="teste",sessao="api",minutos=30,dias=1));task=r.json()["task_id"]
                final=client.get("/status/"+task).json()
                self.assertEqual(final["status"],expected)
                self.assertNotIn("detalhe interno",str(final))
    def test_restart_marks_pending_as_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            store=JobStore(Path(tmp)/"jobs.sqlite");task=store.create("interrupted")
            with TestClient(make_app(tmp)) as client:
                body=client.get("/status/"+task).json()
                self.assertEqual(body["status"],"error")
                self.assertEqual(body["error"]["code"],"PROCESS_RESTARTED")
    def test_404_and_422(self):
        with tempfile.TemporaryDirectory() as tmp,TestClient(make_app(tmp)) as client:
            self.assertEqual(client.get("/status/absent").status_code,404)
            self.assertEqual(client.post("/run",json={"campo_invalido":True}).status_code,422)
