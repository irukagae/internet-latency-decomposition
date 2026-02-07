# LATENCY

## Definition:
Latency is the end-to-end time taken by a data packet to travel from the source node to destination node across network.  
In practice, latency is not a single delay but rather an aggregate of multiple delays incurred at different stages of packet transmission and processing within the network path.  
Latency is usually measured in milliseconds (ms) and is a significant metric for user-perceived performance in the network application.

---

## Latency Decomposition:
Latency decomposition means inferring the individual delay components that together produce the end-to-end latency (RTT), even though those components are not directly measurable.

\[
Latency = Propagation\ Delay + Transmission\ Delay + Queuing\ Delay + Processing\ Delay
\]

Each component arises from a different physical or logical cause and exhibits distinct statistical behavior.

---

## Behavior and Variability:
Latency exhibits both stable as well as highly variable behavior depending on its components:

1. **Propagation Delay**: primarily dependent on physical distance and medium; largely constant for fixed network path  
2. **Transmission Delay**: depends on packet size and link bandwidth; predictable and bounded under stable bandwidth conditions  
3. **Queuing Delay**: depends on traffic load and congestion; highly variable and often responsible for latency spikes  
4. **Processing Delay**: depends on router and server processing capacity; typically small but can fluctuate under heavy load  

As a result, most short-term latency variation is dominated by queuing and processing delay, and not by distance.

---

## Observability in Real Network:
Latency is rarely observed at component level. Instead, it is usually inferred from Round Trip Time (RTT) measurements using tools such as `ping`.

**Important implication:**
- individual delay components are not directly measurable  
- observed latency is a collapsed signal, hiding multiple underlying causes  
- any attempt to analyze or predict latency must rely on inference, and not direct measurement  

---

## Factors Affecting Latency:
Key factors influencing latency are:
- physical distance between endpoints  
- network topology and routing path  
- link bandwidth  
- packet size  
- traffic load and congestion level  
- time-of-day usage pattern  
- hardware and software processing overhead  

---

## Relevance of Machine Learning Modeling:
From machine learning perspective, latency components differ in their learnability:

1. **Propagation Delay**
   - mostly deterministic  
   - poor candidate for ML modeling  

2. **Transmission Delay**
   - formula-driven and predictable  
   - can be estimated analytically  

3. **Queuing Delay**
   - highly dynamic and non-linear  
   - primary target for ML-based prediction  

4. **Processing Delay**
   - noisy and partially observable  
   - secondary candidate for ML prediction  

Effective latency modeling therefore requires:
- analytical estimation of deterministic components  
- ML-based inference of dynamic components  

---

## Role of Latency in this Project:
In context of **Internet Latency Decomposition Model**:
- latency serves as the observable aggregate signal  
- the goal is not merely to predict latency, but to:
  - decompose it into interpretable components  
  - identify the dominant contributors to delay  
  - explain latency spikes rather than just measuring them  
