# RESIDUAL LEARNING THEORY

## 1. Overview in Latency Decomposition Context

This note formalizes *why* it is statistically and mathematically valid to split our modeling problem into two independent stages — Stage 1 (Linear/Quantile Regression) fitting `packet_size → RTT`, and Stage 2 (XGBoost) fitting `features → residual` — rather than training a single end-to-end model directly on raw RTT.

The entire Hybrid Residual Architecture rests on one core mathematical claim, and this note exists to justify it rigorously rather than assume it:

> **Claim:** If Stage 1 correctly captures the deterministic physical component of RTT, then the leftover residual contains (almost) exclusively the stochastic queuing component, and can be modeled by Stage 2 as an independent, self-contained regression problem.

Every subsection below either proves a piece of this claim, states the precise conditions under which it holds, or explicitly documents where it breaks down and what happens if it does.

---

## 2. The General Theory of Residual Modeling

### 2.1 Definition of a Residual

Given any fitted model $\hat{f}$ that produces a prediction $\hat{y}_i = \hat{f}(x_i)$ for a true observed value $y_i$, the **residual** is defined as:

$$
r_i = y_i - \hat{f}(x_i)
$$

A residual is, by construction, whatever the first model **failed to explain**. It is not a new independent quantity invented for convenience — it is a mathematically exact remainder.

### 2.2 The Additive Decomposition Identity

For our project, the true total latency is (per `01_latency.md`):

$$
\text{RTT}_{\text{actual}} = D_{\text{prop}} + D_{\text{trans}} + D_{\text{proc}} + D_{\text{queue}}
$$

Stage 1 produces an estimate of the deterministic sum of physical components:

$$
\text{RTT}_{\text{physical\_predicted}} = \hat{\beta}_0 + \hat{\beta}_1 \cdot \text{packet\_size} \approx \underbrace{(D_{\text{prop}} + D_{\text{proc}})}_{\hat{\beta}_0} + \underbrace{D_{\text{trans}}}_{\hat{\beta}_1 \cdot \text{packet\_size}}
$$

By simple algebraic rearrangement of the identity above:

$$
\text{Residual} = \text{RTT}_{\text{actual}} - \text{RTT}_{\text{physical\_predicted}} = D_{\text{queue}} + \underbrace{\left[(D_{\text{prop}} + D_{\text{proc}}) - \hat{\beta}_0\right] + \left[D_{\text{trans}} - \hat{\beta}_1 \cdot \text{packet\_size}\right]}_{\text{Stage 1 estimation error}}
$$

This equation is the single most important fact in this note. It shows explicitly that the residual is **not purely** $D_{\text{queue}}$ — it is $D_{\text{queue}}$ **plus whatever error Stage 1 made** in estimating the physical baseline and slope. This is why Section 4 (Error Propagation) and Section 6 (Failure Modes) exist: the validity of Stage 2 is entirely conditional on Stage 1's estimation error being small and, more importantly, small in a specific *structured* way (not just small on average).

### 2.3 Why Split the Problem At All? (The Formal Justification)

A single end-to-end model (e.g., one XGBoost model trained directly on raw RTT using all features including `packet_size`) would in principle be *capable* of learning the same total function, since $D_{\text{trans}}$ is itself just a function of `packet_size`. So why not skip Stage 1 entirely?

Three concrete, provable reasons:

