#!/usr/bin/env python3
"""
Data analysis.
Reads:  evaluation/results/*.json
        evaluation/results/stage1_latency.csv
        evaluation/results/stage2_latency_tau090.csv
Writes: evaluation/figures/fig_*.pdf (10 figures)
"""

import matplotlib
matplotlib.use("Agg")

import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import seaborn as sns
import numpy as np
import json
import pandas as pd
from pathlib import Path

FIGURES_DIR = Path("evaluation/figures")
RESULTS_DIR = Path("evaluation/results")

SINGLE_COL = (3.5, 2.5)
DOUBLE_COL = (7.0, 3.0)


def setup_paper_style():
    plt.rcParams.update({
        "figure.dpi": 300,
        "font.size": 10,
        "font.family": "serif",
        "axes.labelsize": 10,
        "xtick.labelsize": 9,
        "ytick.labelsize": 9,
        "legend.fontsize": 9,
        "axes.spines.top": False,
        "axes.spines.right": False,
    })
    sns.set_style("whitegrid")


def save_fig(fig, name):
    FIGURES_DIR.mkdir(parents=True, exist_ok=True)
    path = FIGURES_DIR / f"{name}.pdf"
    fig.savefig(path, bbox_inches="tight", format="pdf")
    print(f"  Saved: {path}")
    plt.close(fig)


def load_json(filename):
    path = RESULTS_DIR / filename
    with open(path) as f:
        return json.load(f)


# ---------------------------------------------------------------------------
# Figure 1: Stage 1 latency histogram
# ---------------------------------------------------------------------------
def fig_latency_stage1():
    df = pd.read_csv(RESULTS_DIR / "stage1_latency.csv")
    latency = df["latency_ms"].values

    mean_val = 40.7
    p95_val = 45.8

    fig, ax = plt.subplots(figsize=SINGLE_COL)
    bins = np.arange(latency.min(), latency.max() + 1, 1)
    ax.hist(latency, bins=bins, color="#4C72B0", alpha=0.8, edgecolor="none")

    ax.axvline(mean_val, color="#C44E52", linewidth=1.5, linestyle="-",
               label=f"Mean {mean_val} ms")
    ax.axvline(p95_val, color="#DD8452", linewidth=1.5, linestyle="--",
               label=f"P95 {p95_val} ms")

    # text labels above lines
    ymax = ax.get_ylim()[1]
    ax.text(mean_val + 0.5, ymax * 0.88, f"μ={mean_val} ms",
            fontsize=7, color="#C44E52")
    ax.text(p95_val + 0.5, ymax * 0.75, f"P95={p95_val} ms",
            fontsize=7, color="#DD8452")

    ax.set_xlabel("Inference latency (ms)")
    ax.set_ylabel("Number of emails")
    ax.set_title("Stage 1 binary model — client-side ONNX inference latency",
                 fontsize=8)
    ax.legend(fontsize=7)

    save_fig(fig, "fig_latency_stage1")


# ---------------------------------------------------------------------------
# Figure 2: Latency comparison box plot
# ---------------------------------------------------------------------------
def fig_latency_comparison():
    s1 = pd.read_csv(RESULTS_DIR / "stage1_latency.csv")
    s2 = pd.read_csv(RESULTS_DIR / "stage2_latency_tau090.csv")

    stage1_vals = s1["latency_ms"].values

    # Gate-passed emails: those whose email_idx appears in stage2 CSV
    gate_passed_idx = set(s2["email_idx"].values)
    s1_passed = s1[s1["email_idx"].isin(gate_passed_idx)].set_index("email_idx")
    s2_indexed = s2.set_index("email_idx")

    # Combined = s1 latency + s2 latency for gate-passed emails
    common_idx = s1_passed.index.intersection(s2_indexed.index)
    combined_vals = (s1_passed.loc[common_idx, "latency_ms"].values
                     + s2_indexed.loc[common_idx, "latency_ms"].values)
    stage2_vals = s2["latency_ms"].values

    data = [stage1_vals, stage2_vals, combined_vals]
    labels = [
        "Stage 1\n(all emails)",
        "Stage 2\n(gate-passed,\nτ=0.90)",
        "Combined\n(τ=0.90)",
    ]

    fig, ax = plt.subplots(figsize=SINGLE_COL)
    bp = ax.boxplot(data, labels=labels, patch_artist=True,
                    medianprops=dict(color="black", linewidth=1.5))

    colors = ["#4C72B0", "#55A868", "#C44E52"]
    for patch, color in zip(bp["boxes"], colors):
        patch.set_facecolor(color)
        patch.set_alpha(0.7)

    ax.axhline(100, color="gray", linewidth=1.0, linestyle="--", alpha=0.8)
    ax.text(2.55, 102, "100 ms threshold", fontsize=7, color="gray")

    ax.set_ylabel("Latency (ms)")
    ax.set_title("Pipeline latency by stage", fontsize=9)

    save_fig(fig, "fig_latency_comparison")


