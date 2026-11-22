import json
from pathlib import Path
from agents import function_tool

ROOT = Path(__file__).resolve().parents[1]

def consultar_catalogo(assunto: str, nivel: str) -> dict:
    dados = json.loads((ROOT / "data/catalogo.json").read_text(encoding="utf-8"))
    recursos = [r for r in dados if r["assunto"].casefold() in assunto.casefold() and r["nivel"] == nivel]
    return {"fonte": "data/catalogo.json", "recursos": recursos,
            "aviso": "" if recursos else "Assunto/nível sem recursos cadastrados; não invente IDs."}

@function_tool
def buscar_recursos(assunto: str, nivel: str) -> str:
    """Consulta o catálogo JSON externo ao modelo por assunto e nível.

    Args:
        assunto: Conteúdo solicitado pelo estudante.
        nivel: iniciante, intermediario ou avancado.
    """
    return json.dumps(consultar_catalogo(assunto, nivel), ensure_ascii=False)
