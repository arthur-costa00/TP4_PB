# Arthur Costa | PB | TP4 | Agente 1

Configure o bloco Ollama de `.env.example` em `.env`. Inicie no Ubuntu WSL:

```bash
uv sync --locked
uv run uvicorn agent.api:app --host 0.0.0.0 --port 8001 --workers 1
```

Consulte `CLAUDE.md` para o contrato e as permissões.