# ---------------------------------------------------------------------------
# Figure 3: ROC curve with baselines
# ---------------------------------------------------------------------------
def fig_roc_curve():
    ts = load_json("threshold_sensitivity.json")
    baselines = load_json("baselines.json")

    sweep = ts["threshold_sweep"]
    # ROC: fpr vs recall (TPR), sorted by fpr ascending
    fpr_vals = [pt["fpr"] for pt in sweep]
    tpr_vals = [pt["recall"] for pt in sweep]

    # Add (0,0) and (1,1) endpoints
    fpr_vals = [0.0] + fpr_vals + [1.0]
    tpr_vals = [0.0] + tpr_vals + [1.0]

    # Sort by FPR
    pairs = sorted(zip(fpr_vals, tpr_vals))
    fpr_sorted = [p[0] for p in pairs]
    tpr_sorted = [p[1] for p in pairs]

    fig, ax = plt.subplots(figsize=SINGLE_COL)

    # Diagonal reference
    ax.plot([0, 1], [0, 1], "k--", linewidth=0.8, alpha=0.5, label="Random classifier")

    ax.plot(fpr_sorted, tpr_sorted, color="#4C72B0", linewidth=1.8,
            label="PhishGuard (AUC=0.9995)")

    # Baseline scatter points
    bl = baselines["baselines"]
    ax.scatter(bl["tfidf_lr"]["fpr"], bl["tfidf_lr"]["recall"],
               marker="^", color="#C44E52", s=50, zorder=5, label="TF-IDF+LR")
    ax.scatter(bl["tfidf_svm"]["fpr"], bl["tfidf_svm"]["recall"],
               marker="s", color="#DD8452", s=50, zorder=5, label="TF-IDF+SVM")
    ax.scatter(bl["onnx_nonstaged"]["fpr"], bl["onnx_nonstaged"]["recall"],
               marker="D", color="#55A868", s=50, zorder=5, label="ONNX non-staged")

    ax.set_xlabel("False positive rate")
    ax.set_ylabel("True positive rate")
    ax.set_xlim(-0.01, 0.15)
    ax.set_ylim(0.85, 1.01)
    ax.legend(fontsize=7, loc="lower right")

    save_fig(fig, "fig_roc_curve")


# ---------------------------------------------------------------------------
# Figure 4: Precision-Recall curve
# ---------------------------------------------------------------------------
def fig_pr_curve():
    ts = load_json("threshold_sensitivity.json")
    baselines = load_json("baselines.json")

    sweep = ts["threshold_sweep"]
    recall_vals = [pt["recall"] for pt in sweep]
    prec_vals = [pt["precision"] for pt in sweep]

    # Add endpoints
    recall_vals = recall_vals + [0.0]
    prec_vals = prec_vals + [1.0]

    pairs = sorted(zip(recall_vals, prec_vals))
    recall_sorted = [p[0] for p in pairs]
    prec_sorted = [p[1] for p in pairs]

    fig, ax = plt.subplots(figsize=SINGLE_COL)

    ax.plot(recall_sorted, prec_sorted, color="#4C72B0", linewidth=1.8,
            label="PhishGuard (PR-AUC=0.9983)")

    # Baseline points
    bl = baselines["baselines"]
    ax.scatter(bl["tfidf_lr"]["recall"], bl["tfidf_lr"]["precision"],
               marker="^", color="#C44E52", s=50, zorder=5, label="TF-IDF+LR")
    ax.scatter(bl["tfidf_svm"]["recall"], bl["tfidf_svm"]["precision"],
               marker="s", color="#DD8452", s=50, zorder=5, label="TF-IDF+SVM")
    ax.scatter(bl["onnx_nonstaged"]["recall"], bl["onnx_nonstaged"]["precision"],
               marker="D", color="#55A868", s=50, zorder=5, label="ONNX non-staged")

    # Annotate operating points
    # τ=0.25
    op_025 = next(pt for pt in sweep if pt["threshold"] == 0.25)
    ax.scatter(op_025["recall"], op_025["precision"],
               marker="o", color="#9467BD", s=70, zorder=6)
    ax.annotate("τ=0.25", (op_025["recall"], op_025["precision"]),
                xytext=(-30, -12), textcoords="offset points", fontsize=7,
                color="#9467BD")

    # τ=0.90
    op_090 = next(pt for pt in sweep if pt["threshold"] == 0.9)
    ax.scatter(op_090["recall"], op_090["precision"],
               marker="o", color="#8C564B", s=70, zorder=6)
    ax.annotate("τ=0.90", (op_090["recall"], op_090["precision"]),
                xytext=(4, -12), textcoords="offset points", fontsize=7,
                color="#8C564B")

    ax.set_xlabel("Recall")
    ax.set_ylabel("Precision")
    ax.set_xlim(0.85, 1.01)
    ax.set_ylim(0.93, 1.01)
    ax.legend(fontsize=7, loc="lower left")

    save_fig(fig, "fig_pr_curve")


