# Transmission Control Protocol (TCP) & Latency Dynamics

## 1. Overview in Latency Decomposition Context
While the internet latency decomposition model aims to isolate physical delay ($D_{\text{prop}}$, $D_{\text{trans}}$) 
from network congestion ($D_{\text{queue}}$), the choice of transport protocol heavily influences the observed Round-Trip Time 
(RTT). Unlike connectionless UDP or raw ICMP, TCP introduces protocol state machines, flow control, and error recovery algorithms
that inject variable logical delay into measurements.

---

## 2. The 3-Way Handshake & Connection Setup Latency
Active probing via TCP requires navigating or simulating the connection state machine. The initial handshake introduces an 
intrinsic delay overhead before upper-layer data transmission can begin.

```
Probing Node (Scapy)                         Target Resolver
           |                                           |
           | ------- [SYN] (packet_size=X) ----------> |  --> RTT_syn
           |                                           |
           | <------ [SYN-ACK] ----------------------- |
           |                                           |
           | ------- [ACK] --------------------------> |
           
 ```

### Latency Modeling Implications:
* **SYN-to-SYN-ACK RTT:** Measuring the time difference between sending a raw `SYN` packet and receiving the `SYN-ACK` packet isolates the network-level layer-4 RTT without upper-layer application processing overhead ($D_{\text{proc}}$ is minimized).
* **Connection Rejection:** If a target port is closed, the remote host returns a `RST` (Reset) packet instead of a `SYN-ACK`. The time-to-RST still acts as a valid RTT measurement indicator for network propagation and queuing.

---

## 3. TCP Flow Control, Congestion Control, and $D_{\text{queue}}$
The core target variable of this research project, $D_{\text{queue}}$ (queuing delay), is fundamentally driven by the interaction between TCP's congestion control loops and hardware router buffers (**Bufferbloat**).

### Sliding Window & Buffer Saturation
TCP uses a dynamic Congestion Window ($cwnd$) to control how many bytes can be outstanding in transit at any moment. 
* As $cwnd$ grows linearly during TCP's congestion avoidance phase, the packet injection rate eventually exceeds the bottleneck link capacity ($C$).
* Excess packets accumulate in the bottleneck router's FIFO queue, directly scaling $D_{\text{queue}}$.

### Multimodal Distributions (GMM Relevance)
When a router buffer fills up completely, packets are dropped (Tail Drop). This triggers a TCP window halving or a timeout event. This behavior splits the latency profile into distinct operational states:
1. **The Fast/Empty Path Mode:** Low $cwnd$, zero queue occupancy, minimum RTT envelope.
2. **The Congestion/Bufferbloat Mode:** Maximum $cwnd$, completely saturated buffers, inflated RTT ($D_{\text{total}} = D_{\text{prop}} + D_{\text{trans}} + D_{\text{proc}} + D_{\text{queue\_max}}$).

---

## 4. Mathematical Modeling of TCP RTT Estimation
Inside standard OS kernel network stacks, TCP dynamically estimates RTT using adaptive tracking algorithms to calculate the Retransmission Timeout ($RTO$). Understanding this internal calculation provides an analytical benchmark for our machine learning baseline models.

TCP updates its Smoothed RTT ($SRTT$) and RTT Variance ($RTTVAR$) using Jacobson’s algorithm:

$$SRTT_{k} = (1 - \alpha) \cdot SRTT_{k-1} + \alpha \cdot RTT_{\text{measured}}$$

$$RTTVAR_{k} = (1 - \beta) \cdot RTTVAR_{k-1} + \beta \cdot |SRTT_{k-1} - RTT_{\text{measured}}|$$

Where typical filter gains are set to $\alpha = 0.125$ and $\beta = 0.25$. The final Retransmission Timeout is derived as:

$$RTO = SRTT + 4 \cdot RTTVAR$$

---

## 5. Active Probing Execution via Scapy (Port 80 SYN Probing)
In our active collection script (`src/collection/probe/tcp.py`), standard socket connections are bypassed. Instead, low-level packet crafting is executed to hit port 80 (HTTP) or 443 (HTTPS) of public DNS anycast targets to ensure firewall traversal.

### Active Probing Mechanics:
1. **Packet Construction:** Construct an Layer-3 IP header coupled with a Layer-4 TCP header where the flag field is strictly set to `S` (SYN).
2. **Payload Modification:** To sweep packet sizes from 64 to 1400 bytes for isolating transmission delay ($D_{\text{trans}}$), arbitrary padding bytes (Raw payload) are appended to the Layer-4 segment to scale total packet size safely below standard path MTU ($1500$ bytes).
3. **Passive Capture Sync:** Concurrently, our passive sniffer filters for returning traffic matching `tcp and src [Target_IP] and tcp[tcpflags] & (tcp-syn|tcp-ack|tcp-rst) != 0` to accurately log `recv_timestamp` without kernel thread delays.