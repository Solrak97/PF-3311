from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.agents.refinement_graph import (
    run_refinement_feedback,
    run_refinement_finalize,
    run_refinement_message,
    run_refinement_start,
)
from app.agents.training_graph import (
    run_training_answer,
    run_training_finalize,
    run_training_finish,
    run_training_start,
    run_training_verdict,
)
from app.experiment.scenarios import list_scenarios
from app.agents.validation_graph import (
    run_validation_ai_judge,
    run_validation_auto_test,
    run_validation_finalize,
    run_validation_generate,
    run_validation_rating,
    run_validation_start,
)
from app.brain.factory import create_brain
from app.experiment.chat import run_experiment_chat
from app.profiles.builder import compile_behavioral
from app.profiles.store import ProfileStore
from app.storage.sqlite_store import SQLiteExperimentStore

logger = logging.getLogger(__name__)


class RawProfilePayload(BaseModel):
    profile_id: str
    modeled_user_alias: str = ""
    created_at: str = ""
    consent_confirmed: bool = False
    samples: list[dict[str, Any]] = Field(default_factory=list)
    interview_transcript: list[dict[str, Any]] = Field(default_factory=list)


class GenerateSamplePayload(BaseModel):
    profile_id: str
    prompt: str = ""


class ValidationPayload(BaseModel):
    profile_id: str
    validator_id: str = ""
    created_at: str = ""
    ratings: list[dict[str, Any]] = Field(default_factory=list)


class ExperimentChatPayload(BaseModel):
    participant_id: str = ""
    session_id: str = ""
    interaction_index: int = 1
    condition: str = "B"
    profile_id: str = ""
    scenario_id: str = ""
    message: str = ""
    conversation_open: bool = False
    conversation_history: list[dict[str, Any]] = Field(default_factory=list)


class QuestionnairePayload(BaseModel):
    run_session_id: str = ""
    session_id: str = ""
    participant_id: str = ""
    condition: str = "B"
    order_group: str = "A-B"
    interaction_index: int = 1
    questionnaire_after_interaction: int = 1
    profile_id: str = ""
    scenario_id: str = ""
    responses: dict[str, Any] = Field(default_factory=dict)


class InterviewStartPayload(BaseModel):
    profile_id: str
    modeled_user_alias: str = ""


class InterviewTurnPayload(BaseModel):
    profile_id: str
    modeled_user_alias: str = ""
    prompt_index: int = 0
    user_message: str = ""
    skip: bool = False
    samples: list[dict[str, Any]] = Field(default_factory=list)
    conversation_history: list[dict[str, Any]] = Field(default_factory=list)


class TrainingStartPayload(BaseModel):
    profile_id: str
    modeled_user_alias: str = ""


class TrainingAnswerPayload(BaseModel):
    profile_id: str
    user_message: str = ""
    skip: bool = False


class TrainingFinalizePayload(BaseModel):
    profile_id: str


class TrainingVerdictPayload(BaseModel):
    profile_id: str
    verdict: str
    user_message: str = ""


class RefinementStartPayload(BaseModel):
    profile_id: str


class RefinementMessagePayload(BaseModel):
    profile_id: str
    message: str


class RefinementFeedbackPayload(BaseModel):
    profile_id: str
    user_message: str = ""
    agent_response: str = ""
    sounds_like_me: int = 4
    tone_correct: int = 4
    phrasing_correct: int = 4
    too_generic: bool = False
    too_exaggerated: bool = False
    unnatural: bool = False
    contextually_incorrect: bool = False
    rewrite: str | None = None


class RefinementFinalizePayload(BaseModel):
    profile_id: str


class ValidationStartPayload(BaseModel):
    profile_id: str


class ValidationGeneratePayload(BaseModel):
    profile_id: str


class ValidationRatingPayload(BaseModel):
    profile_id: str
    validator_id: str = "godot-ui"
    prompt: str = ""
    agent_response: str = ""
    scores: dict[str, Any] = Field(default_factory=dict)


class ValidationFinalizePayload(BaseModel):
    profile_id: str


class ValidationAiJudgePayload(BaseModel):
    profile_id: str
    prompt: str = ""
    agent_response: str = ""
    generate_if_missing: bool = True


class ValidationAutoTestPayload(BaseModel):
    profile_id: str
    samples: int = 1
    finalize: bool = False


