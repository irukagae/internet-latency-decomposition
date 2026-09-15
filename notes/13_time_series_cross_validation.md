# TIME SERIES CROSS-VALIDATION

## 1. Overview in Latency Decomposition Context

This note establishes why **standard k-fold cross-validation is statistically invalid** for evaluating or tuning the Stage 2 XGBoost model in this project, and specifies the exact alternative validation scheme that must be used instead.

The core issue is simple to state but easy to violate accidentally: the residual queuing delay target ($D_{\text{queue}}$) is **temporally autocorrelated** — its value at time $t$ is statistically dependent on its value at time $t-1$, $t-2$, etc. (established in `04_queuing_delay.md`, Section "Role in Internet Latency Decomposition Model": *"queuing delay... has memory. If a router buffer is jammed at time $t$, it will likely be jammed at time $t+1$ as well."*). Any validation scheme that ignores this temporal structure will silently leak information from the future into the training process, producing evaluation metrics that look excellent during development but do not reflect real-world predictive performance.

This is not a minor technical detail — it is the single most common way that time-dependent machine learning projects produce misleading, non-reproducible results. This note treats it accordingly.

---

## 2. What Cross-Validation Is For (First Principles)

### 2.1 The Purpose of Any Validation Scheme

The purpose of splitting data into training and validation (or test) sets is to estimate how well a model will perform on **data it has never seen**, as a proxy for future, real-world data the model will encounter after deployment.

For this estimate to be meaningful, one property must hold absolutely:

> **The validation set must be information-independent of the training set, in exactly the same way that future real-world data is information-independent of the training set.**

If the validation set shares any information with the training set that would *not* be available at real prediction time, the resulting validation score is **optimistically biased** — it overstates how well the model will actually perform once deployed.

### 2.2 Standard K-Fold Cross-Validation (and Why It Assumes Independence)

Standard k-fold cross-validation works as follows:

1. The dataset of $n$ observations is randomly shuffled and partitioned into $k$ equally sized folds.
2. For each fold $i \in \{1, \dots, k\}$: train the model on all folds except $i$, and validate on fold $i$.
3. Average the $k$ validation scores to get a final performance estimate.

This procedure is provably valid **if and only if the observations are independent and identically distributed (i.i.d.)** — that is, knowing the value of observation $j$ tells you nothing about the value of any other observation $i \neq j$, regardless of their order.

This i.i.d. assumption is the crux of the entire problem, and it is examined precisely in Section 3.

---

## 3. Why the i.i.d. Assumption Fails for Our Data

### 3.1 Formal Statement of Temporal Autocorrelation

A sequence of observations $\{r_1, r_2, \dots, r_n\}$ (where $r_t$ is the Stage 2 residual target at time $t$) is said to exhibit **autocorrelation** if:

$$
\text{Corr}(r_t, r_{t-k}) \neq 0 \quad \text{for some lag } k > 0
$$

For our project, this is not a theoretical risk — it is a directly documented, physically grounded property of the target variable:

- **Traffic Intensity persistence**: Per `04_queuing_delay.md`, queuing delay is governed by Traffic Intensity $I = \frac{L \cdot a}{R}$. Traffic volume ($a$, arrival rate) does not change instantaneously and randomly from one probe to the next — it follows smooth patterns (diurnal cycles, sustained downloads, video streaming sessions) that persist across many consecutive seconds or minutes. If $I$ is high at time $t$, it is highly likely to still be elevated at time $t + 1\text{s}$.
- **Bufferbloat persistence**: Per `04_queuing_delay.md`'s discussion of bufferbloat, once a router's buffer fills due to a sustained large transfer, it tends to *stay* full for the duration of that transfer, meaning consecutive probes sent during that window will all show elevated queuing delay together, not independently.
- **TCP congestion window dynamics**: Per `06_tcp_protocol.md`, Section 3, TCP's Congestion Window ($cwnd$) evolves gradually and continuously over time (linear growth during congestion avoidance). The queuing state driven by a TCP flow at time $t$ is mechanically linked to its state at time $t - 1$ through this window evolution — it cannot jump arbitrarily between probes.
- **Time-of-day cyclicity**: Both the roadmap (`README.md`, Phase 2) and `09_protocol_comparison.md` explicitly reference time-of-day as a first-class feature, precisely because network load follows predictable diurnal cycles. Any two observations taken within the same "regime" (e.g., both during a peak evening congestion window) will be more similar to each other than to an observation taken during an overnight low-traffic window — this is autocorrelation at a coarser (hourly/daily) timescale, in addition to the fine-grained (second-to-second) timescale described above.