# ---------------------------------------------------------------------------
# Figure 5: Threshold sensitivity (3-line plot)
# ---------------------------------------------------------------------------
def fig_threshold_sensitivity():
    ts = load_json("threshold_sensitivity.json")
    sweep = ts["threshold_sweep"]

    thresholds = [pt["threshold"] for pt in sweep]
    precision = [pt["precision"] for pt in sweep]
    recall = [pt["recall"] for pt in sweep]
    fpr_scaled = [pt["fpr"] * 10 for pt in sweep]

    fig, ax = plt.subplots(figsize=DOUBLE_COL)

    ax.plot(thresholds, precision, color="#4C72B0", linewidth=1.8,
            linestyle="-", label="Precision")
    ax.plot(thresholds, recall, color="#DD8452", linewidth=1.8,
            linestyle="--", label="Recall")
    ax.plot(thresholds, fpr_scaled, color="#55A868", linewidth=1.5,
            linestyle=":", label="FPR × 10")

    # Vertical lines at canonical operating points
    ax.axvline(0.25, color="gray", linewidth=1.0, linestyle="--", alpha=0.7)
    ax.text(0.25 + 0.01, 0.965, "τ=0.25", fontsize=8, color="gray")
    ax.axvline(0.90, color="gray", linewidth=1.0, linestyle="--", alpha=0.7)
    ax.text(0.90 + 0.01, 0.965, "τ=0.90", fontsize=8, color="gray")

    ax.set_xlabel("Decision threshold τ")
    ax.set_ylabel("Metric value")
    ax.set_ylim(0.95, 1.01)
    ax.legend(fontsize=8)

    save_fig(fig, "fig_threshold_sensitivity")


# ---------------------------------------------------------------------------
# Figure 6: Confusion matrix heatmap at τ=0.25
# ---------------------------------------------------------------------------
def fig_confusion_matrix():
    bev = load_json("binary_eval_v2.json")
    cm = bev["confusion_matrices"]["0.25"]
    # [[TN, FP], [FN, TP]]
    cm_arr = np.array(cm)

    fig, ax = plt.subplots(figsize=SINGLE_COL)

    sns.heatmap(
        cm_arr,
        annot=True, fmt="d", cmap="Blues",
        xticklabels=["Pred Benign", "Pred Phishing"],
        yticklabels=["True Benign", "True Phishing"],
        ax=ax,
        linewidths=0.5,
        cbar=False,
    )
    ax.set_title("Confusion matrix at τ = 0.25", fontsize=9)
    ax.tick_params(axis="x", labelsize=8)
    ax.tick_params(axis="y", labelsize=8, rotation=0)

    save_fig(fig, "fig_confusion_matrix")


