"""Arthur Costa — PB TP3 — contratos do corretor."""
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, model_validator

class StrictModel(BaseModel):
    model_config=ConfigDict(extra="forbid")

class Submission(StrictModel):
    usuario: str = Field(default="aluno-demo",pattern=r"^[a-zA-Z0-9_-]{1,64}$")
    exercicio_id: str = Field(min_length=1,max_length=80)
    resposta: str = Field(min_length=1,max_length=6000)

class CriterionResult(StrictModel):
    criterio_id: str
    pontos: int = Field(ge=0)
    evidencia: str = Field(min_length=1)
    feedback: str = Field(min_length=1)

class Correction(StrictModel):
    exercicio_id: str
    nota: int = Field(ge=0,le=10)
    nota_maxima: Literal[10]
    criterios: list[CriterionResult] = Field(min_length=1)
    pontos_fortes: list[str]
    melhorias: list[str]
    proximo_passo: str
    fonte_rubrica: str

    @model_validator(mode="after")
    def total(self):
        if sum(c.pontos for c in self.criterios)!=self.nota:
            raise ValueError("Nota difere da soma dos critérios")
        ids=[c.criterio_id for c in self.criterios]
        if len(ids)!=len(set(ids)):
            raise ValueError("Critério duplicado")
        return self
