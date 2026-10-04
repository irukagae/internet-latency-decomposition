# ACTIVE VS. PASSIVE MEASUREMENT

## 1. Overview in Latency Decomposition Context

This note formalizes the distinction between **active measurement** (the Scapy-crafted probes described in `06_tcp_protocol.md`, `07_icmp_protocol.md`, `08_udp_protocol.md`) and **passive measurement** (the concurrent background sniffing thread referenced throughout those same notes and in `src/collection/capture/passive.py` per the repository structure), and establishes precisely why this project deliberately combines **both** rather than relying on either one alone. This is not a redundant design choice — each method measures a fundamentally different thing, answers a different question, and carries different, non-overlapping blind spots. Understanding exactly what each method can and cannot see is a precondition for correctly interpreting every feature this project constructs from them.

---

## 2. Active Measurement: Definition and Core Properties

### 2.1 Definition

**Active measurement** means deliberately injecting purpose-built traffic into the network — in this project's case, the hand-crafted ICMP/TCP/UDP probes described in `06`–`08` — specifically in order to observe how the network responds to that injected traffic. The measurement **causes** the event being measured; without the probe, there is no RTT value to record.

### 2.2 What Active Measurement Directly Produces

Active measurement is the **only** source, in this project's design, of the single quantity every other part of this architecture depends on: a precise, timestamped **Round-Trip Time** for a packet of a **known, controlled size**, sent to a **known, controlled destination**, at a **known, controlled time**. This is exactly the controlled experimental structure that makes Stage 1's linear/quantile regression (`03_transmission_delay.md`, `10_quantile_regression_envelope.md`) possible at all: that regression requires `packet_size` to be a clean, researcher-controlled independent variable, swept deliberately across a known range — a property that **only** active measurement can provide, because only active measurement involves the researcher choosing the packet's contents and size in the first place.

### 2.3 The Defining Limitation: Active Measurement Only Sees What It Asks About

Active measurement answers exactly one question, for exactly one path, at exactly one moment: *"what happens if I send a packet of size $X$ to destination $Y$ right now?"* It has **zero visibility** into anything happening on the network that it did not itself directly cause — it cannot see other applications' traffic, other users sharing the same bottleneck link, or background load contributing to the very queuing delay (`04_queuing_delay.md`) the active probe's RTT is trying to help decompose. An active probe's elevated RTT is a **symptom** of congestion; active measurement alone provides no direct evidence of the **cause**.

### 2.4 The Observer Effect: Active Measurement Can Also Influence What It Measures

A subtler, related limitation: because active probes are themselves real packets consuming real link capacity and real router buffer space, sending them **changes, even if only infinitesimally, the very network state being measured** — a general phenomenon sometimes called the **observer effect** in measurement theory. For a single, low-frequency probe, this self-influence is negligible. But `08_udp_protocol.md`, Section 3, already flags a concrete, non-negligible version of this effect specific to this project's design: because UDP has no congestion-aware back-off mechanism (`06_tcp_protocol.md`'s $cwnd$), "executing high-frequency UDP sweeps can deliberately strain bottleneck queues" — meaning a sufficiently dense active probing schedule does not merely *observe* queuing delay, it can genuinely *contribute to* the very queuing delay being measured, a confound that must be kept in mind when interpreting results from denser portions of the sweep schedule.

---

## 3. Passive Measurement: Definition and Core Properties

### 3.1 Definition

**Passive measurement** means observing traffic that is **already traversing the network for some other, independent reason** — in this project's design, this is the background sniffing thread (`src/collection/capture/passive.py`) that monitors the local network interface and records characteristics of **all** traffic it observes, without injecting anything itself. The measurement does not cause the event being measured; it merely observes traffic that would have existed regardless of whether the measurement was being taken.

### 3.2 What Passive Measurement Directly Produces

Passive measurement, in this project's design, is the source of the **contextual, concurrent network-load features** repeatedly referenced as Stage 2 inputs across `09_protocol_comparison.md` (e.g., "passive traffic volume/packet rates," "current packets per second on the interface at the exact millisecond of the active probe") and `16_bufferbloat_and_aqm.md`, Section 5.4 (sustained traffic volume used to diagnose AQM-capped vs. uncapped residual behavior). It directly measures the **ambient network load condition** that active measurement alone has no visibility into (Section 2.3) — this is precisely the information Stage 2's XGBoost model needs in order to explain *why* a given active probe's residual queuing delay was high or low, since Traffic Intensity ($I = L \cdot a / R$, per `04_queuing_delay.md`) is fundamentally a function of *all* traffic sharing the bottleneck, not merely the researcher's own probe traffic.

### 3.3 The Defining Limitation: Passive Measurement Cannot Directly Produce an RTT for a Controlled Packet

