# Research & Domain Knowledge Repository

This directory serves as the central knowledge base and theoretical foundation for the **Internet Latency Decomposition** research project. Rather than houses for disjointed files, the documents maintained here compile the core network science, mathematical proofs, and statistical modeling paradigms that justify and drive our engineering implementation.

> ⚠️ **Disclaimer:** The research documentation, mathematical formulations, and domain analyses contained within this directory are AI-generated. They have been dynamically synthesized and iteratively refined to align precisely with the specific architectural objectives, Windows-native telemetry environment, and hybrid modeling goals of this project.

---

## 🎯 Purpose & Core Objectives

The research documented in this directory bridges the gap between low-level raw network engineering and high-level applied data science. The notes are organized to provide a deep understanding of three main areas:

1.  **Protocol Behavioral Signatures:** Documenting how different layers of the OSI stack (Layer 3 vs. Layer 4, connectionless vs. connection-oriented) influence physical wire behavior, hardware parsing times, and response mechanics.
2.  **Mathematical Latency Bounding:** Defining the theoretical limits of network delay components ($D_{\text{prop}}$, $D_{\text{trans}}$, $D_{\text{proc}}$, and $D_{\text{queue}}$) so they can be mathematically isolated by our code.
3.  **Topology Telemetry Profiling:** Analyzing how geographical, infrastructural, and routing variations between high-density routing hubs (Singapore) and distributed subcontinental topologies (India) impact data variance and model portability.

---

## 🔬 Core Pillars of the Research Space

The documentation within this directory expands upon four critical operational domains:

### 📡 Network Layer Telemetry & Protocol Chaos
Investigates how transport and network layer protocols interact with intermediate infrastructure. This includes analyzing how TCP congestion windows ($cwnd$) interact with router queues to cause bufferbloat, how stateless UDP probing interacts with ISP rate-limiting/traffic-shaping policies, and how ICMP packets suffer from control-plane de-prioritization on core router CPUs.

### 📐 Domain-Informed Statistical Modeling
Explores the mathematical rationale behind using a **Two-Stage Hybrid Residual Architecture** over standard black-box machine learning approaches. The research maps out why deterministic physical constraints (like serialization delay scaling linearly with packet size) must be solved via a rigid linear/quantile layer, while highly non-linear, bursty human traffic cycles are left to tree-based ensemble models (XGBoost).

### 🌍 Cross-Country Topological Comparative Analysis
Hypothesizes and tracks the distinct behavioral variations between the two primary data collection nodes:
* **The Compact, Centralized Edge (Singapore):** Hyper-dense, negligible physical propagation limits, and rock-solid baselines where variance is driven almost entirely by localized logical queuing.
* **The Distributed, Multi-Hop Core (India):** High-variance propagation paths, asymmetric routing shifts, and distinct multi-hop processing delays that challenge baseline model generalization.

### 📊 Mathematical State Separation
Details how downstream unsupervised clustering methodologies (such as Gaussian Mixture Models) can be applied to isolated queuing residuals to mathematically distinguish between different routing paths, baseline operational states, and heavy congestion events.

---

## 💻 Windows Execution Context for Researchers

All empirical observations and protocol behaviors documented throughout these notes are framed around a **Windows 11 Native Development Environment**:

* **Npcap Core Driving:** Unlike Linux kernel-ring sniffing, all time-stamping documented here assumes packet capture is driven by the Npcap packet driver operating in WinPcap-compatible mode. This guarantees that probe arrival timestamps are captured at the driver layer, mitigating Windows user-space thread scheduling jitter.
* **Elevated Winsock Bypasses:** The active probing methodologies analyzed assume execution via an elevated command interface (Run as Administrator) to allow Scapy to execute raw Layer 2/3 socket injection, completely bypassing the automated controls of the standard Windows network stack.