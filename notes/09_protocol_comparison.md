# Cross-Protocol Latency Dynamics within the Hybrid Residual Architecture

## 1. Structural Comparison Matrix

| Feature / Metric | TCP (SYN Probing) | UDP (Port 33434) | ICMP (Echo Request) |
| :--- | :--- | :--- | :--- |
| **OSI Layer** | Layer 4 (Transport) | Layer 4 (Transport) | Layer 3 (Network) |
| **Connection State** | Connection-Oriented (Stateful) | Connectionless (Stateless) | Connectionless (Stateless) |
| **Header Overhead** | 20 Bytes (Variable via TCP Options) | 8 Bytes (Fixed) | 8 Bytes (Fixed) |
| **Target Response** | `SYN-ACK` (Open) / `RST` (Closed) | ICMP Type 3 Code 3 (`Port Unreachable`) | ICMP Type 0 (`Echo Reply`) |
| **Primary $D_{\text{proc}}$ Source** | OS Kernel Network Stack | OS Kernel Stack (Error Generation) | Router Control Plane CPU |
| **Stage 1 Extrapolation Risk** | High (TCP Options shift wire size) | Low (Fixed 8-byte header) | Low (Fixed 8-byte header) |
| **Stage 2 Temporal Correlation**| High (Driven by $cwnd$ loops) | Low (Highly dependent on snapshot metrics) | Medium (Tied to background load cycles) |

---

## 2. Interaction with Stage 1: The Physical Layer (Linear Regression)

In the hybrid architecture, Stage 1 uses Linear Regression to fit `packet_size` against `rtt_ms` strictly to capture the deterministic physics of the path. The protocol choice directly alters how cleanly the model extracts link bandwidth ($\beta_1$) and base propagation delay ($\beta_0$).

$$\text{RTT}_{\text{physical\_predicted}} = \beta_0 + \beta_1 \cdot \text{packet\_size}$$

### ICMP & UDP: High Geometric Integrity
Because both protocols feature non-changing, deterministic 8-byte headers, the independent variable (`packet_size` passed to Scapy) maps flawlessly to the physical bits hitting the wire.
* **Stage 1 Behavior:** The model yields an exceptionally clean linear fit tracking the minimum RTT envelope. The extracted slope ($\beta_1$) accurately maps to the inverse of the bottleneck link bandwidth ($1/C$).
* **Residual Cleanliness:** The resulting residuals contain zero structural packet-size noise, leaving a pure signal for Stage 2.

### TCP: Dynamic Overhead Distortion
The host OS or intermediate transit boxes may dynamically append variable TCP options (e.g., SACK, Timestamps, or Window Scale factors).
* **Stage 1 Behavior:** This introduces minor horizontal variances in actual wire size that the model cannot see from the raw `packet_size` feature alone. This injects minor heteroscedastic noise into the linear fit.
* **Mitigation:** Quantile regression targeting the lowest 5th percentile envelope is required during Stage 1 fitting to prevent variable TCP overhead options from skewing the true physical serialization slope.

---

## 3. Interaction with Stage 2: The Congestion Layer (XGBoost Residual Target)

Stage 2 subtracts the physical predictions of Stage 1 from the actual observed RTTs to isolate the true network queuing delay residual:

$$\text{Residual } (D_{\text{queue}}) = \text{RTT}_{\text{actual}} - \text{RTT}_{\text{physical\_predicted}}$$

XGBoost is then trained strictly to predict this residual. The transport protocol shifts the mathematical nature of what XGBoost is forced to learn:

### TCP Residuals: Modeling Closed-Loop Congestion
TCP residuals represent a closed-loop system where the sender actively responds to network state via the Congestion Window ($cwnd$).
* **XGBoost Feature Priority:** Time-series rolling windows (e.g., mean passive traffic volume or RTT variance over the last 1 to 5 minutes) will hold massive predictive power. Because TCP throttles itself gradually, past states heavily correlate with future residuals.
* **Target Profile:** The residual distribution will exhibit distinct, continuous shifts between an empty-buffer state and a filled-buffer state (perfect for downstream GMM sub-component modeling).

### UDP Residuals: Modeling Open-Loop Volumetric Spikes
UDP residuals represent an open-loop system. Because UDP injects traffic blindly without a back-off mechanism, its residuals are chaotic and memoryless.
* **XGBoost Feature Priority:** Instantaneous, point-in-time metrics from the passive sniffing thread (e.g., current packets per second on the interface at the exact millisecond of the active probe) are far more critical than historical windows.
* **Target Profile:** Residuals will stay flat at approximately zero, interrupted by sharp, non-linear step-function spikes driven by sudden ISP traffic policing boundaries or absolute buffer overflows.

### ICMP Residuals: Modeling Infrastructure Control-Plane Noise
ICMP residuals are heavily contaminated by remote router CPU constraints due to Control Plane de-prioritization.
* **XGBoost Feature Priority:** Target IP identification flags and geographic location identifiers become dominant features over local passive traffic parameters. 
* **Target Profile:** The residuals will display high variance and heavy right-skewed tails, representing mixed local network queuing and artificial processing overhead inside intermediate router CPUs.

---

## 4. Cross-Country Analysis Implications (Singapore vs. India)

When running the hybrid architecture pipeline across the two distinct geographical environments, the cross-protocol data manifests as follows:

* **The Singapore Environment:** Due to minimal geographic distances ($D_{\text{prop}} \approx 0$), Stage 1 intercepts ($\beta_0$) across all three protocols will converge almost perfectly to the same single-digit millisecond baseline. Consequently, Stage 2 XGBoost models will carry the vast majority of the total pipeline variance, parsing out localized bufferbloat and protocol-specific kernel stack variations.
* **The India Environment:** Due to complex, multi-hop subcontinental routing, the protocols will diverge in Stage 1. The ICMP baseline intercept ($\beta_0$) will sit significantly higher than TCP/UDP due to multi-hop router CPU processing de-prioritization along the path. The Stage 2 XGBoost model for India will require robust localization features to adjust for these cross-protocol baseline shifts.