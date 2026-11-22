import asyncio
import os
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
from agent.models import Pedido, Diagnostico, PlanoEstudos
from agent.pipeline import execute

class RetryTest(unittest.TestCase):
    def test_contract_correction_is_bounded(self):
        async def scenario():
            good=PlanoEstudos(assunto="Python",objetivo="Praticar",sessoes=[dict(dia=1,topico="Variáveis",atividade="Exercícios",duracao_minutos=30,recurso_id="py-01")],tempo_total_planejado_minutos=30,fontes=["data/catalogo.json"],contexto_anterior_utilizado=[],justificativa_resumida="Teste")
            bad=good.model_copy(update={"fontes":["fonte-inventada"]})
            diag=Diagnostico(objetivo="Praticar",subproblemas=["Ler","Praticar"],topicos_em_ordem=["Variáveis"],criterios_de_sucesso=["Executar código"])
            tool=SimpleNamespace(type="tool_call_output_item",to_input_item=lambda:dict(type="function_call_output",call_id="teste",output="{}"))
            def result(p): return SimpleNamespace(final_output=p,new_items=[tool])
            for corrected in (True,False):
                runner=AsyncMock(side_effect=[SimpleNamespace(final_output=diag),result(bad),result(good if corrected else bad)])
                with (
                    tempfile.TemporaryDirectory() as tmp,
                    patch.dict(os.environ, {"AGENT_MODEL_STREAMING": "0"}),
                    patch("agent.pipeline.SemanticMemory") as Memory,
                    patch("agent.pipeline.Runner.run", runner),
                ):
                    Memory.return_value.search.return_value=[]
                    _,e=await execute(Pedido(minutos=30,dias=1),state_dir=tmp)
                    self.assertEqual(runner.await_count,3)
                    self.assertEqual(len(e["tentativas"]),2)
                    self.assertIsNotNone(e["tentativas"][0]["erro_validacao"])
                    self.assertEqual(e["erro_validacao"] is None,corrected)
                    self.assertEqual(Memory.return_value.add.call_count,1 if corrected else 0)
        asyncio.run(scenario())
