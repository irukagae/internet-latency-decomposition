# MTU AND FRAGMENTATION

## 1. Overview in Latency Decomposition Context

This note explains **Maximum Transmission Unit (MTU)** and **IP fragmentation**, and precisely why the project's deliberate packet-size sweep design (64–1400 bytes, referenced throughout `06_tcp_protocol.md`, `07_icmp_protocol.md`, `08_udp_protocol.md`) is not an arbitrary range but a specific, necessary engineering choice to keep the Stage 1 linear regression model (`03_transmission_delay.md`, `10_quantile_regression_envelope.md`) mathematically valid. It also documents the specific failure modes that occur if this constraint is violated, since a fragmented packet does not simply behave like "one more packet, slightly delayed" — it breaks the fundamental one-packet-to-one-RTT-measurement assumption this entire project is built on.

---

## 2. What MTU Actually Is

### 2.1 Definition

The **Maximum Transmission Unit (MTU)** of a network link is the largest size, in bytes, of a single Layer-3 (IP) packet that link is capable of transmitting as one indivisible unit, without needing to be split apart.

- **Ethernet's standard MTU** is **1500 bytes** — this is the single most common MTU value across the modern internet's access and core links, and is the de facto ceiling this project's packet-size sweep design is built around.
- MTU is a **per-link** property, not a per-path or per-packet property. A single end-to-end path from the probing node to a target resolver may cross **many** links (home router → ISP access network → ISP core → transit provider → target's network), and **each individual link along that path may have a different MTU**.

### 2.2 Path MTU: The Governing Constraint for an Entire Route

Because a packet must successfully traverse **every single link** along its path, the **effective maximum packet size for the entire path** is governed by whichever single link along that path has the **smallest** MTU — a quantity called the **Path MTU (PMTU)**:

$$
\text{PMTU} = \min(\text{MTU}_1, \text{MTU}_2, \dots, \text{MTU}_n)
$$

Where $\text{MTU}_1, \dots, \text{MTU}_n$ are the MTU values of each of the $n$ individual links composing the full path. A packet larger than the Path MTU **cannot** be delivered across the full path as a single unit — something must happen to it at whichever link it first fails to fit through (Section 3 covers exactly what).

### 2.3 Why 1500 Bytes Is Not a Universal Guarantee

While Ethernet's 1500-byte MTU is extremely common, it is **not universal**, and this project's probing paths (crossing multiple ISPs, transit providers, and potentially satellite, mobile, or VPN-tunneled segments depending on the exact network environment) may encounter links with a **smaller** effective MTU than 1500 bytes, for well-documented reasons:

- **PPPoE (Point-to-Point Protocol over Ethernet)**, commonly used by residential DSL/fiber ISPs, adds its own 8-byte header, reducing the usable MTU to **1492 bytes**.
- **Tunneling protocols** (VPNs, GRE, IPsec, MPLS) each add their own encapsulating headers on top of the original packet, reducing the effective MTU available to the original (inner) packet by the size of that tunnel's overhead — commonly reducing usable MTU to a range anywhere from roughly 1400 to 1480 bytes, depending on the specific tunneling technology and its configuration.
- **Legacy or specialized links** (some older DSL/cable equipment, some mobile carrier networks) may impose other, non-standard MTU values.

**This is precisely why this project's active probing sweep is deliberately bounded at 1400 bytes** (rather than sweeping all the way up to the Ethernet-standard 1500-byte ceiling) — the 1400-byte ceiling is a deliberate, conservative safety margin, chosen specifically to stay comfortably below the smallest MTU plausibly encountered across the diverse, multi-hop, cross-ISP, cross-country paths this project probes (Singapore and India), rather than assuming the Ethernet-standard 1500-byte MTU holds uniformly across every link on every path, which — per the reasoning above — cannot be safely assumed.

---

## 3. What Happens When a Packet Exceeds the Path MTU: Fragmentation

### 3.1 The Two Possible Outcomes

When a packet larger than a given link's MTU needs to cross that link, exactly one of two things happens, governed entirely by a single bit in the IP header: the **Don't Fragment (DF)** flag.

**Outcome A — Fragmentation (DF flag = 0, fragmentation permitted):**

The router at that link splits (**fragments**) the oversized packet into multiple smaller packets (fragments), each small enough to fit within that link's MTU, each carrying its own copy of the IP header (with appropriate offset and "more fragments" metadata) plus a portion of the original packet's payload. These fragments are transmitted separately across the constraining link and are expected to be **reassembled back into the original single packet only at the final destination host** — intermediate routers along the rest of the path do not reassemble fragments; they simply forward each fragment independently, like any other packet.

**Outcome B — Fragmentation-Needed Error (DF flag = 1, "Don't Fragment"):**

If the oversized packet has its DF flag set, the router is **forbidden** from fragmenting it. Instead, the router **drops the packet entirely** and, if functioning correctly, sends back an **ICMP Type 3, Code 4 ("Fragmentation Needed and DF Set")** error message to the original sender, informing it of the MTU of the link that could not accommodate the packet. This is the mechanism underlying a technique called **Path MTU Discovery (PMTUD)** — a sender can deliberately set the DF flag and use these error responses to iteratively discover the actual Path MTU without ever needing fragmentation to occur at all.

### 3.2 Why Fragmentation Is a Direct Threat to This Project's Measurement Model

This project's entire Stage 1 methodology (`03_transmission_delay.md`, `10_quantile_regression_envelope.md`) rests on a foundational, largely implicit assumption:

> **One probe → one packet → one RTT measurement, where the measured RTT corresponds directly and exclusively to that one packet's transmission, propagation, processing, and queuing delay.**

Fragmentation **breaks this assumption outright**, for several independent, compounding reasons:

1. **A fragmented probe is no longer "one packet."** If a 1400-byte ICMP probe (per `07_icmp_protocol.md`) crosses a link with, say, a 1300-byte effective MTU, it is split into two (or more) separate IP fragments. The RTT ultimately observed by the passive capture thread reflects the time for **both** fragments to be sent, potentially reassembled at the destination, and answered — not the clean, single-packet transmission delay the linear model in `03_transmission_delay.md` assumes.
2. **Transmission delay is no longer simply $L/R$ for the original packet.** Each fragment incurs its **own** transmission delay for its own (smaller) size, and these are not simply additive in an easily invertible way once reassembly, potential fragment reordering, and destination-side reassembly buffering delays are factored in. Fitting a linear model treating `packet_size` (the *original*, pre-fragmentation size) as the independent variable directly against the resulting RTT will systematically **misestimate** the true bandwidth slope $\beta_1$, since some data points now silently reflect a two-fragment transmission process rather than the clean single-packet process the model assumes.
3. **Fragment loss causes silent, hard-to-diagnose total failures.** If **any single fragment** among a packet's fragments is lost in transit, the destination can never complete reassembly of the original packet, and the **entire original packet is effectively lost** — even though only one (smaller) fragment out of several was actually dropped. This means fragmentation can produce packet-loss events at a **higher effective rate** than the underlying per-packet loss probability would suggest, since a single fragment loss anywhere causes total loss of the larger logical packet — a subtlety that would corrupt any packet-loss-rate feature computed naively without accounting for fragmentation.
4. **Fragmentation reassembly introduces additional, non-network processing delay.** The destination host's operating system kernel must buffer arriving fragments and perform reassembly logic before the packet can be handed off to the ICMP/UDP/TCP stack for a reply to be generated — this adds a genuinely new source of processing delay (`05_processing_delay.md`) that does not exist for a non-fragmented packet, and which this project's existing processing-delay note does not currently account for, since it assumes single, complete packets throughout.

### 3.3 Why This Project's 64–1400 Byte Sweep Range Is a Deliberate Mitigation, Not an Arbitrary Choice

Given Section 3.2, the project's active probing range — 64 to 1400 bytes, referenced identically across `06_tcp_protocol.md`, `07_icmp_protocol.md`, and `08_udp_protocol.md` — should now be understood precisely as follows: the **upper bound (1400 bytes)** is set specifically to stay below the smallest MTU plausibly encountered on any real-world path this project probes (Section 2.3), specifically **to avoid triggering fragmentation at all**, keeping every single probe a clean, single-packet, single-fragment transmission whose RTT cleanly reflects the four decomposable delay components this entire project is built to isolate (`01_latency.md`). This is the single most important practical justification, previously unstated explicitly, for why the sweep range is bounded exactly where it is.

---

## 4. Direct Diagnostic and Preprocessing Implications

### 4.1 Explicitly Setting the DF Flag During Active Probing

Given Section 3.3's goal (avoiding fragmentation entirely), this project's active probing implementation should **explicitly set the Don't Fragment (DF) flag** on every crafted probe packet (in Scapy, via the IP layer's `flags='DF'` parameter), rather than leaving fragmentation implicitly permitted by default. This converts a *silent, hard-to-detect* fragmentation event (Section 3.2) into an **explicit, easily detected failure**: if a probe genuinely exceeds the true Path MTU of a specific real-world path (despite the conservative 1400-byte ceiling), setting DF guarantees the sender receives a clear, unambiguous **ICMP Fragmentation Needed** error (Section 3.1, Outcome B) rather than having the packet silently fragmented and producing a subtly corrupted RTT measurement that would otherwise be indistinguishable from a normal, valid data point.