1. **Sample efficiency for the deterministic part.** The relationship $D_{\text{trans}} = L/R$ is *exactly* linear (a physical law, not an empirical pattern). A linear model can learn an exact linear relationship from a very small number of samples with a closed-form solution and zero approximation error (beyond noise). A tree ensemble must instead *approximate* a straight line using a staircase of axis-aligned splits, requiring many more splits/trees to achieve the same precision, and it can never represent the line exactly — only approximate it arbitrarily closely. Wasting model capacity approximating a known-exact linear function is inefficient and, more importantly, means that any regularization or pruning of the tree model (Section 4.5 of `11_xgboost_fundamentals.md`) will bias precisely the physical constant we most need to be unbiased.
2. **Interpretability of the physical parameters.** Stage 1's coefficients ($\hat\beta_0$, $\hat\beta_1$) map directly onto physically meaningful quantities — baseline latency and inverse bandwidth (see `10_quantile_regression_envelope.md`, Section 4). A single end-to-end tree ensemble produces no such interpretable coefficients; the physical parameters would be smeared implicitly across hundreds of tree splits with no way to extract them.
3. **Isolating the true target of scientific interest.** The project's actual research target is $D_{\text{queue}}$ — the congestion signal — not raw RTT. Forcing a single model to predict raw RTT means it will spend capacity fitting the (easy, deterministic) physical component and may under-fit the (hard, stochastic) congestion component, since standard loss functions (e.g., mean squared error) will be dominated by whichever term has larger scale/variance, not the term we care about scientifically.

This is a specific case of a broader technique in applied statistics called **orthogonalization** or **partialling out** (well known in econometrics, e.g., the Frisch–Waugh–Lovell theorem for linear regression): when a model contains one component that is well-understood and cheaply estimable, and another that is the true object of interest, isolating the well-understood component first and analyzing the remainder in isolation is both statistically valid and yields a cleaner estimate of the object of interest — **provided the first-stage estimator is well-specified**, which is the entire subject of Section 3.

---

## 3. The Formal Conditions for Validity

Residual modeling is a two-stage estimation procedure, and it is only valid under specific conditions. Below are the conditions, stated explicitly, so it is clear when the architecture works and when it silently produces corrupted results.

### 3.1 Condition 1 — Correct Functional Form in Stage 1

Stage 1 assumes $\text{RTT}_{\text{physical}} = \beta_0 + \beta_1 \cdot \text{packet\_size}$ is the correct functional form for the deterministic component.

- **This is true by physical law** for transmission delay ($D_{\text{trans}} = L/R$, exactly linear in $L$ — see `03_transmission_delay.md`).
- **This is an approximation** for the $(D_{\text{prop}} + D_{\text{proc}})$ baseline, which is assumed constant (independent of packet size) — a reasonable assumption per `02_propagation_delay.md` (propagation is independent of packet size) and `05_processing_delay.md` (processing delay is small and roughly constant for a fixed router architecture and packet type).
- **If this condition fails** (e.g., if processing delay itself scaled with packet size, which it does not under standard architectures per `05_processing_delay.md`), Stage 1's residual would absorb this missing non-linearity, and Stage 2 would incorrectly attribute physical model misspecification to congestion.

### 3.2 Condition 2 — Unbiased Estimation of the Physical Floor (Why OLS Is Insufficient)

Even granting the correct functional form, the *method* used to estimate $\beta_0, \beta_1$ must not itself be biased by the presence of $D_{\text{queue}}$ in the training data.

This is formally proven and explained in full in `10_quantile_regression_envelope.md`, Section 2: **Ordinary Least Squares is provably biased** here because $D_{\text{queue}} \geq 0$ always (queuing can only add delay, never subtract it — see `04_queuing_delay.md`), which violates the classical linear regression assumption that noise is symmetric and mean-zero. This is precisely why quantile regression at $\tau = 0.05$ is used instead of OLS. **Residual learning theory is only valid to the extent that Stage 1's estimation method correctly targets the zero-congestion floor, not the conditional mean.** This is not a stylistic choice — using OLS at Stage 1 would systematically inflate $\hat\beta_0$ and bias $\hat\beta_1$ (per `10_quantile_regression_envelope.md`, Section 2), causing the residual computed in Section 2.2 above to contain a *systematic negative bias* baked into every single observation, not just random noise. A systematically biased residual is far more dangerous to Stage 2 than a noisy one, because Stage 2's trees will learn to "correct" for a constant offset using spurious feature correlations, contaminating the interpretability of every downstream feature importance.

