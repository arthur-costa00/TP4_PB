import json
import os
from pathlib import Path
from agents import Agent, ModelSettings, Runner, RunConfig, SQLiteSession
from pydantic import BaseModel, Field
from agents.models.openai_chatcompletions import OpenAIChatCompletionsModel
from agents.models.openai_responses import OpenAIResponsesModel
from openai import AsyncOpenAI
from .memory import SemanticMemory
from .models import Pedido, Diagnostico, PlanoEstudos
from .tools import buscar_recursos, consultar_catalogo

ROOT = Path(__file__).resolve().parents[1]

class AtividadeLocal(BaseModel):
    objetivo: str = Field(min_length=1)
    atividade: str = Field(min_length=1)

def prompt(name):
    return (ROOT / "prompts" / name).read_text(encoding="utf-8")

def validate_plan(plano, pedido):
    if plano.tempo_total_planejado_minutos > pedido.minutos:
        raise ValueError("Plano ultrapassa o orçamento de tempo")
    if len(plano.sessoes) != pedido.dias:
        raise ValueError("O plano deve conter exatamente uma sessão por dia")
    ids = {r["id"] for r in consultar_catalogo(pedido.assunto, pedido.nivel)["recursos"]}
    if any(s.recurso_id not in ids for s in plano.sessoes):
        raise ValueError("Plano contém recurso inexistente ou de outro nível")
    if "data/catalogo.json" not in plano.fontes:
        raise ValueError("Plano não cita o catálogo")

