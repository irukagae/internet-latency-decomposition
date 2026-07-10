# Internet Latency Decomposition

A machine learning research project that decomposes aggregated Internet Round-Trip Time (RTT) measurements into their constituent physical and logical components using a domain-informed Two-Stage Hybrid Residual Architecture.

Instead of treating latency as a simple "speed test," this system maps the underlying components of network delay—propagation, transmission, processing, and queuing—to enable geographic network profiling, anomaly detection, and granular performance insights.

---

## 🔬 Mathematical Framework & Architecture

The project is governed by the classical network delay equation:

$$
D_{\text{total}} = D_{\text{prop}} + D_{\text{trans}} + D_{\text{proc}} + D_{\text{queue}}
$$

Standard machine learning models struggle to balance the rigid physical laws of serialization with the highly non-linear chaos of human-driven network traffic. To solve this, the framework uses a Two-Stage Hybrid Residual Architecture that decouples physics from congestion modeling.

```text
[ Raw active probe RTT data ]
             │
             ▼
┌──────────────────────────────────────────────┐
│ STAGE 1: The Physical Layer                  │
│ (Linear/Quantile Regression)                 │ ───► Isolates D_trans & Base D_prop
└──────────────────────┬───────────────────────┘
                       │
                       ▼ Calculate Residuals:
          Residual = RTT_actual - RTT_physical
                       │
                       ▼ Target variable is isolated D_queue
┌──────────────────────────────────────────────┐
│ STAGE 2: The Congestion Layer                │
│ (XGBoost Regressor)                          │ ───► Models bursty queuing behavior
└──────────────────────────────────────────────┘
```

### Stage 1: The Physical Layer (Linear / Quantile Regression)

**Objective:** Capture the deterministic, structural physics of the network path.

**Mechanics:** Regresses packet size against RTT to isolate the linear transmission delay:

$$
D_{\text{trans}} = \frac{\text{Packet Size}}{\text{Link Bandwidth}}
$$

**Output:** Extracts the true link capacity (from the slope $\beta_1$) and the zero-congestion baseline physical path delay (from the intercept $\beta_0 \approx D_{\text{prop}} + D_{\text{proc}}$).

### Stage 2: The Congestion Layer (XGBoost)

**Objective:** Capture the stochastic, non-linear patterns of network queuing delay ($D_{\text{queue}}$).

**Mechanics:** Learns exclusively from the mathematical residuals left behind by Stage 1:

$$
\text{Residual } (D_{\text{queue}}) = \text{RTT}_{\text{actual}} - \text{RTT}_{\text{physical\_predicted}}
$$

**Features:** Utilizes concurrent passive capture metrics (traffic volume, packet rates), precise time-of-day cyclostationary variables, target destination signatures, and network protocol flags.

---

## 🛠️ Stack & Technologies

- **Core Language:** Python 3.x (100%)
- **Network Manipulation Engine:** Scapy (low-level packet crafting, L2 injection via srp1(), asynchronous passive sniffing)
- **Data Engineering:** Pandas, NumPy
- **Statistical Modeling & Machine Learning:** Scikit-Learn, XGBoost
- **Visualizations & EDA:** Matplotlib, Seaborn

---

## 📂 Repository Structure

```text
internet-latency-decomposition/
├── src/
│   ├── collection/              # Data collection orchestration
│   │   ├── probe/               # Protocol-specific packet builders
│   │   │   ├── base.py          # RTT measurement abstraction & ARP caching
│   │   │   ├── icmp.py          # ICMP Type 8 Echo Request builder
│   │   │   ├── tcp.py           # TCP SYN packet builder (Port 80/443)
│   │   │   └── udp.py           # UDP datagram builder (Port 33434)
│   │   ├── capture/
│   │   │   └── passive.py       # Async background packet sniffing thread
│   │   ├── experiment/
│   │   │   └── runner.py        # Active probing loop & structural synchronization
│   │   └── persistence/
│   │       └── csv_writer.py    # Time-partitioned serialization logic
│   ├── orchestrator.py          # Main execution driver (Target/Size/Protocol sweeps)
│   ├── preprocessing.py         # Rolling feature extractors & Stage 1/2 data split pipeline
│   ├── model.py                 # Hybrid residual training framework (LR + XGBoost cascaded loops)
│   └── __init__.py
├── data/
│   ├── raw/                     # Time-partitioned CSV logs from active & passive loops
│   └── processed/               # Extracted features, scaled matrices, and isolated residuals
├── notebooks/                   # Jupyter notebooks for cross-country EDA & GMM clustering
├── notes/                       # In-depth architectural & protocol analysis notes
├── requirements.txt             # Project dependency manifest
└── README.md                    # System documentation
```

---

## 🗺️ Research Roadmap & Execution Timeline

This project performs a comparative geographical network study between Singapore (dense, low-propagation, tier-1 architecture) and India (geographically distributed, high-variance routing paths).

### Phase 1: High-Fidelity Data Collection (Current Status)

Run multi-week sweeps across 5 major global anycast DNS resolvers (8.8.8.8, 1.1.1.1, 9.9.9.9, OpenDNS, CleanBrowsing).

Capture protocol diversity across varied payload boundaries (64 to 1400 bytes) with concurrent background traffic sniffs.

**Milestone:** Establish robust, time-synchronized raw datasets for both geographic locations.

### Phase 2: Feature Engineering & Baseline Extrapolation (Weeks 1–2)

Clean raw datasets and map BPF-filtered incoming packets back to their unique experiment IDs.

Implement cyclic feature mapping (sine/cosine transformations) for time-of-day features to ensure 11:59 PM and 12:01 AM preserve structural proximity.

Extract temporal rolling windows from passive captures (e.g., historical packet frequency) as structural context for Stage 2.

### Phase 3: Hybrid Architecture Training & Evaluation (Weeks 3–5)

Implement Stage 1 Quantile Regression to fit the lower bounding envelope of the packet sweeps, isolating physical propagation limits without congestion interference.

Pipeline the computed physical prediction values out, construct the residual array ($D_{\text{queue}}$), and optimize the Stage 2 XGBoost Regressor hyper-parameters via specialized time-series cross-validation splits.

Validate the performance improvements of the Hybrid Cascade against isolated standard baselines (Pure Linear Regression and Pure XGBoost).

### Phase 4: Comparative Cross-Country Analysis & Paper Compilation (Weeks 6+)

Train Gaussian Mixture Models (GMMs) on isolated residuals to extract and map distinct routing states and congestion fingerprints between India and Singapore.

Document structural anomalies (e.g., Anycast routing updates tracked by packet TTL changes vs. localized bufferbloat).

Compile findings into a comprehensive academic research paper outlining the efficiency of domain-informed hybrid machine learning configurations over standard black-box architectures.

---

## 🚀 How to Run

### Installation & System Setup

Because Scapy relies on low-level raw socket interaction to craft packets and access network interfaces, execution requires root/administrator privileges.

```bash
# Clone the repository
git clone https://github.com/irukagae/internet-latency-decomposition.git
cd internet-latency-decomposition

# Install dependencies
pip install -r requirements.txt
```