# QUEUING DELAY

Queuing Delay is the amount of time a packet spends sitting in a router or switch's memory buffer (the queue) waiting to be transmitted
to the ongoing link.

If a router receives packest faster than it can push out onto the wire (limitation dictated by transmission delay), the excess packets
are temporarily stored in buffer. The time a packets spends waiting in this line before it reaches the "front" to be transmitting
is its queuing delay.

Queuing Delay is the most volatile and unpredictable component of total network latency. It is the primary indicator of network 
congestion and the main reason for ping fluctuation from moment to moment.

---

## Formula

Unlike propagation and transmission delay that can be calculated with simple physics and arithmetics, **queuing delay** is *stochastic*
(probabilistic). This is due to the fact that the arrival time of the packets is truly random, there is no single equation to calculate
the queuing delay for an individual packet.

However, statistical models evaluate queuing delay using a metric called **Traffic Intensity**, which predicts the average queuing
behavior of the node:

I = L.a / R

Where,

- **I** -> Traffic Intensity
- **L** -> Packet Length
- **a** -> Average packet arrival rate (in packets per second)
- **R** -> Link Bandwidth / Transmission Rate

---

## How Traffic Intensity Dictates Queuing Delay

The relationship between traffic intensity and queuing delay is exponential. 
- **I ≈ 0 (Empty Queue)**: packets arrives infrequently. The queue is almost always empty, and the queuing delay is effectively 0.
- **I -> 1 (Heavy Congestion)**: the arrival rate approaches the link's maximum capacity. The queue fills up rapidly. As *I* tends towards
zero, the average queuing delay approaches **infinity**. This is where massive latency spike occurs.
- **I > 1 (packet loss)**: bits are arriving faster than the router can physically transmit them. The buffer will eventually overflow, 
resulting in dropped packets.

---

## Factors Affecting Queuing Delay

1. **Packet Arrival Rate**: This is the volume of traffic hitting the router, measure in packets / s. If the arrival rate increases while
router's processing and transmission speed remains constant, the router cannot keep up. Packets pile in the buffer, directly increasing
the time subsequent packets must wait.
2. **Packet Size**: If the arrival rate is same but the size of packets suddenly increases, the total volume of bits entering the router
spikes. Larger packets takes longer to transmit, hence the packet waiting behind them experience higher queuing delay.
3. **Link Bandwidth**: A higher transmission rate empties the queue faster. If we increase the network link (eg.- from 100 Mbps to 1 Gbps),
the router can push the packets much faster, drastically reducing the time any packet spends waiting in the queue.
4. **Router Buffer Capacity**: Every router has a finite amount of physical memory dedicated to its queue.The buffer size dictates the 
absolute maximum queuing delay a packet can experience. If a router has a massive buffer, packets can wait in line for a very long time
, leading to terrible latency. If the buffer is small, the queuing delay is capped, but the router will be forced to drop packets when 
the queue fills up, causing packet loss.
5. **Traffic Burstiness**: The formula of traffic intensity assumes average arrival rate, but real internet traffic is highly erratic.
Even if the average traffic intensity is low, traffic often arrives in dense *"micro-bursts"*. This sudden bursts temporarily 
overwhelms the queue, causing a massive short-term spike in queuing delay, even if the queue is entirely empty a millisecond later.

---

## Effects of Queuing Delay on latency

Queuing Delay is the primary reason for latency to fluctuate from time to time.

- **Introduces Jitter**: Jitter is the variation in latency from one packet to next.Because the length of the router's queue constantly
expands contracts based on the background traffic, packets travelling the exact same physical router will experience different queuing
times.
- **Creates Asymmetric Latency**: The path a packet takes from source to destination often has entirely different queuing dynamics than
the return path. Even on a single home router, the upload queue and download queue operate independently. A congested downstream
will cause high download latency while upload latency remains perfectly fine, leading to skewed RTT from one direction.
- **Causes Bufferbloat**: Modern routers are often designed with massive memory to prevent packet loss. However, if a large data transfer
keeps that buffer constantly full, every single packet, time sensitive packets have to wait in a massive line. This causes total latency
to skyrocket and stay constantly high, degrading the network performance without ever technically dropping packets.
- **Exhibits Non-Linear Latency Spike**: As network traffic increases, queuing delay does not smoothly scale. This means network
latency can jump from negligible to sever almost instantly. 
- **Triggers Packet Loss**: When a queue overflows, the router is forced to discard the incoming packets. While a dropped packet has
technically infinite network latency, it forces transport-layer protocols to detect the loss and retransmit the data. This retransmission
adds massive, compounding delays to *effective application-layer* latency.

---

## Role in Internet Latency Decomposition Model

The three components (propagation, transmission, and processing) are basically just physics and hardware constraints. Once the script
figures out the minimum baseline and the bottleneck bandwidth, those numbers stay static unless the routing path physically changes.
Queuing delay is the only part of the equation that captures the real-time health and congestion of the internet.

- **Mathematical Remainder ("y" value)**: You can't measure $D_{queue}$ directly. The model's first job is to learn the static baseline
  ($D_{prop}$ + $D_{proc}$) and the linear bandwidth limit ($D_{trans}$) specifically so you can subtract them from the total RTT.
The non-linear data that is left the $D_{queue}$ dataset.
- **Core Feature for Anomaly Detection**: In the daily data collection, $D_{queue}$ acts as the main indicator of the network issues.
If sudden spike is observed in the total RTT, it cannot be simply explained by the large packet size, it means that a bufferbloat or an 
active traffic jam in the wild is caught successfully.
- **Residual Signal**: Because queuing delay is based on traffic intensity, it has memory. If a router buffer is jammed at time *t*, 
it will likely be jammed at time *t+1* as well. This makes $D_{queue}$ the perfect target for time-series forecasting. After passing the 
basic linear regression, this is the isolated variable that will be fed to various models like the LSTMs, etc. to predict network 
congestion before it happens.