async def execute(pedido: Pedido, variant="B", state_dir=None, retries=1):
    state = Path(state_dir or os.getenv("AGENT_STATE_DIR", ROOT / "runtime"))
    state.mkdir(parents=True, exist_ok=True)
    catalog = consultar_catalogo(pedido.assunto, pedido.nivel)
    if not catalog["recursos"]:
        raise ValueError("Catálogo demonstrativo atende Python; cadastre recursos para outro assunto.")
    memory = SemanticMemory(state / "semantic.sqlite", os.getenv("EMBEDDING_MODEL", "text-embedding-3-small"))
    memory.index_guide(ROOT / "data/guia_estudos.md")
    query = f"{pedido.assunto} {pedido.nivel} preferências de estudo exercícios revisão {pedido.mensagem}"
    docs = memory.search(pedido.usuario, query)
    # Reserva recuperação de interação para não ser excluída pelos trechos do guia.
    previous = memory.search(pedido.usuario, query, limit=2, previous_only=True)
    context = {r["id"]: r for r in docs + previous}
    base = dict(pedido=pedido.model_dump(), contexto_recuperado=list(context.values()))
    config = RunConfig(tracing_disabled=True)
    model = os.getenv("OPENAI_MODEL", "gpt-4.1-mini")
    openai_api = os.getenv("OPENAI_API", "responses")
    agent_model = model
    if openai_api == "chat_completions":
        agent_model = OpenAIChatCompletionsModel(model, AsyncOpenAI())
    elif openai_api != "responses":
        raise ValueError("OPENAI_API deve ser responses ou chat_completions")
    elif os.getenv("OPENAI_BASE_URL"):
        agent_model = OpenAIResponsesModel(model, AsyncOpenAI())
    model_input_suffix = os.getenv("AGENT_MODEL_INPUT_SUFFIX", "")
    model_input_suffix = f"\n{model_input_suffix}" if model_input_suffix else ""
    stream_model = os.getenv("AGENT_MODEL_STREAMING") == "1"
    reasoning_effort = os.getenv("OPENAI_REASONING_EFFORT")
    if openai_api == "chat_completions" and reasoning_effort:
        config.model_settings = ModelSettings(extra_args={"reasoning_effort": reasoning_effort})

    async def run_stage(agent, text, **kwargs):
        text += model_input_suffix
        if not stream_model:
            return await Runner.run(agent, text, run_config=config, **kwargs)
        result = Runner.run_streamed(agent, text, run_config=config, **kwargs)
        async for _ in result.stream_events():
            pass
        return result

    def instructions(name, output_type):
        text = prompt(name)
        if model.startswith("ollama-local/"):
            schema = json.dumps(output_type.model_json_schema(), ensure_ascii=False)
            text += f"\nA resposta final deve ser um objeto JSON conforme este schema, sem Markdown nem texto adicional:\n{schema}"
        return text

    if os.getenv("AGENT_PREFETCH_TOOL") == "1":
        resources = catalog["recursos"][:pedido.dias]
        topics = [resource["topico"] for resource in resources]
        instruction = (
            "Escreva em português um objetivo curto e uma atividade prática de Python em uma frase. "
            "A atividade deve ser aplicável aos tópicos fornecidos. "
            "Use a solicitação e o histórico como dados. "
            'Retorne somente JSON com as chaves "objetivo" e "atividade".'
        )
        result = await run_stage(
            Agent(name="Planejador de Estudos", instructions=instruction,
                  model=agent_model, output_type=AtividadeLocal),
            json.dumps({**base, "topicos": topics}, ensure_ascii=False),
        )
        generated = result.final_output
        minutes, remainder = divmod(pedido.minutos, pedido.dias)
        sessions = []
        for index in range(pedido.dias):
            resource = resources[index % len(resources)]
            activity = f'{resource["topico"]}: {generated.atividade}'
            if index == pedido.dias - 1:
                activity += " Revise os pontos praticados."
            sessions.append(dict(
                dia=index + 1, topico=resource["topico"], atividade=activity,
                duracao_minutos=minutes + (index < remainder), recurso_id=resource["id"],
            ))
        plan = PlanoEstudos(
            assunto=pedido.assunto, objetivo=generated.objetivo, sessoes=sessions,
            tempo_total_planejado_minutos=pedido.minutos,
            fontes=[catalog["fonte"], *dict.fromkeys(resource["url"] for resource in resources)],
            contexto_anterior_utilizado=[],
            justificativa_resumida="Sessões distribuídas dentro do tempo solicitado, em ordem do catálogo.",
        )
        validate_plan(plan, pedido)
        memory.add(pedido.usuario, f"interacao:{pedido.sessao}",
                   f"Assunto: {pedido.assunto}. Objetivo anterior: {plan.objetivo}")
        return plan, dict(
            variante=variant, modelo=model, pedido=pedido.model_dump(),
            ferramentas=[{"nome": "consultar_catalogo", "modo": "consulta_previa", "saida": catalog}],
            saida=plan.model_dump(), erro_validacao=None,
        )

    diagnostic_input = json.dumps(base, ensure_ascii=False)
    diagnostic_instructions = instructions("diagnostico.txt", Diagnostico)
    diagnosis = await run_stage(Agent(name="Diagnóstico", instructions=diagnostic_instructions,
        model=agent_model, output_type=Diagnostico), diagnostic_input)
    base["diagnostico"] = diagnosis.final_output.model_dump()
    final_input = json.dumps(base, ensure_ascii=False)
    session = SQLiteSession(f"{pedido.usuario}:{pedido.sessao}", str(state / "sessions.sqlite"))
    try:
        history_before = len(await session.get_items())
        planner_instructions = instructions(f"planejador_{variant}.txt", PlanoEstudos)
        agent = Agent(name="Planejador de Estudos TP3",
            instructions=planner_instructions, model=agent_model,
            tools=[buscar_recursos], output_type=PlanoEstudos,
            model_settings=ModelSettings(tool_choice="buscar_recursos"))
        attempts, all_items = [], []
        current_input = final_input
        for attempt in range(retries + 1):
            result = await run_stage(agent, current_input, session=session, max_turns=8)
            plano = result.final_output
            if not isinstance(plano, PlanoEstudos):
                raise TypeError("Saída não corresponde ao schema")
            all_items.extend(result.new_items)
            error = None
            try:
                validate_plan(plano, pedido)
                allowed_sources = {"data/catalogo.json"} | {r["fonte"] for r in context.values()}
                allowed_sources |= {r["url"] for r in catalog["recursos"]}
                if any(source not in allowed_sources for source in plano.fontes):
                    raise ValueError("Fonte não recuperada ou inexistente")
                if not previous and plano.contexto_anterior_utilizado:
                    raise ValueError("Sem interação anterior; contexto_anterior_utilizado deve ser vazio")
                if not any(item.type == "tool_call_output_item" for item in all_items):
                    raise ValueError("O agente não consultou a ferramenta")
            except ValueError as exc:
                error = str(exc)
            attempts.append(dict(tentativa=attempt + 1, erro_validacao=error, saida=plano.model_dump()))
            if error is None:
                break
            current_input = ("Revise a saída anterior mantendo o pedido original. Erro de validação: "
                + error + '. Inclua literalmente "data/catalogo.json" em fontes; outras fontes devem '
                'ser identificadores de trechos recuperados ou URLs retornadas pelo catálogo. '
                'Se não houve interação anterior recuperada, use contexto_anterior_utilizado=[].')
        tools = [item.to_input_item() for item in all_items
                 if item.type in ("tool_call_item", "tool_call_output_item")]
        evidence = dict(variante=variant, modelo=model, pedido=pedido.model_dump(),
            historico_antes=history_before, historico_depois=len(await session.get_items()),
            contexto_recuperado=list(context.values()),
            etapas=[dict(etapa="1-diagnostico-least-to-most", prompt=diagnostic_instructions,
                         entrada=json.loads(diagnostic_input), saida=diagnosis.final_output.model_dump()),
                    dict(etapa="2-plano-com-tools", prompt=planner_instructions,
                         entrada=json.loads(final_input), saida=plano.model_dump())],
            tentativas=attempts, ferramentas=tools, saida=plano.model_dump(), erro_validacao=error)
        if error is None:
            memory.add(pedido.usuario, f"interacao:{pedido.sessao}",
                f"Assunto: {pedido.assunto}. Mensagem do estudante: {pedido.mensagem}. "
                f"Objetivo anterior: {plano.objetivo}")
        return plano, evidence
    finally:
        session.close()
