# TRANSMISSION DELAY

Transmission delay is the amount of time required to push all the packet’s bits into the communication link. It is entirely dictated by the size of the packet and the bandwidth of the link.

---

## Formula

Transmission Delay = L / R

Where:

- **L** → Length of the packet (in bits)
- **R** → Transmission rate or bandwidth of the link (in bits per second, bps)

---

## Factors Affecting Transmission Delay

- **Packet Length**: This is the total size fo the packet being transmitted. The relationship id directly proportional. A larger packet takes longer to push onto the network link than a smaller one.
- **Link Bandwidth / Transmission Rate**: This is the capacity of the network link. It dictates how fast the router's hardware can pulse the digital information onto the physical medium. The relationship is inversely proportional. Higher bandwidth link will have significantly lower transmission delay than a lower bandwidth link for the exact same packet size.
- **Layer1 / Layer2 Protocol Overhead**: Before the packet is transmitted, the lower-level protocol add headers, footers, error checking protocol. Physical Layer encoding schemes also increase the actual number of bits that must be physically transmitted onto the wire, thereby increasing the true transmission delay.

---

## Effects of Transmission Delay on Latency

- Transmission Delay plays a structural role in how packets behave across a path.

- **Compounds at every Hop**: A router must receive a packet in its entirety before it can begin inspecting,
processing, and forwarding it. This means Transmission Dealy isn't one-time cost, but it is added to the 
total latency at every single router or switch along the network path.

- **Drives Queuing Delay**: Transmission delay dictates how quickly a router can clear its outbound queue.  If transmission delay is 
high, subsequent packets back up in the buffer creating a cascading effect where slow transmission rate directly spikes 
the queueing delay for every packet trapped behind it.

- **Introduces Jitter in Variable Traffic**: Since transmission delay is directly proportional to packet
size, a stream of data with fluctuating packet size will experience varying transmission times. This
inconsistency in arrival latency is called jitter, which heavily degrades real-time data stream.

- **Dictates Maximum Path Throughput**: The individual link along a network route with the highest transmission delay acts as the 
fundamental bottleneck for entire connection. Regardless of how fast the surrounding fiber optics links are, the end-to-end
throughput can never exceed the capacity of that of the slowest link.

- **Delays the start of processing**: A router cannot verify the structural integrity of a payload or read the destination IP
address to make routing decision until the very last bit of the packet has been received off the wire. Therefore, a long transmission
delay forces the router to wait, effectively pausing the start of the processing delay phase.

---

## Role in Internet Latency Decomposition Model

Transmission Delay plays a highly specific and fundamental role: it acts as the *predictable linear anchor* that allows machine 
learning model to estimate the network's bottleneck bandwidth.

- **The Key to Bandwidth Estimation**: 
    - Transmission Delay scales linearly with the size of data being sent. Since,
$D_{trans}$ = L / R, L can be manipulated to calculate R.
    - During the active probing phase, crafting custom payloads to send packets of varying, controlled size creates a dataset where
*L* is the independent variable.
    - By fitting *Linear Regression* model to this specific feature, the model can extract the slope of the line. This effectively
reverse-engineers the capacity of the slowest link in the path without needing administrative access to the router.

- **Detecting Data Drifts and Route Changes**: 
  - Internet traffic frequently experiences multi-path routing, if the underlying network  route changes (data drift), both
  the propagation baseline and the bottleneck bandwidth will shift, breaking the initial linear model.
  - Relying on $D_{trans}$ allows the system t detect these structural drifts. If the linear relationship between the packet size and
  RTT suddenly splits into two distinct parallel lines or intersecting slopes, it indicates that the packets are taking different 
  physical path.

- **Stepping Stone to the Target Variable**: 
  - Queueing Delay indicates the congestion and buffer bloat, and is the ultimate target variable. Since, $D_{queue}$ cannot be
  measured directly, it must be isolated through the process of elimination:
    - *Baseline Heuristic*: Find the absolute minimum RTT in dataset, which would represent a state where $D_{queue}$ = 0,
    effectively giving us the static baseline of $D_{prop}$ + $D_{proc.}$
    - *Transmission Substraction*: Applying linear regression model to calculate the exact $D_{trans}$ for any given packet size.
    - *Isolation*: By subtracting both baseline and calculated $D_{trans}$ from the total recorded latency of any packet, the 
    mathematical remainder is the isolated $D_{queue}$