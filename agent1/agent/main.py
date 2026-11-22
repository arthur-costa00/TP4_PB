import argparse
import asyncio
import json
import os
from pathlib import Path
from dotenv import load_dotenv
from .models import Pedido
from .pipeline import execute, ROOT

def main():
    load_dotenv(ROOT / ".env")
    parser = argparse.ArgumentParser(description="TP2 — planejador de estudos com tools e memória")
    parser.add_argument("--assunto", default="Introdução a Python")
    parser.add_argument("--nivel", default="iniciante", choices=["iniciante", "intermediario", "avancado"])
    parser.add_argument("--minutos", type=int, default=180)
    parser.add_argument("--dias", type=int, default=3)
    parser.add_argument("--usuario", default="estudante-demo")
    parser.add_argument("--sessao", default="principal")
    parser.add_argument("--mensagem", default="Crie meu plano de estudos.")
    parser.add_argument("--evidencia", default="output/tp2/ultima_execucao.json")
    args = parser.parse_args()
    if not os.getenv("OPENAI_API_KEY"):
        parser.error("Configure OPENAI_API_KEY no .env (veja .env.example).")
    evidence_path = Path(args.evidencia)
    pedido = Pedido(**{k: v for k, v in vars(args).items() if k != "evidencia"})
    try:
        plano, evidence = asyncio.run(execute(pedido))
        evidence_path.parent.mkdir(parents=True, exist_ok=True)
        evidence_path.write_text(json.dumps(evidence, ensure_ascii=False, indent=2), encoding="utf-8")
        if evidence["erro_validacao"]:
            raise ValueError(evidence["erro_validacao"])
        print(plano.model_dump_json(indent=2))
    except Exception as exc:
        # Não imprimir payloads de requisição ou credenciais em caso de falha.
        raise SystemExit(f"Falha no pipeline ({type(exc).__name__}). Verifique configuração e evidência, se gerada.") from None

if __name__ == "__main__":
    main()