### 3.3 Condition 3 — Residual Independence from the Stage 1 Input Feature

For the two-stage decomposition to be statistically clean, the residual should be **approximately uncorrelated with `packet_size`** (the feature Stage 1 was fit on). If a residual-vs-`packet_size` scatter plot still shows a visible slope or curve, this is direct evidence that Stage 1 has *not* fully captured the transmission-delay relationship, and some portion of $D_{\text{trans}}$ is leaking into what is supposed to be a pure $D_{\text{queue}}$ signal.

- **Diagnostic check (must be run before trusting Stage 2 results):** plot the Stage 1 residuals against `packet_size`. A flat cloud with no trend confirms Condition 3 holds. A residual trend that changes slope at different packet sizes suggests Stage 1's quantile envelope was mis-fit (e.g., due to insufficient data at certain packet-size bins) or that TCP's variable header overhead (see `09_protocol_comparison.md`, Section 2 — "TCP: Dynamic Overhead Distortion") is injecting size-correlated noise that a simple linear fit cannot fully remove.

### 3.4 Condition 4 — No Leakage of Stage 2 Features into Stage 1

Stage 1 is fit using only `packet_size` as the independent variable. It is critical that no feature intended for Stage 2 (traffic volume, time-of-day, protocol flags) is included in Stage 1's fitting process. If Stage 2 features were somehow used to help fit Stage 1 (directly or indirectly, e.g., by filtering training data based on a Stage 2 feature), the resulting residual would no longer represent "whatever Stage 1 couldn't explain" independent of those features — it would represent something artificially decorrelated from them, and Stage 2 would then systematically underestimate the true predictive power of those features. This is a specific instance of a general data-leakage failure mode: **information must flow strictly from Stage 1's inputs into Stage 1's model only**, and Stage 2 must be free to use any remaining feature without contamination.

---

## 4. Error Propagation: How Stage 1 Mistakes Contaminate Stage 2

This section makes the consequence of Section 2.2's decomposition equation fully explicit, because it is the single greatest risk in this architecture.

### 4.1 The General Principle

In any two-stage estimation pipeline, errors from the first stage do not disappear — they are carried forward and become part of the input (or target) for the second stage. This is a well-known phenomenon in statistics sometimes referred to as the **"generated regressor problem"** or, in our case, a **"generated target problem"**, since Stage 2's *target variable itself* (the residual) is not observed directly but is *generated* from Stage 1's fitted values.

### 4.2 Types of Stage 1 Error and Their Effect on Stage 2

| Type of Stage 1 Error | Mathematical Source | Effect on Stage 2 Residual Target |
| :--- | :--- | :--- |
| **Constant bias** (intercept shifted up or down) | Wrong quantile $\tau$ chosen, or insufficient low-traffic samples to find the true floor | Every residual is shifted by the same constant amount — Stage 2 will learn a spurious "baseline offset" feature-independent bias, inflating or deflating all predicted $D_{\text{queue}}$ values uniformly |
| **Slope bias** (wrong $\hat\beta_1$) | OLS contamination (Condition 2), or TCP header-size noise (Condition 3) | Residual magnitude becomes artificially correlated with `packet_size` — Stage 2 may spuriously learn that "larger packets predict more congestion" even when the true cause is an under- or over-estimated bandwidth slope |
| **Regime misspecification** | A single global Stage 1 model fit across a period containing a mid-experiment routing change (see `10_quantile_regression_envelope.md`, Section 5 — "India Envelope") | Residuals in the post-change period will all carry a large constant offset that has nothing to do with real-time congestion, corrupting any time-series feature Stage 2 tries to learn (see `13_time_series_cross_validation.md`, planned) |
| **Variance underestimation** | Overly aggressive quantile ($\tau$ too extreme, e.g., $\tau = 0.01$) picking up a single outlier low-latency reading as the "floor" | Nearly all residuals become artificially inflated (positive), making the entire Stage 2 target distribution non-zero-centered even under genuinely uncongested conditions |

