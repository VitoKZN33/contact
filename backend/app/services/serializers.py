from app.core.config import Settings
from app.domain.constants import CATEGORIES, DIFFICULTIES, PERSONAS
from app.models import Message, Scenario, TrainingResult, TrainingSession
from app.schemas.training import (
    HistoryItem,
    MessageOut,
    PersonaOut,
    ResultOut,
    ScenarioBrief,
    TrainingOut,
)


def message_out(m: Message) -> MessageOut:
    return MessageOut(
        id=str(m.id),
        sequence_number=m.sequence_number,
        role=m.role,  # type: ignore[arg-type]
        content=m.content,
        status=m.status,  # type: ignore[arg-type]
        client_message_id=m.client_message_id,
        created_at=m.created_at,
    )


def scenario_brief(sc: Scenario) -> ScenarioBrief:
    return ScenarioBrief(
        id=str(sc.id),
        slug=sc.slug,
        title=sc.title,
        description=sc.description,
        objective=sc.objective,
        category=sc.category,
        category_title=CATEGORIES[sc.category],
    )


def training_out(
    tr: TrainingSession, sc: Scenario, messages: list[Message], user_turns: int, settings: Settings
) -> TrainingOut:
    return TrainingOut(
        id=str(tr.id),
        status=tr.status,  # type: ignore[arg-type]
        analysis_status=tr.analysis_status,  # type: ignore[arg-type]
        scenario=scenario_brief(sc),
        persona=PersonaOut(
            name=tr.persona_name,
            gender=tr.persona_gender,
            type=tr.persona_type,
            type_title=PERSONAS[tr.persona_type],
        ),
        difficulty=tr.difficulty,
        difficulty_title=DIFFICULTIES[tr.difficulty],
        interaction_mode=tr.interaction_mode,
        custom_situation=tr.custom_situation,
        user_turns=user_turns,
        max_user_turns=settings.max_user_turns,
        started_at=tr.started_at,
        last_message_at=tr.last_message_at,
        completed_at=tr.completed_at,
        messages=[message_out(m) for m in messages],
    )


def result_out(r: TrainingResult) -> ResultOut:
    return ResultOut(
        summary=r.summary,
        strengths=r.strengths,
        improvements=r.improvement_points,
        alternative_replies=r.alternative_replies,
        scores=r.scores,
        created_at=r.created_at,
    )


def history_item(tr: TrainingSession, sc: Scenario, r: TrainingResult | None) -> HistoryItem:
    summary = None
    if r is not None:
        summary = r.summary if len(r.summary) <= 200 else r.summary[:197].rstrip() + "…"
    return HistoryItem(
        id=str(tr.id),
        scenario_title=sc.title,
        category_title=CATEGORIES[sc.category],
        interaction_mode=tr.interaction_mode,
        persona_name=tr.persona_name,
        persona_type_title=PERSONAS[tr.persona_type],
        difficulty_title=DIFFICULTIES[tr.difficulty],
        completed_at=tr.completed_at,
        analysis_status=tr.analysis_status,
        summary=summary,
    )
