from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, model_validator

class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")

class Pedido(StrictModel):
    usuario: str = Field(default="estudante-demo", pattern=r"^[a-zA-Z0-9_-]{1,64}$")
    sessao: str = Field(default="principal", pattern=r"^[a-zA-Z0-9_-]{1,64}$")
    assunto: str = Field(default="Introdução a Python", min_length=1, max_length=200)
    nivel: Literal["iniciante", "intermediario", "avancado"] = "iniciante"
    minutos: int = Field(default=180, gt=0, le=10080)
    dias: int = Field(default=3, gt=0, le=90)
    mensagem: str = Field(default="Crie meu plano de estudos.", max_length=4000)

    @model_validator(mode="after")
    def viavel(self):
        if self.minutos < self.dias:
            raise ValueError("É necessário pelo menos um minuto por dia.")
        return self

class Diagnostico(StrictModel):
    objetivo: str
    subproblemas: list[str] = Field(min_length=2)
    topicos_em_ordem: list[str] = Field(min_length=1)
    criterios_de_sucesso: list[str] = Field(min_length=1)

class Sessao(StrictModel):
    dia: int = Field(gt=0)
    topico: str = Field(min_length=1)
    atividade: str = Field(min_length=1)
    duracao_minutos: int = Field(gt=0)
    recurso_id: str = Field(min_length=1)

class PlanoEstudos(StrictModel):
    assunto: str
    objetivo: str
    sessoes: list[Sessao] = Field(min_length=1)
    tempo_total_planejado_minutos: int = Field(gt=0)
    fontes: list[str] = Field(min_length=1)
    contexto_anterior_utilizado: list[str]
    justificativa_resumida: str

    @model_validator(mode="after")
    def conferir_soma(self):
        if sum(s.duracao_minutos for s in self.sessoes) != self.tempo_total_planejado_minutos:
            raise ValueError("O tempo total deve ser igual à soma das sessões.")
        dias = [s.dia for s in self.sessoes]
        if dias != list(range(1, len(dias) + 1)):
            raise ValueError("Dias devem ser sequenciais, sem repetição.")
        return self