### 3.2 The Formal Consequence: Why Random Shuffling Leaks Information

If observations are autocorrelated, then a randomly shuffled k-fold split will almost certainly place some observations from time $t$ into the training set and their **temporal neighbors** (time $t+1$, $t-1$, or observations from the same sustained congestion episode) into the validation set (or vice versa).

Because $r_t$ and $r_{t+1}$ are correlated (Section 3.1), the model is effectively being validated on data that is statistically "close to" data it has already memorized during training. The validation fold is not truly "unseen" in the way genuinely future, out-of-sample data will be — it has an information leak through the temporal correlation channel.

**Formally:** the validation error estimated this way is a biased (optimistic) estimate of the true **generalization error** the model will exhibit on genuinely future data, because standard k-fold cross-validation's validity proof depends critically on the i.i.d. assumption from Section 2.2, and that assumption is violated.

### 3.3 A Concrete Illustration of the Leak

Suppose the passive capture logs a sustained large file download between 14:32:00 and 14:34:00, causing elevated queuing delay across dozens of consecutive active probes taken during that two-minute window.

Under random k-fold shuffling, roughly $\frac{k-1}{k}$ of those probes end up in the training set and the rest in a validation fold — meaning the model, at validation time, has already seen dozens of near-identical "high congestion, same download event" examples during training. It does not need to have learned a genuine predictive relationship between traffic features and queuing delay; it can succeed on the validation fold simply by recognizing that "this looks like the same event I trained on ten seconds ago." This produces an artificially low validation error that will **not** replicate once the model is deployed and must predict queuing delay for events it has genuinely never encountered before.

---

## 4. The Correct Alternative: Time-Ordered (Walk-Forward) Validation

### 4.1 Core Principle

The validation scheme must enforce one strict rule at all times:

> **No observation in the validation set may ever be used to inform a prediction for an observation in the training set that occurred earlier in time, and no training observation may occur later in time than any validation observation it is being evaluated against.**

In plain terms: **the model can only ever be validated on data that comes strictly after the data it was trained on** — mirroring exactly how the model will actually be used in the real world (trained on past data, deployed to predict future, not-yet-observed events).

### 4.2 Method 1 — Simple Chronological Train/Validation/Test Split

The simplest valid approach: sort the entire dataset by timestamp, then split it into three **contiguous, non-overlapping, chronologically ordered** blocks:

$$
\underbrace{[t_0, \dots, t_{\text{train\_end}}]}_{\text{Training (e.g., first 70\%)}} \quad \underbrace{[t_{\text{train\_end}}, \dots, t_{\text{val\_end}}]}_{\text{Validation (e.g., next 15\%)}} \quad \underbrace{[t_{\text{val\_end}}, \dots, t_n]}_{\text{Test (final 15\%)}}
$$

- The **training set** is used to fit the model.
- The **validation set** is used for hyperparameter tuning (Section 6 of `11_xgboost_fundamentals.md`: `max_depth`, `learning_rate`, `n_estimators`) and for `early_stopping_rounds`.
- The **test set** is touched exactly once, at the very end, to report the final, honest generalization performance estimate. It must never be used to make any modeling decision (no hyperparameter tuning based on test performance, no re-fitting after inspecting test results).

**This is precisely the requirement flagged in `11_xgboost_fundamentals.md`, Section 6.6**, which states early stopping's validation split "must be a chronological holdout... never a random shuffle-based split" — this note formalizes exactly why that requirement exists.

### 4.3 Method 2 — Walk-Forward (Expanding Window) Cross-Validation

