# FEATURE ENGINEERING: CYCLIC TIME ENCODING

## 1. Overview in Latency Decomposition Context

This note specifies exactly how time-of-day must be encoded as a numeric feature for Stage 2 (XGBoost), and proves precisely why the naive approach — feeding raw hour-of-day (0–23) or minute-of-day (0–1439) directly into the model as a single integer — is fundamentally broken for this project's data, along with the correct alternative and how to implement and verify it.

Time-of-day is not a cosmetic feature here. Per `README.md`'s Phase 2 roadmap and `09_protocol_comparison.md`'s discussion of Stage 2 feature priority, time-of-day is a first-class predictor of queuing delay, because network traffic volume follows strong diurnal cycles (office hours, evening streaming peaks, overnight lulls) that directly drive Traffic Intensity ($I = \frac{L \cdot a}{R}$, per `04_queuing_delay.md`). If this feature is encoded incorrectly, the model does not merely lose a little accuracy — it is handed a structurally false signal that actively contradicts the true behavior of the network, as proven in Section 2.

---

## 2. The Problem: Why Raw Numeric Time Encoding Is Broken

### 2.1 The Naive Approach

The most intuitive way to represent "time of day" as a feature is to extract the hour (or minute, or second) from a timestamp and pass it directly to the model as an integer:

$$
\text{hour\_raw} \in \{0, 1, 2, \dots, 23\}
$$

This looks harmless. It is not.

### 2.2 The Core Flaw: False Discontinuity at the Wrap-Around Boundary

Clock time is **cyclic** — it wraps around every 24 hours. But the integers $\{0, 1, \dots, 23\}$ used to represent it are **linear** — they do not wrap around; they simply stop and restart. This creates a mismatch between the true geometry of the underlying phenomenon (a circle) and the geometry of its numeric representation (a line segment).

Concretely: 11:59 PM (`hour_raw = 23`) and 12:01 AM (`hour_raw = 0`) are **two minutes apart in real time**, and should therefore be treated by any model as nearly identical in terms of their effect on traffic patterns (both are deep in the overnight low-traffic period). But under raw numeric encoding:

$$
|\text{hour\_raw}(23) - \text{hour\_raw}(0)| = |23 - 0| = 23
$$

This is the **maximum possible distance** on the entire 0–23 scale — mathematically, the model is told these two moments in time are as different from each other as it is possible for two hours to be, when in reality they are two minutes apart and functionally identical from a network-traffic perspective.

### 2.3 Why This Specifically Breaks a Tree-Based Model Like XGBoost

It might seem like this problem only affects models that assume smooth, continuous relationships (like linear regression). It does not spare XGBoost, and the reason is specific to how trees split data.

Recall from `11_xgboost_fundamentals.md`, Section 2.1: a decision tree splits a feature by choosing a **threshold** (e.g., "is `hour_raw` > 12?") and partitions the data into everything below the threshold and everything above it. A tree can express **any number of separate threshold splits** on a single feature, so in principle a tree *could* learn to treat both very-low integers (0, 1, 2) and very-high integers (21, 22, 23) as belonging to the same "overnight" category — by creating two separate leaves that both output a low congestion prediction.

**However, this is inefficient and fragile in practice, for two concrete reasons:**

1. **It requires the tree to "discover" the wrap-around pattern independently, using extra splits and extra tree depth, for every single tree in the ensemble.** Each of the (potentially hundreds of) trees in the XGBoost ensemble must independently re-learn "0–2 and 21–23 behave the same" using two separate branches, rather than this fact being built into the feature's geometry from the start. This wastes model capacity and increases the risk of overfitting (per `11_xgboost_fundamentals.md`, Section 6.2 — deeper/more fragmented trees increase variance).
2. **It requires enough training data at both ends of the range to independently discover the pattern twice.** If the low-traffic overnight period is under-represented in the collected dataset (a realistic risk, since data collection is more likely to run during a researcher's normal waking hours per the project's actual operating pattern), the tree may simply never see enough examples near `hour_raw = 0` or `hour_raw = 23` to learn the wrap-around relationship at all, and will instead treat them as two unrelated, sparsely-supported edge cases.

