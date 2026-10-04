# EXPERIMENTAL DESIGN AND CONFOUNDS

## 1. Overview in Latency Decomposition Context

This note addresses the final methodological layer of this project: once Stage 1 and Stage 2 are both correctly specified (`12_residual_learning_theory.md`), correctly validated (`13_time_series_cross_validation.md`), and built on a sound dual-stream data collection architecture (`19_active_vs_passive_measurement.md`), there remains a distinct and equally important question that none of those notes directly answer: **does the India vs. Singapore comparison this project is built around (per `README.md`, Phase 4) actually support the causal/comparative conclusions the project wants to draw, or could the observed differences be explained by something other than genuine infrastructural differences between the two countries?**

This is the discipline of **experimental design** — distinct from modeling correctness. A model can be mathematically flawless (correct residuals, correct validation, correct clustering) and still produce a **misleading comparative conclusion** if the underlying data collection itself was not designed to isolate the variable of actual interest (country/infrastructure) from other variables that happen to differ between the two collection efforts. This note catalogs the specific, concrete confounds relevant to this project, explains the mechanism by which each one could distort the India-vs-Singapore comparison, and specifies the control or mitigation required for each.

---

## 2. What a Confound Is, Formally

### 2.1 Definition

A **confounding variable** is a variable that is correlated with **both** the independent variable of interest (here: which country a probe was collected from) and the dependent variable being measured (here: residual queuing delay, $D_{\text{queue}}$), such that an observed association between the independent and dependent variable may be explained, wholly or partly, by the confound rather than by any genuine causal relationship between country and congestion.

### 2.2 Why This Matters Specifically for a Two-Group Comparison

This project's Phase 4 analysis (`README.md`, `15_gaussian_mixture_models.md` Section 7) is fundamentally a **two-group comparison**: India's fitted GMM components vs. Singapore's fitted GMM components. Any systematic difference between how the India dataset and the Singapore dataset were collected — beyond the countries' actual underlying network infrastructure — risks being absorbed into the comparison and misreported as a genuine finding about "India vs. Singapore network characteristics," when it may in fact be an artifact of a confound. **The entire scientific credibility of the project's headline comparative claims depends on these confounds being identified and either controlled for or explicitly acknowledged as limitations.**

---

## 3. Confound 1 — Time-of-Day / Time-Window Mismatch

### 3.1 The Mechanism