def build_experiment_router(
    profile_store: ProfileStore,
    brain: Any | None = None,
    store: SQLiteExperimentStore | None = None,
) -> APIRouter:
    router = APIRouter(tags=["experiment"])
    _brain = brain or create_brain()

    @router.post("/profiles/raw")
    async def post_raw_profile(body: RawProfilePayload) -> dict[str, Any]:
        if not body.profile_id.strip():
            raise HTTPException(status_code=400, detail="missing_profile_id")
        if not body.samples:
            raise HTTPException(status_code=400, detail="no_samples")
        try:
            payload = body.model_dump()
            payload["consent_confirmed"] = True
            saved = profile_store.save_raw(payload)
            behavioral = compile_behavioral(saved)
            profile_store.save_behavioral(behavioral)
            return {"ok": True, "profile_id": saved["profile_id"]}
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @router.post("/profiles/training/start")
    async def training_start(body: TrainingStartPayload) -> dict[str, Any]:
        if not body.profile_id.strip():
            raise HTTPException(status_code=400, detail="missing_profile_id")
        try:
            return await run_training_start(
                _brain,
                profile_store,
                profile_id=body.profile_id.strip(),
                modeled_user_alias=body.modeled_user_alias.strip(),
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @router.post("/profiles/training/answer")
    async def training_answer(body: TrainingAnswerPayload) -> dict[str, Any]:
        if not body.profile_id.strip():
            raise HTTPException(status_code=400, detail="missing_profile_id")
        try:
            return await run_training_answer(
                _brain,
                profile_store,
                profile_id=body.profile_id.strip(),
                user_message=body.user_message.strip(),
                skip=body.skip,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @router.post("/profiles/training/verdict")
    async def training_verdict(body: TrainingVerdictPayload) -> dict[str, Any]:
        if not body.profile_id.strip():
            raise HTTPException(status_code=400, detail="missing_profile_id")
        try:
            return await run_training_verdict(
                _brain,
                profile_store,
                profile_id=body.profile_id.strip(),
                verdict=body.verdict.strip(),
                user_message=body.user_message.strip(),
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @router.post("/profiles/training/finish")
    async def training_finish(body: TrainingFinalizePayload) -> dict[str, Any]:
        if not body.profile_id.strip():
            raise HTTPException(status_code=400, detail="missing_profile_id")
        try:
            return await run_training_finish(_brain, profile_store, profile_id=body.profile_id.strip())
        except ValueError as exc:
            detail = str(exc)
            code = 400 if detail in {"not_enough_cycles", "not_enough_samples", "training_session_not_found", "finish_blocked_awaiting_verdict"} else 400
            raise HTTPException(status_code=code, detail=detail) from exc

    @router.post("/profiles/training/finalize")
    async def training_finalize(body: TrainingFinalizePayload) -> dict[str, Any]:
        if not body.profile_id.strip():
            raise HTTPException(status_code=400, detail="missing_profile_id")
        try:
            return await run_training_finalize(_brain, profile_store, profile_id=body.profile_id.strip())
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @router.post("/profiles/refinement/start")
    async def refinement_start(body: RefinementStartPayload) -> dict[str, Any]:
        try:
            return await run_refinement_start(profile_store, profile_id=body.profile_id.strip())
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @router.post("/profiles/refinement/message")
    async def refinement_message(body: RefinementMessagePayload) -> dict[str, Any]:
        try:
            return await run_refinement_message(
                _brain,
                profile_store,
                profile_id=body.profile_id.strip(),
                user_message=body.message.strip(),
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @router.post("/profiles/refinement/feedback")
    async def refinement_feedback(body: RefinementFeedbackPayload) -> dict[str, Any]:
        try:
            return await run_refinement_feedback(
                _brain,
                profile_store,
                profile_id=body.profile_id.strip(),
                feedback=body.model_dump(),
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @router.post("/profiles/refinement/finalize")
    async def refinement_finalize(body: RefinementFinalizePayload) -> dict[str, Any]:
        return await run_refinement_finalize(profile_store, profile_id=body.profile_id.strip())

    @router.post("/profiles/validation/start")
    async def validation_start(body: ValidationStartPayload) -> dict[str, Any]:
        try:
            return await run_validation_start(profile_store, profile_id=body.profile_id.strip())
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @router.post("/profiles/validation/generate")
    async def validation_generate(body: ValidationGeneratePayload) -> dict[str, Any]:
        try:
            return await run_validation_generate(_brain, profile_store, profile_id=body.profile_id.strip())
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @router.post("/profiles/validation/rating")
    async def validation_rating(body: ValidationRatingPayload) -> dict[str, Any]:
        try:
            return await run_validation_rating(
                profile_store,
                profile_id=body.profile_id.strip(),
                validator_id=body.validator_id.strip() or "godot-ui",
                scores=body.scores,
                prompt=body.prompt.strip(),
                agent_response=body.agent_response.strip(),
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @router.post("/profiles/validation/finalize")
    async def validation_finalize(body: ValidationFinalizePayload) -> dict[str, Any]:
        try:
            return await run_validation_finalize(profile_store, profile_id=body.profile_id.strip())
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @router.post("/profiles/validation/ai-judge")
    async def validation_ai_judge(body: ValidationAiJudgePayload) -> dict[str, Any]:
        try:
            return await run_validation_ai_judge(
                _brain,
                profile_store,
                profile_id=body.profile_id.strip(),
                prompt=body.prompt.strip(),
                agent_response=body.agent_response.strip(),
                generate_if_missing=body.generate_if_missing,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @router.post("/profiles/validation/auto-test")
    async def validation_auto_test(body: ValidationAutoTestPayload) -> dict[str, Any]:
        try:
            return await run_validation_auto_test(
                _brain,
                profile_store,
                profile_id=body.profile_id.strip(),
                samples=body.samples,
                finalize=body.finalize,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @router.post("/profiles/interview/start")
    async def interview_start(body: InterviewStartPayload) -> dict[str, Any]:
        if not body.profile_id.strip():
            raise HTTPException(status_code=400, detail="missing_profile_id")
        try:
            return await run_training_start(
                _brain,
                profile_store,
                profile_id=body.profile_id.strip(),
                modeled_user_alias=body.modeled_user_alias.strip(),
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @router.post("/profiles/interview/turn")
    async def interview_turn(body: InterviewTurnPayload) -> dict[str, Any]:
        if not body.profile_id.strip():
            raise HTTPException(status_code=400, detail="missing_profile_id")
        try:
            result = await run_training_answer(
                _brain,
                profile_store,
                profile_id=body.profile_id.strip(),
                user_message=body.user_message.strip(),
                skip=body.skip,
            )
            result["prompt_index"] = result.get("prompt_index", body.prompt_index)
            return result
        except ValueError as exc:
            detail = str(exc)
            raise HTTPException(status_code=400, detail=detail) from exc

    @router.post("/profiles/interview/verdict")
    async def interview_verdict(body: TrainingVerdictPayload) -> dict[str, Any]:
        if not body.profile_id.strip():
            raise HTTPException(status_code=400, detail="missing_profile_id")
        try:
            return await run_training_verdict(
                _brain,
                profile_store,
                profile_id=body.profile_id.strip(),
                verdict=body.verdict.strip(),
                user_message=body.user_message.strip(),
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @router.post("/profiles/interview/finish")
    async def interview_finish(body: TrainingFinalizePayload) -> dict[str, Any]:
        if not body.profile_id.strip():
            raise HTTPException(status_code=400, detail="missing_profile_id")
        try:
            return await run_training_finish(_brain, profile_store, profile_id=body.profile_id.strip())
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @router.post("/profiles/interview/save")
    async def interview_save(body: RawProfilePayload) -> dict[str, Any]:
        if not body.profile_id.strip():
            raise HTTPException(status_code=400, detail="missing_profile_id")
        try:
            return await run_training_finalize(_brain, profile_store, profile_id=body.profile_id.strip())
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @router.get("/profiles")
    async def list_profiles() -> dict[str, Any]:
        return {"profile_ids": profile_store.list_profile_ids()}

    @router.get("/profiles/{profile_id}/status")
    async def profile_status(profile_id: str) -> dict[str, Any]:
        pid = profile_id.strip()
        if not pid:
            raise HTTPException(status_code=400, detail="missing_profile_id")
        raw = profile_store.load_raw(pid)
        behavioral = profile_store.load_behavioral(pid)
        yaml_profile = profile_store.load_behavioral_yaml(pid)
        validation = profile_store.load_validation_aggregate(pid)
        summary = (validation or {}).get("summary") or {}
        passed = summary.get("passed") if validation else None
        if passed is None and validation:
            passed = validation.get("passed")
        return {
            "profile_id": pid,
            "on_server": raw is not None or behavioral is not None or yaml_profile is not None,
            "has_raw": raw is not None,
            "has_behavioral": behavioral is not None,
            "has_yaml": yaml_profile is not None,
            "validation_passed": passed,
            "validation_summary": summary or None,
        }

    @router.get("/profiles/behavioral/{profile_id}")
    async def get_behavioral_profile(profile_id: str) -> dict[str, Any]:
        try:
            profile = profile_store.load_behavioral(profile_id)
            yaml_profile = profile_store.load_behavioral_yaml(profile_id)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        if profile is None and yaml_profile is None:
            raw = profile_store.load_raw(profile_id)
            if raw is None:
                raise HTTPException(status_code=404, detail="profile_not_found")
            profile = compile_behavioral(raw)
            profile_store.save_behavioral(profile)
        if profile is None and yaml_profile is not None:
            from app.profiles.yaml_profile import profile_to_style_summary

            profile = {
                "profile_id": profile_id,
                "style_summary": profile_to_style_summary(yaml_profile),
                "yaml_profile": yaml_profile,
            }
        if yaml_profile and profile is not None:
            profile["yaml_profile"] = yaml_profile
        return profile

    @router.post("/profiles/validation/generate-sample")
    async def generate_validation_sample(body: GenerateSamplePayload) -> dict[str, Any]:
        try:
            return await run_validation_generate(_brain, profile_store, profile_id=body.profile_id.strip())
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @router.post("/profiles/validation")
    async def post_validation(body: ValidationPayload) -> dict[str, Any]:
        if not body.profile_id.strip():
            raise HTTPException(status_code=400, detail="missing_profile_id")
        saved = profile_store.save_validation(body.model_dump())
        if body.ratings:
            session = profile_store.load_session(body.profile_id.strip(), "validation") or {
                "profile_id": body.profile_id.strip(),
                "validation_results": [],
            }
            for rating in body.ratings:
                scores = rating.get("scores") or rating
                await run_validation_rating(
                    profile_store,
                    profile_id=body.profile_id.strip(),
                    validator_id=body.validator_id.strip() or "godot-ui",
                    scores=scores,
                    prompt=str(rating.get("prompt", "")),
                    agent_response=str(rating.get("agent_response", "")),
                )
        return {"ok": True, "saved": saved.get("created_at", "")}

    @router.get("/experiment/scenarios")
    async def experiment_scenarios() -> dict[str, Any]:
        return {"scenarios": list_scenarios()}

    @router.post("/experiment/chat")
    async def experiment_chat(body: ExperimentChatPayload) -> dict[str, Any]:
        if not body.conversation_open and not body.message.strip():
            raise HTTPException(status_code=400, detail="empty_message")
        text, meta = await run_experiment_chat(
            _brain,
            profile_store,
            message=body.message.strip(),
            condition=body.condition,
            profile_id=body.profile_id,
            conversation_history=body.conversation_history,
            scenario_id=body.scenario_id.strip() or None,
            conversation_open=body.conversation_open,
        )
        return {
            "text": text,
            "audio_url": None,
            "animation": None,
            "metadata": meta,
        }

    @router.post("/experiment/questionnaire")
    async def experiment_questionnaire(body: QuestionnairePayload) -> dict[str, Any]:
        if store is None:
            raise HTTPException(status_code=503, detail="experiment_store_unavailable")
        run_session_id = body.run_session_id.strip()
        session_id = body.session_id.strip()
        participant_id = body.participant_id.strip()
        if not run_session_id and not session_id:
            raise HTTPException(status_code=400, detail="missing_session_id")
        if not participant_id:
            raise HTTPException(status_code=400, detail="missing_participant_id")
        if not body.responses:
            raise HTTPException(status_code=400, detail="empty_responses")
        condition = body.condition.strip().upper()
        if condition not in {"A", "B"}:
            condition = "B"
        row_id = store.insert_questionnaire_response(
            run_session_id=run_session_id or session_id,
            session_id=session_id or run_session_id,
            participant_id=participant_id,
            condition=condition,
            order_group=body.order_group.strip() or "A-B",
            interaction_index=max(1, int(body.interaction_index)),
            questionnaire_after_interaction=max(1, int(body.questionnaire_after_interaction)),
            profile_id=body.profile_id.strip(),
            scenario_id=body.scenario_id.strip(),
            responses=body.responses,
        )
        return {
            "ok": True,
            "id": row_id,
            "run_session_id": run_session_id or session_id,
            "session_id": session_id or run_session_id,
        }

    return router
