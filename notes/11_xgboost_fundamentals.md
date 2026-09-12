# XGBOOST FUNDAMENTALS

## 1. Overview in Latency Decomposition Context

XGBoost (eXtreme Gradient Boosting) is the Stage 2 model in our Hybrid Residual Architecture. Its job is narrow and specific: learn the mapping between concurrent network conditions (traffic volume, time-of-day, protocol flags, destination signature) and the **residual queuing delay** ($D_{\text{queue}}$) left over after Stage 1's linear/quantile regression has removed the deterministic physical component.

XGBoost is not being used here as a general-purpose "black box" — it is chosen specifically because $D_{\text{queue}}$ is:

- **Non-linear**: traffic intensity's effect on delay is not a straight line (see `04_queuing_delay.md` — the relationship approaches infinity as traffic intensity $I \to 1$).
- **Interaction-heavy**: the effect of "packet arrival rate" on delay depends on "time of day" depends on "target destination" — these are conditional, not additive, relationships.
- **Tabular and structured**: our features (packet rate, hour-of-day, protocol flag, destination ID) are discrete, heterogeneous, engineered columns — exactly the data type on which tree ensembles outperform neural networks at our data scale (thousands to low millions of rows, not billions).

---

## 2. Foundational Building Block: The Decision Tree

Before understanding *boosting*, the base learner must be understood precisely.

A **regression decision tree** partitions the feature space into disjoint rectangular regions (leaves) and assigns a constant predicted value to every point falling inside a given region.

### 2.1 How a Split is Chosen

At each node, the tree algorithm considers every feature and every possible threshold value for that feature. For a candidate split that partitions the current node's data into a left set $I_L$ and a right set $I_R$, the algorithm computes how much that split would reduce the model's loss (formalized precisely in Section 4.3 — the **Gain** formula). It picks the feature and threshold that produces the largest loss reduction.

### 2.2 Why a Single Tree Is Not Enough

