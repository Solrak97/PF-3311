"""Within-subjects statistical analysis for the Suena Familiar pilot."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy import stats

from mappings import (
    EXPLORATORY_OUTCOMES,
    PRIMARY_OUTCOMES,
    VALIDATION_THRESHOLDS,
)

Direction = Literal["A > B", "A < B", "two-sided"]


@dataclass
class PairedTestResult:
    outcome: str
    label: str
    hypothesis: str
    n: int
    mean_A: float
    mean_B: float
    sd_A: float
    sd_B: float
    mean_diff: float
    sd_diff: float
    ci95_low: float
    ci95_high: float
    t_stat: float
    p_two_sided: float
    p_one_sided: float
    wilcoxon_stat: float
    wilcoxon_p_two_sided: float
    cohens_dz: float
    shapiro_p_diff: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "outcome": self.outcome,
            "label": self.label,
            "hypothesis": self.hypothesis,
            "n": self.n,
            "mean_A": round(self.mean_A, 4),
            "mean_B": round(self.mean_B, 4),
            "sd_A": round(self.sd_A, 4),
            "sd_B": round(self.sd_B, 4),
            "mean_diff": round(self.mean_diff, 4),
            "sd_diff": round(self.sd_diff, 4),
            "ci95_low": round(self.ci95_low, 4),
            "ci95_high": round(self.ci95_high, 4),
            "t_stat": round(self.t_stat, 4),
            "p_two_sided": round(self.p_two_sided, 4),
            "p_one_sided": round(self.p_one_sided, 4),
            "wilcoxon_stat": round(self.wilcoxon_stat, 4) if not np.isnan(self.wilcoxon_stat) else None,
            "wilcoxon_p_two_sided": round(self.wilcoxon_p_two_sided, 4)
            if not np.isnan(self.wilcoxon_p_two_sided)
            else None,
            "cohens_dz": round(self.cohens_dz, 4) if not np.isnan(self.cohens_dz) else None,
            "shapiro_p_diff": round(self.shapiro_p_diff, 4) if not np.isnan(self.shapiro_p_diff) else None,
        }


def _one_sided_p(two_sided_p: float, mean_diff: float, direction: Direction) -> float:
    if direction == "two-sided":
        return two_sided_p
    if direction == "A > B":
        return two_sided_p / 2 if mean_diff > 0 else 1 - two_sided_p / 2
    return two_sided_p / 2 if mean_diff < 0 else 1 - two_sided_p / 2


def paired_test(
    paired: pd.DataFrame,
    outcome_col: str,
    label: str,
    hypothesis: Direction = "A > B",
) -> PairedTestResult | None:
    col_a, col_b, col_d = f"{outcome_col}_A", f"{outcome_col}_B", f"{outcome_col}_diff"
    if col_a not in paired.columns or col_b not in paired.columns:
        return None
    sub = paired[[col_a, col_b]].dropna()
    if len(sub) < 2:
        return None

    a = sub[col_a].astype(float).values
    b = sub[col_b].astype(float).values
    diff = a - b
    n = len(diff)
    mean_a, mean_b = float(np.mean(a)), float(np.mean(b))
    sd_a = float(np.std(a, ddof=1)) if n > 1 else 0.0
    sd_b = float(np.std(b, ddof=1)) if n > 1 else 0.0
    mean_diff = float(np.mean(diff))
    sd_diff = float(np.std(diff, ddof=1)) if n > 1 else 0.0
    se = sd_diff / np.sqrt(n) if n > 0 else float("nan")
    t_stat, p_two = stats.ttest_rel(a, b, nan_policy="omit")
    ci_low = mean_diff - 1.96 * se if n > 1 and se == se else mean_diff
    ci_high = mean_diff + 1.96 * se if n > 1 and se == se else mean_diff
    dz = mean_diff / sd_diff if sd_diff > 0 else float("nan")

    try:
        w_stat, w_p = stats.wilcoxon(a, b, zero_method="wilcox", alternative="two-sided")
    except ValueError:
        w_stat, w_p = float("nan"), float("nan")

    try:
        _, shapiro_p = stats.shapiro(diff) if 3 <= n <= 5000 else (0.0, float("nan"))
    except Exception:
        shapiro_p = float("nan")

    return PairedTestResult(
        outcome=outcome_col,
        label=label,
        hypothesis=hypothesis,
        n=n,
        mean_A=mean_a,
        mean_B=mean_b,
        sd_A=sd_a,
        sd_B=sd_b,
        mean_diff=mean_diff,
        sd_diff=sd_diff,
        ci95_low=float(ci_low),
        ci95_high=float(ci_high),
        t_stat=float(t_stat),
        p_two_sided=float(p_two),
        p_one_sided=_one_sided_p(float(p_two), mean_diff, hypothesis),
        wilcoxon_stat=float(w_stat) if w_stat == w_stat else float("nan"),
        wilcoxon_p_two_sided=float(w_p) if w_p == w_p else float("nan"),
        cohens_dz=float(dz) if dz == dz else float("nan"),
        shapiro_p_diff=float(shapiro_p) if shapiro_p == shapiro_p else float("nan"),
    )


def run_outcome_battery(
    paired: pd.DataFrame,
    outcomes: dict[str, tuple[str, str]],
) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for label, (col, hyp) in outcomes.items():
        direction: Direction = "A > B" if hyp == "A > B" else "two-sided"
        result = paired_test(paired, col, label, direction)
        if result:
            rows.append(result.to_dict())
    return pd.DataFrame(rows)


def descriptive_by_condition(questionnaires: pd.DataFrame, outcome_cols: list[str]) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for cond in ("A", "B"):
        sub = questionnaires[questionnaires["condition"].astype(str).str.upper() == cond]
        for col in outcome_cols:
            if col not in sub.columns:
                continue
            vals = sub[col].dropna().astype(float)
            if vals.empty:
                continue
            rows.append(
                {
                    "condition": cond,
                    "outcome": col,
                    "n": len(vals),
                    "mean": vals.mean(),
                    "sd": vals.std(ddof=1) if len(vals) > 1 else 0.0,
                    "median": vals.median(),
                    "min": vals.min(),
                    "max": vals.max(),
                }
            )
    return pd.DataFrame(rows)


def _save_fig(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    plt.tight_layout()
    plt.savefig(path, dpi=160, bbox_inches="tight")
    plt.close()


def plot_primary_paired_bars(stats_primary: pd.DataFrame, out_path: Path) -> None:
    if stats_primary.empty:
        return
    df = stats_primary.copy()
    labels = df["label"].tolist()
    x = np.arange(len(labels))
    width = 0.35
    fig, ax = plt.subplots(figsize=(10, 5))
    ax.bar(x - width / 2, df["mean_A"], width, label="Condición A", color="#2a9d8f")
    ax.bar(x + width / 2, df["mean_B"], width, label="Condición B", color="#e9c46a")
    ax.set_xticks(x)
    ax.set_xticklabels(labels, rotation=25, ha="right")
    ax.set_ylabel("Media (escala compuesta)")
    ax.set_title("Comparación intra-sujetos: medias por condición (PI principales)")
    ax.legend()
    _save_fig(out_path)


def plot_spaghetti(paired: pd.DataFrame, outcome_col: str, label: str, out_path: Path) -> None:
    col_a, col_b = f"{outcome_col}_A", f"{outcome_col}_B"
    if col_a not in paired.columns or col_b not in paired.columns:
        return
    sub = paired[[col_a, col_b]].dropna()
    if sub.empty:
        return
    fig, ax = plt.subplots(figsize=(5, 5))
    for _, row in sub.iterrows():
        ax.plot([0, 1], [row[col_a], row[col_b]], "o-", color="#457b9d", alpha=0.7, linewidth=1)
    ax.plot([0, 1], [sub[col_a].mean(), sub[col_b].mean()], "D-", color="#e63946", linewidth=2.5, label="Media")
    ax.set_xticks([0, 1])
    ax.set_xticklabels(["A", "B"])
    ax.set_title(f"Trayectorias por participante — {label}")
    ax.legend()
    _save_fig(out_path)


def plot_diff_forest(stats_df: pd.DataFrame, title: str, out_path: Path) -> None:
    if stats_df.empty:
        return
    df = stats_df.sort_values("mean_diff")
    y = np.arange(len(df))
    fig, ax = plt.subplots(figsize=(8, max(4, len(df) * 0.45)))
    ax.errorbar(
        df["mean_diff"],
        y,
        xerr=[
            df["mean_diff"] - df["ci95_low"],
            df["ci95_high"] - df["mean_diff"],
        ],
        fmt="o",
        color="#1d3557",
        ecolor="#457b9d",
        capsize=3,
    )
    ax.axvline(0, color="#999", linestyle="--", linewidth=1)
    ax.set_yticks(y)
    ax.set_yticklabels(df["label"])
    ax.set_xlabel("Diferencia (A − B)")
    ax.set_title(title)
    _save_fig(out_path)


def plot_item_heatmap(item_paired: pd.DataFrame, out_path: Path, top_n: int = 30) -> None:
    if item_paired.empty:
        return
    df = item_paired.sort_values("mean_diff", ascending=False).head(top_n)
    fig, ax = plt.subplots(figsize=(8, max(4, len(df) * 0.25)))
    colors = ["#e63946" if d > 0 else "#457b9d" for d in df["mean_diff"]]
    ax.barh(df["item_id"], df["mean_diff"], color=colors)
    ax.axvline(0, color="#999", linestyle="--")
    ax.set_xlabel("Media diff (A − B)")
    ax.set_title("Ítems con mayor diferencia (exploratorio)")
    _save_fig(out_path)


def plot_turn_summaries(turn_paired: pd.DataFrame, out_path: Path) -> None:
    if turn_paired.empty:
        return
    metrics = [
        ("n_turns_A", "n_turns_B", "Número de turnos"),
        ("retrieval_rate_A", "retrieval_rate_B", "Tasa de recuperación"),
        ("duration_sec_A", "duration_sec_B", "Duración (s)"),
    ]
    fig, axes = plt.subplots(1, len(metrics), figsize=(12, 4))
    if len(metrics) == 1:
        axes = [axes]
    for ax, (ca, cb, title) in zip(axes, metrics):
        if ca not in turn_paired.columns or cb not in turn_paired.columns:
            ax.set_visible(False)
            continue
        sub = turn_paired[[ca, cb]].dropna()
        ax.boxplot([sub[ca], sub[cb]], tick_labels=["A", "B"])
        ax.set_title(title)
    fig.suptitle("Métricas conductuales de sesión (intra-sujetos)")
    _save_fig(out_path)


def plot_validation_thresholds(validation_agg: pd.DataFrame, out_path: Path) -> None:
    if validation_agg.empty:
        return
    row = validation_agg.iloc[-1]
    metrics = [
        ("mean_similarity", VALIDATION_THRESHOLDS["mean_similarity"], "Similitud"),
        ("mean_naturalness", VALIDATION_THRESHOLDS["mean_naturalness"], "Naturalidad"),
        ("mean_identity_safety", VALIDATION_THRESHOLDS["mean_identity_safety"], "Integridad id."),
    ]
    vals, thr, labels = [], [], []
    for key, threshold, label in metrics:
        if key in row and pd.notna(row[key]):
            vals.append(float(row[key]))
            thr.append(threshold)
            labels.append(label)
    if not vals:
        return
    x = np.arange(len(labels))
    fig, ax = plt.subplots(figsize=(7, 4))
    ax.bar(x, vals, color="#2a9d8f", label="Observado")
    ax.scatter(x, thr, color="#e63946", zorder=5, s=80, label="Umbral")
    ax.set_xticks(x)
    ax.set_xticklabels(labels)
    ax.set_ylim(0, max(max(vals), max(thr)) * 1.15)
    ax.set_title("Validación de perfil (Fase 1)")
    ax.legend()
    _save_fig(out_path)


def generate_all_figures(
    *,
    paired: pd.DataFrame,
    stats_primary: pd.DataFrame,
    stats_exploratory: pd.DataFrame,
    item_paired: pd.DataFrame,
    turn_paired: pd.DataFrame,
    validation_agg: pd.DataFrame,
    figures_dir: Path,
) -> list[str]:
    figures_dir.mkdir(parents=True, exist_ok=True)
    saved: list[str] = []

    def _go(name: str, fn, *args) -> None:
        path = figures_dir / name
        fn(*args, path)
        if path.is_file():
            saved.append(str(path))

    _go("fig01_primary_paired_bars.png", plot_primary_paired_bars, stats_primary)
    _go("fig02_primary_diff_forest.png", plot_diff_forest, stats_primary, "Efectos principales (A − B) con IC95%")
    for _, row in stats_primary.iterrows():
        safe = row["outcome"].replace("/", "_")
        _go(f"fig_spaghetti_{safe}.png", plot_spaghetti, paired, row["outcome"], row["label"])
    _go("fig03_exploratory_diff_forest.png", plot_diff_forest, stats_exploratory, "Outcomes exploratorios (A − B)")
    _go("fig04_item_diff_heatmap.png", plot_item_heatmap, item_paired)
    _go("fig05_turn_summaries.png", plot_turn_summaries, turn_paired)
    _go("fig06_validation_thresholds.png", plot_validation_thresholds, validation_agg)
    return saved


def write_markdown_report(
    *,
    out_path: Path,
    n_participants: int,
    n_complete_runs: int,
    stats_primary: pd.DataFrame,
    stats_exploratory: pd.DataFrame,
    descriptive: pd.DataFrame,
    order_effects: pd.DataFrame,
    turn_paired: pd.DataFrame,
    validation_agg: pd.DataFrame,
    figure_paths: list[str],
) -> str:
    lines = [
        "# Informe de análisis piloto — Suena Familiar",
        "",
        f"Generado: {datetime.now(timezone.utc).isoformat()}",
        "",
        "## Diseño",
        "",
        "- **Diseño:** intra-sujetos con dos condiciones (A = perfil conductual, B = control).",
        "- **Contrabalanceo:** orden A->B / B->A entre participantes.",
        "- **Prueba principal:** *t* de Student pareada (dos colas) y una cola según hipótesis (A > B).",
        "- **Robustez:** Wilcoxon pareado; tamaño del efecto *d* de Cohen para medidas repetidas (*d*z).",
        "",
        f"- Participantes con par A/B completo: **{n_participants}**",
        f"- Corridas completas (2 interacciones + 2 cuestionarios): **{n_complete_runs}**",
        "",
        "> Nota: con muestras piloto pequeñas (p. ej. n < 10) los resultados son **exploratorios**;",
        " interpretar junto con entrevistas y tamaños del efecto, no solo p-valores.",
        "",
    ]

    if not stats_primary.empty:
        lines += ["## Resultados principales (PI1–PI4)", "", _df_to_md(stats_primary), ""]

    if not stats_exploratory.empty:
        lines += ["## Resultados exploratorios", "", _df_to_md(stats_exploratory), ""]

    if not descriptive.empty:
        lines += ["## Estadística descriptiva por condición", "", _df_to_md(descriptive.round(3)), ""]

    if not order_effects.empty:
        lines += ["## Efectos de orden (exploratorio)", "", _df_to_md(order_effects.round(3)), ""]

    if not turn_paired.empty:
        lines += ["## Resumen conductual de sesión", "", _df_to_md(turn_paired.round(3)), ""]

    if not validation_agg.empty:
        lines += ["## Validación de perfil (Fase 1)", "", _df_to_md(validation_agg), ""]

    if figure_paths:
        lines += ["## Figuras generadas", ""]
        for p in figure_paths:
            lines.append(f"- `{p}`")
        lines.append("")

    text = "\n".join(lines)
    out_path.write_text(text, encoding="utf-8")
    return text


def _df_to_md(df: pd.DataFrame) -> str:
    if df.empty:
        return "_Sin datos._"
    cols = [str(c) for c in df.columns]
    header = "| " + " | ".join(cols) + " |"
    sep = "| " + " | ".join("---" for _ in cols) + " |"
    body = []
    for _, row in df.iterrows():
        body.append("| " + " | ".join(str(row[c]) for c in df.columns) + " |")
    return "\n".join([header, sep, *body])


def run_full_analysis(
    frames: dict[str, pd.DataFrame],
    output_dir: Path,
) -> dict[str, Any]:
    from db_extract import (
        build_item_level_paired,
        build_order_effects,
        build_paired_scores,
        build_turn_summaries,
        dedupe_questionnaires_per_condition,
    )

    output_dir.mkdir(parents=True, exist_ok=True)
    figures_dir = output_dir / "figures"

    questionnaires = frames.get("questionnaires", pd.DataFrame())
    runs_summary = frames.get("runs_summary", pd.DataFrame())
    turns = frames.get("turns", pd.DataFrame())
    sessions = frames.get("sessions", pd.DataFrame())
    validation_agg = frames.get("validation_aggregates", pd.DataFrame())

    paired = build_paired_scores(
        questionnaires,
        complete_runs_only=True,
        runs_summary=runs_summary,
    )
    paired.to_csv(output_dir / "paired_scores.csv", index=False)

    stats_primary = run_outcome_battery(paired, PRIMARY_OUTCOMES)
    stats_exploratory = run_outcome_battery(paired, EXPLORATORY_OUTCOMES)
    stats_primary.to_csv(output_dir / "stats_primary.csv", index=False)
    stats_exploratory.to_csv(output_dir / "stats_exploratory.csv", index=False)

    q_deduped = dedupe_questionnaires_per_condition(questionnaires)
    outcome_cols = list({v[0] for v in {**PRIMARY_OUTCOMES, **EXPLORATORY_OUTCOMES}.items()})
    descriptive = descriptive_by_condition(q_deduped, outcome_cols)
    descriptive.to_csv(output_dir / "descriptive_by_condition.csv", index=False)

    item_paired = build_item_level_paired(
        questionnaires,
        complete_runs_only=True,
        runs_summary=runs_summary,
    )
    item_paired.to_csv(output_dir / "stats_items_descriptive.csv", index=False)

    order_effects = build_order_effects(q_deduped)
    order_effects.to_csv(output_dir / "order_effects.csv", index=False)

    turn_paired = build_turn_summaries(turns, sessions)
    turn_paired.to_csv(output_dir / "turn_summaries_paired.csv", index=False)

    figure_paths = generate_all_figures(
        paired=paired,
        stats_primary=stats_primary,
        stats_exploratory=stats_exploratory,
        item_paired=item_paired,
        turn_paired=turn_paired,
        validation_agg=validation_agg,
        figures_dir=figures_dir,
    )

    n_complete = int(runs_summary["run_complete"].sum()) if not runs_summary.empty and "run_complete" in runs_summary.columns else 0
    report = write_markdown_report(
        out_path=output_dir / "report.md",
        n_participants=len(paired),
        n_complete_runs=n_complete,
        stats_primary=stats_primary,
        stats_exploratory=stats_exploratory,
        descriptive=descriptive,
        order_effects=order_effects,
        turn_paired=turn_paired,
        validation_agg=validation_agg,
        figure_paths=figure_paths,
    )

    summary = {
        "n_paired_participants": len(paired),
        "n_complete_runs": n_complete,
        "primary_tests": len(stats_primary),
        "figures": figure_paths,
        "output_dir": str(output_dir.resolve()),
    }
    (output_dir / "analysis_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return {"summary": summary, "report": report, "paired": paired, "stats_primary": stats_primary}