# ---------------------------------------------------------------------------
# Figure 7: Baseline comparison grouped bar chart
# ---------------------------------------------------------------------------
def fig_baseline_comparison():
    bl_data = load_json("baselines.json")
    bl = bl_data["baselines"]
    pg = bl_data["phishguard_staged"]

    systems = ["TF-IDF+LR", "TF-IDF+SVM", "ONNX\nNon-staged", "PhishGuard\nStaged"]
    precision = [
        bl["tfidf_lr"]["precision"],
        bl["tfidf_svm"]["precision"],
        bl["onnx_nonstaged"]["precision"],
        pg["precision"],
    ]
    recall = [
        bl["tfidf_lr"]["recall"],
        bl["tfidf_svm"]["recall"],
        bl["onnx_nonstaged"]["recall"],
        pg["recall"],
    ]
    f1 = [
        bl["tfidf_lr"]["f1"],
        bl["tfidf_svm"]["f1"],
        bl["onnx_nonstaged"]["f1"],
        pg["f1"],
    ]

    x = np.arange(len(systems))
    width = 0.25

    fig, ax = plt.subplots(figsize=DOUBLE_COL)

    baseline_color = "#4C72B0"
    phishguard_color = "#C44E52"

    def bar_colors(base, highlight):
        return [highlight if i == 3 else base for i in range(4)]

    bars_p = ax.bar(x - width, precision, width, label="Precision",
                    color=bar_colors(baseline_color, phishguard_color),
                    alpha=0.85)
    bars_r = ax.bar(x, recall, width, label="Recall",
                    color=bar_colors("#55A868", "#DD8452"),
                    alpha=0.85)
    bars_f = ax.bar(x + width, f1, width, label="F1",
                    color=bar_colors("#8172B3", "#937860"),
                    alpha=0.85)

    # Value labels on top of bars
    for bars in [bars_p, bars_r, bars_f]:
        for bar in bars:
            h = bar.get_height()
            ax.text(bar.get_x() + bar.get_width() / 2, h + 0.001,
                    f"{h:.3f}", ha="center", va="bottom", fontsize=6,
                    rotation=90)

    ax.set_xticks(x)
    ax.set_xticklabels(systems, fontsize=8)
    ax.set_ylabel("Score")
    ax.set_ylim(0.85, 1.025)
    ax.legend(fontsize=8)

    # Highlight PhishGuard column
    ax.axvspan(2.6, 3.4, color="yellow", alpha=0.08, zorder=0)

    save_fig(fig, "fig_baseline_comparison")


# ---------------------------------------------------------------------------
# Figure 8: Intent per-label F1 horizontal bar chart
# ---------------------------------------------------------------------------
def fig_intent_per_label():
    il = load_json("intent_labels_eval.json")
    per_label = il["phish_only_eval"]["per_label"]
    macro_f1 = il["phish_only_eval"]["macro_avg"]["f1"]

    labels_order = [
        "credential_harvesting",
        "payment_fraud",
        "threat_language",
        "impersonation",
    ]
    f1_vals = [per_label[l]["f1"] for l in labels_order]
    support = [per_label[l]["support"] for l in labels_order]

    # Color by support (darker = more support)
    max_sup = max(support)
    colors = [plt.cm.Blues(0.3 + 0.6 * (s / max_sup)) for s in support]

    fig, ax = plt.subplots(figsize=SINGLE_COL)
    bars = ax.barh(labels_order, f1_vals, color=colors, edgecolor="white")

    # Support annotations
    for bar, sup in zip(bars, support):
        ax.text(bar.get_width() + 0.01, bar.get_y() + bar.get_height() / 2,
                f"(n={sup})", va="center", fontsize=7)

    # Macro avg vertical line
    ax.axvline(macro_f1, color="#C44E52", linewidth=1.5, linestyle="--",
               label=f"Macro avg F1={macro_f1:.4f}")

    ax.set_xlabel("F1 score")
    ax.set_xlim(0.0, 1.15)
    ax.set_title("Intent model per-label F1 (weak-label ground truth)", fontsize=8)
    ax.legend(fontsize=7)

    # Footnote
    fig.text(0.05, -0.05,
             "Labels derived from keyword matching — see Section 5.1",
             fontsize=6, style="italic")

    save_fig(fig, "fig_intent_per_label")


# ---------------------------------------------------------------------------
# Figure 9: Staged efficiency dual-axis
# ---------------------------------------------------------------------------
def fig_staged_efficiency():
    se = load_json("staged_efficiency.json")

    thresholds = se["thresholds"]
    trigger_rate_pct = [r * 100 for r in se["stage2_trigger_rate"]]
    savings_pct = se["compute_savings_pct"]

    fig, ax1 = plt.subplots(figsize=SINGLE_COL)
    ax2 = ax1.twinx()

    color1 = "#4C72B0"
    color2 = "#DD8452"

    ax1.plot(thresholds, trigger_rate_pct, color=color1, linewidth=1.8,
             label="Stage 2 trigger rate (%)")
    ax2.plot(thresholds, savings_pct, color=color2, linewidth=1.8,
             linestyle="--", label="Compute savings (%)")

    # Vertical lines at canonical points
    for tau, label_text in [(0.25, "τ=0.25"), (0.90, "τ=0.90")]:
        ax1.axvline(tau, color="gray", linewidth=1.0, linestyle=":", alpha=0.7)

    # Annotate τ=0.90 savings
    idx_090 = thresholds.index(0.9)
    ax2.annotate(
        "76.8% of emails\nbypass Stage 2",
        xy=(0.9, savings_pct[idx_090]),
        xytext=(-60, -25),
        textcoords="offset points",
        fontsize=6.5,
        color=color2,
        arrowprops=dict(arrowstyle="->", color=color2, lw=0.8),
    )

    ax1.set_xlabel("Decision threshold τ")
    ax1.set_ylabel("Stage 2 trigger rate (%)", color=color1)
    ax2.set_ylabel("Compute savings (%)", color=color2)
    ax1.tick_params(axis="y", labelcolor=color1)
    ax2.tick_params(axis="y", labelcolor=color2)

    # Combined legend
    lines1, labels1 = ax1.get_legend_handles_labels()
    lines2, labels2 = ax2.get_legend_handles_labels()
    ax1.legend(lines1 + lines2, labels1 + labels2, fontsize=7, loc="center right")

    save_fig(fig, "fig_staged_efficiency")