### 4.3 Formal Statement of the Bias Transfer

If Stage 1's true bias is a function $\delta(x) = \hat{f}_1(x) - f_1^{\text{true}}(x)$ (the gap between the fitted physical model and the true physical relationship), then the residual computed for Stage 2 is:

$$
r_i = \left[D_{\text{queue},i}\right] - \delta(x_i)
$$

This shows explicitly: **Stage 2 is never learning $D_{\text{queue}}$ directly — it is learning $D_{\text{queue}} - \delta(x)$.** The entire value of the architecture depends on driving $\delta(x)$ as close to zero (and as close to *constant*, if not zero) as possible in Stage 1, which is precisely the purpose of the quantile regression approach in `10_quantile_regression_envelope.md`.

**Practical implication:** any evaluation of Stage 2's performance (e.g., RMSE on the residual) is only meaningful *relative to a correctly specified Stage 1*. If Stage 1 is refit or changed (e.g., switching quantile $\tau$ from 0.05 to 0.10), Stage 2 must be **completely retrained**, since its target variable itself has changed. Stage 2's model artifact is only valid paired with the exact Stage 1 model that generated its training residuals — the two are not independently swappable.

---

## 5. Why the Residual Is (Approximately) a Valid Independent Regression Target

Having established the conditions under which the decomposition is valid (Section 3) and how violations propagate (Section 4), this section states precisely what statistical properties the residual has *when those conditions hold*, and why this makes it fair game for a completely separate model (XGBoost) with its own separate feature set.

### 5.1 Zero (or Near-Zero) Unconditional Mean at the Floor

If Stage 1 correctly estimates the zero-congestion floor (Condition 2, via quantile regression), then in the subset of observations where true congestion is genuinely near zero, $r_i \approx 0$. This is directly testable: filter the dataset for the lowest-traffic-volume time windows (per passive capture logs) and confirm the residual distribution is tightly centered near zero in that subset. Deviation from zero here is direct evidence of Stage 1 bias (Section 4.2, row 1).

### 5.2 Non-Negativity Bias in the Full (Unfiltered) Distribution

Because $D_{\text{queue}} \geq 0$ always, the *unconditional* residual distribution across the full dataset (including congested periods) should be **right-skewed with a floor near zero** — never meaningfully negative except for small amounts of measurement noise (e.g., NIC timestamp jitter). A residual distribution with a significant negative mass is direct evidence of Stage 1 overestimating the physical floor (Section 4.2, row 4) — this is one of the most important sanity checks to run before trusting any Stage 2 output.

### 5.3 Feature Independence Enables Free Model Selection at Stage 2

Because (under Condition 3) the residual is uncorrelated with `packet_size`, Stage 2 is free to select any model class and any feature set without needing to re-include `packet_size` as a control variable. This is what allows Stage 2 to be a completely different model family (tree ensemble vs. linear) trained on a completely different feature set (traffic/time/protocol vs. packet size) — the two stages are statistically decoupled *specifically because* the residual has had the `packet_size` relationship fully removed.

---

## 6. Failure Modes: What Happens When Residual Learning Theory Breaks Down

This section exists explicitly because the person using this note will not be reviewing it before applying it — these are the scenarios that must be checked for empirically once real data exists, since they cannot be verified from the notes alone.

### 6.1 Failure Mode: Insufficient Low-Congestion Samples

Quantile regression at $\tau = 0.05$ requires that at least ~5% of the dataset genuinely represents near-zero-congestion conditions. If the data collection window happens to coincide with persistently high background traffic (e.g., probes only run during peak evening hours), there may be no genuinely uncongested samples at all, and the "5th percentile" the model fits will actually still contain non-trivial queuing delay, silently violating Condition 2. **Mitigation:** ensure data collection explicitly spans low-traffic hours (e.g., early morning) as well as peak hours, and verify the fitted intercept against an independent sanity check, such as a geographic-distance-based theoretical minimum propagation delay (`02_propagation_delay.md`, Formula section).

