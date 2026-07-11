# Quantile Regression Envelope for Physical Baseline Estimation

## 1. The Geometry of Network Latency Scatter Plots
In Stage 1 of our Hybrid Architecture, we plot `packet_size` (independent variable, $X$) against `rtt_ms` 
(dependent variable, $Y$). Because our active collection sweeps loop through controlled byte boundaries (64 to 1400 bytes), 
the resulting scatter plot exhibits a highly specific geometric structure: a clean, sharp **lower linear boundary** topped by 
an asymmetric, highly right-skewed cloud of data points.

```
RTT (ms)
▲
│        *  (Queuing Noise / Bufferbloat Cloud)
│     *      *       *
│  *     *       *       *
│─────────────────────────────   ◄─── OLS Regression Line (Distorted by Noise)
├─────────────────────────   ◄─── Quantile Regression Envelope (τ = 0.05)
│ 64                    1400
└─────────────────────────────► Packet Size (Bytes)
```

This distribution is a direct visual representation of our physical delay equation:
* The data points stretching upward away from the lower line represent stochastic network congestion ($D_{\text{queue}}$).
* The absolute floor of the scatter plot represents the **zero-congestion physical state**, where $D_{\text{queue}} \approx 0$. 

To isolate the deterministic properties of the link—transmission speed and propagation delay—our model must track this lower 
floor rather than the center of the cloud.

---

## 2. The Failure of Ordinary Least Squares (OLS) Linear Regression
Standard Linear Regression uses Ordinary Least Squares (OLS) to minimize the sum of squared residuals. This forces the model 
to estimate the **conditional mean** of the data, $E[Y|X]$. 

In network latency decomposition, OLS introduces two critical flaws that invalidate the entire downstream Stage 2 pipeline:

1. **Intercept Inflation ($\beta_0$):** Network queuing noise is asymmetric; it can only add delay, never subtract it. Because 
OLS averages out this purely positive noise, the calculated intercept ($\beta_0$) shifts drastically upward. This falsely 
inflates our estimate of physical propagation delay ($D_{\text{prop}}$).
2. **Slope Distortion ($\beta_1$):** Network congestion is frequently correlated with larger packet sizes due to router 
MTU constraints and buffer saturation characteristics. This correlation creates an artificial upward tilt in the OLS slope, 
leading to an underestimation of the true physical link bandwidth.

Because OLS absorbs traffic congestion into its physical parameters, subtracting an OLS baseline from raw RTT yields highly 
corrupted residuals that do not accurately represent true queuing delay.

---

## 3. Mathematical Formulation of the Lower Bounding Envelope
To isolate the true physical floor of the network link, our pipeline implements **Quantile Regression (QR)**. Instead of 
estimating the conditional mean, Quantile Regression models the conditional $\tau$-th quantile of the target variable, 
$Q_{\tau}(Y|X)$.

For our physical layer baseline, we set $\tau = 0.05$ (the 5th percentile). This targets the absolute bottom envelope of 
our active sweeps, ensuring we capture the link at its quietest operational moments.

### The Objective Function & Pinball Loss
Quantile Regression replaces the squared error loss of OLS with an asymmetric absolute loss function, commonly referred 
to as the **Pinball Loss Function** ($\rho_\tau$). 

For a given residual $u = y - \hat{y}$, the loss is defined mathematically as:

$$\rho_\tau(u) = u \cdot (\tau - \mathbb{I}_{\{u < 0\}})$$

Where $\mathbb{I}$ is the indicator function. Written explicitly as a piecewise function:

$$\rho_\tau(u) = \begin{cases} 
\tau \cdot u & \text{if } u \geq 0 \text{ (Underestimation)} \\
(\tau - 1) \cdot u & \text{if } u < 0 \text{ (Overestimation)} 
\end{cases}$$

### Visualizing Asymmetric Weights
When fitting the 5th percentile envelope ($\tau = 0.05$), the penalties are heavily weighted to force the regression line 
to the bottom of the dataset:
* **Underestimating a point ($u \geq 0$):** The model incurs a minor penalty multiplier of $0.05$. Data points in the 
high-congestion queuing cloud above the line are largely ignored.
* **Overestimating a point ($u < 0$):** If the regression line rises above a valid low-latency baseline point, it incurs
a massive penalty multiplier of $|0.05 - 1| = 0.95$. 

This steep penalty asymmetry strictly pins the Stage 1 regression line directly to the absolute minimum envelope of the 
raw packet sweeps.

---

## 4. Extracting Physical Parameters from Coefficients
Once the Stage 1 model minimizes the total pinball loss across the dataset, the resulting linear equation yields the clean, 
isolated physics of the network path:

$$\text{RTT}_{\text{physical}} = \beta_0 + \beta_1 \cdot \text{packet\_size}$$

### Isolating Link Bandwidth ($C$)
The slope coefficient ($\beta_1$) represents the serialization delay per byte over the bottleneck link. Because transmission
delay is physically defined as $D_{\text{trans}} = \frac{\text{Packet Size}}{\text{Bandwidth}}$, we can compute the absolute 
bottleneck capacity ($C$) in bits per second directly from our model's slope:

$$C = \frac{8}{\beta_1 \times 10^{-3}} \text{ bits/second}$$

### Isolating Base Path Latency ($D_{\text{prop}} + D_{\text{proc}}$)
The intercept coefficient ($\beta_0$) represents the theoretical RTT when packet size reaches zero bytes under zero network
congestion. This value cleanly isolates our static, hardware-bound variables:

$$\beta_0 = D_{\text{prop}} + D_{\text{proc}}$$

---

## 5. Cross-Country Analysis & Data Cleaning Manifest (Singapore vs. India)

When optimizing the Stage 1 envelope across our two target geographical locations, the model captures completely different 
infrastructure signatures:

### The Singapore Envelope: High Density & Minimal Variance
* **Characteristics:** Because Singapore sits directly on massive Tier-1 exchange points and features exceptionally short 
fiber runs, the data points crowd tightly against the lower envelope.
* **Modeling Action:** The 5th percentile ($\tau = 0.05$) works perfectly out of the box. The boundary line is highly distinct, 
yielding an exceptionally stable $\beta_0$ and $\beta_1$.

### The India Envelope: Highly Volatile & Multimodal Lower Bounds
* **Characteristics:** The Indian dataset features significant routing instability. If an ISP dynamically switches 
intermediate paths mid-experiment (a BGP routing shift), the physical propagation floor will instantly jump upward, creating
a stepped or fragmented lower boundary.
* **Modeling Action:** Running a standard global quantile regression across a multi-week Indian dataset will warp the 
true physical envelope. To protect the integrity of the Stage 2 residuals, the Indian dataset must be preprocessed using 
**Time-Window Localized Quantile Regression** or controlled for route changes via Npcap `ttl` feature tracking before the 
baseline is locked in