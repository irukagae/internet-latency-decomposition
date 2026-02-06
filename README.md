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
- [x] Develop `src/collection/` to build probes; capture active & passive probes; and `csv_writer.py`.
- [x] Build `orchestrator.py` to collect data on the basis of active and passive probes.
- [ ] Start collecting raw dataset (`data/raw/`).

### Phase 2: Analysis & Baseline Modeling
- [ ] Exploratory Data Analysis (EDA) to visualize Packet Size vs. RTT linear relationships.
- [ ] Train **Baseline Heuristic Model** (Minimum RTT subtraction).
- [ ] Train **Linear Regression Model** to estimate link bandwidth ($D_{trans}$).

### Phase 3: The Automation
- [ ] Configure GitHub Actions for **Daily Data Collection**.
- [ ] Build `src/monitor.py` to detect **Data Drift** (network route changes).
- [ ] Implement automated weekly model evaluation.

## 📂 Repository Structure
```text
internet-latency-decomposition/
├── .github/workflows/   
├── data
|   ├──processed/
|   └──raw/
├── notebooks/           
├── src/
│   ├── collection/
│   │   ├── capture/
│   │   │   ├── .gitkeep
│   │   │   └── passive.py
│   │   ├── experiment/
│   │   │   ├── .gitkeep
│   │   │   └── runner.py
│   │   ├── persistence/
│   │   │   └── csv_writer.py
│   │   └── probe/
│   │       ├── base.py
│   │       ├── icmp.py
│   │       ├── tcp.py
│   │       └── udp.py
│   ├── __init__.py
│   ├── model.py
│   ├── orchestrator.py
│   └── preprocessing.py
├── requirements.txt 
├── notes/    
└── README.md            
```
---

Author: Vedang Kulkarni