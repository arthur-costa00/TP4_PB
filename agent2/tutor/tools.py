import json
from pathlib import Path
from agents import function_tool
ROOT=Path(__file__).resolve().parents[1]

def lookup(exercicio_id: str) -> dict:
    rubricas=json.loads((ROOT/"data/rubricas.json").read_text(encoding="utf-8"))
    for rubrica in rubricas:
        if rubrica["id"]==exercicio_id:
            return {"fonte":f"rubricas.json#{exercicio_id}","rubrica":rubrica}
    raise ValueError("Exercício não cadastrado")

@function_tool
def consultar_rubrica(exercicio_id: str) -> str:
    """Consulta enunciado, gabarito e critérios de pontuação no catálogo local.

    Args:
        exercicio_id: Identificador do exercício que o aluno respondeu.
    """
    return json.dumps(lookup(exercicio_id),ensure_ascii=False)