Passive measurement, by construction, only observes traffic that **already exists** for some other reason — it has no mechanism to request, control, or guarantee the arrival of a packet of any particular size, to any particular destination, at any particular moment. This means passive measurement **cannot, on its own, produce the clean `packet_size → RTT` dataset Stage 1 requires** (Section 2.2): it would need to wait for naturally-occurring traffic to happen to include packets of the exact sizes needed across the full 64–1400 byte sweep range, to the exact target destinations of interest, which is not something passively observed, organic traffic can be relied upon to provide in a controlled, complete, or timely way.

### 3.4 A Further Limitation: Passive Measurement Cannot See Return-Path Asymmetry Directly for Foreign Flows

Passive capture on the probing node's own network interface sees the local interface's send and receive traffic — but for a TCP connection or UDP exchange belonging to someone *else's* application on the same local network segment (e.g., another device sharing the same home/office router), the passive sniffer may see only a partial, one-sided view of that flow's traffic (e.g., it may see outbound-bound packets forwarded through a shared gateway but miss timing detail internal to a different device's own stack), limiting how precisely passive capture alone can reconstruct full round-trip behavior for traffic it did not itself initiate. In practice, this project's passive capture is used primarily for **aggregate volumetric features** (packet counts, byte rates) rather than attempting to reconstruct other flows' precise RTTs, which sidesteps this specific limitation — but it is worth stating explicitly as a boundary on what passive capture can and cannot reliably deliver.

---

## 4. Why This Project Requires Both, Simultaneously, Not Either Alone

### 4.1 The Formal Argument

Restating Sections 2 and 3 as a direct logical argument:

- Stage 1 requires a controlled, swept `packet_size → RTT` dataset → **only active measurement can produce this** (Section 2.2, Section 3.3).
- Stage 2 requires contextual features describing concurrent ambient network load, independent of the researcher's own probe traffic, in order to explain *why* the Stage 1 residual (`12_residual_learning_theory.md`) is elevated or not at a given moment → **only passive measurement can produce this** (Section 3.2, Section 2.3).

**Neither method alone can supply what the other provides.** A project using active measurement alone could compute an accurate Stage 1 physical baseline but would have Stage 2 limited to only self-referential features (e.g., "how many probes has *this script* sent recently"), entirely blind to the actual, dominant source of real-world queuing delay — concurrent third-party traffic. A project using passive measurement alone could observe general traffic volume patterns but would have no clean, controlled `packet_size → RTT` relationship from which to extract the physical bandwidth and baseline-delay parameters in the first place, since organic traffic's packet sizes and destinations are not controlled by the researcher and cannot be relied upon to span the needed range.

### 4.2 The Concurrent-Capture Synchronization Requirement

Because both methods are needed **simultaneously**, this project's architecture (per the repository structure: `src/collection/experiment/runner.py` coordinating active probing while `src/collection/capture/passive.py` runs concurrently) must ensure the two data streams are **time-synchronized** precisely enough that a given active probe's RTT can be correctly matched against the passive traffic volume features observed in the specific, narrow time window immediately surrounding that probe's transmission. A timestamp misalignment between the two threads — even a small one — would cause a Stage 2 training row to pair an active probe's residual with the *wrong* window's ambient traffic context, silently corrupting the very relationship Stage 2 is trying to learn. This is precisely why `06_tcp_protocol.md` Section 5, `07_icmp_protocol.md` Section 5, and `08_udp_protocol.md` Section 5 each emphasize that the passive thread's BPF filter is designed specifically "to accurately log `recv_timestamp` without kernel thread delays" / "bypassing user-space thread scheduling latency" — this precision requirement exists precisely to support correct cross-stream alignment between the active and passive data, not merely for the active RTT measurement's own sake.

### 4.3 Complementary Blind Spots, Not Overlapping Redundancy

It is worth stating explicitly, because it clarifies why this is not a wasteful duplication of effort: active and passive measurement in this project's design are **not** two independent methods both trying to measure the same thing (in which case running both would be redundant) — they are two methods each measuring a **different, complementary half** of the full picture (the controlled physical-delay relationship vs. the uncontrolled ambient-congestion context), whose outputs are only combined downstream, in Stage 2's feature set, after being produced independently. This is the precise justification for the project's dual-thread collection architecture, rather than a simpler, single-method design.

---

## 5. Comparison Table

| Property | Active Measurement | Passive Measurement |
| :--- | :--- | :--- |
| **Does it inject traffic?** | Yes — deliberately crafted probes | No — observes pre-existing traffic only |
| **Can it control packet size?** | Yes — the core requirement for Stage 1's sweep | No — limited to whatever sizes naturally occur |
| **Can it control destination?** | Yes | No |
| **Can it control timing?** | Yes | No |
| **Does it see other users' traffic?** | No (Section 2.3) | Yes — this is its primary value (Section 3.2) |
| **Primary output used in this project** | `packet_size → RTT` pairs for Stage 1 | Concurrent traffic volume/rate features for Stage 2 |
| **Key limitation** | Blind to ambient network load it did not itself cause (Section 2.3); can itself perturb the network under dense sweeps (Section 2.4) | Cannot produce a controlled RTT measurement for a packet of a chosen size (Section 3.3) |
| **Relevant project source file** | `src/collection/probe/{icmp,tcp,udp}.py` | `src/collection/capture/passive.py` |

---

## 6. Relevance to Experimental Design and Known Confounds

### 6.1 Active Probing Frequency Is a Direct Trade-off, Not a Free Parameter

Per Section 2.4, there is a genuine tension in choosing how frequently to run the active sweep: **too infrequent**, and the resulting dataset has large temporal gaps, limiting Stage 2's ability to learn fine-grained rolling-window features (per `13_time_series_cross_validation.md`, Section 5.1, which depends on having dense-enough historical observations to compute meaningful rolling statistics); **too frequent**, and the active probing traffic itself begins to measurably contribute to the ambient congestion that passive capture is simultaneously trying to characterize as an independent variable, per Section 2.4's observer-effect concern, particularly for UDP sweeps given `08_udp_protocol.md`'s explicit warning on this point. This trade-off should be treated as an explicit, documented experimental design decision (with a stated probing interval and a stated justification for it) rather than an arbitrary implementation detail, since it directly affects the statistical cleanliness of the resulting dataset.

### 6.2 Passive Capture Completeness Depends on Interface Placement

Passive capture's value (Section 3.2) is entirely contingent on the sniffing thread actually having visibility into the traffic that matters — i.e., it must be capturing on the specific network interface through which the bottleneck link's traffic actually flows. On a typical single-NIC research/home setup this is usually straightforward, but if the probing node has multiple network interfaces (e.g., both Wi-Fi and Ethernet active simultaneously, or a VPN-tunneled virtual interface layered on top of a physical one), passive capture configured on the wrong interface could systematically **undercount** true ambient traffic volume, producing a Stage 2 feature that looks artificially low/quiet even during genuinely congested conditions — a silent data-quality issue that would not be obvious without explicitly verifying which interface is bearing the actual probe and background traffic during data collection.

### 6.3 This Note's Relationship to the Project's Overall Validity Chain

This note sits logically "upstream" of `12_residual_learning_theory.md` and `13_time_series_cross_validation.md`: those notes assume a dataset in which Stage 1's `packet_size → RTT` pairs and Stage 2's contextual features both already exist, correctly time-aligned and complete. This note establishes **why** both data sources are structurally necessary in the first place (Section 4), and flags the two concrete places (Section 6.1's frequency trade-off, Section 6.2's interface-placement completeness) where the underlying data collection itself — prior to any modeling step — could silently undermine everything built on top of it, regardless of how correctly Stage 1 and Stage 2 are subsequently implemented.

---

## 7. Summary: The Precise Chain of Reasoning

1. Active measurement deliberately injects controlled, researcher-chosen probe packets and directly produces the clean `packet_size → RTT` dataset Stage 1 requires, but is structurally blind to any network activity it did not itself cause, and can, under dense enough probing (particularly UDP), measurably perturb the very congestion state it is trying to help characterize (Section 2).
2. Passive measurement observes pre-existing, organic traffic and directly produces the ambient network-load context Stage 2 requires to explain residual queuing delay, but has no mechanism to produce a controlled RTT measurement for a packet of a chosen size, destination, or timing (Section 3).
3. These two blind spots are precisely complementary, not redundant: each method supplies exactly what the other structurally cannot, which is the direct, formal justification for this project's dual-thread (active + passive) collection architecture (Section 4.1, 4.3).
4. Because both streams are needed simultaneously and must be correctly paired per probe, tight timestamp synchronization between the active probing thread and the passive capture thread is a hard requirement, not a nice-to-have — a misalignment would silently corrupt the Stage 2 training data by pairing each residual with the wrong ambient-traffic context (Section 4.2).
5. Active probing frequency is a genuine, explicit design trade-off between dataset density (needed for rolling-window Stage 2 features) and self-induced congestion contamination (particularly relevant for UDP), and should be a documented decision rather than an arbitrary default (Section 6.1).
6. Passive capture's usefulness depends entirely on correct network-interface placement; capturing on the wrong interface in a multi-interface environment would silently undercount true ambient traffic without producing any obvious error (Section 6.2).
7. This note establishes the structural necessity and correct joint operation of the project's two measurement methods, sitting logically upstream of, and as a precondition for, the residual-validity and cross-validation concerns already addressed in `12_residual_learning_theory.md` and `13_time_series_cross_validation.md` (Section 6.3).