The correct fix does not ask the model to discover the cyclic structure from data — it **encodes the cyclic structure directly into the feature's geometry**, so that the true real-world distance between any two times of day is faithfully reflected in the numeric distance between their feature values, before the model ever sees a single training row.

---

## 3. The Correct Solution: Sine/Cosine (Circular) Encoding

### 3.1 The Core Idea

Instead of representing time-of-day as a single point on a line, represent it as a single point on a **circle** — specifically, on the unit circle in a 2-dimensional plane. Every moment in the 24-hour cycle maps to a unique angle around that circle, and the position on the circle is captured using two coordinates: sine and cosine.

### 3.2 The Formula

Given a raw hour value $h \in [0, 24)$ (this generalizes cleanly to finer granularity, e.g., $h \in [0, 24)$ computed as `hour + minute/60 + second/3600` for sub-hour precision — see Section 3.5), the cyclic encoding produces **two** features:

$$
\text{hour\_sin} = \sin\left(\frac{2\pi h}{24}\right)
$$

$$
\text{hour\_cos} = \cos\left(\frac{2\pi h}{24}\right)
$$

Where:

- $h$ → the raw time-of-day value, on a 24-hour scale
- $\frac{2\pi h}{24}$ → converts $h$ into an **angle in radians**, where a full 24-hour cycle maps exactly onto a full $2\pi$ radian rotation around the circle (i.e., $h = 0$ maps to angle $0$, and $h = 24$ maps to angle $2\pi$, which is the same point on the circle as angle $0$ — this is precisely the wrap-around property being enforced)
- $\sin(\cdot)$ and $\cos(\cdot)$ → the standard trigonometric functions, which convert the angle into the $y$-coordinate and $x$-coordinate (respectively) of the corresponding point on the unit circle

### 3.3 Formal Proof That This Solves the Wrap-Around Problem

The critical property to verify is that $h = 0$ (midnight) and $h = 24$ (also midnight, one full cycle later) map to the **exact same point**, and that $h = 23.97$ (11:59 PM) and $h = 0.017$ (12:01 AM) map to **nearly identical points**.

**At $h = 0$:**
$$
\text{hour\_sin} = \sin(0) = 0, \qquad \text{hour\_cos} = \cos(0) = 1
$$

**At $h = 24$:**
$$
\text{hour\_sin} = \sin(2\pi) = 0, \qquad \text{hour\_cos} = \cos(2\pi) = 1
$$

These are **identical**, confirming the encoding correctly treats the end of one cycle and the start of the next as the same point — exactly the property that raw integer encoding (Section 2.2) failed to provide.

**At $h = 23.967$ (11:58 PM) and $h = 0.033$ (12:02 AM)** — two moments 4 minutes apart in real time — the corresponding angles are $\frac{2\pi \times 23.967}{24} \approx 6.2745$ rad and $\frac{2\pi \times 0.033}{24} \approx 0.00864$ rad. Because angle is computed modulo $2\pi$, these two angles are separated by only about $0.0174$ radians (roughly 1 degree) once wraparound is accounted for — an extremely small angular distance, correctly reflecting that these two moments are nearly adjacent. Contrast this with the raw-integer encoding's distance of 23 (Section 2.2) for a comparable near-midnight pair — a difference of several orders of magnitude in how "close" the two representations consider the same real-world time gap.

### 3.4 Why Two Features (Sine AND Cosine) Are Both Required — Not Just One

A common mistake is to use only $\sin\left(\frac{2\pi h}{24}\right)$ alone, believing it fully captures the cyclic pattern. This is provably insufficient, and here is the exact reason:

The sine function is not one-to-one (injective) over a full cycle — multiple distinct times of day produce the **same** sine value. For example:

$$
\sin\left(\frac{2\pi \times 6}{24}\right) = \sin\left(\frac{\pi}{2}\right) = 1
$$
$$
\sin\left(\frac{2\pi \times 6}{24}\right) \text{ and, separately: } h = 6 \text{ (6 AM) gives } \sin = 1
$$