### 6.2 Failure Mode: Structural Breaks (Routing Changes Mid-Collection)

As detailed in `10_quantile_regression_envelope.md`, Section 5, a mid-experiment BGP routing change instantaneously shifts the true physical floor. A single Stage 1 model fit across the entire multi-week collection window will average across both the pre-change and post-change floors, producing a hybrid $\hat\beta_0$ that is wrong for both regimes. **Mitigation:** the note's own recommendation — Time-Window Localized Quantile Regression, or explicit segmentation of the dataset using TTL-based route-change detection — must be applied before Stage 2 ever sees the residuals, since Section 4.2 (row 3) shows this failure mode is not something Stage 2 can compensate for; it can only pattern-match around it, which corrupts the interpretability of the resulting model.

### 6.3 Failure Mode: Protocol-Specific Header Overhead Contamination (TCP-Specific)

Per `09_protocol_comparison.md`, Section 2, TCP's variable options (SACK, timestamps, window scaling) mean the same nominal `packet_size` fed into the Scapy probe does not always correspond to the same true wire size. This directly violates Condition 1 (correct functional form) in a subtle way: the independent variable itself has measurement noise. **Mitigation:** the mitigation already specified in `09_protocol_comparison.md` — quantile regression targeting the lowest percentile envelope — partially absorbs this, but it should be explicitly validated by checking whether TCP residuals show higher variance than ICMP/UDP residuals under matched traffic conditions; if so, some of that excess TCP residual variance is header-noise contamination, not real queuing signal, and should be reported as a limitation rather than interpreted as "TCP experiences more congestion."

### 6.4 Failure Mode: Treating Stage 2 Feature Importance as Causal

Even when Conditions 1–4 all hold, Stage 2's XGBoost feature importances describe **predictive association with the residual**, not proven causal influence on true queuing delay. For example, if "target destination ID" ranks as a top feature, this may reflect genuine differences in queuing behavior at different routers, or it may reflect an uncontrolled confounder (e.g., certain destinations were only ever probed at certain times of day due to how the experiment loop was scheduled). **Mitigation:** this is not a flaw unique to residual learning theory, but it is worth stating explicitly here since it is easy to conflate "Stage 2 says feature X matters" with "feature X causes more queuing" — the former is a purely statistical claim, the latter requires controlled experimental design (see planned `20_experimental_design_and_confounds.md`).

---

## 7. Summary: The Precise Chain of Reasoning

1. Total RTT is an additive sum of four physical/logical delay components (`01_latency.md`).
2. A residual is an exact algebraic remainder — whatever Stage 1's model did not explain (Section 2.1–2.2).
3. Splitting into two stages is more sample-efficient, interpretable, and scientifically targeted than a single end-to-end model, *provided* Stage 1 is correctly specified and unbiased (Section 2.3, Section 3).
4. Stage 1's method (quantile regression) is chosen specifically to satisfy the unbiasedness condition, because OLS would violate it due to the inherent non-negativity of queuing delay (Section 3.2, cross-referenced to `10_quantile_regression_envelope.md`).
5. Any bias remaining in Stage 1, however small, is mathematically transferred directly into the residual and therefore into Stage 2's training target — it is never eliminated, only carried forward (Section 4).
6. The residual only becomes a valid, independently-modelable target once empirically verified against the diagnostic checks in Section 5 (zero mean at low congestion, non-negative skew, no correlation with `packet_size`).
7. Several concrete failure modes (Section 6) must be checked against real collected data before any Stage 2 results are trusted or published — this note describes the *theory* of why the architecture is valid, but validity is conditional on diagnostics that can only be run once actual data exists.