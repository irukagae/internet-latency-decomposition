# Internet Control Message Protocol (ICMP) & Latency Dynamics

## 1. Overview in Latency Decomposition Context
In the internet latency decomposition framework, the Internet Control Message Protocol (ICMP) serves as the primary 
operational baseline for network-layer diagnostic probing. Operating strictly at Layer 3 (Network Layer), ICMP bypasses 
transport-layer state overheads (like TCP handshakes) and application-layer processing delays. This makes it an ideal 
instrument for capturing raw network transport characteristics, though it introduces distinct architectural quirks related 
to router prioritization.

---

## 2. Echo Request/Reply Mechanics
Active probing via ICMP utilizes the control messaging pair designed for connectivity verification (Ping).

```
Probing Node (Scapy)                         Target Resolver
           |                                           |
           | -- [Type 8: Echo Request] (size=X) -----> |  --> RTT_icmp
           |                                           |
           | <- [Type 0: Echo Reply] ----------------- |
```

### Latency Modeling Implications:
* **Stateless Measurements:** Because ICMP is connectionless, each probe is independent. The Round-Trip Time (RTT) represents a point-in-time snapshot of the current network state, unaffected by previous packet history or window sizes.
* **Minimal Processing Overhead:** Target servers handle ICMP Echo Requests directly within the kernel space network stack. This minimizes host-side processing delay ($D_proc \approx 0$), making the minimum observed ICMP RTT a highly accurate proxy for pure physical propagation delay ($D_prop$).

---

## 3. The ICMP Prioritization Bias ($D_proc$ and $D_queue$ Distortions)
While ICMP is excellent for baseline measurements, it introduces a major systemic bias known as **Control Plane De-prioritization**, which must be factored into the Gaussian Mixture Models (GMMs) and XGBoost features.

### Router Architecture & Control Plane Throttling
Modern routers split traffic handling into the *Data Plane* (fast path in hardware ASICs for standard TCP/UDP user data) and the *Control Plane* (CPU-driven software path for routing updates and management traffic).
* **De-prioritization:** When a core router along the path experience high traffic load, it will prioritize routing data plane packets over processing ICMP messages. This artificially inflates the processing delay ($D_proc$) of the ICMP probe at intermediate hops, which the model could misinterpret as path queuing congestion ($D_queue$).
* **Rate Limiting:** To prevent Denial of Service (DoS) attacks, many public DNS anycast edge routers enforce strict ICMP rate-limiting. When thresholds are breached, packets are dropped completely rather than queued, resulting in an artificial spike in the target packet loss metrics without a corresponding curve in queuing delay.

---

## 4. Mathematical Mapping of Transmission Delay ($D_trans$)
Because ICMP headers are lightweight and static (8 bytes), sweeping the underlying payload size provides a highly clean linear mapping for isolating serialization and transmission delays.

The total packet size on the wire is modeled as:

Total_Size = IP_Header (20 bytes) + ICMP_Header (8 bytes) + Raw_Payload (X bytes)

When regressing total packet size against RTT, the linear equation remains:

RTT = beta_0 + beta_1 * Total_Size + epsilon

* **ICMP Clean Envelope:** Because there are no dynamic TCP options (like SACK or Window Scaling) changing header sizes across packets, the step-increment of `packet_size` in your active probe loop provides a completely stable independent variable for calculating the link bandwidth coefficient (`1 / beta_1`).

---

## 5. Active Probing Execution via Scapy (Type 8 Echo Request)
In `src/collection/probe/icmp.py`, Scapy bypasses the OS `ping` utility to craft raw Layer-3 and Layer-4 headers, allowing exact byte alignment.

### Active Probing Architecture:
1. **Packet Composition:** An Layer-3 `IP()` header targets the destination anycast IP, bound to an Layer-4 `ICMP()` header where `type=8` (Echo Request) and `code=0`.
2. **Padding Constraints:** Arbitrary data padding is calculated and appended via the `Raw()` layer to sweep packet configurations from 64 to 1400 bytes.
3. **Passive Thread Mapping:** The concurrent passive capture thread listens for incoming packets matching `icmp and icmp[0] == 0` (Echo Reply) to extract highly precise arrival timestamps from the network interface card (NIC), bypassing user-space thread scheduling latency.