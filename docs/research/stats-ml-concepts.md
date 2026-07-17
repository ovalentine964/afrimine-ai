# AfriMine AI — Statistical & ML Algorithm Reference for Developers

> **Purpose:** Algorithm specification for every statistical/ML concept implemented in the AfriMine platform.  
> **Audience:** Developers implementing the pipeline. Assumes familiarity with Python, NumPy, pandas.  
> **User context:** Has Economics & Statistics degree — do NOT explain basic stats concepts. Focus on *what to code*.

---

## Table of Contents

1. [A. Geostatistics](#a-geostatistics)
2. [B. Grade Estimation](#b-grade-estimation)
3. [C. Resource Classification](#c-resource-classification)
4. [D. Statistical ML for Mining](#d-statistical-ml-for-mining)
5. [E. Spatial Statistics](#e-spatial-statistics)
6. [F. Bayesian Methods](#f-bayesian-methods)
7. [G. Data Quality](#g-data-quality)

---

## A. Geostatistics

### A1. Variogram — Measuring Spatial Correlation of Grades

**What:** A function that quantifies how grade differences between two sample points increase with distance. The foundation of all kriging. If two nearby samples have similar grades, the variogram is low at short distances.

**Math:**

Semi-variogram (theoretical):

$$\gamma(h) = \frac{1}{2} \text{Var}[Z(x+h) - Z(x)]$$

Experimental (empirical) variogram from data pairs:

$$\hat{\gamma}(h) = \frac{1}{2N(h)} \sum_{i=1}^{N(h)} [Z(x_i) - Z(x_i + h)]^2$$

where $N(h)$ = number of pairs separated by distance $h$.

**Common models to fit:**

| Model | Formula | Parameters |
|-------|---------|------------|
| Spherical | $\gamma(h) = c \left[ \frac{3h}{2a} - \frac{1}{2}\left(\frac{h}{a}\right)^3 \right]$ for $h \leq a$; $c$ for $h > a$ | nugget $c_0$, sill $c$, range $a$ |
| Exponential | $\gamma(h) = c \left[1 - \exp\left(-\frac{h}{a}\right)\right]$ | $c_0$, $c$, $a$ |
| Gaussian | $\gamma(h) = c \left[1 - \exp\left(-\frac{h^2}{a^2}\right)\right]$ | $c_0$, $c$, $a$ |

**Nugget** ($c_0$): variance at zero distance (measurement error + micro-scale variability).  
**Sill** ($c_0 + c$): plateau — beyond this distance, samples are uncorrelated.  
**Range** ($a$): distance at which the sill is reached.

**Python — GSTools:**

```python
import gstools as gs
import numpy as np

# x, y: sample coordinates; grades: assay values
# 1. Compute experimental variogram
bin_edges = np.arange(0, 500, 25)  # bins every 25m up to 500m
variogram = gs.SpatialGrid(dim=2)
variogram.set_pos([x, y])  # sample coordinates

# Experimental variogram
exp_vario = gs.vario_estimate(
    pos=[x, y],
    field=grades,
    bin_edges=bin_edges,
    estimator="matheron"  # or "cressie" for robust
)

# 2. Fit a model
model = gs.Spherical(dim=2)
model.fit_variogram(bin_edges, exp_vario, nugget=True)

# Access fitted parameters
print(f"Nugget: {model.nugget}")
print(f"Sill: {model.sill}")
print(f"Range: {model.len_scale}")

# 3. Plot for validation
import matplotlib.pyplot as plt
model.plot(x_max=500)
plt.plot(bin_edges, exp_vario, "o")
plt.title("Experimental vs Fitted Variogram")
plt.show()
```

**Alternative — PyKrige:**

```python
from pykrige.ok import OrdinaryKriging

# PyKrige fits variogram internally when you specify the model
OK = OrdinaryKriging(
    x, y, grades,
    variogram_model='spherical',  # 'linear', 'power', 'gaussian', 'exponential'
    variogram_parameters={
        'sill': 2.5,
        'range': 300,
        'nugget': 0.3
    },
    verbose=True,
    enable_plotting=True  # shows variogram fit
)
```

**Where in AfriMine:** `geostatistics/variogram.py` — called for every estimation domain before kriging. Variogram parameters are stored per domain and used by all downstream kriging routines.

---

### A2. Kriging — Spatial Interpolation of Grades

**What:** Best linear unbiased estimator (BLUE) for grade at an unsampled location. Weights nearby samples based on their spatial correlation (from the variogram) to produce an estimate and a measure of uncertainty (kriging variance).

**Math — Ordinary Kriging system:**

To estimate $\hat{Z}(x_0)$ at location $x_0$ from $n$ samples:

$$\hat{Z}(x_0) = \sum_{i=1}^{n} \lambda_i Z(x_i)$$

Solve the system:

$$\begin{bmatrix} \gamma(x_1,x_1) & \cdots & \gamma(x_1,x_n) & 1 \\ \vdots & \ddots & \vdots & \vdots \\ \gamma(x_n,x_1) & \cdots & \gamma(x_n,x_n) & 1 \\ 1 & \cdots & 1 & 0 \end{bmatrix} \begin{bmatrix} \lambda_1 \\ \vdots \\ \lambda_n \\ \mu \end{bmatrix} = \begin{bmatrix} \gamma(x_1,x_0) \\ \vdots \\ \gamma(x_n,x_0) \\ 1 \end{bmatrix}$$

Kriging variance:

$$\sigma^2_{OK}(x_0) = \sum_{i=1}^{n} \lambda_i \gamma(x_i, x_0) + \mu$$

**Python — PyKrige:**

```python
from pykrige.ok import OrdinaryKriging

OK = OrdinaryKriging(
    x, y, grades,
    variogram_model='spherical',
    variogram_parameters={'sill': 2.5, 'range': 300, 'nugget': 0.3},
    nlags=12,
    weight=True
)

# Grid for estimation
gridx = np.arange(0, 1000, 25)  # 25m grid
gridy = np.arange(0, 1000, 25)

# Execute kriging
z_est, ss_est = OK.execute('grid', gridx, gridy)
# z_est: estimated grades (2D array)
# ss_est: kriging variance (2D array) — THIS IS THE UNCERTAINTY

# For a single point:
z_point, ss_point = OK.execute('points', np.array([500.0]), np.array([300.0]))
```

**Python — GSTools (more control):**

```python
import gstools as gs

# Build kriging field
krige = gs.krige.Ordinary(
    model=model,  # fitted variogram model from A1
    cond_pos=[x, y],
    cond_val=grades,
)

# Evaluate on grid
krige(gridx, gridy)
estimated = krige.field        # grade estimates
variance = krige.krig_var      # kriging variance
```

**Where in AfriMine:** `geostatistics/kriging.py` — core estimation engine. Takes variogram model + drillhole data → produces grade surface/block model + uncertainty map.

---

### A3. Ordinary Kriging vs Universal Kriging

**What:** Ordinary Kriging (OK) assumes a constant (unknown) mean locally. Universal Kriging (UK) assumes the mean is a polynomial function of coordinates (trend surface). Use UK when there's a systematic spatial trend in grades (e.g., grades increasing with depth).

**When to use UK:** If the data shows a clear trend (regional drift) that violates the OK stationarity assumption. Test by plotting grades vs. coordinates and checking if residuals from a trend fit are stationary.

**Math — Universal Kriging:**

The mean is modeled as:

$$E[Z(x)] = \sum_{k=0}^{K} a_k f_k(x)$$

where $f_k(x)$ are polynomial basis functions (e.g., $1, x, y, x^2, xy, y^2$ for a quadratic trend).

The kriging system adds constraints for each basis function:

$$\sum_{j=1}^{n} \lambda_j f_k(x_j) = f_k(x_0), \quad k = 0, \ldots, K$$

**Python — PyKrige:**

```python
from pykrige.uk import UniversalKriging

UK = UniversalKriging(
    x, y, grades,
    variogram_model='spherical',
    variogram_parameters={'sill': 2.5, 'range': 300, 'nugget': 0.3},
    drift_terms=['regional_linear']  # or 'specified', 'functional'
)

z_est, ss_est = UK.execute('grid', gridx, gridy)
```

**Python — GSTools:**

```python
krige_universal = gs.krige.Universal(
    model=model,
    cond_pos=[x, y],
    cond_val=grades,
    drift_functions=[lambda x, y: x, lambda x, y: y],  # linear trend
    # Or for quadratic: [1, x, y, x*y, x**2, y**2]
)
krige_universal(gridx, gridy)
```

**Decision logic in AfriMine:**

```python
def select_kriging_type(x, y, grades, model):
    """Auto-select OK vs UK based on trend test."""
    from scipy.stats import linregress
    # Test for trend in x-direction
    slope_x, _, r_x, p_x, _ = linregress(x, grades)
    slope_y, _, r_y, p_y, _ = linregress(y, grades)

    has_trend = (p_x < 0.05 and abs(r_x) > 0.3) or (p_y < 0.05 and abs(r_y) > 0.3)

    if has_trend:
        return "universal"
    else:
        return "ordinary"
```

**Where in AfriMine:** `geostatistics/kriging.py` — select_kriging_type() is called per domain. UK is rare for gold but common for sedimentary deposits with systematic grade trends.

---

### A4. Co-Kriging — Multi-Variable Estimation

**What:** Uses a secondary variable (e.g., arsenic, magnetic susceptibility) that is correlated with the primary variable (gold grade) and sampled more densely, to improve grade estimation. Especially useful when the primary variable is sparsely sampled.

**Math:**

Estimate $\hat{Z}_1(x_0)$ using both $Z_1$ (primary) and $Z_2$ (secondary):

$$\hat{Z}_1(x_0) = \sum_{i=1}^{n_1} \lambda_i Z_1(x_i) + \sum_{j=1}^{n_2} \mu_j Z_2(x_j)$$

Requires modeling:
- Variogram of $Z_1$ (primary)
- Variogram of $Z_2$ (secondary)
- **Cross-variogram** between $Z_1$ and $Z_2$:

$$\gamma_{12}(h) = \frac{1}{2N(h)} \sum [Z_1(x_i) - Z_1(x_i+h)][Z_2(x_i) - Z_2(x_i+h)]$$

**Python — PyKrige:**

```python
from pykrige.ok import OrdinaryKriging
from pykrige.rk import Krige  # or use the co-kriging via VTK/conftab

# PyKrige doesn't have native co-kriging. Use GSTools instead:
import gstools as gs

# Model the cross-variogram
model1 = gs.Spherical(dim=2, len_scale=300, nugget=0.3, var=2.5)
model2 = gs.Spherical(dim=2, len_scale=250, nugget=0.2, var=1.0)

# Build a linear model of co-regionalization (LMC)
# This ensures all variograms/cross-variograms are jointly valid
cov_model = gs.CovModel.create(
    # Manual LMC construction
)

# For production, use the CM class:
cc = gs.CM(
    dim=2,
    var=[[2.5, 0.8], [0.8, 1.0]],  # covariance matrix at lag 0
    len_scale=300,
    nugget=[[0.3, 0.1], [0.1, 0.2]],
)

# Co-kriging with GSTools
krige_ck = gs.krige.CoKrige(
    model=cc,
    cond_pos=[x_primary, y_primary],       # primary sample locations
    cond_val=[gold_grades, arsenic_grades], # [primary, secondary] values
    # Note: secondary can have different (denser) locations
)
krige_ck(gridx, gridy)
```

**When to use in AfriMine:** When gold drillholes are widely spaced (e.g., >50m) but geochemistry (soil/rock chip) is dense (<25m). Typically improves estimation by 10-20% in RMSE.

**Where in AfriMine:** `geostatistics/cokriging.py` — optional upgrade path from standard OK when dense secondary data exists.

---

### A5. Block Kriging — Estimating Average Grade for a Block

**What:** Instead of estimating grade at a point, estimate the average grade over a block (e.g., 10m × 10m × 5m mining block). This is what goes into the block model that mining engineers use.

**Math:**

$$\hat{Z}_B = \sum_{i=1}^{n} \lambda_i Z(x_i)$$

The difference from point kriging: the right-hand side of the kriging system uses the **average covariance between each sample and the entire block** (not just a single point):

$$\bar{\gamma}(x_i, B) = \frac{1}{|B|} \int_B \gamma(x_i, x) \, dx$$

This integral is computed numerically by discretizing the block into sub-points.

**Python — PyKrige:**

```python
from pykrige.ok import OrdinaryKriging

OK = OrdinaryKriging(x, y, grades, variogram_model='spherical',
                     variogram_parameters={'sill': 2.5, 'range': 300, 'nugget': 0.3})

# Block estimate: specify block_size to average over
# PyKrige executes on a grid; the grid spacing IS the block size
block_size = 10  # 10m × 10m blocks
gridx = np.arange(5, 1000, block_size)  # block centers
gridy = np.arange(5, 1000, block_size)

z_block, var_block = OK.execute('grid', gridx, gridy)
```

**GSTools with block support:**

```python
krige_block = gs.krige.Ordinary(
    model=model,
    cond_pos=[x, y],
    cond_val=grades,
)
# Use point_no to average over sub-points within the block
krige_block(gridx, gridy, point_no=100)  # 100 sub-points per block for integration
```

**Where in AfriMine:** `geostatistics/block_model.py` — generates the final block model CSV/array that feeds into mine planning. Block size is a config parameter (typically 5-25m depending on mining method).

---

### A6. Kriging Variance — Grade Estimation Uncertainty

**What:** The variance of the kriging estimate — tells you how confident you should be in each block's grade. NOT dependent on the actual grade values, only on sample locations and variogram. A block surrounded by many close samples has low variance; an isolated block has high variance.

**Math:**

$$\sigma^2_{OK}(x_0) = \sum_{i=1}^{n} \lambda_i \gamma(x_i, x_0) + \mu$$

**Key insight for developers:** Kriging variance is a function of geometry only. It can be computed *before* assays are available. Use this for planning where additional drilling would reduce uncertainty most.

**Python:**

```python
# Both PyKrige and GSTools return kriging variance automatically:
z_est, krig_var = OK.execute('grid', gridx, gridy)

# Convert to standard deviation for reporting
krig_std = np.sqrt(krig_var)

# Confidence intervals
ci_lower = z_est - 1.96 * krig_std
ci_upper = z_est + 1.96 * krig_std

# For resource classification: ratio of kriging variance to sill
# Low ratio → Measured/Indicated; High ratio → Inferred
relative_variance = krig_var / model.sill
```

**Where in AfriMine:** `geostatistics/uncertainty.py` — produces uncertainty maps, drives resource classification logic, and feeds into the "where to drill next" optimizer (Bayesian optimization in section F4).

---

## B. Grade Estimation

### B1. Log-Normal Distribution of Gold Grades

**What:** Gold grades are almost universally log-normally distributed — many low-grade samples and a few very high-grade ones. This is critical: many geostatistical methods assume normality, so you must log-transform before kriging.

**Math:**

If $G$ is log-normal, then $\ln(G) \sim N(\mu_{\ln}, \sigma^2_{\ln})$.

Relationship between arithmetic and log-space parameters:

$$\mu_{\text{arith}} = \exp\left(\mu_{\ln} + \frac{\sigma^2_{\ln}}{2}\right)$$

$$\sigma^2_{\text{arith}} = \mu_{\text{arith}}^2 \left(\exp(\sigma^2_{\ln}) - 1\right)$$

Back-transform bias correction (Journel's correction):

$$\hat{G}_{\text{arith}} = \exp\left(\hat{G}_{\ln} + \frac{\sigma^2_{OK,\ln}}{2}\right)$$

where $\sigma^2_{OK,\ln}$ is the kriging variance in log-space.

**Python:**

```python
import numpy as np
from scipy import stats

grades = np.array([0.5, 1.2, 0.8, 15.3, 2.1, 0.3, 0.9, 45.0, 1.5, 0.7])

# 1. Test for log-normality
log_grades = np.log(grades)
stat, p_value = stats.shapiro(log_grades)
print(f"Log-normality test p-value: {p_value:.4f}")
# p > 0.05 → can assume log-normal

# 2. Log-transform for geostatistics
grades_ln = np.log(grades)

# 3. Perform kriging in log-space (using methods from A2)
# ... kriging produces ln_grade_est and kriging_var_ln

# 4. Back-transform with bias correction
def back_transform_bias_corrected(ln_estimate, kriging_variance_ln):
    """Journel's log-normal back-transform."""
    return np.exp(ln_estimate + kriging_variance_ln / 2.0)

# 5. Recovery above cut-off
def recovery_above_cutoff(ln_mean, ln_var, cutoff):
    """Probability that grade exceeds cutoff (log-normal)."""
    z = (np.log(cutoff) - ln_mean) / np.sqrt(ln_var)
    return 1 - stats.norm.cdf(z)
```

**Where in AfriMine:** `grade_estimation/lognormal.py` — applied before any kriging. The pipeline: test distribution → log-transform → kriging in log-space → back-transform with correction.

---

### B2. Top-Cutting / Capping

**What:** Extreme high-grade samples (e.g., a 200 g/t Au assay in a field averaging 1.5 g/t) can distort variograms and inflate estimates. Top-cutting caps these outliers at a threshold, typically set using statistical methods.

**Methods to determine the top-cut:**

1. **Cumulative frequency approach:** Plot grade vs. cumulative % of samples. The "break" in the curve suggests the cut.
2. **Mean + 3σ in log-space:** $\text{top-cut} = \exp(\mu_{\ln} + 3\sigma_{\ln})$
3. **Decile analysis:** If the top decile contributes >50% of total metal, cap it.
4. **Re-gression method:** Cap where the slope of the cumulative grade-tonnage curve changes.

**Python:**

```python
import numpy as np

def determine_topcut(grades, method='log3sigma'):
    """Determine top-cut value."""
    log_grades = np.log(grades[grades > 0])

    if method == 'log3sigma':
        mu_ln = np.mean(log_grades)
        sig_ln = np.std(log_grades)
        return np.exp(mu_ln + 3 * sig_ln)

    elif method == 'decile':
        sorted_g = np.sort(grades)[::-1]
        cumulative_metal = np.cumsum(sorted_g)
        total_metal = cumulative_metal[-1]
        # Find where top samples contribute disproportionate metal
        for i in range(1, len(sorted_g)):
            pct_samples = i / len(sorted_g)
            pct_metal = cumulative_metal[i] / total_metal
            if pct_metal > 0.5 and pct_samples < 0.1:
                return sorted_g[i]
        return sorted_g[0]  # no capping needed

    elif method == 'cumfreq':
        from scipy import stats
        sorted_g = np.sort(grades)
        cdf = np.arange(1, len(sorted_g) + 1) / len(sorted_g)
        # Find inflection point (max second derivative)
        second_deriv = np.diff(cdf, n=2)
        inflection = np.argmax(np.abs(second_deriv)) + 1
        return sorted_g[inflection]


def apply_topcut(grades, topcut):
    """Apply top-cut and return capped array + flag."""
    capped = np.minimum(grades, topcut)
    n_capped = np.sum(grades > topcut)
    print(f"Capped {n_capped} samples at {topcut:.2f} g/t")
    return capped, grades > topcut
```

**Where in AfriMine:** `grade_estimation/capping.py` — runs before variography. Top-cut value is logged per domain and auditable. The QA/QC report shows original vs. capped grades.

---

### B3. Compositing — Combining Short Samples

**What:** Drillhole samples come in varying lengths (0.5m to 2m). Geostatistics requires uniform length (composited intervals, e.g., 1m or 2m) to avoid length-bias in variograms and estimates. Compositing calculates length-weighted averages.

**Math:**

$$G_{\text{composite}} = \frac{\sum_{i=1}^{n} g_i \cdot l_i}{\sum_{i=1}^{n} l_i}$$

where $g_i$ = grade of sample $i$, $l_i$ = length of sample $i$.

**Python:**

```python
import pandas as pd
import numpy as np

def composite_drillhole(df, composite_length=2.0, min_recovery=0.75):
    """
    Composite drillhole samples to uniform length.

    Parameters:
        df: DataFrame with columns ['hole_id', 'from', 'to', 'grade']
        composite_length: target composite length (m)
        min_recovery: minimum fraction of composite_length required

    Returns:
        DataFrame with composited intervals
    """
    results = []

    for hole_id, group in df.groupby('hole_id'):
        group = group.sort_values('from').reset_index(drop=True)
        comp_start = group['from'].iloc[0]
        accumulated_length = 0.0
        accumulated_grade_length = 0.0

        for _, row in group.iterrows():
            sample_length = row['to'] - row['from']
            remaining = composite_length - accumulated_length

            if sample_length <= remaining:
                # Entire sample fits in current composite
                accumulated_grade_length += row['grade'] * sample_length
                accumulated_length += sample_length
            else:
                # Sample spans composite boundary — split
                accumulated_grade_length += row['grade'] * remaining
                accumulated_length = composite_length

                # Emit completed composite
                if accumulated_length >= composite_length * min_recovery:
                    results.append({
                        'hole_id': hole_id,
                        'from': comp_start,
                        'to': comp_start + composite_length,
                        'grade': accumulated_grade_length / accumulated_length,
                        'length': accumulated_length,
                        'recovery': accumulated_length / composite_length
                    })

                # Start new composite with remainder
                comp_start = comp_start + composite_length
                remainder_length = sample_length - remaining
                accumulated_grade_length = row['grade'] * remainder_length
                accumulated_length = remainder_length

        # Emit final partial composite
        if accumulated_length >= composite_length * min_recovery:
            results.append({
                'hole_id': hole_id,
                'from': comp_start,
                'to': comp_start + accumulated_length,
                'grade': accumulated_grade_length / accumulated_length,
                'length': accumulated_length,
                'recovery': accumulated_length / composite_length
            })

    return pd.DataFrame(results)
```

**Where in AfriMine:** `grade_estimation/compositing.py` — runs after capping, before variography. Composite length is a config parameter, typically matching the selective mining unit (SMU).

---

### B4. Domain Boundaries

**What:** A mineralization domain is a 3D body with consistent geological/grade characteristics. Kriging should only use samples from within the same domain. Cross-domain estimation produces artifacts.

**Approach:**

1. **Geological coding:** Each sample is coded by lithology/alteration/structure.
2. **Statistical testing:** Compare grade distributions between domains (Mann-Whitney U test, Kolmogorov-Smirnov test). If distributions differ significantly → separate domains.
3. **3D modeling:** Domains are typically 3D wireframes (surfaces or solids) exported as GOCAD, DXF, or implicit models.

**Python:**

```python
from scipy import stats
import numpy as np

def test_domain_boundary(grades_domain1, grades_domain2, alpha=0.05):
    """Test if two populations should be separate domains."""
    # Mann-Whitney U (non-parametric, doesn't assume normality)
    stat_mw, p_mw = stats.mannwhitneyu(grades_domain1, grades_domain2, alternative='two-sided')

    # Kolmogorov-Smirnov (tests if distributions differ)
    stat_ks, p_ks = stats.ks_2samp(grades_domain1, grades_domain2)

    # Log-space comparison (important for gold)
    log1, log2 = np.log(grades_domain1[grades_domain1 > 0]), np.log(grades_domain2[grades_domain2 > 0])
    stat_log, p_log = stats.mannwhitneyu(log1, log2, alternative='two-sided')

    separate = (p_mw < alpha) or (p_ks < alpha) or (p_log < alpha)

    return {
        'mann_whitney_p': p_mw,
        'ks_test_p': p_ks,
        'log_mw_p': p_log,
        'separate_domains': separate,
        'recommendation': 'SEPARATE' if separate else 'MERGE'
    }


def assign_samples_to_domains(samples_df, domain_wireframes):
    """Assign drillhole samples to geological domains using point-in-polyhedron test."""
    # Uses trimesh or pyvista for 3D containment
    import pyvista as pv

    samples_df['domain'] = 'unassigned'

    for domain_name, mesh_file in domain_wireframes.items():
        mesh = pv.read(mesh_file)
        points = samples_df[['x', 'y', 'z']].values
        # Select points inside the mesh
        select = mesh.select_enclosed_points(points)
        inside = select['SelectedPoints'].astype(bool)
        samples_df.loc[inside, 'domain'] = domain_name

    return samples_df
```

**Where in AfriMine:** `grade_estimation/domains.py` — provides domain filtering for all kriging routines. Domain wireframes are stored in the project database; samples are tagged with domain codes.

---

### B5. Change of Support — Point vs Block Estimates

**What:** A point estimate (kriging at a location) will differ from a block estimate (average grade over a volume) due to the smoothing effect of averaging. This is the "change of support" problem. Critical for reconciling drillhole-scale data with mining-block-scale estimates.

**Math — Regularization:**

The variance of block grades is less than point variance:

$$\sigma^2_B < \sigma^2_{\text{point}}$$

The relationship depends on the variogram and block size. For a spherical model:

$$\sigma^2_B = \sigma^2_{\text{point}} - \bar{\gamma}(B, B)$$

where $\bar{\gamma}(B, B)$ is the within-block average semi-variance.

**Discrete Gaussian Model (DGM) — for grade-tonnage curves:**

Used to estimate how much ore is above a cut-off at block scale vs. point scale.

```python
import numpy as np
from scipy import stats

def change_of_support_dgm(point_mean, point_var, block_var, cutoffs):
    """
    Discrete Gaussian Model for change of support.
    Returns grade-tonnage curves at block support.
    """
    # Support coefficient (Krige's relation)
    # block_var = point_var * (1 - smoothing_factor)
    smoothing_factor = 1 - (block_var / point_var)

    results = {}
    for cutoff in cutoffs:
        # Point support
        z_point = (np.log(cutoff) - point_mean) / np.sqrt(point_var)
        tonnage_point = 1 - stats.norm.cdf(z_point)
        grade_point = point_mean * stats.norm.cdf(-z_point + np.sqrt(point_var)) / tonnage_point if tonnage_point > 0 else 0

        # Block support (reduced variance)
        z_block = (np.log(cutoff) - point_mean) / np.sqrt(block_var)
        tonnage_block = 1 - stats.norm.cdf(z_block)
        grade_block = point_mean * stats.norm.cdf(-z_block + np.sqrt(block_var)) / tonnage_block if tonnage_block > 0 else 0

        results[cutoff] = {
            'point_tonnage': tonnage_point,
            'point_grade': grade_point,
            'block_tonnage': tonnage_block,
            'block_grade': grade_block,
        }

    return results
```

**Where in AfriMine:** `grade_estimation/change_of_support.py` — used when generating grade-tonnage curves for feasibility studies. The block model is always at mining-block scale; this module handles the reconciliation.

---

## C. Resource Classification

### C1. JORC Code Categories

**What:** The JORC Code defines three categories based on confidence in the estimate:

| Category | Typical Kriging Std / Grade | Search Radius | Min. Samples | Drill Spacing |
|----------|---------------------------|---------------|-------------|----------------|
| **Measured** | <15% of mean | 1st search neighborhood | ≥15 | Close (e.g., 25-50m) |
| **Indicated** | 15-30% of mean | 1st-2nd search neighborhood | ≥8 | Medium (e.g., 50-100m) |
| **Inferred** | 30-50% of mean | Extended search | ≥4 | Wide (e.g., 100-200m) |

**Implementation logic:**

```python
import numpy as np

def classify_resource_block(kriging_grade, kriging_variance, n_samples,
                            search_radius, variogram_range, mean_grade):
    """
    Classify a single block according to JORC categories.

    Returns: 'measured', 'indicated', 'inferred', or 'unclassified'
    """
    kriging_std = np.sqrt(kriging_variance)
    relative_std = kriging_std / mean_grade if mean_grade > 0 else 999

    # Ratio of search radius to variogram range
    radius_ratio = search_radius / variogram_range

    # Classification rules (simplified — adjust per company policy)
    if (relative_std < 0.15 and n_samples >= 15 and radius_ratio <= 0.5):
        return 'measured'
    elif (relative_std < 0.30 and n_samples >= 8 and radius_ratio <= 1.0):
        return 'indicated'
    elif (relative_std < 0.50 and n_samples >= 4):
        return 'inferred'
    else:
        return 'unclassified'


def classify_block_model(block_model_df, mean_grade, variogram_range):
    """Classify all blocks in the model."""
    block_model_df['resource_category'] = block_model_df.apply(
        lambda row: classify_resource_block(
            row['kriging_grade'],
            row['kriging_variance'],
            int(row['n_samples']),
            row['search_radius'],
            variogram_range,
            mean_grade
        ), axis=1
    )
    return block_model_df
```

**Where in AfriMine:** `resource/classification.py` — runs after block model generation. Outputs the classified block model for reporting. Must be auditable and traceable to input parameters.

---

### C2. Confidence Intervals for Resource Estimates

**What:** Quantify the uncertainty in the total metal/tonnage for a resource category. Uses kriging variance per block to build confidence intervals for the sum.

**Math:**

For $N$ blocks, total estimated metal:

$$M = \sum_{i=1}^{N} V_i \cdot \rho \cdot \hat{Z}_i$$

where $V_i$ = block volume, $\rho$ = density, $\hat{Z}_i$ = estimated grade.

Variance of total metal (assuming independent blocks):

$$\text{Var}(M) = \sum_{i=1}^{N} (V_i \cdot \rho)^2 \cdot \sigma^2_{OK,i}$$

95% CI: $M \pm 1.96 \sqrt{\text{Var}(M)}$

**Python:**

```python
import numpy as np

def resource_confidence_interval(block_volumes, densities, grades, kriging_variances,
                                  confidence=0.95):
    """
    Calculate confidence interval for total contained metal.
    """
    # Total metal per block (tonnes × g/t = grams, convert to kg or oz)
    metal_per_block = block_volumes * densities * grades  # in grams

    # Total metal
    total_metal = np.sum(metal_per_block)

    # Variance per block
    var_per_block = (block_volumes * densities) ** 2 * kriging_variances

    # Total variance (independent blocks assumption)
    total_var = np.sum(var_per_block)
    total_std = np.sqrt(total_var)

    # Confidence interval
    z = 1.96 if confidence == 0.95 else 2.576 if confidence == 0.99 else 1.645
    ci_lower = total_metal - z * total_std
    ci_upper = total_metal + z * total_std

    return {
        'total_metal_kg': total_metal / 1000,
        'std_kg': total_std / 1000,
        'ci_lower_kg': ci_lower / 1000,
        'ci_upper_kg': ci_upper / 1000,
        'relative_std_pct': (total_std / total_metal) * 100 if total_metal > 0 else 0
    }
```

**Where in AfriMine:** `resource/confidence.py` — produces the uncertainty table in the resource report (NI 43-101 / JORC compliant).

---

### C3. Search Neighborhoods

**What:** The search algorithm selects which samples to include in each kriging estimate. Uses an ellipsoidal search volume oriented along the axes of continuity (from variogram modeling).

**Parameters:**

```python
from dataclasses import dataclass
from typing import List

@dataclass
class SearchNeighborhood:
    """Search ellipsoid parameters."""
    max_range: float      # major axis length (m)
    medium_range: float   # medium axis length (m)
    min_range: float      # minor axis length (m)
    azimuth: float        # orientation of major axis (degrees from north)
    dip: float            # plunge of major axis (degrees from horizontal)
    max_samples: int      # max samples per octant or total
    min_samples: int      # minimum samples required
    max_per_octant: int   # max samples per octant (ensures spatial distribution)
    num_sectors: int      # number of sectors (4 or 8)


def find_samples_in_search(block_center, samples_df, search: SearchNeighborhood):
    """
    Select samples within the search ellipsoid for a block.
    """
    # 1. Rotate coordinates to align with search ellipsoid
    # Transform to ellipsoid-local coordinates
    dx = samples_df['x'].values - block_center[0]
    dy = samples_df['y'].values - block_center[1]
    dz = samples_df['z'].values - block_center[2]

    # Rotate by azimuth and dip
    az_rad = np.radians(search.azimuth)
    dip_rad = np.radians(search.dip)

    # Rotation matrices
    cos_az, sin_az = np.cos(az_rad), np.sin(az_rad)
    cos_dip, sin_dip = np.cos(dip_rad), np.sin(dip_rad)

    # Rotate to ellipsoid axes
    x_rot = dx * cos_az + dy * sin_az
    y_rot = -dx * sin_az + dy * cos_az
    z_rot = dz

    # Further rotate for dip
    x_final = x_rot * cos_dip + z_rot * sin_dip
    y_final = y_rot
    z_final = -x_rot * sin_dip + z_rot * cos_dip

    # 2. Normalize by ellipsoid axes
    normalized_dist = np.sqrt(
        (x_final / search.max_range) ** 2 +
        (y_final / search.medium_range) ** 2 +
        (z_final / search.min_range) ** 2
    )

    # 3. Select within ellipsoid
    inside = normalized_dist <= 1.0
    candidates = samples_df[inside].copy()
    candidates['normalized_distance'] = normalized_dist[inside]

    # 4. Octant selection (distribute samples spatially)
    if len(candidates) > search.max_samples:
        candidates = octant_selection(candidates, search)

    return candidates
```

**Where in AfriMine:** `geostatistics/search.py` — called by the kriging engine for every block. Search parameters are configurable per domain and resource category.

---

### C4. QA/QC Procedures

**What:** Quality Assurance/Quality Control ensures assay data is reliable. Involves inserting standards (certified reference materials), blanks (sterile material), and field duplicates at regular intervals.

**Python:**

```python
import pandas as pd
import numpy as np

class QaQcAnalyzer:
    """Assay QA/QC analysis for mining projects."""

    def __init__(self, sample_df):
        """
        sample_df columns:
        - sample_id, grade, sample_type ('sample','standard','blank','duplicate'),
        - standard_certified_value, standard_certified_uncertainty,
        - duplicate_of (sample_id of original)
        """
        self.df = sample_df

    def analyze_standards(self, tolerance_pct=10):
        """Check if standards fall within certified value ± tolerance."""
        stds = self.df[self.df['sample_type'] == 'standard'].copy()
        stds['pct_deviation'] = abs(stds['grade'] - stds['standard_certified_value']) / stds['standard_certified_value'] * 100
        stds['pass'] = stds['pct_deviation'] <= tolerance_pct

        pass_rate = stds['pass'].mean() * 100
        failed = stds[~stds['pass']]

        return {
            'total_standards': len(stds),
            'pass_rate_pct': pass_rate,
            'mean_deviation_pct': stds['pct_deviation'].mean(),
            'failed_samples': failed[['sample_id', 'grade', 'standard_certified_value', 'pct_deviation']].to_dict('records'),
            'status': 'PASS' if pass_rate >= 95 else 'WARNING' if pass_rate >= 90 else 'FAIL'
        }

    def analyze_blanks(self, detection_limit=0.01, threshold=0.05):
        """Check if blanks are below detection or very low."""
        blanks = self.df[self.df['sample_type'] == 'blank'].copy()
        blanks['above_detection'] = blanks['grade'] > detection_limit
        blanks['above_threshold'] = blanks['grade'] > threshold

        contamination_rate = blanks['above_threshold'].mean() * 100

        return {
            'total_blanks': len(blanks),
            'contamination_rate_pct': contamination_rate,
            'max_blank_grade': blanks['grade'].max(),
            'status': 'PASS' if contamination_rate < 5 else 'WARNING' if contamination_rate < 10 else 'FAIL'
        }

    def analyze_duplicates(self, cv_threshold=20):
        """Check precision using field duplicates."""
        dupes = self.df[self.df['sample_type'] == 'duplicate'].copy()
        # Merge with original
        originals = self.df[self.df['sample_type'] == 'sample'].set_index('sample_id')
        dupes['original_grade'] = dupes['duplicate_of'].map(originals['grade'])
        dupes = dupes.dropna(subset=['original_grade'])

        # Coefficient of variation
        dupes['mean_grade'] = (dupes['grade'] + dupes['original_grade']) / 2
        dupes['cv_pct'] = abs(dupes['grade'] - dupes['original_grade']) / dupes['mean_grade'] * 100

        overall_cv = dupes['cv_pct'].mean()

        return {
            'total_duplicates': len(dupes),
            'mean_cv_pct': overall_cv,
            'max_cv_pct': dupes['cv_pct'].max(),
            'status': 'PASS' if overall_cv < cv_threshold else 'WARNING' if overall_cv < cv_threshold * 1.5 else 'FAIL'
        }

    def full_report(self):
        """Generate complete QA/QC report."""
        return {
            'standards': self.analyze_standards(),
            'blanks': self.analyze_blanks(),
            'duplicates': self.analyze_duplicates(),
        }
```

**Where in AfriMine:** `data_quality/qaqc.py` — runs on every data import. Blocks resource estimation if QA/QC fails. Stores results for audit trail.

---

## D. Statistical ML for Mining

### D1. Random Forest for Mineral Prospectivity Mapping

**What:** Predicts the probability of mineralization at unsampled locations using multiple geological/geophysical/geochemical features. Each decision tree votes; the forest averages.

**Math:**

For $T$ trees, each trained on bootstrap sample with random feature subset:

$$\hat{p}(\text{mineralized} | \mathbf{x}) = \frac{1}{T} \sum_{t=1}^{T} \mathbb{1}[h_t(\mathbf{x}) = 1]$$

Feature importance via mean decrease in impurity (MDI) or permutation importance.

**Python — scikit-learn:**

```python
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import cross_val_score, StratifiedKFold
from sklearn.preprocessing import StandardScaler
import pandas as pd
import numpy as np

class ProspectivityMapper:
    """Random Forest prospectivity mapping for mineral exploration."""

    def __init__(self):
        self.model = RandomForestClassifier(
            n_estimators=500,
            max_depth=15,
            min_samples_leaf=5,
            class_weight='balanced',  # mineralized sites are rare
            random_state=42,
            n_jobs=-1
        )
        self.scaler = StandardScaler()
        self.feature_names = None

    def prepare_features(self, grid_df):
        """
        Extract features for each grid cell.

        Expected columns: geology_code, proximity_fault, magnetic_anomaly,
        gravity_anomaly, geochem_As, geochem_Cu, elevation, slope, etc.
        """
        # One-hot encode geology
        features = pd.get_dummies(grid_df, columns=['geology_code'])

        # Add derived features
        features['mag_grad'] = np.gradient(features['magnetic_anomaly'])
        features['fault_prox_log'] = np.log1p(features['proximity_fault'])

        self.feature_names = features.columns.tolist()
        return features

    def train(self, X, y):
        """Train on known mineralized (1) vs barren (0) locations."""
        X_scaled = self.scaler.fit_transform(X)
        self.model.fit(X_scaled, y)

        # Cross-validation score
        cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
        scores = cross_val_score(self.model, X_scaled, y, cv=cv, scoring='roc_auc')
        print(f"AUC: {scores.mean():.3f} ± {scores.std():.3f}")

    def predict_prospectivity(self, X_new):
        """Predict probability of mineralization for new grid cells."""
        X_scaled = self.scaler.transform(X_new)
        proba = self.model.predict_proba(X_scaled)[:, 1]
        return proba

    def feature_importance(self):
        """Get ranked feature importances."""
        importances = self.model.feature_importances_
        return pd.DataFrame({
            'feature': self.feature_names,
            'importance': importances
        }).sort_values('importance', ascending=False)
```

**Where in AfriMine:** `ml/prospectivity.py` — generates prospectivity maps for greenfield exploration targeting. Features come from GIS layers (geology, geophysics, geochemistry, remote sensing).

---

### D2. XGBoost for Grade Estimation from Geochemistry

**What:** Use gradient-boosted trees to predict gold grade from surface geochemistry, geology, and geophysical data. Faster and often more accurate than kriging for noisy, high-dimensional data.

**Python:**

```python
import xgboost as xgb
from sklearn.model_selection import GridSearchCV
from sklearn.metrics import mean_squared_error, r2_score
import numpy as np

class GradeEstimatorXGB:
    """XGBoost grade estimation from multi-source data."""

    def __init__(self):
        self.model = xgb.XGBRegressor(
            n_estimators=500,
            max_depth=6,
            learning_rate=0.05,
            subsample=0.8,
            colsample_bytree=0.8,
            reg_alpha=0.1,      # L1 regularization
            reg_lambda=1.0,     # L2 regularization
            objective='reg:squarederror',
            random_state=42,
            n_jobs=-1
        )

    def train(self, X_train, y_train, X_val=None, y_val=None):
        """Train with early stopping."""
        fit_params = {
            'verbose': 50,
        }
        if X_val is not None:
            fit_params['eval_set'] = [(X_val, y_val)]

        self.model.fit(X_train, y_train, **fit_params)

    def hyperparameter_search(self, X, y):
        """Grid search for optimal parameters."""
        param_grid = {
            'max_depth': [4, 6, 8],
            'learning_rate': [0.01, 0.05, 0.1],
            'n_estimators': [300, 500, 1000],
            'subsample': [0.7, 0.8, 0.9],
        }
        grid = GridSearchCV(self.model, param_grid, cv=5,
                           scoring='neg_mean_squared_error', n_jobs=-1, verbose=1)
        grid.fit(X, y)
        self.model = grid.best_estimator_
        return grid.best_params_, grid.best_score_

    def predict_with_uncertainty(self, X, n_estimators_subset=100):
        """
        Estimate prediction uncertainty using individual tree predictions.
        """
        # Use first N trees for uncertainty estimation
        preds = np.array([
            self.model.predict(X, iteration_range=(0, i))
            for i in range(1, n_estimators_subset + 1)
        ])
        return {
            'mean': preds.mean(axis=0),
            'std': preds.std(axis=0),
            'q10': np.percentile(preds, 10, axis=0),
            'q90': np.percentile(preds, 90, axis=0),
        }

    def feature_importance(self, X, y):
        """Permutation-based feature importance (more reliable than built-in)."""
        from sklearn.inspection import permutation_importance
        result = permutation_importance(self.model, X, y, n_repeats=10, random_state=42)
        return result.importances_mean
```

**Where in AfriMine:** `ml/grade_estimation.py` — alternative/complement to kriging. Used when high-dimensional feature sets are available (multi-element geochemistry + geology + geophysics). Can ensemble with kriging estimates.

---

### D3. Gaussian Processes for Spatial Prediction

**What:** A non-parametric Bayesian model that provides predictions AND uncertainty estimates. The ML equivalent of kriging — in fact, kriging IS a special case of GP regression. GPs are more flexible: they can learn the kernel (variogram) from data.

**Math:**

Prior: $f(\mathbf{x}) \sim \mathcal{GP}(m(\mathbf{x}), k(\mathbf{x}, \mathbf{x}'))$

Posterior prediction at $\mathbf{x}_*$:

$$\bar{f}_* = \mathbf{k}_*^T (\mathbf{K} + \sigma_n^2 \mathbf{I})^{-1} \mathbf{y}$$

$$\text{Var}(f_*) = k(\mathbf{x}_*, \mathbf{x}_*) - \mathbf{k}_*^T (\mathbf{K} + \sigma_n^2 \mathbf{I})^{-1} \mathbf{k}_*$$

**Python — GPyTorch (GPU-accelerated):**

```python
import torch
import gpytorch

class SpatialGPModel(gpytorch.models.ExactGP):
    """Gaussian Process for spatial grade prediction."""

    def __init__(self, train_x, train_y, likelihood):
        super().__init__(train_x, train_y, likelihood)
        self.mean_module = gpytorch.means.ConstantMean()
        # Matérn kernel (generalization of exponential/spherical variogram)
        self.covar_module = gpytorch.kernels.ScaleKernel(
            gpytorch.kernels.MaternKernel(nu=2.5)  # nu=2.5 is smooth, like spherical
        )

    def forward(self, x):
        mean = self.mean_module(x)
        covar = self.covar_module(x)
        return gpytorch.distributions.MultivariateNormal(mean, covar)


def train_gp_spatial(x_train, y_train, n_epochs=200):
    """Train GP model for spatial prediction."""
    # Convert to tensors
    train_x = torch.tensor(x_train, dtype=torch.float32)
    train_y = torch.tensor(y_train, dtype=torch.float32)

    likelihood = gpytorch.likelihoods.GaussianLikelihood()
    model = SpatialGPModel(train_x, train_y, likelihood)

    model.train()
    likelihood.train()

    optimizer = torch.optim.Adam(model.parameters(), lr=0.1)
    mll = gpytorch.mlls.ExactMarginalLogLikelihood(likelihood, model)

    for epoch in range(n_epochs):
        optimizer.zero_grad()
        output = model(train_x)
        loss = -mll(output, train_y)
        loss.backward()
        optimizer.step()
        if (epoch + 1) % 50 == 0:
            print(f'Epoch {epoch+1}/{n_epochs} - Loss: {loss.item():.3f}')

    return model, likelihood


def predict_gp(model, likelihood, x_new):
    """Predict grades with uncertainty at new locations."""
    model.eval()
    likelihood.eval()

    with torch.no_grad(), gpytorch.settings.fast_pred_var():
        x_test = torch.tensor(x_new, dtype=torch.float32)
        pred = likelihood(model(x_test))

    return {
        'mean': pred.mean.numpy(),
        'std': pred.stddev.numpy(),
        'lower_95': (pred.mean - 1.96 * pred.stddev).numpy(),
        'upper_95': (pred.mean + 1.96 * pred.stddev).numpy(),
    }
```

**Scikit-learn alternative (simpler, CPU only):**

```python
from sklearn.gaussian_process import GaussianProcessRegressor
from sklearn.gaussian_process.kernels import Matern, WhiteKernel, ConstantKernel

kernel = ConstantKernel() * Matern(nu=2.5) + WhiteKernel()

gp = GaussianProcessRegressor(
    kernel=kernel,
    n_restarts_optimizer=10,
    normalize_y=True,
    random_state=42
)

gp.fit(x_train, y_train)
y_pred, y_std = gp.predict(x_new, return_std=True)
```

**Where in AfriMine:** `ml/gp_spatial.py` — alternative to kriging for projects with complex, non-stationary grade patterns. Also useful for multi-output prediction (simultaneous grade + geology).

---

### D4. Neural Networks for Image Classification (Mineral Photos)

**What:** CNN-based classifier for identifying minerals from core photos, thin sections, or hand specimens. Uses transfer learning from pretrained models.

**Python — PyTorch:**

```python
import torch
import torch.nn as nn
from torchvision import models, transforms
from torch.utils.data import DataLoader

class MineralClassifier:
    """Transfer learning mineral image classifier."""

    def __init__(self, n_classes, model_name='resnet50'):
        self.device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')

        # Load pretrained model
        if model_name == 'resnet50':
            self.model = models.resnet50(pretrained=True)
            # Freeze early layers
            for param in list(self.model.parameters())[:-20]:
                param.requires_grad = False
            # Replace classifier head
            self.model.fc = nn.Sequential(
                nn.Dropout(0.3),
                nn.Linear(self.model.fc.in_features, 256),
                nn.ReLU(),
                nn.Dropout(0.2),
                nn.Linear(256, n_classes)
            )

        self.model = self.model.to(self.device)

        self.transform = transforms.Compose([
            transforms.Resize((224, 224)),
            transforms.RandomHorizontalFlip(),
            transforms.RandomRotation(15),
            transforms.ColorJitter(brightness=0.2, contrast=0.2),
            transforms.ToTensor(),
            transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225])
        ])

    def train(self, train_dataset, val_dataset, epochs=30, lr=1e-4):
        train_loader = DataLoader(train_dataset, batch_size=32, shuffle=True)
        val_loader = DataLoader(val_dataset, batch_size=32)

        optimizer = torch.optim.AdamW(
            filter(lambda p: p.requires_grad, self.model.parameters()),
            lr=lr, weight_decay=1e-4
        )
        criterion = nn.CrossEntropyLoss()
        scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=epochs)

        for epoch in range(epochs):
            self.model.train()
            running_loss = 0.0
            for images, labels in train_loader:
                images, labels = images.to(self.device), labels.to(self.device)
                optimizer.zero_grad()
                outputs = self.model(images)
                loss = criterion(outputs, labels)
                loss.backward()
                optimizer.step()
                running_loss += loss.item()

            scheduler.step()

            # Validation
            self.model.eval()
            correct = 0
            total = 0
            with torch.no_grad():
                for images, labels in val_loader:
                    images, labels = images.to(self.device), labels.to(self.device)
                    outputs = self.model(images)
                    _, predicted = outputs.max(1)
                    total += labels.size(0)
                    correct += predicted.eq(labels).sum().item()

            print(f'Epoch {epoch+1}/{epochs} - Loss: {running_loss/len(train_loader):.4f} '
                  f'- Val Acc: {100.*correct/total:.1f}%')

    def predict(self, image):
        """Predict mineral class for a single image."""
        self.model.eval()
        with torch.no_grad():
            img_tensor = self.transform(image).unsqueeze(0).to(self.device)
            output = self.model(img_tensor)
            probabilities = torch.softmax(output, dim=1)
        return probabilities.cpu().numpy()[0]
```

**Mineral classes for AfriMine:** pyrite, arsenopyrite, chalcopyrite, galena, sphalerite, magnetite, hematite, gold (visible), quartz, calcite, chlorite, sericite, etc.

**Where in AfriMine:** `ml/mineral_classifier.py` — integrated with core photography workflow. Auto-labels minerals in drill core photos for geological logging assistance.

---

### D5. Ensemble Methods — Combining Multiple Models

**What:** Combine predictions from kriging, RF, XGBoost, and GP to produce a single, more robust grade estimate. Ensembles reduce variance and capture different aspects of the data.

**Python:**

```python
import numpy as np
from sklearn.linear_model import RidgeCV

class GradeEnsemble:
    """Ensemble of grade estimation models."""

    def __init__(self):
        self.models = {}
        self.meta_learner = None

    def add_model(self, name, model):
        self.models[name] = model

    def simple_average(self, X):
        """Equal-weight ensemble."""
        preds = np.array([m.predict(X) for m in self.models.values()])
        return preds.mean(axis=0), preds.std(axis=0)

    def weighted_average(self, X, weights):
        """Manual weights based on CV performance."""
        preds = np.array([m.predict(X) for m in self.models.values()])
        weights = np.array(weights) / sum(weights)
        weighted = (preds * weights[:, None]).sum(axis=0)
        return weighted

    def stacking(self, X_train, y_train, X_test):
        """
        Stacking: train a meta-learner on base model predictions.
        Uses out-of-fold predictions to avoid overfitting.
        """
        from sklearn.model_selection import cross_val_predict

        # Generate out-of-fold predictions from each base model
        meta_features_train = np.column_stack([
            cross_val_predict(m, X_train, y_train, cv=5)
            for m in self.models.values()
        ])

        # Train meta-learner
        self.meta_learner = RidgeCV(alphas=[0.01, 0.1, 1.0, 10.0])
        self.meta_learner.fit(meta_features_train, y_train)

        # Predict on test set
        meta_features_test = np.column_stack([
            m.predict(X_test) for m in self.models.values()
        ])

        return self.meta_learner.predict(meta_features_test)

    def uncertainty_from_disagreement(self, X):
        """Uncertainty estimate from model disagreement."""
        preds = np.array([m.predict(X) for m in self.models.values()])
        return {
            'mean': preds.mean(axis=0),
            'std': preds.std(axis=0),
            'min': preds.min(axis=0),
            'max': preds.max(axis=0),
            'coefficient_of_variation': preds.std(axis=0) / preds.mean(axis=0)
        }
```

**Where in AfriMine:** `ml/ensemble.py` — the final estimation step. Combines kriging, RF, XGBoost, and GP outputs. The stacking weights are trained on cross-validation data and stored per domain.

---

## E. Spatial Statistics

### E1. Spatial Autocorrelation (Moran's I)

**What:** Tests whether nearby samples have similar grades (positive autocorrelation) or dissimilar grades (negative). If Moran's I is near zero, the data is spatially random — geostatistics won't help.

**Math:**

$$I = \frac{n}{\sum_{i}\sum_{j} w_{ij}} \cdot \frac{\sum_{i}\sum_{j} w_{ij}(z_i - \bar{z})(z_j - \bar{z})}{\sum_{i}(z_i - \bar{z})^2}$$

where $w_{ij}$ = spatial weight (inverse distance, binary neighbor, etc.).

$E[I] = -1/(n-1)$ under null hypothesis of no autocorrelation.

$I > E[I]$ → positive spatial autocorrelation (clustered).  
$I < E[I]$ → negative (dispersed).

**Python — PySAL:**

```python
import libpysal as lps
from esda.moran import Moran, Moran_Local
import numpy as np

def test_spatial_autocorrelation(x, y, values, k_neighbors=8):
    """
    Test for global and local spatial autocorrelation.

    Returns global Moran's I and local indicators (LISA).
    """
    # Build spatial weights matrix
    from libpysal.weights import KNN
    coords = np.column_stack([x, y])
    w = KNN(coords, k=k_neighbors)
    w.transform = 'r'  # row-standardize

    # Global Moran's I
    mi = Moran(values, w, two_tailed=True)

    global_result = {
        'I': mi.I,
        'expected_I': mi.EI,
        'p_value': mi.p_sim,
        'z_score': mi.z_sim,
        'significant': mi.p_sim < 0.05,
        'interpretation': 'clustered' if mi.I > mi.EI else 'dispersed' if mi.I < mi.EI else 'random'
    }

    # Local Moran's I (LISA) — identifies clusters and outliers
    lisa = Moran_Local(values, w, two_tailed=True)

    # Classify each point
    sig = lisa.p_sim < 0.05
    quadrants = lisa.q  # 1=HH, 2=LH, 3=LL, 4=HL

    labels = np.where(sig & (quadrants == 1), 'high-high',
             np.where(sig & (quadrants == 2), 'low-high',
             np.where(sig & (quadrants == 3), 'low-low',
             np.where(sig & (quadrants == 4), 'high-low', 'not-significant'))))

    return {
        'global': global_result,
        'local_labels': labels,
        'local_p_values': lisa.p_sim,
        'n_clusters': np.sum(sig & ((quadrants == 1) | (quadrants == 3))),
        'n_outliers': np.sum(sig & ((quadrants == 2) | (quadrants == 4)))
    }
```

**Where in AfriMine:** `spatial/autocorrelation.py` — run as part of EDA before variography. If Moran's I is not significant, geostatistical estimation won't add value over simple averaging.

---

### E2. Geographically Weighted Regression (GWR)

**What:** Regression where coefficients vary spatially. Instead of one global relationship between, say, arsenic and gold, GWR fits a separate regression at each location using nearby data. Reveals where relationships change.

**Python — mgwr:**

```python
from mgwr.gwr import GWR
from mgwr.sel_bw import Sel_BW
import numpy as np

def spatial_regression(x, y, dependent, independents):
    """
    GWR: fit spatially varying regression coefficients.

    Parameters:
        x, y: coordinates
        dependent: array of dependent variable (e.g., gold grade)
        independents: 2D array of independent variables (e.g., As, Cu, Fe)
    """
    coords = np.column_stack([x, y])

    # Select optimal bandwidth
    selector = Sel_BW(coords, dependent.reshape(-1, 1), independents)
    bandwidth = selector.search(criterion='AICc')
    print(f"Optimal bandwidth: {bandwidth:.1f}")

    # Fit GWR
    gwr_model = GWR(coords, dependent.reshape(-1, 1), independents, bandwidth)
    gwr_results = gwr_model.fit()

    return {
        'local_params': gwr_results.params,           # coefficients per location
        'local_R2': gwr_results.localR2,              # local R² per location
        'predictions': gwr_results.predy.flatten(),
        'residuals': gwr_results.resid.flatten(),
        'bandwidth': bandwidth,
        'AICc': gwr_results.aicc,
        'global_R2': gwr_results.R2,
        'summary': gwr_results.summary()
    }
```

**Where in AfriMine:** `spatial/gwr.py` — used in geochemical exploration to map how element relationships change spatially. E.g., the As-Au correlation might be strong in one zone but weak in another.

---

### E3. Point Pattern Analysis

**What:** Tests whether sample locations are clustered, random, or dispersed. Critical for understanding whether the drilling pattern introduces bias.

**Python:**

```python
import numpy as np
from scipy.spatial.distance import pdist, cdist

def clark_evans_test(x, y, area):
    """
    Clark-Evans test for clustering of sample locations.
    R < 1: clustered, R = 1: random, R > 1: dispersed.
    """
    n = len(x)
    coords = np.column_stack([x, y])

    # Mean nearest-neighbor distance
    dist_matrix = cdist(coords, coords)
    np.fill_diagonal(dist_matrix, np.inf)
    nearest_distances = dist_matrix.min(axis=1)
    mean_nn = nearest_distances.mean()

    # Expected under CSR (complete spatial randomness)
    expected_nn = 0.5 / np.sqrt(n / area)

    # Ratio
    R = mean_nn / expected_nn

    # Z-test
    se = 0.26136 / np.sqrt(n * (n / area))
    z = (mean_nn - expected_nn) / se
    from scipy.stats import norm
    p_value = 2 * (1 - norm.cdf(abs(z)))

    return {
        'R': R,
        'z_score': z,
        'p_value': p_value,
        'pattern': 'clustered' if R < 1 and p_value < 0.05 else 'dispersed' if R > 1 and p_value < 0.05 else 'random'
    }


def k_function(x, y, area, n_bins=20, max_dist=None):
    """
    Ripley's K function — shows clustering at multiple scales.
    K(h) > πh²: clustered at distance h
    K(h) = πh²: random
    K(h) < πh²: dispersed
    """
    coords = np.column_stack([x, y])
    n = len(x)
    pairwise = pdist(coords)

    if max_dist is None:
        max_dist = pairwise.max() / 2

    bin_edges = np.linspace(0, max_dist, n_bins + 1)
    bin_centers = (bin_edges[:-1] + bin_edges[1:]) / 2

    intensity = n / area
    k_values = []

    for i in range(n_bins):
        count = np.sum((pairwise >= bin_edges[i]) & (pairwise < bin_edges[i+1]))
        # K(h) = count / (n * intensity)  (simplified)
        k_h = count / (n * intensity)
        k_values.append(k_h)

    # Expected under CSR
    expected = np.pi * bin_centers ** 2

    return {
        'distances': bin_centers,
        'K_observed': np.array(k_values),
        'K_expected': expected,
        'L_observed': np.sqrt(np.array(k_values) / np.pi),  # L(h) = sqrt(K/π)
        'L_expected': bin_centers
    }
```

**Where in AfriMine:** `spatial/point_pattern.py` — run on drillhole locations to detect sampling bias. If samples are clustered in one area, kriging estimates in sparse areas will have high uncertainty.

---

### E4. Spatial Outlier Detection

**What:** Identifies samples whose grade is inconsistent with their neighbors. These could be real high-grade zones (important!) or data errors (dangerous!).

**Python:**

```python
import numpy as np
from scipy import stats

def detect_spatial_outliers(x, y, grades, k_neighbors=6, z_threshold=2.5):
    """
    Detect spatial outliers: samples that deviate from their neighbors.

    Method: Compare each sample's grade to the local neighborhood mean.
    """
    from scipy.spatial import cKDTree

    coords = np.column_stack([x, y])
    tree = cKDTree(coords)

    outlier_flags = []
    local_stats = []

    for i in range(len(grades)):
        # Find k nearest neighbors (excluding self)
        distances, indices = tree.query(coords[i], k=k_neighbors + 1)
        neighbor_indices = indices[1:]  # exclude self
        neighbor_grades = grades[neighbor_indices]

        local_mean = np.mean(neighbor_grades)
        local_std = np.std(neighbor_grades)

        if local_std > 0:
            z_local = (grades[i] - local_mean) / local_std
        else:
            z_local = 0

        is_outlier = abs(z_local) > z_threshold

        outlier_flags.append(is_outlier)
        local_stats.append({
            'sample_index': i,
            'grade': grades[i],
            'local_mean': local_mean,
            'local_std': local_std,
            'z_local': z_local,
            'is_spatial_outlier': is_outlier,
            'type': 'high' if z_local > z_threshold else 'low' if z_local < -z_threshold else 'normal'
        })

    return {
        'outlier_flags': np.array(outlier_flags),
        'n_outliers': sum(outlier_flags),
        'details': local_stats
    }
```

**Where in AfriMine:** `spatial/outliers.py` — runs after compositing, before variography. Spatial outliers are flagged for manual review. If confirmed real, they may indicate a high-grade shoot; if errors, they're corrected or removed.

---

## F. Bayesian Methods

### F1. Bayesian Resource Estimation

**What:** Instead of a single kriging estimate, produce a full probability distribution for each block's grade. Combines prior knowledge (geological model, analogous deposits) with observed data to get a posterior distribution.

**Math:**

$$P(\text{grade} | \text{data}) \propto P(\text{data} | \text{grade}) \cdot P(\text{grade})$$

Prior: geological expectation (e.g., log-normal with mean 1.5 g/t, based on deposit type).  
Likelihood: kriging model (variogram-based).  
Posterior: updated grade distribution incorporating both.

**Python — PyMC:**

```python
import pymc as pm
import numpy as np
import arviz as az

def bayesian_grade_estimation(x, y, grades, x_target, y_target,
                               prior_mean=1.5, prior_std=0.5):
    """
    Bayesian estimation of grade at a target location using PyMC.

    Uses a spatial model with Matérn covariance.
    """
    with pm.Model() as spatial_model:
        # Priors for variogram parameters
        length_scale = pm.Gamma('length_scale', alpha=3, beta=0.01)  # ~300m
        variance = pm.Gamma('variance', alpha=2, beta=0.8)           # ~2.5
        nugget = pm.Gamma('nugget', alpha=1.5, beta=5)              # ~0.3

        # Mean grade (prior from deposit knowledge)
        mu = pm.Normal('mu', mu=prior_mean, sigma=prior_std)

        # Build covariance matrix
        coords = np.column_stack([x, y])
        coords_with_target = np.vstack([coords, [x_target, y_target]])

        # Using GP framework
        gp = pm.gp.Marginal(
            cov_func=variance * pm.gp.cov.Matern52(2, ls=length_scale) +
                     pm.gp.cov.WhiteNoise(nugget)
        )

        # Observed data
        y_obs = pm.Normal('y_obs', mu=mu, sigma=nugget, observed=grades)

        # Target prediction
        f_target = gp.marginal_likelihood('f_target', X=coords_with_target,
                                           y=np.append(grades, np.nan))

        # Sample posterior
        trace = pm.sample(2000, tune=1000, cores=2, return_inferencedata=True)

    return trace


def summarize_posterior(trace, cutoff=0.5):
    """Extract useful summaries from posterior."""
    samples = trace.posterior['f_target'].values.flatten()

    return {
        'mean': np.mean(samples),
        'median': np.median(samples),
        'std': np.std(samples),
        'ci_90': (np.percentile(samples, 5), np.percentile(samples, 95)),
        'prob_above_cutoff': np.mean(samples > cutoff),
        'expected_grade_if_above': np.mean(samples[samples > cutoff]) if np.any(samples > cutoff) else 0
    }
```

**Where in AfriMine:** `bayesian/resource_estimation.py` — produces posterior grade distributions per block. More computationally expensive than kriging but provides richer uncertainty quantification.

---

### F2. Uncertainty Quantification — Probability of Exceeding Cut-off

**What:** For each block, what is the probability that the true grade exceeds the mining cut-off grade? This is more useful than a single point estimate for mine planning decisions.

**Python:**

```python
import numpy as np
from scipy import stats

def probability_above_cutoff(kriging_grade, kriging_variance, cutoff,
                              distribution='lognormal'):
    """
    Probability that true grade exceeds cutoff.

    Parameters:
        kriging_grade: kriging estimate (in original space or log-space)
        kriging_variance: kriging variance
        cutoff: cut-off grade
    """
    if distribution == 'lognormal':
        # Assume kriging was done in log-space
        # kriging_grade is in log-space
        z = (np.log(cutoff) - kriging_grade) / np.sqrt(kriging_variance)
        prob = 1 - stats.norm.cdf(z)

    elif distribution == 'normal':
        z = (cutoff - kriging_grade) / np.sqrt(kriging_variance)
        prob = 1 - stats.norm.cdf(z)

    return prob


def grade_tonnage_curve(grades_array, variances_array, cutoffs, densities,
                        block_volumes, distribution='lognormal'):
    """
    Generate grade-tonnage curves with uncertainty bands.
    """
    results = []

    for cutoff in cutoffs:
        probs = np.array([
            probability_above_cutoff(g, v, cutoff, distribution)
            for g, v in zip(grades_array, variances_array)
        ])

        # Expected tonnage above cut-off
        tonnage = np.sum(probs * block_volumes * densities)

        # Expected grade above cut-off (weighted by probability)
        above_mask = probs > 0.5  # simplified; use weighted for rigorous
        if above_mask.any():
            avg_grade = np.average(grades_array[above_mask],
                                   weights=probs[above_mask])
        else:
            avg_grade = 0

        # Metal content
        metal = tonnage * avg_grade

        # Uncertainty via Monte Carlo (see F3)
        results.append({
            'cutoff': cutoff,
            'tonnage_mt': tonnage / 1e6,
            'grade_gt': avg_grade,
            'metal_kg': metal / 1000,
            'metal_oz': metal / 31.1035
        })

    return results
```

**Where in AfriMine:** `bayesian/grade_tonnage.py` — produces the grade-tonnage curves that drive mine design and economic analysis. Shows how tonnage and grade change with different cut-off decisions.

---

### F3. Monte Carlo Simulation

**What:** Simulate thousands of possible grade realizations that honor the variogram and data, to quantify uncertainty in resource estimates. Each simulation is a possible "reality."

**Python — Sequential Gaussian Simulation (SGS):**

```python
import gstools as gs
import numpy as np

def sgs_simulation(model, cond_pos, cond_val, gridx, gridy, n_realizations=100):
    """
    Sequential Gaussian Simulation — generate multiple equiprobable grade realizations.

    Each realization honors:
    1. The variogram model (spatial structure)
    2. The conditioning data (drillhole grades at sample locations)
    """
    simulations = []

    for i in range(n_realizations):
        # SGS via GSTools
        srf = gs.SRF(model, seed=i)

        # Condition on drillhole data
        srf(
            [gridx, gridy],
            conditioning=(cond_pos, cond_val)
        )

        simulations.append(srf.field.copy())

    simulations = np.array(simulations)

    # Statistics across realizations
    return {
        'realizations': simulations,
        'mean': simulations.mean(axis=0),
        'std': simulations.std(axis=0),
        'p10': np.percentile(simulations, 10, axis=0),
        'p50': np.percentile(simulations, 50, axis=0),
        'p90': np.percentile(simulations, 90, axis=0),
        'prob_above_cutoff': (simulations > cutoff).mean(axis=0),
    }


def uncertainty_propagation(simulations, block_volume, density, cutoff):
    """
    From simulation realizations, derive resource uncertainty.
    """
    n_realizations = simulations.shape[0]
    total_metals = []
    total_tonnages = []

    for i in range(n_realizations):
        field = simulations[i]
        above = field > cutoff
        tonnage = above.sum() * block_volume * density
        metal = (field[above] * block_volume * density).sum()
        total_tonnages.append(tonnage)
        total_metals.append(metal)

    return {
        'tonnage_mean': np.mean(total_tonnages),
        'tonnage_std': np.std(total_tonnages),
        'tonnage_p10': np.percentile(total_tonnages, 10),
        'tonnage_p90': np.percentile(total_tonnages, 90),
        'metal_mean': np.mean(total_metals),
        'metal_std': np.std(total_metals),
        'metal_p10': np.percentile(total_metals, 10),
        'metal_p90': np.percentile(total_metals, 90),
    }
```

**Where in AfriMine:** `bayesian/monte_carlo.py` — the most computationally intensive module. Run on GPU/cluster for large models. Outputs feed into financial risk analysis (NPV distributions).

---

### F4. Bayesian Optimization — Where to Sample Next

**What:** Uses the uncertainty model to suggest the most informative location for the next drillhole. Balances exploration (high uncertainty) vs. exploitation (near known mineralization).

**Math:**

Expected Improvement (EI) acquisition function:

$$EI(x) = E[\max(f(x) - f^+, 0)]$$

where $f^+$ is the current best observed value. For a GP posterior:

$$EI(x) = (\mu(x) - f^+)\Phi(z) + \sigma(x)\phi(z)$$

where $z = \frac{\mu(x) - f^+}{\sigma(x)}$.

**Python — scikit-optimize:**

```python
from skopt import gp_minimize
from skopt.space import Real
import numpy as np

class DrillholeOptimizer:
    """Bayesian optimization for drillhole targeting."""

    def __init__(self, variogram_model, existing_data, domain_boundary):
        self.model = variogram_model
        self.data = existing_data
        self.domain = domain_boundary

    def acquisition_expected_improvement(self, candidate_x, candidate_y,
                                          gp_model, best_grade):
        """Compute EI at a candidate location."""
        X_candidate = np.array([[candidate_x, candidate_y]])
        mean, std = gp_model.predict(X_candidate, return_std=True)

        if std == 0:
            return 0

        z = (mean - best_grade) / std
        from scipy.stats import norm
        ei = (mean - best_grade) * norm.cdf(z) + std * norm.pdf(z)
        return ei[0]

    def suggest_next_drillhole(self, search_area_bounds, n_suggestions=5):
        """
        Suggest optimal drillhole locations that maximize information gain.

        Combines:
        1. Expected improvement (grade potential)
        2. Kriging variance reduction (uncertainty reduction)
        3. Spatial coverage (avoid clustering)
        """
        from sklearn.gaussian_process import GaussianProcessRegressor
        from sklearn.gaussian_process.kernels import Matern

        # Fit GP on existing data
        X = self.data[['x', 'y']].values
        y = self.data['grade'].values

        kernel = Matern(nu=2.5)
        gp = GaussianProcessRegressor(kernel=kernel, random_state=42)
        gp.fit(X, y)

        # Generate candidate grid
        x_range = np.arange(search_area_bounds[0][0], search_area_bounds[0][1], 25)
        y_range = np.arange(search_area_bounds[1][0], search_area_bounds[1][1], 25)
        xx, yy = np.meshgrid(x_range, y_range)
        candidates = np.column_stack([xx.ravel(), yy.ravel()])

        # Score each candidate
        means, stds = gp.predict(candidates, return_std=True)
        best_grade = y.max()

        # Composite score: EI + uncertainty bonus
        ei_scores = []
        for i in range(len(candidates)):
            ei = self.acquisition_expected_improvement(
                candidates[i, 0], candidates[i, 1], gp, best_grade
            )
            # Add uncertainty bonus (information gain)
            uncertainty_bonus = stds[i] * 0.5
            ei_scores.append(ei + uncertainty_bonus)

        # Select top N non-redundant locations
        ei_scores = np.array(ei_scores)
        suggestions = []
        min_spacing = 100  # minimum distance between suggested holes

        sorted_indices = np.argsort(ei_scores)[::-1]
        for idx in sorted_indices:
            if len(suggestions) >= n_suggestions:
                break
            candidate = candidates[idx]
            # Check spacing from existing and other suggestions
            all_existing = np.vstack([X] + [s.reshape(1, -1) for s in suggestions]) if suggestions else X
            distances = np.sqrt(np.sum((all_existing - candidate) ** 2, axis=1))
            if distances.min() >= min_spacing:
                suggestions.append(candidate)

        return [{
            'x': s[0], 'y': s[1],
            'ei_score': ei_scores[np.where((candidates == s).all(axis=1))[0][0]],
            'predicted_grade': gp.predict(s.reshape(1, -1))[0],
            'uncertainty': gp.predict(s.reshape(1, -1), return_std=True)[1][0]
        } for s in suggestions]
```

**Where in AfriMine:** `bayesian/drillhole_optimizer.py` — interactive tool for exploration managers. Takes the current block model + uncertainty map → outputs ranked drillhole targets with rationale.

---

## G. Data Quality

### G1. Detection Limits

**What:** Analytical instruments (XRF, ICP-MS, fire assay) have minimum detection limits. Values reported as "<0.01 ppm" are left-censored — the true value is between 0 and 0.01. These must be handled properly or they bias grade estimates.

**Python:**

```python
import numpy as np

class DetectionLimitHandler:
    """Handle below-detection-limit (BDL) values in geochemical data."""

    def __init__(self, detection_limits):
        """
        detection_limits: dict of {element: limit_value}
        e.g., {'Au': 0.005, 'As': 0.5, 'Cu': 0.2}
        """
        self.limits = detection_limits

    def impute_bdl(self, values, element, method='half_limit'):
        """
        Replace BDL values with estimated values.

        Methods:
        - 'half_limit': replace with detection_limit / 2 (simple, common)
        - 'lognormal_mle': use MLE on detected values to estimate BDL mean
        - 'regression': use correlated elements to predict BDL values
        """
        limit = self.limits[element]
        bdl_mask = values < limit

        if method == 'half_limit':
            values_clean = values.copy()
            values_clean[bdl_mask] = limit / 2

        elif method == 'lognormal_mle':
            from scipy import stats
            detected = values[~bdl_mask]
            log_detected = np.log(detected[detected > 0])

            # MLE for lognormal parameters from censored data
            mu_mle = np.mean(log_detected)
            sigma_mle = np.std(log_detected)

            # Expected value of truncated lognormal
            # E[X | X < limit] for lognormal
            z = (np.log(limit) - mu_mle) / sigma_mle
            from scipy.stats import norm
            e_truncated = np.exp(mu_mle + sigma_mle**2 / 2) * norm.cdf(z - sigma_mle) / norm.cdf(z)

            values_clean = values.copy()
            values_clean[bdl_mask] = e_truncated

        elif method == 'regression':
            # Use a correlated element to predict BDL values
            # (implement if strong correlation exists)
            raise NotImplementedError("Regression imputation requires correlation analysis")

        return values_clean, bdl_mask

    def report_censoring(self, df, element):
        """Report censoring statistics."""
        values = df[element].values
        limit = self.limits[element]
        bdl_count = np.sum(values < limit)
        total = len(values)

        return {
            'element': element,
            'detection_limit': limit,
            'total_samples': total,
            'bdl_count': bdl_count,
            'censoring_pct': bdl_count / total * 100,
            'warning': 'HIGH CENSORING' if bdl_count / total > 0.3 else 'OK'
        }
```

**Where in AfriMine:** `data_quality/detection_limits.py` — runs on import of geochemical data. If >30% of an element is BDL, flag for alternative analytical method.

---

### G2. Censored Data Handling

**What:** Beyond simple imputation, proper statistical treatment of censored data uses maximum likelihood estimation (MLE) or robust methods like ROS (Regression on Order Statistics) to estimate distribution parameters.

**Python — NADA2 approach:**

```python
import numpy as np
from scipy import stats
from scipy.optimize import minimize

def mle_censored_lognormal(values, detection_limit):
    """
    MLE for lognormal parameters with left-censored data.

    values: array where values < detection_limit are BDL (marked as detection_limit)
    """
    censored = values <= detection_limit
    detected = values[~censored & (values > 0)]

    if len(detected) < 5:
        raise ValueError("Too few detected values for MLE")

    def neg_log_likelihood(params):
        mu, sigma = params
        if sigma <= 0:
            return 1e10

        # Log-likelihood for detected values
        ll_detected = np.sum(stats.norm.logpdf(np.log(detected), mu, sigma))

        # Log-likelihood for censored values (probability of being below limit)
        n_censored = np.sum(censored)
        ll_censored = n_censored * stats.norm.logcdf(np.log(detection_limit), mu, sigma)

        return -(ll_detected + ll_censored)

    # Initial estimates from detected values
    x0 = [np.mean(np.log(detected)), np.std(np.log(detected))]

    result = minimize(neg_log_likelihood, x0, method='Nelder-Mead')
    mu_mle, sigma_mle = result.x

    # Back-transform to arithmetic space
    mean_arithmetic = np.exp(mu_mle + sigma_mle**2 / 2)
    var_arithmetic = mean_arithmetic**2 * (np.exp(sigma_mle**2) - 1)

    return {
        'mu_log': mu_mle,
        'sigma_log': sigma_mle,
        'mean_arithmetic': mean_arithmetic,
        'std_arithmetic': np.sqrt(var_arithmetic),
        'n_detected': len(detected),
        'n_censored': int(np.sum(censored)),
        'converged': result.success
    }
```

**Where in AuMine:** `data_quality/censored.py` — alternative to simple imputation for projects with heavy censoring. Used when >15% of values are BDL.

---

### G3. Outlier Detection

**What:** Distinguishes genuine high-grade samples from data entry errors, mis-assayed samples, or mixed-up sample IDs. Must be conservative — removing a real high-grade sample is worse than keeping an error.

**Python:**

```python
import numpy as np
from scipy import stats

class OutlierDetector:
    """Multi-method outlier detection for mining data."""

    def __init__(self, grades):
        self.grades = grades
        self.log_grades = np.log(grades[grades > 0])

    def method_iqr(self, factor=3.0):
        """IQR method in log-space (robust to skewness)."""
        q1, q3 = np.percentile(self.log_grades, [25, 75])
        iqr = q3 - q1
        lower = q1 - factor * iqr
        upper = q3 + factor * iqr
        outliers = (self.log_grades < lower) | (self.log_grades > upper)
        return {
            'method': 'IQR',
            'threshold_low': np.exp(lower),
            'threshold_high': np.exp(upper),
            'outlier_indices': np.where(outliers)[0],
            'n_outliers': outliers.sum()
        }

    def method_mad(self, threshold=3.5):
        """Median Absolute Deviation — very robust."""
        median = np.median(self.log_grades)
        mad = np.median(np.abs(self.log_grades - median))
        modified_z = 0.6745 * (self.log_grades - median) / mad
        outliers = np.abs(modified_z) > threshold
        return {
            'method': 'MAD',
            'threshold': threshold,
            'outlier_indices': np.where(outliers)[0],
            'n_outliers': outliers.sum(),
            'outlier_grades': np.exp(self.log_grades[outliers])
        }

    def method_isolation_forest(self, features):
        """Isolation Forest for multivariate outlier detection."""
        from sklearn.ensemble import IsolationForest

        iso = IsolationForest(contamination=0.05, random_state=42)
        labels = iso.fit_predict(features)

        return {
            'method': 'IsolationForest',
            'outlier_indices': np.where(labels == -1)[0],
            'n_outliers': (labels == -1).sum()
        }

    def comprehensive_report(self):
        """Run all methods and flag consensus outliers."""
        iqr = self.method_iqr()
        mad = self.method_mad()

        # Consensus: flagged by multiple methods
        all_indices = set(iqr['outlier_indices']) | set(mad['outlier_indices'])
        consensus = []
        for idx in all_indices:
            count = sum([
                idx in iqr['outlier_indices'],
                idx in mad['outlier_indices'],
            ])
            if count >= 2:
                consensus.append(idx)

        return {
            'iqr': iqr,
            'mad': mad,
            'consensus_outliers': consensus,
            'recommendation': 'REVIEW' if consensus else 'OK'
        }
```

**Where in AfriMine:** `data_quality/outliers.py` — runs before capping. Consensus outliers are flagged in the QA/QC report. The geologist makes the final call (keep/remove/cap).

---

### G4. Assay Quality Control

**What:** End-to-end QC workflow that validates the entire assay chain: from sample collection → preparation → analysis → reporting.

**Python:**

```python
class AssayQCPipeline:
    """Complete QA/QC pipeline for assay data."""

    def __init__(self, standards_certified, detection_limits):
        self.standards = standards_certified
        self.detection_limits = detection_limits

    def run_full_qc(self, samples_df):
        """
        Run complete QC analysis.

        samples_df columns:
        - sample_id, hole_id, from, to, grade, sample_type,
        - lab_code, analysis_method, date_received
        """
        report = {}

        # 1. Standards analysis
        report['standards'] = self._check_standards(samples_df)

        # 2. Blanks analysis
        report['blanks'] = self._check_blanks(samples_df)

        # 3. Duplicates analysis
        report['duplicates'] = self._check_duplicates(samples_df)

        # 4. Detection limit compliance
        report['detection_limits'] = self._check_detection_limits(samples_df)

        # 5. Grade distribution sanity
        report['distribution'] = self._check_distribution(samples_df)

        # 6. Spatial consistency
        report['spatial'] = self._check_spatial_consistency(samples_df)

        # Overall status
        statuses = [r.get('status', 'PASS') for r in report.values()]
        if 'FAIL' in statuses:
            report['overall_status'] = 'FAIL - BLOCK ESTIMATION'
        elif 'WARNING' in statuses:
            report['overall_status'] = 'WARNING - REVIEW REQUIRED'
        else:
            report['overall_status'] = 'PASS'

        return report

    def _check_standards(self, df):
        stds = df[df['sample_type'] == 'standard']
        if len(stds) == 0:
            return {'status': 'WARNING', 'message': 'No standards in dataset'}

        results = []
        for _, row in stds.iterrows():
            cert = self.standards.get(row.get('standard_id'))
            if cert:
                pct_dev = abs(row['grade'] - cert['value']) / cert['value'] * 100
                results.append({
                    'sample_id': row['sample_id'],
                    'measured': row['grade'],
                    'certified': cert['value'],
                    'pct_deviation': pct_dev,
                    'within_tolerance': pct_dev <= cert.get('tolerance', 10)
                })

        pass_rate = sum(r['within_tolerance'] for r in results) / len(results) * 100
        return {
            'status': 'PASS' if pass_rate >= 95 else 'FAIL',
            'pass_rate': pass_rate,
            'details': results
        }

    def _check_blanks(self, df):
        blanks = df[df['sample_type'] == 'blank']
        if len(blanks) == 0:
            return {'status': 'WARNING', 'message': 'No blanks in dataset'}

        contaminated = blanks['grade'] > self.detection_limits.get('Au', 0.01) * 3
        return {
            'status': 'PASS' if contaminated.sum() / len(blanks) < 0.05 else 'FAIL',
            'n_blanks': len(blanks),
            'n_contaminated': contaminated.sum(),
            'max_blank_grade': blanks['grade'].max()
        }

    def _check_duplicates(self, df):
        dupes = df[df['sample_type'] == 'duplicate']
        if len(dupes) == 0:
            return {'status': 'WARNING', 'message': 'No duplicates in dataset'}

        # Calculate precision metrics
        originals = df[df['sample_type'] == 'sample'].set_index('sample_id')
        merged = dupes.merge(originals[['grade']], left_on='duplicate_of',
                             right_index=True, suffixes=('_dup', '_orig'))

        abs_diff = abs(merged['grade_dup'] - merged['grade_orig'])
        mean_pair = (merged['grade_dup'] + merged['grade_orig']) / 2
        cv = abs_diff / mean_pair * 100

        return {
            'status': 'PASS' if cv.mean() < 20 else 'WARNING' if cv.mean() < 30 else 'FAIL',
            'n_duplicates': len(dupes),
            'mean_cv_pct': cv.mean(),
            'max_cv_pct': cv.max()
        }

    def _check_detection_limits(self, df):
        checks = {}
        for element, limit in self.detection_limits.items():
            if element in df.columns:
                bdl_pct = (df[element] < limit).sum() / len(df) * 100
                checks[element] = {
                    'detection_limit': limit,
                    'bdl_pct': bdl_pct,
                    'status': 'PASS' if bdl_pct < 15 else 'WARNING' if bdl_pct < 30 else 'FAIL'
                }
        return checks

    def _check_distribution(self, df):
        """Check if grade distribution is reasonable for the deposit type."""
        grades = df[df['sample_type'] == 'sample']['grade']
        log_grades = np.log(grades[grades > 0])

        from scipy.stats import shapiro, skew, kurtosis
        _, p_normal = shapiro(log_grades[:5000])  # limit for shapiro

        return {
            'status': 'PASS' if p_normal > 0.01 else 'WARNING',
            'log_normality_p': p_normal,
            'skewness': skew(log_grades),
            'kurtosis': kurtosis(log_grades),
            'n_samples': len(grades),
            'mean': grades.mean(),
            'median': grades.median(),
            'max': grades.max()
        }

    def _check_spatial_consistency(self, df):
        """Flag if samples don't follow expected spatial patterns."""
        # Check for duplicate coordinates (sample mix-up)
        coords = df[['hole_id', 'from']].drop_duplicates()
        n_dup_coords = len(df) - len(coords)

        return {
            'status': 'PASS' if n_dup_coords == 0 else 'WARNING',
            'duplicate_intervals': n_dup_coords
        }
```

**Where in AfriMine:** `data_quality/assay_qc.py` — runs automatically on every data import. Generates a PDF/HTML QC report. Resource estimation is blocked until QC passes.

---

## Pipeline Integration Map

```
┌─────────────────────────────────────────────────────────────┐
│                    DATA IMPORT LAYER                         │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐   │
│  │ Drillhole│  │  Geochem │  │ Geophysics│  │  Images  │   │
│  │  data    │  │  data    │  │  data     │  │  (core)  │   │
│  └────┬─────┘  └────┬─────┘  └────┬──────┘  └────┬─────┘   │
│       └──────────────┴─────────────┴──────────────┘         │
│                          ↓                                   │
│  ┌─────────────────────────────────────────────────────┐    │
│  │           G. DATA QUALITY PIPELINE                   │    │
│  │  Detection Limits → Censored Data → Outliers → QC   │    │
│  │  [G1]              [G2]            [G3]     [G4]    │    │
│  └────────────────────────┬────────────────────────────┘    │
└───────────────────────────┼─────────────────────────────────┘
                            ↓
┌───────────────────────────┼─────────────────────────────────┐
│           GRADE ESTIMATION LAYER                            │
│                           │                                  │
│  ┌────────┐  ┌──────────┐│┌──────────┐  ┌──────────────┐   │
│  │Log-Norm│→ │ Composit-│││  Domain  │→ │  Top-Cut /   │   │
│  │ Test   │  │  ing     │││ Boundary │  │  Capping     │   │
│  │ [B1]   │  │  [B3]    │││  [B4]    │  │  [B2]        │   │
│  └────────┘  └──────────┘│└──────────┘  └──────────────┘   │
│                           ↓                                  │
│  ┌─────────────────────────────────────────────────────┐    │
│  │           A. GEOSTATISTICS                           │    │
│  │  Variogram → Kriging Type Selection → Block Kriging  │    │
│  │  [A1]       [A3]                [A5]   [A2]         │    │
│  │                   ↓                                   │    │
│  │            Kriging Variance [A6]                      │    │
│  │            Co-Kriging (optional) [A4]                 │    │
│  └────────────────────────┬────────────────────────────┘    │
│                           │                                  │
│  ┌────────────────────────┴────────────────────────────┐    │
│  │           D. ML LAYER (parallel to kriging)          │    │
│  │  RF Prospectivity [D1]  XGBoost Grade [D2]          │    │
│  │  GP Spatial [D3]        Mineral CNN [D4]             │    │
│  │            Ensemble [D5]                              │    │
│  └────────────────────────┬────────────────────────────┘    │
│                           ↓                                  │
│  ┌─────────────────────────────────────────────────────┐    │
│  │  Change of Support [B5] → Grade-Tonnage Curves      │    │
│  └────────────────────────┬────────────────────────────┘    │
└───────────────────────────┼─────────────────────────────────┘
                            ↓
┌───────────────────────────┼─────────────────────────────────┐
│           RESOURCE CLASSIFICATION                           │
│  ┌──────────────┐  ┌───────────────┐  ┌────────────────┐   │
│  │ JORC Classif.│  │  Confidence   │  │ Search Neigh-  │   │
│  │ [C1]         │  │  Intervals    │  │ borhoods [C3]  │   │
│  │              │  │  [C2]         │  │                │   │
│  └──────────────┘  └───────────────┘  └────────────────┘   │
└───────────────────────────┼─────────────────────────────────┘
                            ↓
┌───────────────────────────┼─────────────────────────────────┐
│           BAYESIAN / UNCERTAINTY LAYER                      │
│  ┌──────────────┐  ┌───────────────┐  ┌────────────────┐   │
│  │ Bayes Estim. │  │ Monte Carlo   │  │  Drillhole     │   │
│  │ [F1]         │  │ Simulation    │  │  Optimizer     │   │
│  │              │  │ [F3]          │  │  [F4]          │   │
│  │ P(>cutoff)   │  │               │  │                │   │
│  │ [F2]         │  │               │  │                │   │
│  └──────────────┘  └───────────────┘  └────────────────┘   │
└───────────────────────────┼─────────────────────────────────┘
                            ↓
┌───────────────────────────┼─────────────────────────────────┐
│           SPATIAL ANALYSIS                                  │
│  Moran's I [E1]  GWR [E2]  Point Pattern [E3]  Outliers [E4]│
│  (used throughout for validation and EDA)                   │
└─────────────────────────────────────────────────────────────┘
```

---

## Library Dependencies

```toml
# requirements.txt for AfriMine statistics/ML stack

# Core
numpy>=1.24
pandas>=2.0
scipy>=1.10

# Geostatistics
gstools>=1.5
pykrige>=1.7

# Spatial Statistics
libpysal>=4.7
esda>=2.5
mgwr>=2.2

# Machine Learning
scikit-learn>=1.3
xgboost>=2.0

# Deep Learning
torch>=2.0
torchvision>=0.15
gpytorch>=1.11

# Bayesian
pymc>=5.0
arviz>=0.15
scikit-optimize>=0.9

# 3D Geometry (domain wireframes)
pyvista>=0.40
trimesh>=4.0

# Visualization
matplotlib>=3.7
seaborn>=0.12
plotly>=5.15
```

---

*Document generated for AfriMine AI development team. Each section is self-contained — developers can implement modules independently following the pipeline map.*
