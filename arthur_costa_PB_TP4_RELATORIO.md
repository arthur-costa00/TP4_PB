# Arthur Costa | PB | TP4

## Orquestração n8n

O principal envia `POST /run` ao planejador (8001). O sub-workflow recebe `base_url` e `status_url`, repete o GET enquanto a tarefa estiver `pending`, devolve `task_id` e `result` em `done` e encerra em `error` ou no limite de consultas.

Com o plano pronto, o n8n envia a resposta do aluno ao corretor (8002) e reutiliza o polling. O Merge junta plano e correção. O AI Agent usa o Ollama Chat Model para sugerir revisão em português e tem a Calculator conectada. `Apresentar resultado` calcula a porcentagem com a nota da API.

## Contratos e requisitos

| Requisito | Implementação |
| --- | --- |
| Plano de estudo | `agent1/CLAUDE.md` documenta entradas, sessões, duração e fontes. `agent/pipeline.py` valida o plano. |
| Correção de exercício | `agent2/CLAUDE.md` documenta submissão, nota, critérios e evidências. `tutor/pipeline.py` valida a correção pela rubrica. |
| Serviços independentes | Cada agente mantém sua API FastAPI e seu SQLite. O n8n coordena as chamadas. |
| Polling reutilizável e Merge | Os dois JSONs estão em `workflows/`. |
| Permissões | Cada `.claude/settings.json` permite leituras e testes comuns, restringe dados locais e pede confirmação para alterações de código ou dados do projeto. |
| Hook | O `PreToolUse` do Agente 1 bloqueia `Edit` e `Write` em arquivos locais de ambiente. |
| Skill | `/revisar-plano` verifica duração, sessões, catálogo, fontes e contrato da API. |
| Subagente | `revisor-rubricas` usa contexto separado e só acessa ferramentas de leitura. A revisão usa rubricas, modelos e testes do corretor. |

## Testes

- Os 20 testes Python passaram.
- O Claude Code no WSL comparou trechos dos contratos com as APIs. O HTTP 409 do corretor foi incluído no `CLAUDE.md`.
- O hook bloqueou `Write` em um arquivo de ambiente fictício. O Claude Code iniciou uma sessão do revisor. Em teste separado, o revisor reproduziu os pesos 6 e 4 com os critérios fornecidos.
- A execução nº 73 do n8n chegou à saída final com 10/10, 100% e revisão em português.

## Como executar

1. Configure o bloco Ollama de `.env.example` em cada agente e inicie os serviços conforme seus READMEs.
2. Importe e publique o sub-workflow de polling. Importe o principal e selecione o sub-workflow em ambos os nós de consulta se o ID mudar.
3. Confirme os endereços dos serviços no n8n. Na instalação usada, `local` aponta para o WSL e o Ollama é acessado pela rede Docker.
4. Associe a credencial do Ollama Chat Model e execute o principal.