If data collection for India and Singapore is not run on a **matched, overlapping schedule** (e.g., if the India collection script happens to run predominantly during Indian daytime hours while the Singapore collection happens to run predominantly during Singapore nighttime hours, due to differing time zones and researcher scheduling convenience), then any observed difference in average queuing delay between the two datasets could simply reflect **"daytime traffic is heavier than nighttime traffic"** (a pattern this project's own cyclic time features, `14_feature_engineering_cyclic_time.md`, are specifically designed to capture) rather than any genuine difference in the two countries' underlying network infrastructure.

### 3.2 Why This Is a Particularly Severe Risk for This Project Specifically

India and Singapore sit in **different time zones** (IST is UTC+5:30, SGT is UTC+8:00 — a 2.5-hour offset). A naive data collection schedule run on a fixed wall-clock schedule in the researcher's own local time, without deliberate adjustment, would systematically sample **different local-time-of-day windows** in each country, directly inducing this confound by construction, not merely by accident.

### 3.3 The Required Control

**Data collection must be scheduled to cover matched, equivalent local-time windows in both countries** — i.e., the collection schedule should be designed in terms of *local time at the target country*, not wall-clock time at the researcher's location, ensuring that (for example) both datasets contain comparable proportions of probes taken during local morning peak, local evening peak, and local overnight low-traffic hours. If perfectly matched local-time coverage is not achievable, this must be explicitly reported as a limitation, and any cross-country comparison should be **conditioned on time-of-day** (e.g., comparing India's 8 PM–10 PM local residuals specifically against Singapore's 8 PM–10 PM local residuals, rather than comparing unconditioned full-dataset averages) rather than comparing raw, pooled distributions that may reflect different underlying time-of-day mixes.

---

## 4. Confound 2 — Day-of-Week / Calendar-Period Mismatch

### 4.1 The Mechanism

Analogous to Confound 1 but at a coarser timescale: if the India data collection run happens to span a different mix of weekdays vs. weekends than the Singapore run (e.g., due to differing collection start/end dates, differing run durations, or unplanned gaps/interruptions in one country's collection relative to the other), residential vs. office-driven traffic pattern differences (already anticipated by this project's inclusion of day-of-week cyclic features, per `14_feature_engineering_cyclic_time.md`, Section 3.5) could again be misattributed to country-level infrastructural differences rather than calendar-period sampling mismatch.

### 4.2 A Related, More Subtle Version: Local Public Holidays and Events

India and Singapore do not share the same public holiday calendar, and major unpredictable or semi-predictable national/regional events (e.g., a major shopping sale day, a national holiday with a known surge in video streaming, a local sporting event) can produce genuine but **country-specific, calendar-driven** traffic anomalies unrelated to any structural infrastructural difference. A single day of unusually heavy or unusually light traffic coinciding with data collection in only one of the two countries could visibly shift that country's GMM component means (`15_gaussian_mixture_models.md`) without reflecting any general, ongoing characteristic of that country's network.

### 4.3 The Required Control

**Data collection should span a full, matched number of complete weeks in both countries** (ensuring equal representation of each day-of-week), and the specific calendar dates of each country's collection window should be **explicitly logged and reported**, so that any known major local holidays or events falling within either collection window can be identified and either excluded from the final dataset or explicitly flagged as a known, documented anomaly when interpreting results, rather than silently left in the data to be absorbed unexplained into the GMM fitting.

---

## 5. Confound 3 — ISP / Last-Mile Connection Type Mismatch

### 5.1 The Mechanism

The "last mile" connection — the specific link between the probing node and its immediate ISP (e.g., residential fiber, residential DSL, mobile/cellular data, a university or corporate network connection) — has its **own** bandwidth, latency, and (per `16_bufferbloat_and_aqm.md`) buffer-sizing/AQM characteristics, entirely independent of anything downstream in the broader internet path toward the target DNS resolver. If the India probing node happens to be connected via, say, a residential DSL connection, while the Singapore probing node is connected via a university or corporate fiber connection, **any observed difference in baseline latency or queuing behavior could trivially be explained by this last-mile connection-type difference alone**, with no bearing whatsoever on the two countries' broader internet infrastructure — directly undermining the project's intended "cross-country topological comparison" framing (`README.md`).

### 5.2 Why This Confound Is Especially Easy to Overlook

Unlike time-of-day (Confound 1), which is an obvious, well-understood variable that researchers are generally primed to think about, last-mile connection type is easy to treat as a fixed, unremarkable background detail of "wherever I happen to be running the script from," precisely because it is not the variable the researcher is consciously trying to manipulate or study. This makes it a genuine blind-spot risk rather than a well-known, already-mitigated concern.

### 5.3 The Required Control

At minimum, the **specific last-mile connection type and approximate advertised bandwidth** used for data collection in each country must be **explicitly documented** as part of the experimental record (e.g., "India: residential fiber, 100 Mbps; Singapore: residential fiber, 1 Gbps"), so that any observed baseline difference can be evaluated against this known starting condition rather than left unexplained. Where feasible, using **comparable connection types and bandwidth tiers** in both locations substantially strengthens the validity of the cross-country comparison; where this is not feasible (e.g., only one type of connection is available in a given location), the mismatch should be explicitly acknowledged as a limitation when reporting Phase 4 findings, and, if possible, Stage 1's fitted bandwidth coefficient ($\hat\beta_1$, per `10_quantile_regression_envelope.md`, Section 4) for each country should be reported alongside the cross-country comparison specifically so a reader can assess whether the two datasets' underlying last-mile bandwidths were in fact comparable.

---

## 6. Confound 4 — Sample Size Imbalance

### 6.1 The Mechanism

If substantially more probes are collected in one country than the other (e.g., due to differing collection run durations, differing rates of script interruption/failure, or simply starting one country's collection earlier than the other), this does not bias the *direction* of any comparison, but it directly affects the **statistical reliability** of each country's independently-fit GMM (`15_gaussian_mixture_models.md`): the country with fewer samples will have **less reliable, higher-variance parameter estimates** ($\hat\mu_k$, $\hat\sigma_k^2$, per `15_gaussian_mixture_models.md`, Section 4.4) and less statistically confident model-selection outcomes (the BIC-selected $K$, per Section 5.3 of that note), making it genuinely harder to distinguish "this country has a different number/shape of congestion states" (a real finding) from "this country simply has a noisier, less-well-estimated model due to fewer data points" (a sample-size artifact).

### 6.2 The Required Control

Track and report the **final sample size** (post any fragmentation/instance-flap filtering, per `18_mtu_and_fragmentation.md` and `17_anycast_dns_routing.md`) achieved for each country's dataset. If a substantial imbalance exists, consider either (a) **downsampling** the larger dataset to match the smaller one before fitting comparative GMMs, so that any observed difference in model complexity or component shape cannot trivially be explained by unequal statistical power, or (b) explicitly computing and reporting **confidence intervals or bootstrap-resampled uncertainty estimates** around each country's GMM parameters (rather than reporting single point estimates as if they were equally reliable), so a reader can correctly weigh how much confidence to place in each side of the comparison.

---

## 7. Confound 5 — Differing Degrees of Routing/Instance Volatility (Interaction With Anycast)

### 7.1 The Mechanism

`17_anycast_dns_routing.md`, Section 5.2, already generates a specific, falsifiable hypothesis: India's dataset is expected to show *more* anycast instance-flap events (higher hop-count variance) than Singapore's. This is itself a legitimate, interesting finding if confirmed — but it also means that, if instance-flap-contaminated segments are not correctly filtered out via the Section 4.3 diagnostic from `17_anycast_dns_routing.md` (and the corresponding Time-Window Localized Quantile Regression mitigation from `10_quantile_regression_envelope.md`), **any residual Stage 1 bias from unfiltered instance flaps would disproportionately contaminate the India dataset more than the Singapore dataset**, purely as a side effect of India's routing being more volatile — meaning an *under-filtered* India dataset could show artificially elevated or more dispersed GMM components **not because Indian network congestion genuinely is more variable, but because the Stage 1 baseline itself was less cleanly estimated for India due to incomplete anycast-instance segmentation.**

### 7.2 Why This Confound Is Structurally Different From the Others

Unlike Confounds 1–4, which are external to the modeling pipeline and arise purely from data-collection scheduling/environment choices, this confound arises from an **interaction between a genuine country-level difference (routing volatility) and a methodological step (Stage 1 fitting) that is supposed to be country-agnostic.** This makes it the most subtle and most dangerous confound on this list: it can masquerade as confirming the project's own working hypothesis (`09_protocol_comparison.md`'s "India = volatile" framing) for the wrong reason — not because India's *congestion* is genuinely more variable, but because India's *measurement pipeline* was left noisier due to incompletely filtered routing artifacts.

### 7.3 The Required Control

Before any cross-country GMM comparison is reported, **explicitly verify, separately for each country, that the anycast instance-flap filtering described in `17_anycast_dns_routing.md`, Section 4.3, achieved comparable effectiveness** — e.g., report the number/proportion of probes excluded or re-segmented due to detected instance flaps in each country's dataset, and confirm that the *post-filtering* residual distributions no longer show the structural-break symptoms described in `12_residual_learning_theory.md`, Section 6.2, for either country. Only after this check passes independently for both datasets should any difference in GMM component structure be attributed to genuine congestion-behavior differences rather than residual Stage 1 estimation noise.

---

## 8. Confound 6 — Researcher/Script Behavior Differences Between Runs

### 8.1 The Mechanism

If the data collection script, its configuration (probe interval, target list, retry logic), or the host machine's own background load differs in any way between the India run and the Singapore run — even unintentionally, e.g., due to a code update made between the two collection periods, or one machine running other background applications that compete for CPU/network resources during collection — this introduces a confound at the measurement-apparatus level itself, independent of any genuine network-path difference. This is directly connected to `05_processing_delay.md`'s discussion of software-based processing delay and CPU-contention-driven jitter: if the probing *host itself* is more loaded in one country's run than the other, this could inflate that country's apparent processing/queuing delay for reasons entirely internal to the measurement setup, with nothing to do with the actual internet path being studied.

### 8.2 The Required Control

Use the **exact same, version-pinned collection script and configuration** for both countries' data collection runs (i.e., do not make code changes to the probing logic between the two collection periods without re-running both, or at minimum explicitly documenting and accounting for the change). Where feasible, run the host machine with minimal concurrent background load during active collection periods in both locations, and log basic host-level resource utilization (CPU load, available memory) alongside the network data, so that any anomalous collection period can be identified and, if necessary, excluded.

---

## 9. A Consolidated Pre-Analysis Checklist

Before treating any Phase 4 cross-country finding as a genuine, reportable result, the following should be explicitly confirmed, directly corresponding to the confounds above:

1. **Time-of-day coverage** (Section 3.3): both datasets cover matched local-time windows, or comparisons are explicitly conditioned on time-of-day.
2. **Calendar coverage** (Section 4.3): both datasets span a matched, whole number of weeks, with known local holidays/events during either window explicitly documented.
3. **Last-mile connection parity** (Section 5.3): connection type/bandwidth for each country is documented, and Stage 1's fitted $\hat\beta_1$ per country is reported alongside any cross-country comparison.
4. **Sample size parity** (Section 6.2): final post-filtering sample sizes are reported for both countries, with downsampling or uncertainty quantification applied if substantially imbalanced.
5. **Anycast-filtering parity** (Section 7.3): instance-flap filtering effectiveness is verified and reported independently for both countries before any GMM-based comparative claim is made.
6. **Apparatus consistency** (Section 8.2): identical, version-pinned collection code and configuration were used for both runs, with any deviations explicitly documented.

---

## 10. Relationship to the Rest of This Project's Note Series

This note sits at the **top** of the project's methodological validity chain, logically downstream of, and dependent on, every other note in this series:

- `12_residual_learning_theory.md` establishes that Stage 2's target is only valid if Stage 1 is correctly specified — this note's Confound 7 (Section 7) shows a concrete way country-level differences can interact with that requirement asymmetrically.
- `13_time_series_cross_validation.md` establishes correct within-country model validation — this note's Confounds 1–2 (Sections 3–4) establish that even a perfectly-validated within-country model can still support an invalid *between*-country comparison if the underlying data collection windows are mismatched.
- `17_anycast_dns_routing.md` and `18_mtu_and_fragmentation.md` establish specific data-quality filtering requirements — this note's Section 7 shows why *differential* filtering effectiveness between countries is itself a confound, not just a per-country data-quality concern.
- `19_active_vs_passive_measurement.md`'s Section 6.1–6.2 (probing frequency trade-off, interface placement) are themselves specific instances of the general "apparatus consistency" confound formalized here in Section 8.

**The overarching principle this note contributes, not fully stated elsewhere in this project's notes:** correctness of the modeling pipeline (Stages 1 and 2, validation, clustering) is a **necessary but not sufficient** condition for the project's ultimate comparative claims to be valid. Experimental design — ensuring the *only* systematically-differing variable between the India and Singapore datasets is, as far as practically achievable, the countries' actual underlying network infrastructure — is an **independent, additional requirement** that must be deliberately engineered into the data collection process itself, and explicitly audited against before Phase 4's findings are written up.

---

## 11. Summary: The Precise Chain of Reasoning

1. A confound is a variable correlated with both the comparison of interest (country) and the outcome being measured (queuing delay), capable of producing a misleading comparative result even when every individual model in the pipeline is mathematically correct (Section 2).
2. Time-of-day and day-of-week/calendar mismatches between the two countries' collection windows are the most immediately obvious confounds, directly exploitable given India and Singapore's differing time zones and independent holiday calendars, and are controlled by scheduling collection around matched local-time and matched calendar-week coverage (Sections 3–4).
3. Last-mile ISP connection type/bandwidth is an easily-overlooked confound, since it sits outside the researcher's conscious focus on "the internet path," yet can single-handedly explain an observed baseline difference; it is controlled by explicit documentation and, ideally, deliberate parity between the two locations' connection setups (Section 5).
4. Sample size imbalance does not bias direction but degrades statistical reliability unevenly between the two countries' independently-fit GMMs, and is controlled via downsampling or explicit uncertainty quantification (Section 6).
5. The most subtle confound arises from an interaction between a genuine country-level difference (anycast routing volatility, per `17_anycast_dns_routing.md`) and a supposedly country-agnostic modeling step (Stage 1 fitting) — incomplete instance-flap filtering could inflate India's apparent congestion variability for measurement-pipeline reasons rather than genuine network reasons, and must be explicitly ruled out via parity checks on filtering effectiveness before trusting any resulting comparative claim (Section 7).
6. Differences in the collection script, its configuration, or host-level resource contention between the two runs constitute a confound at the measurement-apparatus level itself, controlled via version-pinned, consistent tooling and logged host resource utilization (Section 8).
7. A consolidated pre-analysis checklist (Section 9) operationalizes all six confounds into concrete, checkable conditions that should be explicitly confirmed before any Phase 4 cross-country finding is reported as genuine.
8. This note establishes that modeling correctness (addressed by the rest of this project's note series) is necessary but not sufficient for valid comparative conclusions — experimental design validity is an independent, additional requirement that must be deliberately engineered into data collection itself, not assumed to follow automatically from a correctly-built modeling pipeline (Section 10).