# ANYCAST DNS ROUTING

## 1. Overview in Latency Decomposition Context

This note explains **anycast routing** — the addressing and routing technique used by all five of this project's active probing targets (8.8.8.8, 1.1.1.1, 9.9.9.9, OpenDNS, CleanBrowsing, per `README.md`) — and precisely why this technique fundamentally changes how "distance to target" must be reasoned about in the Stage 1 physical model (`02_propagation_delay.md`, `10_quantile_regression_envelope.md`).

The central fact this note establishes: **an anycast IP address does not correspond to a single physical server in a single physical location.** It corresponds to *many* physical servers, deployed at many different locations worldwide, all simultaneously announcing the *same* IP address to the internet's routing infrastructure. Which physical server actually receives a given probe is determined dynamically by routing protocol behavior, not by anything the prober controls or can predict from the destination IP address alone. This has direct, concrete consequences for how this project's propagation-delay baseline, cross-country comparison, and quantile-regression envelope must all be interpreted.

---

## 2. Unicast vs. Anycast: The Fundamental Addressing Difference

### 2.1 Unicast — The Default, Familiar Model

Under standard **unicast** addressing, one IP address identifies **exactly one specific network interface, on exactly one specific physical machine, in exactly one specific physical location**. When a packet is sent to a unicast address, there is exactly one possible physical destination it can be routed toward, and that destination does not change over time (barring rare re-numbering events).

Under this model, the propagation delay formula from `02_propagation_delay.md` ($D_{\text{prop}} = D/S$) has an unambiguous meaning: $D$ is a fixed, well-defined physical distance between the prober and one specific, unchanging destination.

### 2.2 Anycast — Same IP Address, Many Physical Locations

Under **anycast** addressing, the *same* IP address (e.g., `8.8.8.8`) is simultaneously assigned to network interfaces on **many separate physical servers**, distributed across many separate data centers around the world (in the case of major public DNS providers, often dozens to hundreds of distinct physical sites globally). Every one of these physical sites independently announces, via the internet's inter-domain routing protocol (BGP — Border Gateway Protocol), "I am a valid destination for traffic addressed to `8.8.8.8`."

**The critical consequence:** when a probe packet is sent to `8.8.8.8`, it does not travel to one single, fixed, globally-unique server. Instead, standard internet routing (BGP path selection, which typically favors the path with the fewest inter-network hops — the "shortest AS path") delivers the packet to **whichever of the many announcing physical sites is closest, in terms of network routing topology, to the sender's own network location** — a property commonly summarized as anycast routing to the topologically "nearest" instance.

### 2.3 Why "Nearest" Means Nearest in Routing Topology, Not Physical Geography

A critical, easy-to-misunderstand nuance: BGP path selection is based on **routing-topology proximity** (fewest autonomous system hops, and other BGP path-selection attributes such as local preference and MED, configured independently by every network operator along the way) — **not** literal physical/geographic proximity. It is entirely possible, and not uncommon in practice, for a prober in one city to be routed to an anycast instance in a *more distant* city (by straight-line geographic distance) simply because the network path to that more distant instance happens to traverse fewer autonomous system hops, or because of business/peering-relationship routing preferences between ISPs that have nothing to do with physical distance. **"Nearest" in the anycast sense is a statement about the graph structure of internet routing, not a statement about physical geography.**

---

## 3. Why This Breaks the Naive Propagation-Delay Model

### 3.1 The Assumption Anycast Violates

`02_propagation_delay.md`'s formula, $D_{\text{prop}} = D/S$, and its stated application ("Propagation delay can be estimated using the geographical distance between the two endpoints"), implicitly assumes a **fixed, known, single destination location**. Anycast directly violates the "fixed, known, single destination" part of this assumption:

- **The specific physical instance actually reached is not exposed by the destination IP address itself.** `8.8.8.8` looks identical on the wire regardless of which of Google's dozens of anycast instances actually answers a given probe.
- **The specific instance reached can differ between the Singapore and India probing locations, even for the exact same destination IP**, precisely because BGP path selection depends on the prober's own network position (Section 2.3) — meaning a straightforward "distance from Singapore to $X$" vs. "distance from India to $X$" comparison is not even well-posed unless it is first established that "$X$" refers to the same physical instance in both cases, which cannot be assumed.
- **The specific instance reached can, in principle, change over time** for a single fixed probing location, if the announcing network's BGP routes shift (e.g., due to a routing policy change, a link failure rerouting traffic to a different instance, or planned maintenance) — this is a second, independent source of the "structural break" / "BGP routing shift" scenario already flagged as a risk in `10_quantile_regression_envelope.md`, Section 5 ("India Envelope... if an ISP dynamically switches intermediate paths mid-experiment").

### 3.2 Direct Implication: The Stage 1 Baseline Estimates a *Path*, Not a *Point*

Given Section 3.1, the correct interpretation of Stage 1's fitted intercept ($\hat\beta_0 = D_{\text{prop}} + D_{\text{proc}}$, per `10_quantile_regression_envelope.md`, Section 4) must be revised from "the physical delay to reach destination server $X$" to the more precise and more defensible: **"the physical delay along the path to whichever anycast instance BGP currently routes this specific prober's traffic toward."** This is not a cosmetic wording change — it has a direct consequence for Section 5 below.