More concretely, consider $h = 6$ (6 AM) and $h = 18$ (6 PM):

$$
\sin\left(\frac{2\pi \times 6}{24}\right) = \sin(90°) = 1.0
$$
$$
\sin\left(\frac{2\pi \times 18}{24}\right) = \sin(270°) = -1.0
$$

These differ — good. But now consider $h = 6$ (6 AM) and $h = 6$ again is trivially the same; the real ambiguity is a different pair: $h$ values that are **mirror images across the sine curve's peak**. For example, $h = 3$ and $h = 9$:

$$
\sin\left(\frac{2\pi \times 3}{24}\right) = \sin(45°) \approx 0.707
$$
$$
\sin\left(\frac{2\pi \times 9}{24}\right) = \sin(135°) \approx 0.707
$$

**These two completely different times of day (3 AM and 9 AM) produce the identical sine value.** Using sine alone, the model would be mathematically unable to distinguish 3 AM from 9 AM — a genuinely serious ambiguity, since these represent very different traffic regimes (deep overnight lull vs. morning ramp-up).

**Adding cosine resolves this ambiguity completely**, because sine and cosine are 90 degrees out of phase — where one is ambiguous (flat/repeating), the other is not:

$$
\cos\left(\frac{2\pi \times 3}{24}\right) = \cos(45°) \approx 0.707
$$
$$
\cos\left(\frac{2\pi \times 9}{24}\right) = \cos(135°) \approx -0.707
$$

The cosine values are clearly different ($+0.707$ vs. $-0.707$), so the **pair** $(\sin, \cos)$ together uniquely identifies every distinct point on the 24-hour cycle, with no ambiguity anywhere on the circle. This is a direct consequence of the mathematical fact that $(\sin\theta, \cos\theta)$ is a bijective (one-to-one) mapping from angle $\theta \in [0, 2\pi)$ to a unique point on the unit circle, whereas $\sin\theta$ alone is a many-to-one mapping (exactly the ambiguity demonstrated above).

**Rule, stated plainly: sine and cosine must always be included together as a pair. Never use one without the other for cyclic encoding.**

### 3.5 Generalizing Beyond Hour-of-Day

The exact same technique applies to **any** cyclic time unit relevant to this project, simply by changing the denominator to match that unit's natural period:

| Cyclic Unit | Period | Formula |
| :--- | :--- | :--- |
| Hour of day (whole-hour granularity) | 24 | $\sin\left(\frac{2\pi h}{24}\right), \cos\left(\frac{2\pi h}{24}\right)$ where $h \in [0,24)$ |
| Minute of day (fine granularity, recommended — see Section 4.3) | 1440 | $\sin\left(\frac{2\pi m}{1440}\right), \cos\left(\frac{2\pi m}{1440}\right)$ where $m = h \times 60 + \text{minute} \in [0, 1440)$ |
| Day of week | 7 | $\sin\left(\frac{2\pi d}{7}\right), \cos\left(\frac{2\pi d}{7}\right)$ where $d \in \{0, \dots, 6\}$ |
| Day of year (for seasonal patterns, if collection spans months) | 365 (or 365.25 to account for leap years) | $\sin\left(\frac{2\pi j}{365.25}\right), \cos\left(\frac{2\pi j}{365.25}\right)$ where $j$ is day-of-year |

**Relevance of day-of-week to this project:** per the roadmap in `README.md`, data collection is planned across multiple weeks. Weekday vs. weekend traffic patterns (e.g., office-driven daytime traffic on weekdays vs. different residential patterns on weekends) are a plausible independent source of variation in Traffic Intensity, separate from time-of-day alone. Day-of-week cyclic encoding should be included as an additional feature pair alongside hour-of-day, not as a replacement for it — the two capture different, complementary cyclic patterns (a 24-hour cycle and a 7-day cycle) and must each get their own sine/cosine pair.

---

## 4. Implementation Specification

