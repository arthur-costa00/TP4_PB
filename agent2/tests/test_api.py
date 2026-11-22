import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from fastapi import BackgroundTasks
from fastapi.testclient import TestClient
from tutor.api import make_app
from tutor.jobs import JobStore
from tutor.models import Correction

def output():
    return Correction(exercicio_id="py-func-01",nota=10,nota_maxima=10,criterios=[dict(criterio_id="resultado",pontos=6,evidencia="8",feedback="Correto"),dict(criterio_id="explicacao",pontos=4,evidencia="4 por 2",feedback="Correto")],pontos_fortes=[],melhorias=[],proximo_passo="Pratique",fonte_rubrica="rubricas.json#py-func-01")

class ApiTests(unittest.TestCase):
    def test_background_scheduling_and_pending(self):
        with tempfile.TemporaryDirectory() as tmp:
            app=make_app(tmp,executor=lambda *a,**k:None)
            with TestClient(app) as client, patch.object(BackgroundTasks,"add_task") as add:
                r=client.post("/run",json=dict(exercicio_id="py-func-01",resposta="8 pois multiplica 4 por 2"))
                self.assertEqual(r.status_code,202)
                add.assert_called_once()
                task=r.json()["task_id"]
                self.assertEqual(client.get("/status/"+task).json()["status"],"pending")
                self.assertEqual(client.get("/status/absent").status_code,404)
    def test_done_and_error(self):
        async def ok(*args,**kwargs):return output(),{"erro_validacao":None}
        async def fail(*args,**kwargs):raise ValueError("detalhe interno não deve aparecer")
        for worker,expected in [(ok,"done"),(fail,"error")]:
            with tempfile.TemporaryDirectory() as tmp,TestClient(make_app(tmp,worker)) as client:
                r=client.post("/run",json=dict(exercicio_id="py-func-01",resposta="8 pois multiplica 4 por 2"));task=r.json()["task_id"]
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
