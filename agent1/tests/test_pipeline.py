import asyncio
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from agents import Agent, Runner, RunConfig, SQLiteSession
from agents.models.interface import Model, ModelResponse
from agents.usage import Usage
from openai.types.responses import ResponseFunctionToolCall, ResponseOutputMessage, ResponseOutputText
from pydantic import ValidationError
from agent.models import Pedido, PlanoEstudos
from agent.pipeline import validate_plan
from agent.tools import buscar_recursos, consultar_catalogo
from agent.memory import SemanticMemory, cosine

PLAN=dict(assunto="Python",objetivo="Praticar",sessoes=[dict(dia=1,topico="Variáveis",atividade="Exercícios",duracao_minutos=30,recurso_id="py-01")],tempo_total_planejado_minutos=30,fontes=["data/catalogo.json"],contexto_anterior_utilizado=[],justificativa_resumida="Uma sessão")

class FakeEmbedding:
    """Somente teste unitário de armazenamento/ranking; não evidência semântica real."""
    embeddings=None
    def __init__(self): self.embeddings=self
    def create(self,model,input):
        return SimpleNamespace(data=[SimpleNamespace(embedding=[1.0,0.0] if "exerc" in input else [0.0,1.0])])

class ScriptedModel(Model):
    def __init__(self): self.seen=[]
    async def get_response(self,system_instructions,input,*args,**kwargs):
        self.seen=input
        if not any(isinstance(x,dict) and x.get("type")=="function_call_output" for x in input):
            item=ResponseFunctionToolCall(type="function_call",name="buscar_recursos",arguments=json.dumps(dict(assunto="Python",nivel="iniciante")),call_id="offline-tool-1")
        else:
            item=ResponseOutputMessage(id="msg-offline",type="message",role="assistant",status="completed",content=[ResponseOutputText(type="output_text",text=json.dumps(PLAN),annotations=[])])
        return ModelResponse(output=[item],usage=Usage(),response_id=None)
    async def stream_response(self,*args,**kwargs):
        raise NotImplementedError
        yield

class Tests(unittest.TestCase):
    def test_input_and_total(self):
        for data in [dict(minutos=0),dict(dias=0),dict(minutos=1,dias=3),dict(usuario="../outro")]:
            with self.assertRaises(ValidationError): Pedido(**data)
        with self.assertRaises(ValidationError): PlanoEstudos(**{**PLAN,"tempo_total_planejado_minutos":31})
    def test_business_contract(self):
        p=PlanoEstudos(**PLAN)
        validate_plan(p,Pedido(minutos=30,dias=1))
        with self.assertRaises(ValueError): validate_plan(p,Pedido(minutos=20,dias=1))
        with self.assertRaises(ValueError): validate_plan(p,Pedido(minutos=30,dias=2))
        bad=p.model_copy(deep=True); bad.sessoes[0].recurso_id="inventado"
        with self.assertRaises(ValueError): validate_plan(bad,Pedido(minutos=30,dias=1))
    def test_catalog(self):
        self.assertEqual(len(consultar_catalogo("Introdução a Python","iniciante")["recursos"]),3)
        self.assertEqual(consultar_catalogo("assunto ausente","iniciante")["recursos"],[])
    def test_persistent_rag_scope(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/"m.sqlite"
            m=SemanticMemory(path,client=FakeEmbedding())
            m.add("ana","interacao:1","Prefiro exercícios")
            m.add("bia","interacao:1","Outros exercícios privados")
            m=SemanticMemory(path,client=FakeEmbedding())
            found=m.search("ana","exercícios",previous_only=True)
            self.assertEqual(len(found),1)
            self.assertEqual(found[0]["texto"],"Prefiro exercícios")
            self.assertEqual(cosine([0,0],[1,0]),0)
            with self.assertRaises(ValueError): cosine([1],[1,2])
    def test_sdk_tool_output_and_session(self):
        async def scenario():
            with tempfile.TemporaryDirectory() as tmp:
                path=str(Path(tmp)/"session.sqlite")
                session=SQLiteSession("ana:1",path)
                agent=Agent(name="offline",model=ScriptedModel(),tools=[buscar_recursos],output_type=PlanoEstudos)
                result=await Runner.run(agent,"Plano Python",session=session,run_config=RunConfig(tracing_disabled=True))
                self.assertIsInstance(result.final_output,PlanoEstudos)
                self.assertTrue(any(i.type=="tool_call_output_item" for i in result.new_items))
                session.close()
                reopened=SQLiteSession("ana:1",path)
                self.assertGreater(len(await reopened.get_items()),2)
                reopened.close()
                new=SQLiteSession("ana:2",path)
                self.assertEqual(await new.get_items(),[])
                new.close()
        asyncio.run(scenario())

if __name__=="__main__": unittest.main()