### 4.2 Treating "Fragmentation Needed" Errors as a Distinct, Loggable Event Type

The passive capture thread's BPF filters (already documented per-protocol in `06_tcp_protocol.md` Section 5, `07_icmp_protocol.md` Section 5, `08_udp_protocol.md` Section 5) should be extended to **also** explicitly capture and log any received `icmp and icmp[0] == 3 and icmp[1] == 4` packets (ICMP Type 3, Code 4 — Fragmentation Needed, per Section 3.1) as their own distinct event category, separate from a normal successful reply and separate from ordinary packet loss (timeout with no response at all). This distinction matters because a Fragmentation-Needed response is a **deterministic, path-structural fact** (this specific path's Path MTU is smaller than the attempted packet size) rather than a stochastic congestion-related loss event (`04_queuing_delay.md`) — conflating the two into a single generic "packet loss" feature would misattribute a structural path property to what the rest of this project's modeling framework treats as a congestion signal.

### 4.3 Sanity-Checking the Sweep Ceiling Empirically, Not Just Theoretically

Because Section 2.3 establishes that real-world effective MTU can plausibly dip as low as ~1400 bytes under certain tunneling configurations, the 1400-byte sweep ceiling, while a reasonable conservative default, is not an absolute guarantee against ever triggering a Fragmentation-Needed response on every possible real-world path. **Concrete recommended check:** during initial data collection for each new target/network-environment combination (i.e., each of the 5 DNS resolvers, from each of the Singapore and India vantage points), explicitly verify — via the DF-flag-triggered error detection described in Section 4.1–4.2 — that **zero** Fragmentation-Needed events occur across the full sweep range before treating that dataset as clean. If any such events are observed for a specific target/environment combination, the sweep ceiling for that specific combination should be reduced (e.g., to 1350 or 1300 bytes) rather than silently accepting the resulting fragmented, methodologically compromised data points into the Stage 1 training set.