# ---------------------------------------------------------------------------
# Figure 10: 5-fold cross-validation error bar
# ---------------------------------------------------------------------------
def fig_crossval():
    cv = load_json("crossval.json")
    mean = cv["mean"]
    std = cv["std"]

    metrics_main = ["precision", "recall", "f1"]
    labels_main = ["Precision", "Recall", "F1"]
    means_main = [mean[m] for m in metrics_main]
    stds_main = [std[m] for m in metrics_main]

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=DOUBLE_COL)

    x_main = np.arange(len(metrics_main))
    ax1.bar(x_main, means_main, yerr=stds_main, color="#4C72B0", alpha=0.8,
            capsize=4, edgecolor="white", error_kw={"elinewidth": 1.5})
    ax1.set_xticks(x_main)
    ax1.set_xticklabels(labels_main)
    ax1.set_ylabel("Score")
    ax1.set_ylim(0.97, 1.005)
    ax1.set_title("5-fold CV: P / R / F1", fontsize=9)
    for i, (m, s) in enumerate(zip(means_main, stds_main)):
        ax1.text(i, m + s + 0.0003, f"{m:.4f}\n±{s:.4f}",
                 ha="center", fontsize=6.5)

    # FPR subplot
    fpr_mean = mean["fpr"]
    fpr_std = std["fpr"]
    ax2.bar([0], [fpr_mean], yerr=[fpr_std], color="#C44E52", alpha=0.8,
            capsize=4, edgecolor="white", error_kw={"elinewidth": 1.5})
    ax2.set_xticks([0])
    ax2.set_xticklabels(["FPR"])
    ax2.set_ylabel("False positive rate")
    ax2.set_ylim(0, 0.01)
    ax2.set_title("5-fold CV: FPR", fontsize=9)
    ax2.text(0, fpr_mean + fpr_std + 0.0001,
             f"{fpr_mean:.4f}\n±{fpr_std:.4f}",
             ha="center", fontsize=6.5)

    plt.tight_layout()
    save_fig(fig, "fig_crossval")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    setup_paper_style()
    print("Generating paper figures...")

    print("\nFigure 1: Stage 1 latency histogram")
    fig_latency_stage1()

    print("Figure 2: Latency comparison box plot")
    fig_latency_comparison()

    print("Figure 3: ROC curve")
    fig_roc_curve()

    print("Figure 4: PR curve")
    fig_pr_curve()

    print("Figure 5: Threshold sensitivity")
    fig_threshold_sensitivity()

    print("Figure 6: Confusion matrix")
    fig_confusion_matrix()

    print("Figure 7: Baseline comparison")
    fig_baseline_comparison()

    print("Figure 8: Intent per-label F1")
    fig_intent_per_label()

    print("Figure 9: Staged efficiency")
    fig_staged_efficiency()

    print("Figure 10: Cross-validation")
    fig_crossval()

    print("""
Generated figures:
  evaluation/figures/fig_latency_stage1.pdf
  evaluation/figures/fig_latency_comparison.pdf
  evaluation/figures/fig_roc_curve.pdf
  evaluation/figures/fig_pr_curve.pdf
  evaluation/figures/fig_threshold_sensitivity.pdf
  evaluation/figures/fig_confusion_matrix.pdf
  evaluation/figures/fig_baseline_comparison.pdf
  evaluation/figures/fig_intent_per_label.pdf
  evaluation/figures/fig_staged_efficiency.pdf
  evaluation/figures/fig_crossval.pdf
""")


if __name__ == "__main__":
    main()