### 4.1 Step-by-Step Procedure

1. Parse the timestamp of each observation into its constituent time components (hour, minute, second, day-of-week, etc.) using the timestamp already logged by `src/collection/persistence/csv_writer.py`.
2. Compute the fractional time value on whatever period is being encoded (e.g., for minute-of-day precision: $m = \text{hour} \times 60 + \text{minute} + \text{second}/60$).
3. Apply the sine and cosine formulas from Section 3.2 (or the generalized table in Section 3.5) to produce exactly two new numeric columns per cyclic unit being encoded (e.g., `hour_sin`, `hour_cos`, and separately `dow_sin`, `dow_cos` if day-of-week is also being encoded).
4. **Drop the original raw integer time columns** (`hour_raw`, `day_of_week_raw`, etc.) from the final feature set passed to XGBoost. Leaving the raw column in *alongside* the sine/cosine pair does not actively break the sine/cosine encoding's benefit, but it reintroduces the exact false-discontinuity signal described in Section 2 as a redundant, misleading feature that the model must now learn to ignore — wasted model capacity for zero benefit, and a small but real risk that the tree ends up partially relying on the flawed raw feature simply because it happened to fit the training data's noise better in a particular boosting round (per `11_xgboost_fundamentals.md`, Section 4.7, a tree will use whatever feature/threshold maximizes Gain — it has no built-in preference for the "correct" feature over a spurious one).

### 4.2 Reference Implementation (Python / pandas)

```python
import numpy as np
import pandas as pd

def add_cyclic_time_features(df: pd.DataFrame, timestamp_col: str = "timestamp") -> pd.DataFrame:
    """
    Adds sine/cosine cyclic encodings for minute-of-day and day-of-week
    to the given DataFrame. Assumes `timestamp_col` is already a
    pandas datetime64 dtype column (parse with pd.to_datetime first
    if it is not).
    """
    ts = df[timestamp_col]

    # --- Minute-of-day cyclic encoding (fine-grained, period = 1440) ---
    minute_of_day = ts.dt.hour * 60 + ts.dt.minute + ts.dt.second / 60.0
    df["minute_of_day_sin"] = np.sin(2 * np.pi * minute_of_day / 1440.0)
    df["minute_of_day_cos"] = np.cos(2 * np.pi * minute_of_day / 1440.0)

    # --- Day-of-week cyclic encoding (period = 7) ---
    # Monday=0, Sunday=6 (pandas default for .dt.dayofweek)
    day_of_week = ts.dt.dayofweek
    df["dow_sin"] = np.sin(2 * np.pi * day_of_week / 7.0)
    df["dow_cos"] = np.cos(2 * np.pi * day_of_week / 7.0)

    # Explicitly drop any raw/intermediate columns that must not
    # reach the final feature matrix (see Section 4.1, Step 4).
    # Raw hour/minute/day-of-week integer columns should never be
    # passed to the model alongside their cyclic encodings.

    return df
```

### 4.3 Why Minute-of-Day Precision Is Recommended Over Hour-of-Day

Encoding at the hour level (period = 24, Section 3.2) forces every observation within the same clock hour (e.g., everything between 14:00:00 and 14:59:59) to collapse onto the **exact same** point on the circle, discarding any finer-grained timing information within that hour. Given that active probing per the project's collection design (`06_tcp_protocol.md`, `07_icmp_protocol.md`, `08_udp_protocol.md`) can be dense — potentially many probes per minute during a sweep — encoding at **minute-of-day** granularity (period = 1440, per Section 3.5's table) preserves substantially more temporal resolution at effectively zero extra implementation cost, and is the recommended default for this project's feature pipeline. Hour-of-day encoding should only be used if minute-level timestamp precision is unavailable in the underlying passive/active capture logs.

### 4.4 Interaction With the Time-Series Cross-Validation Requirement