### 4.4 A Secondary, Related Consideration: The Protocol Header Overhead Interacts With the MTU Ceiling

This connects directly to the total-packet-size formulas already given per-protocol in `07_icmp_protocol.md` (Section 4) and `08_udp_protocol.md` (Section 4):

$$
\text{Total\_Size} = \text{IP\_Header (20 bytes)} + \text{Transport\_Header (8 bytes, ICMP/UDP)} + \text{Raw\_Payload (X bytes)}
$$

**This is the value that must be kept under the effective Path MTU — not the raw payload size $X$ alone.** A probe loop that sweeps `X` (the `Raw()` padding parameter passed to Scapy) up to a full 1400 bytes, without accounting for the additional 28 bytes of IP+ICMP/UDP header overhead, would actually be putting a **1428-byte** packet on the wire — already exceeding the intended 1400-byte safety ceiling described in Section 3.3, and creeping uncomfortably close to the standard 1500-byte Ethernet MTU with essentially no safety margin left for any of the MTU-reducing scenarios described in Section 2.3. **The correct implementation sweeps the *raw payload* `X` such that the *total wire size* (including all headers) stays at or below the intended 1400-byte ceiling** — for ICMP/UDP (28 bytes of combined IP+transport header), this means the raw payload parameter itself should be swept only up to approximately 1372 bytes to keep total wire size at exactly 1400 bytes; for TCP (which per `06_tcp_protocol.md` may have a variable header size due to optional fields, as already flagged in `09_protocol_comparison.md`'s "TCP: Dynamic Overhead Distortion"), an even larger safety margin below 1400 bytes total wire size is warranted specifically to accommodate this header-size variability.

---

## 5. Relevance to Stage 1 Model Validity (Cross-Reference)

### 5.1 Direct Connection to Residual Learning Theory's Condition 1

`12_residual_learning_theory.md`, Section 3.1 (Condition 1) requires that Stage 1's assumed functional form — $\text{RTT} = \beta_0 + \beta_1 \cdot \text{packet\_size}$, strictly linear — correctly reflects the true underlying physical relationship. Section 3.2 of this note demonstrates precisely **one concrete, previously-unstated mechanism by which Condition 1 can be silently violated**: if even a small subset of probes within the training sweep happen to be fragmented (due to an unexpectedly low real-world Path MTU on some subset of paths, per Section 4.3), those specific data points no longer follow the clean linear transmission-delay relationship the model assumes, and will appear in the dataset as unexplained, unusually high-RTT outliers that do not fit the fitted line — potentially being misattributed as extreme *queuing delay* residual values (`04_queuing_delay.md`) once passed into Stage 2, when in fact they reflect a structural, deterministic fragmentation-and-reassembly artifact rather than genuine network congestion.

### 5.2 Why This Reinforces (Rather Than Duplicates) the Quantile Regression Approach

It is worth being precise about the division of labor here: `10_quantile_regression_envelope.md`'s quantile regression approach is designed to robustly handle *ordinary, expected* queuing-delay noise contaminating the scatter plot (Section 2 of that note). It is **not** designed to, and should not be relied upon to, silently absorb or correctly handle occasional fragmentation-induced outliers, which are a **fundamentally different kind of data contamination** — a deterministic, structural measurement artifact rather than genuine stochastic network noise. Fragmented data points should be explicitly detected and excluded via the mechanisms in Section 4.1–4.2 **before** the quantile regression step, not left in the dataset under the assumption that the lower-envelope-fitting procedure will naturally handle them — a fragmentation-induced RTT spike could, in principle, still fall anywhere in the distribution (not necessarily at the extreme high end), and there is no guarantee the quantile regression's specific $\tau = 0.05$ envelope-fitting approach would reliably exclude it the way it is designed to exclude ordinary congestion-driven noise.

---

## 6. Summary: The Precise Chain of Reasoning

1. Every network link has a maximum packet size (MTU) it can carry as one unit; the smallest MTU among all links on a given path (the Path MTU) governs the largest packet size that can cross that entire path without being split (Section 2).
2. Real-world Path MTU is frequently smaller than the commonly-assumed 1500-byte Ethernet standard, due to PPPoE, tunneling, and other overhead-adding protocols — this is the specific, concrete reason this project's sweep design uses a conservative 1400-byte ceiling rather than sweeping to 1500 bytes (Section 2.3, 3.3).
3. A packet exceeding the Path MTU is either silently fragmented into multiple sub-packets (if permitted) or dropped with an explicit ICMP error returned (if the Don't-Fragment flag is set) — and fragmentation directly breaks this project's foundational one-packet-to-one-clean-RTT-measurement assumption, corrupting the transmission-delay linear relationship, inflating apparent packet loss, and introducing unaccounted-for reassembly processing delay (Section 3).
4. The correct, recommended implementation explicitly sets the Don't-Fragment flag on every probe (converting a silent corruption risk into an explicit, detectable error), separately logs any resulting Fragmentation-Needed ICMP responses as a distinct, structural (non-congestion) event category, and empirically validates per-target/per-environment that the sweep ceiling is genuinely low enough to avoid triggering fragmentation on real observed paths (Section 4.1–4.3).
5. The sweep ceiling must account for the full on-wire packet size (IP header + transport header + raw payload), not the raw payload size alone — a common, easy-to-make implementation mistake that could silently reintroduce exactly the fragmentation risk the sweep design is meant to avoid (Section 4.4).
6. Occasional undetected fragmentation directly violates Condition 1 of `12_residual_learning_theory.md` and produces a structurally different, deterministic form of data contamination that should be explicitly filtered out before Stage 1 fitting — not conflated with, or assumed to be automatically handled by, the quantile-regression approach already used to manage ordinary stochastic queuing noise in `10_quantile_regression_envelope.md` (Section 5).