A single regression tree can only produce a **piecewise-constant** prediction surface — it cannot represent smooth non-linear relationships without an impractically large number of splits, and a tree deep enough to fit the training data precisely will **overfit**: it memorizes noise (including the queuing delay's inherent stochastic jitter) instead of learning the underlying pattern.

This motivates **ensembling**: combining many *weak* (shallow, deliberately limited) trees so that their aggregate prediction is more accurate and more stable than any single tree, while each individual tree is too simple to memorize noise on its own.

---

## 3. From Bagging to Boosting: Two Different Ensembling Philosophies

It is essential not to conflate XGBoost with Random Forests — they are both tree ensembles but combine trees in fundamentally different ways.

### 3.1 Bagging (e.g., Random Forest)

- Many trees are trained **independently and in parallel**, each on a random bootstrap sample of the data (and often a random subset of features per split).
- Final prediction = **average** of all trees' predictions.
- Goal: **reduce variance**. Each tree overfits its own bootstrap sample differently; averaging cancels out the uncorrelated overfitting noise.
- Trees do not know about each other's errors.

### 3.2 Boosting (XGBoost)

- Trees are trained **sequentially**, one at a time.
- Each new tree is trained specifically to correct the **errors made by the ensemble of all previous trees combined**.
- Final prediction = **sum** of all trees' outputs (each typically scaled down by a learning rate — see Section 6.1).
- Goal: **reduce bias**. The ensemble starts crude and each new tree incrementally sharpens it.
- Trees explicitly depend on the sequence before them — tree $k$ cannot be trained until trees $1$ through $k-1$ exist.

**Why this distinction matters for our project:** our residual target ($D_{\text{queue}}$) has a complex, multimodal error surface (per `04_queuing_delay.md`, it behaves differently in "empty queue" vs. "heavy congestion" regimes). Boosting's sequential error-correction is what allows the ensemble to progressively carve out these distinct regimes, whereas bagging would only smooth out noise without targeting the specific regions the model currently gets wrong.

---

## 4. The Mathematics of Gradient Boosting

### 4.1 The Additive Model

XGBoost builds its final prediction $\hat{y}_i$ for a data point $i$ as the sum of outputs from $K$ sequentially trained trees:

$$
\hat{y}_i = \sum_{k=1}^{K} f_k(x_i), \quad f_k \in \mathcal{F}
$$

Where:

- $x_i$ → the feature vector for observation $i$ (e.g., traffic volume, hour-of-day sine/cosine, protocol flag)
- $f_k$ → the $k$-th regression tree, treated as a function mapping features to a real-valued output
- $\mathcal{F}$ → the space of all possible regression trees (a given structure and set of leaf weights)

### 4.2 Training Objective Function

At boosting round $t$, the model already has predictions from the previous $t-1$ trees:

$$
\hat{y}_i^{(t-1)} = \sum_{k=1}^{t-1} f_k(x_i)
$$

The new tree $f_t$ is chosen to minimize the following regularized objective:

$$
\mathcal{L}^{(t)} = \sum_{i=1}^{n} l\left(y_i, \hat{y}_i^{(t-1)} + f_t(x_i)\right) + \Omega(f_t)
$$

Where:

- $y_i$ → the true observed target value (in our case, the actual isolated residual $D_{\text{queue}}$ for observation $i$)
- $l(y_i, \hat{y}_i)$ → a differentiable loss function measuring prediction error (for regression, typically **squared error**: $l = (y_i - \hat{y}_i)^2$)
- $\Omega(f_t)$ → a **regularization term** penalizing model complexity (defined explicitly in Section 4.5)
- $n$ → total number of training observations

The core idea: instead of re-fitting all $K$ trees jointly (computationally intractable), boosting fixes trees $1$ through $t-1$ and greedily solves for only the next tree $f_t$ that best reduces the *remaining* error.

### 4.3 Second-Order Taylor Approximation (Why XGBoost Is Faster Than Classic Gradient Boosting)

Directly minimizing $\mathcal{L}^{(t)}$ for an arbitrary loss function is computationally expensive because it requires evaluating the loss at every candidate tree structure. XGBoost's key innovation is approximating the loss using a **second-order Taylor expansion** around the current prediction $\hat{y}_i^{(t-1)}$:

$$
\mathcal{L}^{(t)} \approx \sum_{i=1}^{n} \left[ l(y_i, \hat{y}_i^{(t-1)}) + g_i f_t(x_i) + \frac{1}{2} h_i f_t(x_i)^2 \right] + \Omega(f_t)
$$

Where:

- $g_i = \dfrac{\partial\, l(y_i, \hat{y}_i^{(t-1)})}{\partial\, \hat{y}_i^{(t-1)}}$ → the **first-order gradient** (first derivative) of the loss with respect to the current prediction
- $h_i = \dfrac{\partial^2\, l(y_i, \hat{y}_i^{(t-1)})}{\partial\, (\hat{y}_i^{(t-1)})^2}$ → the **second-order gradient (Hessian)** of the loss

For **squared error loss**, $l = (y_i - \hat{y}_i)^2$, these simplify to closed forms:

$$
g_i = -2(y_i - \hat{y}_i^{(t-1)}), \qquad h_i = 2
$$

Because $l(y_i, \hat{y}_i^{(t-1)})$ is a constant with respect to $f_t$ (it depends only on already-fixed previous trees), it can be dropped from the optimization, leaving a simplified objective that depends only on $g_i$, $h_i$, and the new tree's structure. This is what makes XGBoost's per-tree optimization dramatically faster and more precise than earlier boosting implementations, which relied on gradient information alone (first-order only).

### 4.4 Expressing a Tree in Formal Terms

To optimize the simplified objective, a tree $f_t$ is formally defined as:

$$
f_t(x) = w_{q(x)}, \quad w \in \mathbb{R}^T, \quad q: \mathbb{R}^d \rightarrow \{1, 2, \dots, T\}
$$

Where:

- $T$ → the total number of leaves in the tree
- $q(x)$ → a function mapping an input feature vector to the index of the leaf it falls into
- $w_j$ → the constant numeric output (weight) assigned to leaf $j$

Let $I_j = \{i \mid q(x_i) = j\}$ denote the set of training observations that land in leaf $j$.

### 4.5 The Regularization Term

$$
\Omega(f_t) = \gamma T + \frac{1}{2}\lambda \sum_{j=1}^{T} w_j^2
$$

Where:

- $\gamma$ → a fixed penalty applied per additional leaf (controls tree size directly — a higher $\gamma$ forces the algorithm to only add a leaf if the resulting loss reduction exceeds this cost)
- $\lambda$ → an L2 penalty on the leaf weight magnitudes (shrinks extreme leaf values toward zero, similar in spirit to Ridge regression)

This regularization is what distinguishes XGBoost from naive gradient boosting: it explicitly penalizes complexity inside the mathematical objective itself, rather than relying purely on external constraints like max-depth.

### 4.6 Optimal Leaf Weight (Closed-Form Solution)

Given a fixed tree structure $q$, the objective becomes a simple quadratic function of each leaf's weight $w_j$, independently solvable per leaf. Setting the derivative to zero yields the closed-form optimal weight for leaf $j$:

$$
w_j^{*} = -\frac{\sum_{i \in I_j} g_i}{\sum_{i \in I_j} h_i + \lambda}
$$

And the corresponding minimized loss value contributed by that leaf:

$$
\mathcal{L}_j^{*} = -\frac{1}{2} \cdot \frac{\left(\sum_{i \in I_j} g_i\right)^2}{\sum_{i \in I_j} h_i + \lambda} + \gamma
$$

**Interpretation for our project:** for a leaf grouping together, say, "high traffic volume + late evening + India target," $w_j^*$ is essentially the (regularized) average residual queuing delay observed for that specific combination of conditions in the training data.

### 4.7 The Gain Formula (How Splits Are Actually Chosen)

When considering whether to split a leaf into a left child ($I_L$) and right child ($I_R$), XGBoost computes the **Gain** — how much total loss decreases by making that split versus keeping the leaf unsplit:

$$
\text{Gain} = \frac{1}{2}\left[ \frac{\left(\sum_{i \in I_L} g_i\right)^2}{\sum_{i \in I_L} h_i + \lambda} + \frac{\left(\sum_{i \in I_R} g_i\right)^2}{\sum_{i \in I_R} h_i + \lambda} - \frac{\left(\sum_{i \in I_L \cup I_R} g_i\right)^2}{\sum_{i \in I_L \cup I_R} h_i + \lambda} \right] - \gamma
$$

The first two terms inside the brackets represent the loss reduction achieved by scoring the left and right leaves *separately*; the third term is the loss if they were kept as a single unsplit leaf. The formula explicitly subtracts $\gamma$ — meaning **a split is only performed if the improvement in fit exceeds the fixed complexity cost of adding a leaf.** If Gain is negative, the split is rejected and the node remains a leaf. This is called **pruning**, and in XGBoost it is done exactly (via this formula), not just approximately.

---

## 5. Practical Algorithm Flow (Putting It All Together)

1. **Initialize**: Set the initial prediction $\hat{y}_i^{(0)}$ for every observation to a constant (typically the mean of the target, or 0.5 by default for regression in some implementations).
2. **For each boosting round $t = 1$ to $K$:**
   a. Compute $g_i$ and $h_i$ for every training observation using the current predictions $\hat{y}_i^{(t-1)}$.
   b. Greedily build a regression tree $f_t$ by recursively selecting splits that maximize Gain (Section 4.7), stopping when Gain is negative, or a stopping criterion (max depth, minimum child weight) is reached.
   c. Assign each leaf its optimal weight $w_j^*$ (Section 4.6).
   d. Update predictions: $\hat{y}_i^{(t)} = \hat{y}_i^{(t-1)} + \eta \cdot f_t(x_i)$, where $\eta$ is the learning rate (Section 6.1).
3. **Final prediction**: $\hat{y}_i = \hat{y}_i^{(K)}$, the sum of the initial value and all $K$ trees' (scaled) contributions.

---

## 6. Key Hyperparameters Relevant to This Project

### 6.1 `learning_rate` (also called `eta`)

Scales down the contribution of each individual tree before adding it to the running prediction:

$$
\hat{y}_i^{(t)} = \hat{y}_i^{(t-1)} + \eta \cdot f_t(x_i), \quad 0 < \eta \leq 1
$$

- **Lower values** (e.g., 0.01–0.1) force the model to take smaller corrective steps, requiring more trees (`n_estimators`) to converge, but generally produce a more robust, less overfit model.
- **Higher values** converge faster but risk overshooting and overfitting to noise — a real risk here since raw queuing delay residuals are inherently noisy (per `04_queuing_delay.md`, driven by stochastic traffic micro-bursts).
- **Rule of thumb**: lower `learning_rate` should be paired with higher `n_estimators`, and the pair should be tuned together, not independently.

### 6.2 `max_depth`

The maximum number of sequential splits allowed from the root to a leaf in any single tree.

- Directly controls how many **feature interactions** a single tree can capture — a tree of depth $d$ can capture interactions between up to $d$ features simultaneously.
- **Shallow trees** (depth 3–6) are standard for tabular boosting; they act as genuinely "weak" learners, which is a deliberate design goal (Section 2.2).
- **Deep trees** increase variance and overfitting risk sharply, since each individual tree begins to memorize specific noisy observations rather than general patterns.
- For our residual target, which is influenced by interacting factors (protocol × time-of-day × traffic volume — see `09_protocol_comparison.md`), a moderate depth (4–8) is typically needed to let trees express these interactions without over-fragmenting the data into leaves containing very few samples.

### 6.3 `n_estimators`

The total number of boosting rounds $K$ — i.e., how many trees are sequentially added to the ensemble.

- Too few: the model underfits (hasn't had enough rounds to reduce bias).
- Too many: the model can begin overfitting the training residuals, especially at higher learning rates.
- Should always be tuned jointly with **early stopping** (Section 6.6) rather than fixed to an arbitrary number.

### 6.4 `subsample`

The fraction of training rows randomly sampled (without replacement) to grow **each individual tree**.

- Value < 1.0 (commonly 0.7–0.9) introduces randomness across boosting rounds, which reduces variance and helps prevent any single tree from overfitting to a specific subset of anomalous observations (e.g., a single burst of anomalous congestion during data collection).
- This is conceptually similar to bagging's bootstrap sampling (Section 3.1), but applied *within* a boosting framework rather than as the sole ensembling mechanism.

### 6.5 `colsample_bytree` (and `colsample_bylevel` / `colsample_bynode`)

The fraction of **features** randomly sampled when constructing each tree (or at each level/split node, depending on the variant).

- Prevents any single dominant feature (e.g., raw traffic volume) from being selected at the top of every tree, forcing the ensemble to also learn from secondary signals (time-of-day, protocol flags, destination ID).
- Improves generalization in the same spirit as Random Forest's per-split feature subsampling.

### 6.6 `early_stopping_rounds`

Rather than fixing `n_estimators` in advance, a held-out validation set's loss is monitored after every boosting round. Training halts once the validation loss fails to improve for a specified number of consecutive rounds ("patience").

- This directly prevents overfitting without requiring manual tuning of `n_estimators`.
- **Critical caveat for this project**: because $D_{\text{queue}}$ is a **temporally correlated** signal (queuing state at time $t$ predicts queuing state at time $t+1$ — per `04_queuing_delay.md`'s discussion of residual "memory"), the validation split used for early stopping must be a **chronological holdout** (e.g., the most recent 10–15% of the time-ordered data), never a random shuffle-based split. A randomly shuffled validation set would leak future information into training and produce an artificially optimistic (and invalid) stopping point. This should be handled together with the time-series cross-validation approach described in the (planned) `13_time_series_cross_validation.md` note.

### 6.7 `min_child_weight`

The minimum sum of Hessian values ($\sum h_i$) required in a leaf for a split to be considered valid.

- For squared-error loss, $h_i = 2$ for every observation (Section 4.3), so this parameter effectively behaves like a minimum-sample-count-per-leaf constraint.
- Prevents the tree from creating leaves based on only one or two observations — an important safeguard against overfitting to individual noisy probe measurements (e.g., a single anomalous ping caused by a transient wireless interference event rather than genuine network queuing).

### 6.8 `reg_alpha` and `reg_lambda`

- `reg_lambda` corresponds directly to $\lambda$ in Section 4.5 (L2 regularization on leaf weights).
- `reg_alpha` adds an **L1** regularization term on leaf weights, which can push some leaf weights exactly to zero, effectively performing a form of automatic feature/leaf pruning across the ensemble.

---

## 7. Why XGBoost Specifically Suits Stage 2 of This Architecture

Tying the above mathematics directly back to the project's design:

1. **Handles non-linearity natively**: unlike Stage 1's linear/quantile regression (see `10_quantile_regression_envelope.md`), XGBoost requires no explicit feature transformation to capture the non-linear relationship between traffic intensity and queuing delay described by $I = \dfrac{L \cdot a}{R}$ in `04_queuing_delay.md`.
2. **Captures feature interactions automatically**: a single tree's sequential splits (e.g., first split on protocol, then on time-of-day within each protocol branch) inherently model conditional relationships — exactly the "TCP residuals need rolling-window features, UDP residuals need instantaneous features" distinction described in `09_protocol_comparison.md`.
3. **Robust to differing feature scales and units**: because trees split purely on ordering (is feature value > threshold?), XGBoost requires no feature scaling/normalization — convenient since our feature set mixes packet counts, cyclic sine/cosine time encodings, and categorical destination IDs.
4. **Built-in regularization** (Section 4.5) directly combats overfitting to the inherently noisy, stochastic nature of queuing delay residuals, which is critical since our target variable is, by construction (per `04_queuing_delay.md`), the most volatile and unpredictable component of total latency.
5. **Missing-value tolerance**: XGBoost has a native, learned strategy for routing observations with missing feature values to whichever branch (left or right) minimizes loss at each split — relevant if passive capture occasionally fails to log a metric for a given probe window due to a dropped packet or sniffing thread timing gap.

---

## 8. Common Misconceptions to Avoid (Explicitly Addressed)

- **"XGBoost trees are trained in parallel like a Random Forest."** False — trees are strictly sequential; each depends on the residual errors of the ensemble formed by every prior tree. (Parallelism in XGBoost's implementation exists only *within* the construction of a single tree, e.g., parallelizing the search for the best split across features — not across trees.)
- **"A lower training loss always means a better model."** False — without regularization (Section 4.5) and validation-based early stopping (Section 6.6), a model can drive training loss arbitrarily low by memorizing noise, producing poor performance on unseen data. This is especially dangerous for our project because queuing delay noise is large relative to signal.
- **"XGBoost predicts the target directly from raw RTT."** False, in this project's specific architecture — Stage 2 XGBoost never sees raw RTT as its target. It is trained exclusively on the **residual** produced after subtracting Stage 1's physical prediction, as defined in `03_transmission_delay.md` and `09_protocol_comparison.md`. Feeding it raw RTT instead of the residual would cause it to re-learn the already-deterministic physical relationship, wasting model capacity and defeating the purpose of the two-stage architecture.
- **"More trees are always better."** False — without early stopping, additional trees beyond the point of validation-loss convergence only continue fitting training-set noise, degrading generalization.