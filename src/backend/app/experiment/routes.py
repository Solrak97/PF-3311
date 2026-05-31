from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.brain.factory import create_brain
from app.experiment.chat import run_experiment_chat
from app.experiment.interview import (
    build_raw_profile_payload,
    generate_interview_start,
    generate_interview_turn,
)
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
    participant_id: str
    session_id: str
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

    @router.post("/profiles/interview/start")
    async def interview_start(body: InterviewStartPayload) -> dict[str, Any]:
        if not body.profile_id.strip():
            raise HTTPException(status_code=400, detail="missing_profile_id")
        try:
            return await generate_interview_start(
                _brain,
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
            return await generate_interview_turn(
                _brain,
                profile_id=body.profile_id.strip(),
                modeled_user_alias=body.modeled_user_alias.strip(),
                prompt_index=body.prompt_index,
                user_message=body.user_message.strip(),
                samples=body.samples,
                conversation_history=body.conversation_history,
                skip=body.skip,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @router.post("/profiles/interview/save")
    async def interview_save(body: RawProfilePayload) -> dict[str, Any]:
        if not body.profile_id.strip():
            raise HTTPException(status_code=400, detail="missing_profile_id")
        if not body.samples:
            raise HTTPException(status_code=400, detail="no_samples")
        try:
            payload = build_raw_profile_payload(
                profile_id=body.profile_id.strip(),
                modeled_user_alias=body.modeled_user_alias.strip(),
                samples=body.samples,
                conversation_history=body.interview_transcript,
            )
            saved = profile_store.save_raw(payload)
            behavioral = compile_behavioral(saved)
            profile_store.save_behavioral(behavioral)
            return {"ok": True, "profile_id": saved["profile_id"]}
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @router.get("/profiles")
    async def list_profiles() -> dict[str, Any]:
        return {"profile_ids": profile_store.list_profile_ids()}

    @router.get("/profiles/behavioral/{profile_id}")
    async def get_behavioral_profile(profile_id: str) -> dict[str, Any]:
        try:
            profile = profile_store.load_behavioral(profile_id)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        if profile is None:
            raw = profile_store.load_raw(profile_id)
            if raw is None:
                raise HTTPException(status_code=404, detail="profile_not_found")
            profile = compile_behavioral(raw)
            profile_store.save_behavioral(profile)
        return profile

    @router.post("/profiles/validation/generate-sample")
    async def generate_validation_sample(body: GenerateSamplePayload) -> dict[str, Any]:
        profile = profile_store.load_behavioral(body.profile_id)
        if profile is None:
            raise HTTPException(status_code=404, detail="profile_not_found")
        prompt = body.prompt.strip() or "Cuéntame brevemente cómo fue tu día."
        text, meta = await run_experiment_chat(
            _brain,
            profile_store,
            message=prompt,
            condition="A",
            profile_id=body.profile_id,
            conversation_history=[],
        )
        return {"prompt": prompt, "agent_response": text, "metadata": meta}

    @router.post("/profiles/validation")
    async def post_validation(body: ValidationPayload) -> dict[str, Any]:
        if not body.profile_id.strip():
            raise HTTPException(status_code=400, detail="missing_profile_id")
        saved = profile_store.save_validation(body.model_dump())
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