---

## 4. Anycast and Route Stability: A New, Anycast-Specific Source of "Structural Breaks"

### 4.1 Recap: The Structural Break Problem Already Identified

`10_quantile_regression_envelope.md`, Section 5, and `12_residual_learning_theory.md`, Section 6.2, both already flag "a mid-experiment BGP routing change" as a failure mode requiring Time-Window Localized Quantile Regression. This note supplies a specific, concrete, and highly plausible **mechanism** by which such a routing change can occur, distinct from ordinary path-level BGP churn on a unicast destination.

### 4.2 Anycast-Specific Route Flap: "Instance Flapping"

Because multiple physically distant instances are simultaneously eligible destinations for the same anycast IP (Section 2.2), and because BGP path-selection outcomes between near-equally-attractive paths can be sensitive to minor, transient changes in network conditions (a link congestion event, a brief outage, a routine BGP session reset at any intermediate network), it is possible for a *single prober's* traffic to be rerouted from one anycast instance to an **entirely different, physically distant** instance, and potentially back again, **within the timespan of a single data-collection run** — a phenomenon sometimes informally called "anycast instance flapping" or "anycast route flapping."

**Why this is a materially more severe structural break than ordinary unicast route changes:** an ordinary unicast BGP path change typically reroutes traffic to the *same physical destination* via a moderately different path, producing a modest, incremental shift in $D_{\text{prop}}$. An anycast instance flap can reroute traffic to a **completely different physical destination**, potentially thousands of kilometers away, in a different country with entirely different local infrastructure, producing a **large, discontinuous jump** in the true physical baseline — not a gradual drift, but an instantaneous step-change in the underlying "ground truth" that Stage 1 is trying to estimate.

### 4.3 Direct, Concrete Diagnostic: Using TTL as an Anycast-Instance-Change Detector

This note makes explicit and actionable a technique already referenced in passing in `10_quantile_regression_envelope.md`, Section 5 ("controlled for route changes via Npcap `ttl` feature tracking"), specifically in its anycast context:

- The IP header's **Time-To-Live (TTL)** field is decremented by exactly 1 at every router hop a packet passes through (this is the mechanism, per `05_processing_delay.md`'s $D_{\text{modification}}$ term, underlying standard `traceroute` tools).
- The **received** TTL value of a reply packet (subtracted from the sender's known initial TTL, typically a round power-of-two-adjacent default like 64, 128, or 255 depending on the remote OS) reveals the **exact number of router hops** the reply traversed.
- **If two consecutive probes to the exact same anycast destination IP return replies with a visibly different derived hop count**, this is strong, direct, per-packet evidence that the probe was answered by a **different physical anycast instance** than the previous probe — since the hop count to a genuinely fixed, unchanging destination should be highly stable over the short timescales between consecutive probes, whereas a hop-count *shift* is exactly what would result from being routed to a different, differently-distanced physical instance.

**Concrete recommended implementation for this project's preprocessing pipeline:** compute a derived `hop_count` feature from each response's TTL for every probe, and flag (or entirely segment out) any contiguous block of probes whose hop count has shifted from the immediately preceding block by more than a small tolerance (e.g., ±1, to allow for ordinary, non-anycast-related minor path fluctuation) as belonging to a **distinct anycast-instance regime**, to be treated as its own independent Stage 1 fitting window — directly operationalizing the "Time-Window Localized Quantile Regression" mitigation already specified in `10_quantile_regression_envelope.md`.

---

## 5. Relevance to This Project's Cross-Country Comparison (Section 7 of `README.md`'s Phase 4)

### 5.1 Singapore vs. India: Differing Anycast Catchment Characteristics

Per `09_protocol_comparison.md`, Section 4, this project's own working hypothesis already states that Singapore, sitting near major Tier-1 exchange points, should show minimal $D_{\text{prop}}$ variance, while India's more distributed, multi-hop topology should show greater variance. Anycast routing provides a direct, additional, and highly plausible structural reason *why* this specific asymmetry should be expected, beyond the general "distributed topology" framing already given:

- **Singapore** is itself host to, or extremely well-connected (via major regional Tier-1/Tier-2 transit and peering infrastructure) to, anycast instances for most or all five of this project's major public DNS providers (Google, Cloudflare, Quad9, OpenDNS, CleanBrowsing all maintain significant Asia-Pacific presence, commonly including Singapore itself as a regional hub). A Singapore-based prober is therefore likely to be consistently routed to a **nearby, stable** anycast instance for every target, and to stay routed to that same instance throughout a collection run — directly supporting the "high density, minimal variance" characterization already given in `10_quantile_regression_envelope.md`, Section 5.
- **India**, per the project's own working hypothesis (multi-hop, subcontinental routing, `09_protocol_comparison.md`), may be routed to anycast instances that are farther away, may have **more genuinely competitive, near-equally-attractive alternative paths to multiple different distant instances** (increasing the likelihood of the instance-flapping phenomenon described in Section 4.2), and may exhibit **provider-to-provider variation in instance placement quality** — i.e., a well-provisioned anycast network might maintain a nearby regional instance serving India specifically, while a less extensively deployed provider might not, causing probes to different DNS providers from the same Indian vantage point to be routed to instances at meaningfully different distances, in a way that would not occur under Singapore's more uniformly well-served routing environment.

### 5.2 A Concrete, Testable Prediction This Note Generates

Given Section 5.1, this note generates a specific, falsifiable prediction that can be checked directly against real collected data once available: **the derived `hop_count` feature (Section 4.3) should show measurably lower variance, and fewer instance-flap events, in the Singapore dataset than in the India dataset, across all five target providers.** This is presented explicitly as a hypothesis to validate empirically, not as an established finding — but it is a direct, concrete, testable consequence of the anycast routing theory presented in this note, and confirming or refuting it provides independent evidence for or against the broader "Singapore = stable, India = volatile" narrative this project's roadmap is built around.

---

## 6. Practical Implications for Active Probing and Data Collection

### 6.1 A Single "Distance to Target" Feature Is Not Well-Defined for Anycast Targets

Any feature engineering step that attempts to use a **static, precomputed geographic distance** to a DNS provider's IP address (e.g., by geolocating the IP address once via a public geolocation database and treating that as a fixed feature) is methodologically unsound for anycast targets, per Section 3.1–3.2. IP geolocation databases frequently either report the anycast operator's **corporate headquarters location** (which may have no relationship whatsoever to which physical instance actually answers a given probe) or, at best, an approximate regional location for one commonly-observed instance — neither of which reliably reflects the *actual* instance reached by a *specific* probe at a *specific* time.

**Correct alternative, consistent with Section 4.3**: rather than treating "distance to target" as a static, externally-sourced feature, this project's pipeline should treat the derived `hop_count` (or, where feasible, a full `traceroute`-style hop-by-hop path trace run periodically alongside the main probing loop) as the empirically grounded, per-probe proxy for path length — since it is derived directly from the actual packets that actually traversed the actual path taken by that specific probe, rather than from an external, potentially stale or approximate database lookup.

### 6.2 Rate-Limiting Behavior May Also Differ Per-Instance

As a secondary, related point building on `07_icmp_protocol.md`, Section 3 ("ICMP Rate Limiting... many public DNS anycast edge routers enforce strict ICMP rate-limiting"): because different anycast instances of the same provider are physically distinct servers/routers, potentially operated with **independently configured** rate-limiting policies (even under the same corporate provider), a probing pattern that appears to trigger rate-limiting at one point in a collection run and not at another may, in part, reflect having been transparently rerouted to a *different* physical instance with different local rate-limiting configuration — not necessarily a genuine change in the *same* instance's policy or load. This is offered as an additional plausible explanation to consider (alongside genuine load-based throttling) when interpreting any observed packet-loss or rate-limiting pattern in the collected data, and reinforces the value of the hop-count-based instance-flap detection described in Section 4.3 as a general-purpose diagnostic tool.

---

## 7. Summary: The Precise Chain of Reasoning

1. Anycast addressing assigns the *same* IP address to *many* physically distinct servers worldwide; BGP routing delivers each probe to whichever announcing instance is topologically (not necessarily geographically) nearest the sender, a decision made independently for each network path and potentially each moment in time (Section 2).
2. This directly violates the "fixed, single, known destination" assumption implicit in the basic propagation-delay model (`02_propagation_delay.md`), meaning Stage 1's fitted intercept must be reinterpreted as describing the path to *whichever instance is currently being routed to*, not a fixed physical point (Section 3).
3. Because multiple physically distant instances can be near-equally attractive under BGP path selection, a single prober's traffic can be transparently rerouted between entirely different physical instances mid-collection — "anycast instance flapping" — producing large, discontinuous jumps in the true physical baseline that are structurally distinct from, and potentially more severe than, ordinary unicast route changes (Section 4.2).
4. Derived hop-count (from response TTL) is a direct, per-packet, empirically grounded diagnostic for detecting these instance changes, and should be used to segment the dataset into distinct Stage 1 fitting windows, operationalizing the mitigation already specified in `10_quantile_regression_envelope.md` and `12_residual_learning_theory.md` (Section 4.3).
5. This theory provides a concrete, mechanistic explanation for why Singapore is expected to show lower propagation-baseline variance than India in this project's own working hypothesis — differing anycast instance density, proximity, and routing stability across the two regions — and generates a specific, falsifiable, testable prediction (lower hop-count variance and fewer instance-flap events in Singapore) that should be checked against real data (Section 5).
6. Static, externally-sourced IP geolocation is not a methodologically sound way to compute a "distance to target" feature for anycast destinations; the empirically-derived, per-probe hop-count feature is the correct alternative, and should also inform interpretation of any observed rate-limiting or packet-loss patterns, since these too may vary by physical instance rather than reflecting a uniform, provider-wide policy (Section 6).