The cyclic encoding described in this note is a **pure, row-wise, non-leaking transformation** — each observation's `minute_of_day_sin`/`cos` and `dow_sin`/`cos` values are computed using only that observation's own timestamp, with no dependency on any other row, past or future. This means cyclic time encoding is **safe to compute once, upfront, across the entire dataset**, unlike the rolling-window features discussed in `13_time_series_cross_validation.md`, Section 5.1, which must be computed strictly backward-looking and fold-specific. **This distinction matters and must not be conflated**: cyclic time features carry no leakage risk under any cross-validation scheme (Section 4 of `13_time_series_cross_validation.md`), while rolling traffic-volume features absolutely do. Cyclic encoding should not be lumped together with rolling features when auditing a pipeline for temporal leakage — it is a categorically different, and inherently safe, type of feature.

---

## 5. Diagnostic Checks to Confirm Correct Implementation

Since this note will not be manually reviewed before implementation, the following concrete checks should be run against the actual feature pipeline output to confirm correctness:

1. **Wrap-around continuity check**: compute `minute_of_day_sin`/`cos` for `23:59:00` and `00:01:00` (or the finer-grained equivalent) and confirm the Euclidean distance between the two resulting $(\sin, \cos)$ points is small (close to the distance expected for a 2-minute gap), not large. This directly validates the property proven in Section 3.3.
2. **Uniqueness-of-pair check**: pick two times that are exact mirror images around a sine peak or trough (e.g., 3:00 AM and 9:00 AM, as in Section 3.4) and confirm that while their `sin` values may coincide, their `cos` values do not — verifying the pair together is non-ambiguous, per Section 3.4.
3. **Full-circle coverage check**: plot all `(minute_of_day_sin, minute_of_day_cos)` pairs across a full day of synthetic test timestamps (e.g., one point per minute, 1440 points total) and visually/programmatically confirm the points trace out a complete, evenly-spaced circle with no gaps or clustering artifacts — a bug in the formula (e.g., an incorrect period denominator, or forgetting the $2\pi$ factor) will typically manifest as an incomplete arc or an uneven, non-circular distribution rather than a full circle.
4. **Raw column exclusion check**: before finalizing the Stage 2 feature matrix, explicitly assert (e.g., via a Python `assert` statement or a unit test) that no raw, non-cyclic time integer column (`hour`, `minute`, `day_of_week`, etc.) is present among the final columns passed to the XGBoost `fit()` call, per the requirement in Section 4.1, Step 4.

---

## 6. Summary: The Precise Chain of Reasoning

1. Time-of-day is a cyclic quantity (it wraps around every 24 hours / 7 days), but raw integer encoding represents it as a linear quantity that does not wrap around — creating a false maximum-distance discontinuity at the wrap-around boundary (Section 2.2).
2. This flaw is not neutralized by using a tree-based model like XGBoost; it merely forces every tree in the ensemble to inefficiently and unreliably attempt to rediscover the wrap-around pattern from data, which may fail entirely if training data near the boundary is sparse (Section 2.3).
3. The correct fix is to map each time value onto a point on the unit circle using paired sine and cosine transformations, which mathematically guarantees that real-world temporal closeness is preserved as numeric closeness, including across the midnight boundary (Section 3.2–3.3).
4. Sine and cosine must always be used **together** as a pair, never individually, because sine alone (or cosine alone) is not a one-to-one mapping and creates real ambiguity between distinct times of day (Section 3.4).
5. This technique generalizes directly to any other cyclic time unit relevant to the project (day-of-week, day-of-year), each requiring its own independent sine/cosine pair scaled to that unit's own natural period (Section 3.5).
6. Minute-of-day granularity is recommended over hour-of-day for this project's dense probing design, and raw integer time columns must be explicitly dropped from the final feature set once their cyclic encodings have been computed (Section 4.1, 4.3).
7. Cyclic time encoding is a safe, non-leaking, row-wise transformation and can be computed once upfront — unlike rolling-window traffic features, which require strict fold-specific, backward-looking computation per `13_time_series_cross_validation.md` (Section 4.4).
8. A concrete set of diagnostic checks (Section 5) should be run against the actual implemented pipeline to catch common formula or implementation bugs before trusting the resulting features.