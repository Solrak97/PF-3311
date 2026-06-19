"""Instrument item groups aligned to research questions (PI1--PI4)."""

from __future__ import annotations

# Post-interaction questionnaire (Godot ExperimentQuestionnaireData)
PI1_FAMILIARITY = (
    "fam_recognizable",
    "fam_familiar",
    "fam_someone",
    "fam_style",
    "fam_implicit",
)

PI3_SAM = (
    "sam_valence",
    "sam_arousal",
    "sam_dominance",
)

PI3_CLOSENESS = (
    "closeness_warm",
    "closeness_connected",
    "closeness_comfort",
)

PI4_CONTEXT = (
    "ctx_understood",
    "ctx_knew_me",
    "ctx_trust",
    "ctx_dependable",
)

# Godspeed sections — PI2 emphasizes animacy; anthropomorphism included for completeness.
PI2_GODSPEED_ANIMACY = (
    "gs_anim_dead",
    "gs_anim_stagnant",
    "gs_anim_mechanical",
    "gs_anim_artificial",
    "gs_anim_inert",
    "gs_anim_apathetic",
)

PI2_GODSPEED_ANTHRO = (
    "gs_anthro_fake",
    "gs_anthro_machine",
    "gs_anthro_unconscious",
    "gs_anthro_artificial",
    "gs_anthro_rigid",
)

PI2_GODSPEED_LIKE = (
    "gs_like_dislike",
    "gs_like_unfriendly",
    "gs_like_unkind",
    "gs_like_unpleasant",
)

PI2_GODSPEED_INTEL = (
    "gs_intel_incompetent",
    "gs_intel_ignorant",
    "gs_intel_irresponsible",
    "gs_intel_unintelligent",
    "gs_intel_foolish",
)

PI2_GODSPEED_SAFETY = (
    "gs_safe_anxious",
    "gs_safe_agitated",
    "gs_safe_quiescent",
)

PI2_GODSPEED_ALL = (
    PI2_GODSPEED_ANTHRO
    + PI2_GODSPEED_ANIMACY
    + PI2_GODSPEED_LIKE
    + PI2_GODSPEED_INTEL
    + PI2_GODSPEED_SAFETY
)

COMPOSITE_GROUPS: dict[str, tuple[str, ...]] = {
    "pi1_familiarity_mean": PI1_FAMILIARITY,
    "pi2_godspeed_animacy_mean": PI2_GODSPEED_ANIMACY,
    "pi2_godspeed_anthro_mean": PI2_GODSPEED_ANTHRO,
    "pi2_godspeed_like_mean": PI2_GODSPEED_LIKE,
    "pi2_godspeed_intel_mean": PI2_GODSPEED_INTEL,
    "pi2_godspeed_safety_mean": PI2_GODSPEED_SAFETY,
    "pi2_godspeed_all_mean": PI2_GODSPEED_ALL,
    "pi3_sam_valence": ("sam_valence",),
    "pi3_sam_arousal": ("sam_arousal",),
    "pi3_sam_dominance": ("sam_dominance",),
    "pi3_closeness_mean": PI3_CLOSENESS,
    "pi4_context_mean": PI4_CONTEXT,
}

# Fase 1 profile validation (EvaluateProfileMode / validation_graph)
VALIDATION_RATING_KEYS = (
    "tone_similarity",
    "phrasing_similarity",
    "response_length_similarity",
    "behavioral_consistency",
    "reminds_me_of_person",
    "naturalness",
    "identity_leakage_absent",
)

VALIDATION_SIMILARITY_KEYS = (
    "tone_similarity",
    "phrasing_similarity",
    "response_length_similarity",
    "behavioral_consistency",
    "reminds_me_of_person",
)

VALIDATION_THRESHOLDS = {
    "mean_similarity": 4.5,
    "mean_naturalness": 4.0,
    "mean_identity_safety": 5.5,
}

# Primary outcomes for Fase 2 (paper hypotheses: higher in Condición A)
PRIMARY_OUTCOMES: dict[str, tuple[str, str]] = {
    "PI1_familiaridad": ("pi1_familiarity_mean", "A > B"),
    "PI2_animacidad": ("pi2_godspeed_animacy_mean", "A > B"),
    "PI2_antropomorfismo": ("pi2_godspeed_anthro_mean", "A > B"),
    "PI3_cercania": ("pi3_closeness_mean", "A > B"),
    "PI3_valencia_SAM": ("pi3_sam_valence", "A > B"),
    "PI4_conocimiento_contextual": ("pi4_context_mean", "A > B"),
}

EXPLORATORY_OUTCOMES: dict[str, tuple[str, str]] = {
    "PI2_godspeed_like": ("pi2_godspeed_like_mean", "A > B"),
    "PI2_godspeed_intel": ("pi2_godspeed_intel_mean", "A > B"),
    "PI2_godspeed_safety": ("pi2_godspeed_safety_mean", "A > B"),
    "PI2_godspeed_all": ("pi2_godspeed_all_mean", "A > B"),
    "PI3_activacion_SAM": ("pi3_sam_arousal", "A > B"),
    "PI3_control_SAM": ("pi3_sam_dominance", "A > B"),
}

ALL_OUTCOME_COLS: tuple[str, ...] = tuple(dict.fromkeys(
    [v[0] for v in PRIMARY_OUTCOMES.values()]
    + [v[0] for v in EXPLORATORY_OUTCOMES.values()]
    + list(COMPOSITE_GROUPS.keys())
))
