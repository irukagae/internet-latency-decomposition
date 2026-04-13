# PROPAGATION DELAY

Propagation Delay refers to the time required for a signal to travel through the transmission medium from the sender to the receiver after transmission begins. It starts when the **first bit enters the medium** and ends when that bit reaches the destination.

Propagation delay purely depends on:

- Physical distance  
- Propagation speed of the signal in the medium  

It is **independent of packet size and bandwidth**.

---

## Formula

Propagation Delay = D / S

Where:

- **D** → Distance between sender and receiver (meters, m)  
- **S** → Speed of the signal in the medium (typically ≈ 2 × 10⁸ m/s in optical fiber)

---

## Factors Affecting Propagation Delay

- **Distance**: Greater distance increases propagation delay linearly.  
- **Transmission Medium**: Different media have different propagation speeds.  
- **Signal Speed**: Higher propagation speed reduces delay.  
- **Physical Path**: Longer or indirect routing paths increase delay.  

---

## Effects of Propagation Delay on Latency

- Propagation delay is one of the fixed components in the total latency formula. It directly increases total network latency by adding the physical travel time of the signal.

- It **dominates latency over long distances**.

- It increases **Round Trip Time (RTT)**.

  Higher propagation delay → Higher RTT → Slower:
  - TCP handshake  
  - TLS handshake  
  - Request–response cycle  

- It reduces maximum throughput in TCP.

  Throughput depends on:

  Bandwidth–Delay Product (BDP) = Bandwidth × RTT

  Higher propagation delay → Higher RTT → Larger BDP  

  If the TCP window size is small, the network cannot fully utilize high-bandwidth links over long distances.

- It cannot be optimized away (it can only be minimized by reducing physical distance).

---

## Role in Internet Latency Decomposition Model

In a machine learning-based latency decomposition model:

- Propagation delay acts as a **deterministic baseline component**.
- It can be estimated using the geographical distance between the two endpoints.
- It represents the non-residual physical component of latency.

Propagation delay is useful for:

- Establishing the theoretical RTT floor  
- Feature engineering (distance-based features)  
- Outlier detection  
- Model validation  
- Identifying abnormal routing paths  
