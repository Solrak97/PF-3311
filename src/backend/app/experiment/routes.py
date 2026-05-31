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
from app.agents.training_graph import run_training_answer, run_training_finalize, run_training_finish, run_training_start
from app.agents.validation_graph import (
    run_validation_finalize,
    run_validation_generate,
    run_validation_rating,
    run_validation_start,
)
from app.brain.factory import create_brain
from app.experiment.chat import run_experiment_chat
from app.profiles.builder import compile_behavioral
from app.profiles.store import ProfileStore

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
    message: str
    conversation_history: list[dict[str, Any]] = Field(default_factory=list)


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


def build_experiment_router(
    profile_store: ProfileStore,
    brain: Any | None = None,
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

    @router.post("/profiles/training/finish")
    async def training_finish(body: TrainingFinalizePayload) -> dict[str, Any]:
        if not body.profile_id.strip():
            raise HTTPException(status_code=400, detail="missing_profile_id")
        try:
            return await run_training_finish(_brain, profile_store, profile_id=body.profile_id.strip())
        except ValueError as exc:
            detail = str(exc)
            code = 400 if detail in {"not_enough_samples", "training_session_not_found"} else 400
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

    @router.post("/experiment/chat")
    async def experiment_chat(body: ExperimentChatPayload) -> dict[str, Any]:
        if not body.message.strip():
            raise HTTPException(status_code=400, detail="empty_message")
        text, meta = await run_experiment_chat(
            _brain,
            profile_store,
            message=body.message.strip(),
            condition=body.condition,
            profile_id=body.profile_id,
            conversation_history=body.conversation_history,
        )
        return {
            "text": text,
            "audio_url": None,
            "animation": None,
            "metadata": meta,
        }

    return router
