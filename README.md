# Internet Latency Decomposition 

An end-to-end Machine Learning project to decompose aggregated Internet Round-Trip Time (RTT) into its constituent physical and logical components. This system moves beyond simple "speed tests" to diagnose the *root cause* of network latency using statistical modeling and packet-level analysis.

## 🎯 Project Objective
Standard network tools (like `ping`) provide a single metric: Total Latency. This metric is a "black box" that hides the true behavior of the network. 

**The Goal:** To mathematically decompose Total Delay ($D_{total}$) into:
$$D_{total} = D_{prop} + D_{trans} + D_{proc} + D_{queue}$$

1.  **Propagation Delay ($D_{prop}$):** Physics-based limits (fiber optics/distance).
2.  **Transmission Delay ($D_{trans}$):** Bandwidth constraints (packet size / link speed).
3.  **Processing Delay ($D_{proc}$):** Hardware/Router logic overhead.
4.  **Queuing Delay ($D_{queue}$):** **The Target Variable.** Network congestion and buffer bloat.

## 🛠️ Tech Stack
* **Core Engine:** Python, Scapy (for packet-level probing)
* **Data Processing:** Pandas, NumPy
* **Machine Learning:** Scikit-Learn (Regression, GMM), LSTM (Planned)
* **Automation:** GitHub Actions (Daily data harvesting)
* **Visualization:** Matplotlib, Seaborn

## 🗺️ Project Roadmap
This project follows a strict MLOps lifecycle, prioritizing original data collection over static datasets.

### Phase 1: The Probe (Current Status) 🚧
- [x] Repository Architecture & Environment Setup
- [ ] Develop `src/collector.py` using Scapy to probe targets with varying packet sizes.
- [ ] Implement robust error handling for network timeouts.
- [ ] Generate initial raw dataset (`data/raw/`).

### Phase 2: Analysis & Baseline Modeling
- [ ] Exploratory Data Analysis (EDA) to visualize Packet Size vs. RTT linear relationships.
- [ ] Train **Baseline Heuristic Model** (Minimum RTT subtraction).
- [ ] Train **Linear Regression Model** to estimate link bandwidth ($D_{trans}$).

### Phase 3: The Automation (MLOps)
- [ ] Configure GitHub Actions for **Daily Data Collection**.
- [ ] Build `src/monitor.py` to detect **Data Drift** (network route changes).
- [ ] Implement automated weekly model evaluation.

## 📂 Repository Structure
```text
internet-latency-decomposition/
├── .github/workflows/   # Automation pipelines (Daily Collection)
├── data/                # Local data storage (Ignored by Git)
├── notebooks/           # Jupyter notebooks for experiments & visualization
├── src/                 # Production Source Code
│   ├── __init__.py               
│   ├── collector.py     # Scapy-based probing engine
│   ├── preprocessing.py # Data cleaning & feature engineering
│   └── model.py         # Latency decomposition logic
├── requirements.txt 
├── notes/    
└── README.md            # Project Documentation
```
---

Author: Vedang Kulkarni