# User Datagram Protocol (UDP) & Latency Dynamics

## 1. Overview in Latency Decomposition Context
Within the internet latency decomposition framework, the User Datagram Protocol (UDP) offers a connectionless, stateless 
transport-layer alternative to TCP. Featuring a minimal, fixed 8-byte header, UDP introduces no protocol-level handshake 
or state-tracking overhead. This makes it an invaluable probe type for capturing the raw, immediate state of network 
pipelines, though its interaction with network security policies and firewalls introduces unique measurement features.

---

## 2. Probing Mechanics via ICMP Port Unreachable Responses
Because UDP is connectionless and does not have a native universal echo mechanism (unlike ICMP Echo Requests), active 
probing to public destinations relies on eliciting standard error responses from the target's network stack. Our framework 
targets port `33434` (the classical baseline port for standardized traceroute operations).

```
Probing Node (Scapy)                         Target Resolver
           |                                           |
           | ---- [UDP Datagram] (Port 33434) -------> |  --> RTT_udp
           |                                           |
           | <--- [ICMP Type 3 Code 3] --------------- |
           |      (Destination Port Unreachable)       |
```

### Latency Modeling Implications:
* **Cross-Protocol Round Trip:** The measured RTT spans a hybrid path: a Layer-4 UDP datagram traveling outbound, and a Layer-3 ICMP Destination Unreachable packet traveling inbound. 
* **Host Processing Accuracy:** When the target receives a packet on a closed UDP port, the operating system kernel immediately generates an ICMP error packet. This bypasses application-layer scheduling entirely, keeping host processing delay ($D_{\text{proc}}$) negligible.

---

## 3. Absence of Flow Control & Congestion Fingerprinting
Unlike TCP, UDP does not possess a Congestion Window ($cwnd$) or flow control feedback loops. It injects packets onto the wire exactly at the rate dictated by the application layer.

### Buffer Overflows and Queue Slicing
* Because UDP does not back off when encountering network congestion, executing high-frequency UDP sweeps can deliberately strain bottleneck queues.
* When router buffers reach capacity, UDP packets are dropped indiscriminately alongside TCP packets. However, while TCP drops cause the sender to scale back transmission rates, UDP drops act as sharp, non-linear cutoffs in your dataset.

### ISP Traffic Policing & Shaping (XGBoost Features)
Many internet service providers (ISPs) and edge routers deploy strict Traffic Policing policies specifically targeting UDP traffic to mitigate amplification DDoS attacks.
* **Rate Limiting:** If our active probe sweeps cross a volume threshold within a tight time window, routers may artificially queue or drop subsequent UDP probes.
* **Distribution Profiles:** In our Gaussian Mixture Models (GMMs), this behavior manifests as a distinct high-latency component (policed queue) or a sudden spike in the packet loss feature, separate from standard TCP congestion behavior.

---

## 4. Mathematical Mapping of Transmission Delay ($D_{\text{trans}}$)
UDP utilizes a completely fixed, simple header layout consisting of 4 fields (Source Port, Destination Port, Length, Checksum) totaling exactly 8 bytes.

The total packet size on the wire is modeled explicitly as:

$$\text{Total\_Size} = \text{IP\_Header (20 bytes)} + \text{UDP\_Header (8 bytes)} + \text{Raw\_Payload (X bytes)}$$

When regressing total packet size against RTT to isolate serialization bottlenecks:

$$\text{RTT} = \beta_0 + \beta_1 \cdot \text{Total\_Size} + \epsilon$$

* **Structural Predictability:** Because the UDP header size never scales or changes dynamically (unlike TCP options such as timestamps or window scaling), the structural relationship between `packet_size` and $D_{\text{trans}}$ is perfectly linear. The slope ($\beta_1$) provides a remarkably clean estimate of physical bottleneck link capacity ($1/C$).

---

## 5. Active Probing Execution via Scapy (Port 33434 Probing)
In our active network engine (`src/collection/probe/udp.py`), Scapy bypasses standard OS socket layer constraints to craft raw datagram sequences.

### Implementation Blueprint:
1. **Packet Composition:** Layer-3 `IP()` configuration paired directly with Layer-4 `UDP()` layers targeting destination port `33434`.
2. **Payload Sweeps:** An arbitrary byte array (`Raw(RandString(size))`) is injected to scale the total wire footprint linearly from 64 up to 1400 bytes.
3. **Passive Integration:** The background capture thread tracks returning packets using the specific BPF filter: `icmp and icmp[0] == 3 and icmp[1] == 3`. This extracts precise hardware-level arrival timestamps from the network interface card (NIC), bypassing user-space scheduling jitter.