A single chronological split (Section 4.2) only produces one validation estimate, which can be noisy, particularly for a project with a limited multi-week data collection window (per `README.md`'s roadmap). **Walk-forward validation** generalizes the idea to produce multiple validation folds while still strictly respecting temporal order.

The dataset is split into $k$ sequential folds. For fold $i = 1, \dots, k-1$:

$$
\text{Train on: } \{t_0, \dots, t_i\} \qquad \text{Validate on: } \{t_{i+1}\}
$$

Each successive fold **expands** the training window to include everything up through the previous validation fold, then validates on the next chronological block. This is visualized as:

```
Fold 1: [ TRAIN ][ VALIDATE ]
Fold 2: [ TRAIN ][ VALIDATE ]
Fold 3: [ TRAIN ][ VALIDATE ]
Fold 4: [ TRAIN ][ VALIDATE ]
(time →)
```


The final reported metric is the average (or distribution) of validation scores across all $k-1$ folds, giving both a more stable estimate and a sense of how performance varies as more historical data becomes available for training — directly relevant here, since data collection is ongoing per the project roadmap and the model's validation performance should be expected to change as the training window grows.

### 4.4 Method 3 — Sliding (Rolling) Window Cross-Validation

A variant of Method 2 where, instead of the training window **expanding** indefinitely, it **slides** forward, keeping a fixed-size training window and discarding the oldest data as new data is added:

```
Fold 1: [ TRAIN ][ VALIDATE ]
Fold 2: [ TRAIN ][ VALIDATE ]
Fold 3: [ TRAIN ][ VALIDATE ]
Fold 4: [ TRAIN ][ VALIDATE ]
(time →)
```


**When to prefer this over the expanding-window method (Section 4.3):** if the underlying network conditions are believed to be **non-stationary** over long timescales — for example, if an ISP infrastructure upgrade occurs mid-collection, or a persistent BGP routing change alters the baseline path (directly referenced as a real risk in `10_quantile_regression_envelope.md`, Section 5, "India Envelope"). In such cases, training on very old data (from before the structural change) may actively *hurt* the model's ability to predict current conditions, since the relationship between features and the residual target may have fundamentally shifted. A sliding window naturally "forgets" data old enough to reflect an outdated network regime, whereas an expanding window keeps diluting the training set with old, possibly-now-irrelevant data.

### 4.5 Choosing a Fold/Window Boundary Granularity

A critical, easy-to-miss detail: the fold boundaries in Sections 4.3–4.4 should **not** be drawn at arbitrary observation-count boundaries (e.g., "every 1,000 rows"). Because probes are collected in rapid controlled sweeps (per `06_tcp_protocol.md`/`07_icmp_protocol.md`/`08_udp_protocol.md`, which describe sweeping payload sizes across many packets within a short experiment run), an observation-count-based split can still cut a single active congestion episode in half, placing part of it in training and part in validation — reintroducing exactly the leakage problem this note exists to prevent, just at a smaller scale.

**Correct approach:** define fold boundaries using **calendar time gaps** (e.g., "every 6 hours" or "every calendar day"), not row counts. This ensures each fold boundary falls in a genuine temporal gap between distinct experiment runs, rather than mid-sweep.

---

## 5. Interaction With Data Leakage From Feature Engineering

Time-ordered validation splitting is necessary but **not sufficient** on its own — it must be paired with equally careful handling of any features that are themselves computed using rolling windows, or the leakage this note addresses will simply re-enter through the back door.

### 5.1 The Rolling-Feature Leakage Risk

Per the project roadmap (`README.md`, Phase 2 / `areas` roadmap), planned Stage 2 features include **rolling window features** — e.g., "mean passive traffic volume over the last 1–5 minutes" (referenced directly in `04_queuing_delay.md`'s discussion of $D_{\text{queue}}$'s residual "memory," and in `09_protocol_comparison.md`'s discussion of TCP residual feature priority).

Any rolling feature computed for an observation at time $t$ **must only use data strictly prior to $t$** (a "causal" or "backward-looking" rolling window). If a rolling feature is accidentally computed using a **centered** window (common in naive implementations, e.g., pandas' default `rolling()` combined with careless indexing, or any window that includes samples *after* $t$), the feature itself leaks future information directly into the training row for time $t$ — a leak that exists independently of, and in addition to, the train/validation split leak described in Sections 2–3. This would corrupt results even under a perfectly correct walk-forward validation scheme, because the leak is baked into the feature value itself before the split ever happens.

**Mitigation:** every rolling/windowed feature must be computed using an explicitly backward-only window (e.g., pandas' `.rolling(window=W, closed='left')` or equivalent, applied to data sorted strictly by timestamp, with careful attention to whether the window function's boundary convention includes or excludes the current timestamp).

### 5.2 Global Statistics Leakage

A more subtle version of the same problem: if any feature or preprocessing step uses a **global** statistic computed across the *entire* dataset (e.g., normalizing traffic volume by "the mean traffic volume across the whole collection period," or one-hot-encoding destination IDs based on categories observed across the whole dataset including future dates), this implicitly leaks whole-dataset information — including future information — into every single training row, regardless of how the train/validation split itself is structured.

**Mitigation:** any such statistic (scaling parameters, category encodings, imputation values) must be computed **only on the training portion** of each fold, then applied unchanged to that fold's validation portion — never computed once on the full dataset up front. This must be repeated independently for every fold in a walk-forward scheme (Section 4.3), since the training portion itself grows/changes fold to fold.

---

## 6. Diagnostic Checks to Confirm the Validation Scheme Is Working Correctly

Since this note will not be manually reviewed before being used to guide implementation, the following concrete checks should be run against real collected data to confirm the validation approach was implemented correctly, rather than trusting the implementation by construction:

1. **Timestamp monotonicity check**: before splitting, explicitly assert that every timestamp in the training set is strictly less than every timestamp in the corresponding validation set, for every fold. This is a simple, mechanical check that catches an incorrectly implemented split (e.g., an accidental `shuffle=True` left over from a generic ML template) immediately.
2. **Validation score sanity comparison**: fit the same model once using a correct time-ordered split and once using a naive random k-fold split (Section 2.2) purely as a diagnostic (never as the basis for the reported result). If the random-split validation score is substantially better than the time-ordered validation score, this confirms the autocorrelation-driven leakage described in Section 3 is present and material for this dataset — and the time-ordered score is the one that should be trusted and reported.
3. **Rolling feature backward-only check**: for a small manually inspected sample of rows, manually verify that the value of any rolling-window feature at time $t$ does not change when future rows (after $t$) are removed from the dataset. If it does change, the window is not strictly backward-looking (Section 5.1).
4. **Fold boundary alignment check**: confirm that no fold boundary (Section 4.5) falls strictly inside a contiguous block of probes belonging to the same experiment sweep (identifiable via the experiment run ID logged by `src/collection/persistence/csv_writer.py`).

---

## 7. Summary: The Precise Chain of Reasoning

1. Standard k-fold cross-validation is only valid under an i.i.d. assumption on the data (Section 2.2).
2. Our target variable, queuing delay, is provably autocorrelated in time due to traffic intensity persistence, bufferbloat persistence, and TCP congestion window dynamics — all independently documented in this project's own existing notes (Section 3.1).
3. This autocorrelation means random shuffling leaks temporally adjacent (and therefore statistically similar) observations across the train/validation boundary, producing an optimistically biased performance estimate that will not replicate at deployment (Section 3.2–3.3).
4. The correct fix is to enforce strict chronological ordering between training and validation data, via either a single chronological split (Section 4.2), walk-forward expanding-window validation (Section 4.3), or sliding-window validation if the underlying network regime is suspected to be non-stationary (Section 4.4).
5. Fold boundaries must be chosen using calendar-time gaps aligned with actual experiment run boundaries, not arbitrary row counts (Section 4.5).
6. Correct train/validation splitting is necessary but not sufficient — rolling-window features and any globally computed statistics must also be constructed using strictly backward-looking, fold-specific logic, or leakage re-enters through feature engineering regardless of how the split itself is done (Section 5).
7. A concrete set of diagnostic checks (Section 6) should be run against real collected data to confirm the validation scheme was implemented as intended, since implementation bugs in this area are common and easy to miss by inspection alone.

