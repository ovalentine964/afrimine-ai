# AfriMine AI — Mining Engineering Concept Reference
## Module Specifications for Platform Development

*Generated: 2026-07-18*
*Purpose: Software-oriented extraction of mining domain concepts for AI platform implementation*

---

## A. RESOURCE ESTIMATION

### A1. JORC/SAMREC Resource Classification

**What it is:** A standardized framework that classifies mineral resources into three confidence tiers — **Measured** (highest confidence, <10% error), **Indicated** (moderate confidence, <25% error), and **Inferred** (lowest confidence, conceptual-level). JORC is the Australian standard; SAMREC is the South African equivalent used across Africa.

**Code/Data Translation:**
```
enum ResourceCategory {
  MEASURED,    // drill spacing ~25-50m, high confidence
  INDICATED,   // drill spacing ~50-100m, moderate confidence
  INFERRED     // drill spacing ~100-200m, low confidence
}

struct ResourceEstimate {
  tonnage: float          // million tonnes
  grade: float            // g/t Au or % Cu
  category: ResourceCategory
  cut_off_grade: float
  confidence_interval: float  // e.g. ±15% for Measured
}
```

**Where in platform:** Resource classification module — input for economic assessment, mine planning, and investor reporting dashboards.

---

### A2. Cut-Off Grade

**What it is:** The minimum grade at which a block of ore is economically worth mining. Below this grade, the rock is classified as waste. Cut-off grade changes with metal price, processing cost, and mining method.

**Code/Data Translation:**
```
formula: cut_off_grade = (mining_cost + processing_cost + admin_cost) / (metal_price × recovery_rate × payability)

// Example for gold:
// If mining=$4/t, processing=$15/t, admin=$3/t, gold=$1800/oz, recovery=92%, payability=95%
// cut_off = (4+15+3) / (1800 × 0.03215 × 0.92 × 0.95) ≈ 0.44 g/t
// (Note: 0.03215 converts oz to grams)

struct CutOffParams {
  mining_cost_per_tonne: float    // USD/t
  processing_cost_per_tonne: float
  admin_cost_per_tonne: float
  metal_price: float              // USD/oz or USD/lb
  recovery_rate: float            // 0.0 - 1.0
  payability: float               // smelter terms, 0.0 - 1.0
}

func calculateCutOff(p: CutOffParams) float:
  return (p.mining_cost + p.processing_cost + p.admin_cost) / 
         (p.metal_price * p.recovery_rate * p.payability)
```

**Where in platform:** Economic engine — dynamically recalculates as metal prices change. Critical for "what-if" scenarios and real-time resource reclassification.

---

### A3. Grade-Tonnage Curves

**What it is:** A graph showing the relationship between cut-off grade and the total tonnage of ore available at that grade. Higher cut-off = less ore but higher average grade. Used to find the optimal economic balance.

**Code/Data Translation:**
```
func generateGradeTonnageCurve(blockModel: []Block, cutOffRange: []float) []CurvePoint:
  results = []
  for co in cutOffRange:
    oreBlocks = filter(blockModel, b => b.grade >= co)
    tonnage = sum(oreBlocks, b => b.tonnage)
    avgGrade = weightedAverage(oreBlocks, b => b.grade, b => b.tonnage)
    metalContent = tonnage * avgGrade
    results.append({cutOff: co, tonnage, avgGrade, metalContent})
  return results

struct CurvePoint {
  cut_off: float
  tonnage: float      // kt or Mt
  average_grade: float
  metal_content: float // oz or kg
}
```

**Where in platform:** Visualization module — interactive charts for geologists. Feeds into NPV optimization to find the profitable cut-off.

---

### A4. Block Models

**What it is:** A 3D grid dividing a mineral deposit into rectangular blocks (typically 5m×5m×5m to 25m×25m×10m), each assigned an estimated grade from drill hole interpolation. The fundamental data structure of modern mining.

**Code/Data Translation:**
```
struct Block {
  coordinates: Vec3      // x, y, z center point
  dimensions: Vec3       // dx, dy, dz size
  grade: float           // estimated grade
  tonnage: float         // calculated from dimensions × density
  density: float         // tonnes/m³ (typically 2.5-3.0 for gold ore)
  category: ResourceCategory
  rock_type: string
  material_type: enum { ORE, WASTE, MARGINAL }
}

struct BlockModel {
  origin: Vec3
  block_size: Vec3
  dimensions: Vec3      // number of blocks in each direction
  blocks: [][][]Block   // 3D array
  parent_blocks: []Block  // sub-blocked for grade boundaries
}

// Tonnage of a single block:
func blockTonnage(b: Block) float:
  volume = b.dimensions.x * b.dimensions.y * b.dimensions.z
  return volume * b.density
```

**Where in platform:** Core data model — every module (planning, scheduling, economics) reads from the block model. Storage and querying of block models is a primary database challenge.

---

### A5. Kriging Parameters

**What it is:** A geostatistical interpolation method that estimates grade in unsampled blocks using weighted averages of nearby drill holes. Parameters control how the estimation behaves.

**Code/Data Translation:**
```
struct KrigingParams {
  block_size: Vec3           // dimensions of output blocks
  search_radius: Vec3        // max distance to look for samples
  min_samples: int           // minimum drill holes required (typically 4-8)
  max_samples: int           // maximum samples to use (typically 12-24)
  variogram_model: VariogramModel
  anisotropy: AnisotropyRatio  // directional search scaling
}

struct VariogramModel {
  type: enum { SPHERICAL, EXPONENTIAL, GAUSSIAN }
  nugget: float        // micro-variability (random noise)
  sill: float          // total variance at plateau
  range: float         // distance where correlation ends (meters)
  // For anisotropic models:
  ranges: Vec3         // different range in x, y, z directions
  rotations: Vec3      // angles for anisotropy axes
}

// Variogram formula (spherical model):
func sphericalVariogram(h, nugget, sill, range) float:
  if h == 0: return 0
  if h >= range: return sill
  return nugget + (sill - nugget) * (1.5 * (h/range) - 0.5 * (h/range)**3)
```

**Where in platform:** Geostatistics engine — must support variogram modeling and kriging interpolation. This is where AI/ML can add value by automating variogram fitting and validating estimates.

---

## B. MINING METHODS

### B1. Artisanal Mining

**What it is:** Small-scale, manual mining using basic tools (picks, shovels, sluice boxes, mercury amalgamation). Operated by individuals or small groups, often informal. In Kenya, concentrated in areas like Migori, Kakamega, and Turkana. Major gold producing method in rural Kenya.

**Code/Data Translation:**
```
struct ArtisanalOperation {
  location: GeoPoint
  miners_count: int
  method: enum { PANNING, SLUICE, TUNNELING, SURFACE }
  equipment: []string    // ["pickaxe", "sluice_box", "mercury", "diesel_pump"]
  estimated_production: float  // grams/month
  permit_status: enum { NONE, PENDING, ACTIVE, EXPIRED }
  permit_number: string
  permit_expiry: date
  mercury_use: bool      // environmental flag
  safety_rating: int     // 1-5 risk score
}

// Key data inputs for platform:
// - GPS coordinates of operation
// - Registration status with county government
// - Monthly production estimates (self-reported or surveyed)
// - Mercury/heavy metal usage assessment
```

**Where in platform:** Community engagement module, compliance tracking, supply chain traceability, and artisanal miner formalization programs.

---

### B2. Small-Scale Mining

**What it is:** Semi-mechanized operations above artisanal but below large-scale. Uses excavators, crushers, and processing plants. In Kenya, requires a Small-Scale Mining Permit (KES 60,000). Typically 5-50 workers, operating defined claims.

**Code/Data Translation:**
```
struct SmallScaleOperation {
  claim_area: float         // hectares (max 10 ha in Kenya)
  permit: Permit
  equipment: EquipmentSet
  workforce: int
  daily_throughput: float   // tonnes/day (typically 10-100)
  processing_method: []enum { GRAVITY, CIL, CIP, FLOTATION }
  annual_production: float  // oz Au or tonnes Cu
  operating_cost: float     // USD/tonne
}

struct EquipmentSet {
  excavator: bool          // typically 5-20 tonne
  crusher: bool            // jaw crusher, typically 10-50 tph
  processing_plant: bool   // gravity + CIL/CIP
  generator: bool          // power supply
  pumps: bool              // dewatering
  vehicles: int
}
```

**Where in platform:** Equipment recommendation engine, production tracking, cost modeling, permit management.

---

### B3. Open Pit vs Underground

**What it is:** Two fundamental mining approaches. **Open pit** removes waste rock from surface downward in terraced benches — used when ore is near surface and the strip ratio is economic. **Underground** accesses ore via tunnels/shafts — used when ore is deep or the strip ratio makes open pit uneconomic.

**Code/Data Translation:**
```
struct MiningMethodSelection {
  ore_depth: float              // meters from surface
  deposit_width: float          // meters
  strip_ratio: float            // waste:ore
  rock_strength: float          // MPa (UCS)
  grade_distribution: []float   // is it higher at depth?
  water_table_depth: float
  selected_method: enum { OPEN_PIT, UNDERGROUND, COMBINATION }
}

// Decision heuristic:
func selectMethod(params) enum:
  if params.ore_depth < 300 and params.strip_ratio < 15:
    return OPEN_PIT
  if params.ore_depth > 500 or params.strip_ratio > 20:
    return UNDERGROUND
  return COMBINATION   // open pit transitioning to underground
```

**Where in platform:** Mine method selection module — automated evaluation comparing economics of each approach. Critical for scoping studies.

---

### B4. Alluvial Mining

**What it is:** Mining gold from river sediments and flood plains. Gold particles settle in specific locations (inside bends, behind boulders, on bedrock) due to gravity. Common in Kenyan rivers. Uses panning, sluice boxes, or dredges.

**Code/Data Translation:**
```
struct AlluvialDeposit {
  location: GeoPoint
  river_name: string
  sediment_depth: float         // meters to bedrock
  gold_concentration: float     // mg/m³
  particle_size: enum { FINE, COARSE, NUGGET }
  clay_content: float           // % (affects processing)
  water_availability: bool
  flood_risk: enum { LOW, MEDIUM, HIGH }
  season_access: enum { YEAR_ROUND, DRY_ONLY }
}

// Production estimate:
// gold_recovery = area × depth × concentration × recovery_factor
// recovery_factor typically 0.5-0.8 for gravity methods
```

**Where in platform:** Alluvial deposit assessment, seasonal production planning, equipment sizing (sluice capacity vs. volume throughput).

---

### B5. Hard Rock Mining

**What it is:** Extracting gold from quartz veins or stockwork in solid rock. Requires drilling, blasting, hauling, and crushing. Higher capital cost but more consistent grade. Common in Kenya's greenstone belts (Kakamega, Migori).

**Code/Data Translation:**
```
struct VeinDeposit {
  vein_width: float         // meters (often 0.5-3m for gold veins)
  dip: float                // degrees from horizontal
  strike: float             // compass bearing
  plunge: float             // degrees from horizontal in strike direction
  grade: float              // g/t (often 5-30 g/t for high-grade veins)
  rock_quality: RQD         // Rock Quality Designation
  alteration: string        // wall rock alteration type
}

// Key economic factor: narrow veins (<1.5m) are expensive to mine
// because dilution (mixing waste with ore) increases significantly
// Dilution formula:
// diluted_grade = vein_grade × vein_width / (vein_width + dilution_width)
```

**Where in platform:** Vein modeling, underground design, dilution estimation, selective mining optimization.

---

## C. MINE PLANNING

### C1. Pit Optimization (Lerchs-Grossmann Algorithm)

**What it is:** A graph-theory algorithm that finds the optimal open pit shape — the pit that maximizes total profit while respecting geotechnical slope constraints. It assigns economic value to each block (revenue minus cost) and finds the "ultimate pit" shell.

**Code/Data Translation:**
```
struct PitOptimizationInput {
  block_model: BlockModel
  metal_price: float
  recovery_rate: float
  mining_cost: float        // $/t for waste
  mining_cost_ore: float    // $/t for ore (may differ)
  processing_cost: float    // $/t
  selling_cost: float       // $/t
  slope_angles: SlopeAngles // geotechnical constraints
  discount_rate: float      // for nested pits
}

struct SlopeAngles {
  overall: float            // degrees (typically 45-55°)
  inter_ramp: float
  bench_face: float         // typically 60-70°
  bench_height: float       // meters (typically 5-10m)
  berms_width: float        // safety berms
}

// Block economic value:
func blockValue(block, params) float:
  if block.material_type == WASTE:
    return -params.mining_cost  // cost to remove
  revenue = block.tonnage * block.grade * params.metal_price * params.recovery_rate
  cost = block.tonnage * (params.mining_cost_ore + params.processing_cost + params.selling_cost)
  return revenue - cost

// LG algorithm produces:
// 1. Ultimate Pit Limits (UPL) — the largest profitable pit
// 2. Nested Pits — a series of smaller pits at different revenue factors
//    used for pushback sequencing and phase planning
```

**Where in platform:** Pit optimizer module — core of open pit mine design. Must handle large block models (millions of blocks). AI can speed up computation for real-time scenario analysis.

---

### C2. Production Scheduling

**What it is:** Determining what to mine and when — which blocks are extracted in each period (month, quarter, year). Goal is to maximize NPV while respecting equipment capacity, grade blending targets, and mine sequence constraints.

**Code/Data Translation:**
```
struct SchedulePeriod {
  period_id: int
  blocks: []Block
  tonnes_mined: float       // total tonnes (ore + waste)
  tonnes_ore: float
  average_grade: float
  metal_production: float
  cash_flow: float          // revenue - costs, discounted
  equipment_fleet: Fleet
}

struct ScheduleConstraints {
  max_mining_rate: float    // Mt/quarter
  min_mining_rate: float
  max_processing_rate: float // Mt/quarter
  min_grade: float          // blending constraint
  max_grade: float
  max_stripping_ratio: float
  pit_access: []SequenceRule  // precedence constraints
}

// Optimization objective:
// maximize NPV = Σ(period_cashflow / (1 + discount_rate)^period)
// subject to all constraints
```

**Where in platform:** Schedule optimizer — generates and compares multiple schedule scenarios. Real-time rescheduling when conditions change (equipment breakdown, price moves).

---

### C3. Waste-to-Ore Ratio (Strip Ratio)

**What it is:** The tonnes of waste rock that must be removed to access one tonne of ore. For open pit gold mines, typically 2:1 to 10:1. Higher ratio = higher mining cost per tonne of ore. The "break-even strip ratio" is where mining cost equals ore revenue.

**Code/Data Translation:**
```
// Strip ratio calculation for a given pit:
func stripRatio(totalWaste, totalOre) float:
  return totalWaste / totalOre

// Break-even strip ratio:
func breakEvenStripRatio(oreRevenue, wasteCost, oreMiningCost) float:
  // When: oreRevenue = (strip_ratio × wasteCost) + oreMiningCost
  // Solve: strip_ratio = (oreRevenue - oreMiningCost) / wasteCost
  return (oreRevenue - oreMiningCost) / wasteCost

// Example:
// oreRevenue = 2.5 g/t × $1800/oz × 0.92 recovery × 0.03215 = $133.3/t
// wasteCost = $4/t, oreMiningCost = $5/t (ore slightly more expensive)
// breakEvenSR = (133.3 - 5) / 4 = 32:1 (very favorable)
```

**Where in platform:** Economic threshold analysis — determines how deep the pit can go before it becomes uneconomic. Drives pit optimization and phase design.

---

### C4. Mine Life Calculation

**What it is:** How many years the mine will operate based on total reserves, annual production rate, and potential for reserve growth through exploration.

**Code/Data Translation:**
```
struct MineLifeEstimate {
  proven_reserves: float      // Mt
  probable_reserves: float    // Mt
  annual_processing_rate: float // Mt/year
  recovery_rate: float
  expansion_potential: float  // inferred resources that may convert
  mine_life_years: float
}

func calculateMineLife(reserves, annualRate, recovery) float:
  return (reserves * recovery) / annualRate

// Typical ranges:
// Small-scale gold mine in Kenya: 3-10 years
// Medium-scale: 10-20 years
// Large-scale: 15-30+ years
```

**Where in platform:** Financial modeling — mine life directly impacts NPV, financing, and community planning. Longer mine life = higher NPV due to deferred stripping and economies of scale.

---

## D. PROCESSING / METALLURGY

### D1. Gravity Separation

**What it is:** Using the density difference between gold (19.3 g/cm³) and waste rock (~2.7 g/cm³) to separate free gold particles. Simplest and cheapest method. Effective for coarse gold (>100 microns). Methods: jigs, spirals, shaking tables, centrifugal concentrators (Knelson/Falcon).

**Code/Data Translation:**
```
struct GravityRecovery {
  feed_grade: float         // g/t
  feed_rate: float          // tph
  recovery_rate: float      // typically 30-60% of total gold
  concentrate_grade: float  // g/t (often 500-5000 g/t)
  gold_particle_size: float // microns
  liberation_size: float    // microns (gold free from host rock)
}

// Gravity recovery depends on gold particle size:
// >250 μm → 70-90% gravity recovery
// 100-250 μm → 50-70%
// 50-100 μm → 30-50%
// <50 μm → 10-30% (need cyanidation)

// Often used as pre-concentration before CIL/CIP:
// total_recovery = gravity_recovery + (1 - gravity_recovery) × leach_recovery
```

**Where in platform:** Processing plant design, recovery optimization, circuit simulation. AI can optimize gravity circuit parameters in real-time.

---

### D2. Cyanidation (CIL/CIP)

**What it is:** The standard gold extraction process. Crushed ore is mixed with a dilute cyanide solution that dissolves gold. In **Carbon-in-Leach (CIL)**, activated carbon adsorbs gold simultaneously with leaching. In **Carbon-in-Pulp (CIP)**, carbon is added after leaching. Gold is then stripped from carbon and electrowon.

**Code/Data Translation:**
```
struct CyanidationCircuit {
  feed_rate: float           // tonnes/day
  feed_grade: float          // g/t
  grind_size: float          // P80 in microns (typically 75-106 μm)
  cyanide_concentration: float // ppm NaCN (typically 200-500 ppm)
  dissolved_oxygen: float    // ppm (typically 8-10 ppm)
  leach_time: float          // hours (typically 24-48 hours)
  carbon_inventory: float    // tonnes of activated carbon
  carbon_activity: float     // g Au/kg C
  stages: int                // number of CIL/CIP tanks (typically 6-8)
  expected_recovery: float   // typically 90-95%
}

// Key formula — gold dissolution rate (simplified):
// dAu/dt = k × [CN⁻] × [O₂]^0.5 × (Au_remaining - Au_eq)
// where k = rate constant, Au_eq = equilibrium loading

// Recovery estimation:
func estimateRecovery(ore: OreProperties, circuit: CyanidationCircuit) float:
  // Based on testwork correlations
  base_recovery = 0.93  // typical for free-milling ore
  // Adjustments:
  if ore.sulfur_content > 2.0: base_recovery -= 0.15  // refractory
  if ore.clay_content > 15: base_recovery -= 0.05     // preg-robbing
  if circuit.grind_size > 106: base_recovery -= 0.03  // coarse grind
  return min(base_recovery, 0.98)
```

**Where in platform:** Processing simulation, recovery prediction, reagent cost modeling. AI/ML for real-time recovery optimization based on feed characteristics.

---

### D3. Flotation

**What it is:** A process that separates valuable minerals from waste by exploiting differences in surface chemistry. Finely ground ore is mixed with water, chemicals (collectors, frothers), and air bubbles. Hydrophobic minerals attach to bubbles and float as froth. Used for copper-gold ores and sulfide concentrates.

**Code/Data Translation:**
```
struct FlotationCircuit {
  feed_grade_cu: float      // % Cu
  feed_grade_au: float      // g/t Au
  grind_size: float         // P80 μm
  ph: float                 // typically 9-11 for Cu-Au
  collector_dosage: float   // g/t (typically 20-50 g/t)
  frother_dosage: float     // g/t (typically 10-30 g/t)
  retention_time: float     // minutes per cell
  cells: int                // number of flotation cells
  rougher_recovery: float   // typically 85-95% Cu
  cleaner_recovery: float   // additional upgrading
  concentrate_grade: float  // % Cu, g/t Au
}

// Key output — two products:
// 1. Concentrate (goes to smelter) — small volume, high grade
// 2. Tailings (waste) — large volume, low grade
```

**Where in platform:** Process design for polymetallic deposits (common in Kenya's greenstone belts). AI for reagent dosage optimization and grade prediction.

---

### D4. Recovery Rate

**What it is:** The percentage of metal in the ore that is actually recovered as saleable product. A mine with 2.5 g/t ore and 92% recovery effectively treats the ore as 2.3 g/t. Recovery is the single biggest lever on project economics.

**Code/Data Translation:**
```
struct RecoveryChain {
  mining_recovery: float     // % of ore actually extracted (vs left in pillars/walls)
  processing_recovery: float // % of metal recovered in plant
  smelting_recovery: float   // % of metal recovered at smelter/refinery
  payability: float          // % of metal paid for (smelter terms)
}

// Overall recovery:
func overallRecovery(chain: RecoveryChain) float:
  return chain.mining_recovery * chain.processing_recovery * 
         chain.smelting_recovery * chain.payability

// Typical gold values:
// mining: 90-95% (open pit), 85-90% (underground)
// processing: 88-95% (free milling), 70-85% (refractory)
// smelting: 99%+
// payability: 95-98%
// Overall: 75-85% typical
```

**Where in platform:** Economics engine — recovery directly impacts revenue. Also used in reconciliation (comparing predicted vs actual recovery).

---

### D5. Refractory Gold

**What it is:** Gold that is physically locked inside sulfide minerals (typically pyrite or arsenopyrite) and cannot be dissolved by normal cyanidation. Requires pre-treatment: roasting, pressure oxidation (POX), bio-oxidation, or ultra-fine grinding to expose the gold before leaching.

**Code/Data Translation:**
```
struct RefractorinessAssessment {
  total_gold: float          // g/t (assay)
  free_gold: float           // g/t (visible/exposed)
  locked_gold: float         // g/t (in sulfides)
  sulfide_content: float     // % S
  arsenic_content: float     // % As
  organic_carbon: float      // % C (preg-robbing)
  cyanide_recovery: float    // % without pre-treatment
  pre_treatment: enum { NONE, ROASTING, POX, BIO_OXIDATION, UFG }
  expected_recovery: float   // % with pre-treatment
}

// Classification heuristic:
func classifyOre(sulfur, cyanide_recovery) enum:
  if cyanide_recovery > 90: return FREE_MILLING
  if sulfur > 2.0 and cyanide_recovery < 80: return REFRACTORY_SULFIDE
  if organic_carbon > 0.5: return REFRACTORY_CARBONACEOUS
  return MILDLY_REFRACTORY

// Pre-treatment cost impact:
// Roasting: +$15-25/t
// POX: +$20-40/t (capital intensive)
// Bio-oxidation: +$10-20/t (slow, lower capital)
```

**Where in platform:** Ore type classification, process route selection, economic modeling. Critical for Kenyan deposits which often contain sulfide-hosted gold.

---

## E. ECONOMICS

### E1. Net Present Value (NPV)

**What it is:** The total value of a mine today, calculated by discounting all future cash flows back to present value. The primary metric for investment decisions. NPV > 0 means the project creates value.

**Code/Data Translation:**
```
struct CashFlowModel {
  initial_capex: float        // USD (mine construction)
  sustaining_capex: float     // USD/year (ongoing equipment)
  annual_revenue: []float     // USD/year
  annual_opex: []float        // USD/year
  tax_rate: float             // % (Kenya: 30% corporate)
  royalty_rate: float         // % (Kenya: varies by mineral)
  discount_rate: float        // % (typically 8-10% for mining)
  mine_life: int              // years
  terminal_value: float       // salvage/closure costs
}

func calculateNPV(model: CashFlowModel) float:
  npv = -model.initial_capex
  for year in 1..model.mine_life:
    revenue = model.annual_revenue[year]
    opex = model.annual_opex[year]
    royalty = revenue * model.royalty_rate
    tax = max(0, (revenue - opex - royalty) * model.tax_rate)
    cashflow = revenue - opex - royalty - tax - model.sustaining_capex
    npv += cashflow / (1 + model.discount_rate)^year
  npv += model.terminal_value / (1 + model.discount_rate)^model.mine_life
  return npv

// Typical NPV ranges for gold projects:
// Small-scale (Kenya): $1M - $20M
// Medium-scale: $50M - $200M
// Large-scale: $500M - $3B+
```

**Where in platform:** Financial modeling dashboard — the primary output investors and decision-makers see. Must support real-time recalculation when parameters change.

---

### E2. Internal Rate of Return (IRR)

**What it is:** The discount rate at which NPV equals zero. Expressed as a percentage. Higher IRR = better project. Mining investors typically require 15-25% IRR to justify the risk.

**Code/Data Translation:**
```
func calculateIRR(cashFlows: []float, guess: float) float:
  // Newton-Raphson iteration
  // Find rate where NPV(cashFlows, rate) = 0
  rate = guess
  for i in 0..100:  // max iterations
    npv = calculateNPVAtRate(cashFlows, rate)
    npv_derivative = calculateNPVDerivative(cashFlows, rate)
    new_rate = rate - npv / npv_derivative
    if abs(new_rate - rate) < 0.0001: break
    rate = new_rate
  return rate

// Decision criteria:
// IRR > hurdle_rate (typically 15-25%) → PROJECT ACCEPTED
// IRR < hurdle_rate → PROJECT REJECTED
// Compare IRR across competing projects for capital allocation
```

**Where in platform:** Investment analysis module — reported alongside NPV. Sensitivity charts showing IRR at different gold prices.

---

### E3. Payback Period

**What it is:** How many years until the initial capital investment is recovered from mine cash flows. Shorter is better. Mining projects typically target 3-5 year payback. "Discounted payback" accounts for time value of money.

**Code/Data Translation:**
```
func paybackPeriod(initialCapex: float, annualCashFlows: []float) float:
  cumulative = 0.0
  for year, cf in annualCashFlows:
    cumulative += cf
    if cumulative >= initialCapex:
      // Interpolate for fractional year
      shortfall = initialCapex - (cumulative - cf)
      return year + shortfall / cf
  return -1  // never pays back

func discountedPayback(capex, cashFlows, rate) float:
  cumulative = 0.0
  for year, cf in cashFlows:
    discounted_cf = cf / (1 + rate)^year
    cumulative += discounted_cf
    if cumulative >= capex:
      return year  // approximate
  return -1
```

**Where in platform:** Risk assessment — payback period is a quick filter for project viability. Shorter payback = lower risk.

---

### E4. Sensitivity Analysis

**What it is:** Testing how project economics change when key variables change. Typically: gold price ±20%, operating cost ±15%, recovery ±5%, capex ±20%. Shows which variables the project is most sensitive to.

**Code/Data Translation:**
```
struct SensitivityVariable {
  name: string
  base_value: float
  min_value: float
  max_value: float
  steps: int              // number of test points
}

func sensitivityAnalysis(baseModel: CashFlowModel, variables: []SensitivityVariable) []SensitivityResult:
  results = []
  for var in variables:
    for step in var.steps:
      test_value = lerp(var.min_value, var.max_value, step / var.steps)
      modified_model = modifyModel(baseModel, var.name, test_value)
      npv = calculateNPV(modified_model)
      irr = calculateIRR(modified_model)
      results.append({
        variable: var.name,
        value: test_value,
        npv: npv,
        irr: irr
      })
  return results

// Key outputs — tornado chart showing which variable has biggest impact
// Typically: Gold price > Recovery > Mining cost > Processing cost > Capex
```

**Where in platform:** Risk analysis dashboard — interactive tornado diagrams, spider plots, Monte Carlo simulation for probability distributions.

---

### E5. Royalty Calculations (Kenya)

**What it is:** Payments to the government based on mineral production value. Kenya's Mining Act 2016 sets royalties as a percentage of gross mineral value, varying by mineral type and form.

**Code/Data Translation:**
```
struct RoyaltyRate {
  mineral: string
  form: string              // "ore", "concentrate", "refined"
  rate: float               // percentage
}

// Kenya Mining Act 2016 royalty rates (key minerals):
var KENYA_ROYALTIES = {
  "gold":     { "ore": 0.05, "concentrate": 0.05, "refined": 0.05 },  // 5%
  "copper":   { "ore": 0.05, "concentrate": 0.05 },
  "titanium": { "ore": 0.05 },
  "soda_ash": { "ore": 0.05 },
  "salt":     { "ore": 0.05 },
  "gemstones":{ "ore": 0.05 },
  "coal":     { "ore": 0.05 },
  // Default for unlisted minerals:
  "default":  { "ore": 0.05 }
}

func calculateRoyalty(production_value: float, mineral: string, form: string) float:
  rate = KENYA_ROYALTIES[mineral][form] or KENYA_ROYALTIES["default"]["ore"]
  return production_value * rate

// Production value calculation:
// value = production_oz × metal_price_per_oz
// Royalty is on GROSS value, not net
```

**Where in platform:** Financial model — royalties are a direct cost. Also important for compliance reporting and government revenue projections.

---

## F. SAFETY & ENVIRONMENTAL

### F1. Ground Stability / Slope Stability

**What it is:** Assessing whether pit walls, underground openings, or waste dumps will remain stable. Failure can be catastrophic. Depends on rock mass properties, discontinuity orientation (joints, faults), groundwater, and blasting vibration.

**Code/Data Translation:**
```
struct SlopeStabilityInput {
  rock_mass_rating: float     // RMR (0-100)
  discontinuity_orientation: Vec3  // dip/dip_direction of joints
  slope_orientation: Vec3
  cohesion: float             // kPa
  friction_angle: float       // degrees
  unit_weight: float          // kN/m³
  water_pressure: float       // kPa
  slope_height: float         // meters
  slope_angle: float          // degrees
}

// Factor of Safety (simplified planar failure):
func factorOfSafety(params) float:
  // FOS = resisting forces / driving forces
  // Simplified: FOS = (c + σn × tan(φ)) / τ
  // where σn = normal stress, τ = shear stress on failure plane
  FOS = (params.cohesion + effectiveNormalStress * tan(radians(params.friction_angle))) / shearStress
  return FOS
  // FOS > 1.3 → stable
  // FOS 1.0-1.3 → marginal (monitoring required)
  // FOS < 1.0 → unstable (design change required)

// Classification:
func stabilityRating(fos) string:
  if fos >= 1.5: return "STABLE"
  if fos >= 1.3: return "ACCEPTABLE"
  if fos >= 1.0: return "MARGINAL"
  return "UNSTABLE"
```

**Where in platform:** Geotechnical module — pit wall angle optimization, monitoring alert system, design compliance checking.

---

### F2. Water Management

**What it is:** Managing water in and around mining operations. Includes: **dewatering** (pumping groundwater to keep pit dry), **water treatment** (removing contaminants before discharge), **water balance** (tracking all water in/out of the mine), and **contamination prevention** (acid mine drainage, heavy metals).

**Code/Data Translation:**
```
struct WaterBalance {
  rainfall: float             // mm/year → m³/year for catchment area
  groundwater_inflow: float   // m³/day
  process_water: float        // m³/day (recirculated)
  makeup_water: float         // m³/day (fresh water required)
  evaporation: float          // m³/day
  seepage: float              // m³/day
  discharge: float            // m³/day (to environment)
  dam_storage: float          // m³
}

struct WaterQuality {
  ph: float
  heavy_metals: {pb: float, as: float, hg: float, cd: float}  // mg/l
  cyanide: float              // mg/l (WAD cyanide)
  tss: float                  // total suspended solids mg/l
  conductivity: float         // μS/cm
  // Kenya NEMA discharge limits:
  // pH: 6-9, Pb < 0.1 mg/l, As < 0.1 mg/l, CN < 0.1 mg/l
}

// Dewatering pump sizing:
// pump_capacity = peak_inflow × safety_factor (typically 1.5-2.0)
```

**Where in platform:** Environmental monitoring, water treatment design, compliance reporting, real-time water quality dashboards.

---

### F3. Environmental Impact Assessment (EIA)

**What it is:** A mandatory study before any mining project in Kenya (under EMCA 1999, managed by NEMA). Identifies potential environmental and social impacts and proposes mitigation measures. Required for all mining licenses.

**Code/Data Translation:**
```
struct EIAReport {
  project_name: string
  location: GeoPoint
  nema_ref: string            // NEMA reference number
  project_category: enum { CATEGORY_A, CATEGORY_B }
  // Category A: Full EIA required (large mines)
  // Category B: Partial EIA (small-scale)

  baseline_studies: {
    air_quality: AirQualityData
    water_quality: WaterQualityData
    soil_quality: SoilQualityData
    biodiversity: BiodiversitySurvey
    noise_levels: NoiseData
    socio_economics: SocioEconomicBaseline
  }

  impacts: []ImpactAssessment
  mitigation_measures: []Mitigation
  monitoring_plan: MonitoringPlan
  closure_plan: ClosurePlan
  public_consultation: ConsultationRecord
}

struct ImpactAssessment {
  phase: enum { CONSTRUCTION, OPERATION, CLOSURE, POST_CLOSURE }
  component: string           // "water quality", "air quality", etc.
  impact_type: enum { POSITIVE, NEGATIVE }
  significance: enum { NEGLIGIBLE, MINOR, MODERATE, MAJOR, CRITICAL }
  likelihood: enum { RARE, UNLIKELY, POSSIBLE, LIKELY, ALMOST_CERTAIN }
  reversibility: enum { REVERSIBLE, IRREVERSIBLE }
  mitigation: string
}
```

**Where in platform:** Compliance module — EIA checklist generator, impact assessment matrix, monitoring schedule tracker. Helps small-scale miners navigate the EIA process.

---

### F4. Rehabilitation / Restoration

**What it is:** Returning a mined area to a safe, stable, and environmentally acceptable condition after mining ends. In Kenya, mine operators must submit a rehabilitation plan and provide financial assurance (rehabilitation bond) before mining begins.

**Code/Data Translation:**
```
struct ClosurePlan {
  site_area: float            // hectares
  disturbance_type: []enum { PIT, WASTE_DUMP, TAILINGS, PROCESS_PLANT, ROADS }
  closure_actions: []ClosureAction
  estimated_cost: float       // USD
  bond_amount: float          // financial guarantee
  timeline_years: int         // years to complete rehabilitation
  success_criteria: []SuccessCriterion
}

struct ClosureAction {
  area: string
  action: enum { BACKFILL, CONTOUR, TOPSOIL, REVEGETATE, WATER_TREATMENT, DEMOLITION }
  cost_per_hectare: float
  duration_months: int
}

struct SuccessCriterion {
  parameter: string           // "vegetation cover", "slope stability", "water quality"
  target: float
  monitoring_period: int      // years
}

// Bond calculation (Kenya):
// Typically 10-30% of estimated closure cost
// Or based on per-hectare rates set by NEMA
func calculateRehabBond(closureCost, bondRate) float:
  return closureCost * bondRate
```

**Where in platform:** Closure planning module, bond estimation, long-term environmental monitoring schedule.

---

## G. KENYA-SPECIFIC REGULATORY

### G1. Mining Act 2016 Requirements

**What it is:** Kenya's primary mining legislation (Mining Act, 2016, No. 12 of 2016). Replaced the old Mining Act of 1940. Establishes the licensing framework, rights of miners, community participation, and government oversight through the Ministry of Mining and the Mining Cadastre.

**Code/Data Translation:**
```
struct MiningLicense {
  license_type: enum { 
    RECONNAISSANCE,    // 1 year, large area, low commitment
    EXPLORATION,       // 3 years (renewable), defined area
    RETENTION,         // 3 years (max), when market conditions unfavorable
    MINING_LEASE,      // 21 years (renewable), production
    SMALL_SCALE,       // 5 years (renewable), ≤10 ha
    ARTISANAL,         // 3 years (renewable), individuals/groups
    PROCESSING,        // for processing plants
    DEALER,            // mineral trading
    TRANSPORTER        // mineral transport
  }
  area_hectares: float
  duration_years: int
  renewal_possible: bool
  annual_fee: float           // KES
  work_commitment: float      // USD exploration spend
  conditions: []string
}

// License hierarchy for gold mining:
// 1. Reconnaissance Permit → find prospects
// 2. Exploration License → drill and define resource
// 3. Mining Lease → extract and sell
// Each requires progressively more data and investment
```

**Where in platform:** Regulatory compliance module — license tracker, application workflow, renewal reminders, work program reporting.

---

### G2. Artisanal Mining Permit

**What it is:** A permit under the Mining Act 2016 for artisanal miners. Costs KES 1,000 (~$8 USD). Available to Kenyan citizens who are members of recognized artisanal mining cooperatives. Limited to hand tools and simple machinery. Valid for 3 years, renewable.

**Code/Data Translation:**
```
struct ArtisanalPermit {
  permit_cost: 1000           // KES
  duration: 3                 // years
  eligibility: {
    citizenship: "Kenyan",
    cooperative_member: true,
    age_minimum: 18
  }
  restrictions: {
    area_max: null            // defined by cooperative
    equipment: ["hand_tools", "simple_machinery"],
    explosives: false,
    mechanized: false
  }
  requirements: []string {
    "Membership in registered cooperative",
    "Environmental management plan",
    "Safety training certificate",
    "Site restoration plan"
  }
}

// Permit application workflow:
// 1. Form cooperative (minimum 10 members)
// 2. Register with county government
// 3. Apply to Ministry of Mining
// 4. Environmental compliance (NEMA)
// 5. Pay KES 1,000
// 6. Receive permit
```

**Where in platform:** Permit application assistant, cooperative management, compliance tracker, production reporting.

---

### G3. Small-Scale Mining Permit

**What it is:** A permit for semi-mechanized operations. Costs KES 60,000 (~$465 USD). Maximum area of 10 hectares. Requires more formal processes than artisanal mining, including environmental impact assessment and detailed work program.

**Code/Data Translation:**
```
struct SmallScalePermit {
  permit_cost: 60000          // KES
  duration: 5                 // years (renewable)
  max_area: 10                // hectares
  eligibility: {
    citizenship: "Kenyan",
    company_registration: true,
    technical_competence: true
  }
  requirements: []string {
    "Environmental Impact Assessment (EIA)",
    "Work program and budget",
    "Technical report on mineral potential",
    "Financial capability statement",
    "Community consultation records",
    "Mine closure plan",
    "Rehabilitation bond",
    "Safety management plan"
  }
  annual_requirements: []string {
    "Annual production report",
    "Environmental monitoring report",
    "Royalty payments (5% of gross value)",
    "Safety incident reporting"
  }
}
```

**Where in platform:** License management, EIA workflow, annual reporting automation, royalty calculation.

---

### G4. Environmental Compliance (NEMA)

**What it is:** The National Environment Management Authority (NEMA) oversees all environmental compliance in Kenya under EMCA 1999. Mining projects require: EIA license, annual environmental audits, waste management licenses, and effluent discharge permits.

**Code/Data Translation:**
```
struct NEMACompliance {
  eia_license: {
    required: true
    category: enum { A, B }  // based on project scale
    processing_time: "90-180 days"
    cost: "varies by project scale"
  }
  annual_audit: {
    required: true
    due_date: "anniversary of EIA license"
    submitted_by: "licensed environmental auditor"
  }
  waste_management: {
    hazardous_waste_license: bool
    tailings_management_plan: bool
    waste_manifest: bool      // tracking waste disposal
  }
  discharge_permit: {
    required: true            // if discharging treated water
    parameters: ["pH", "heavy_metals", "TSS", "cyanide", "conductivity"]
    limits: WaterQuality      // reference to limits struct above
  }
  penalties: {
    non_compliance: "suspension or cancellation of license"
    pollution: "fine up to KES 2M or imprisonment up to 2 years"
  }
}
```

**Where in platform:** Compliance calendar, document management, audit scheduling, environmental monitoring integration.

---

### G5. Community Benefit Requirements

**What it is:** The Mining Act 2016 requires mining companies to contribute to local communities. This includes: community development agreements, local employment quotas, procurement from local suppliers, and environmental/social impact mitigation. County governments also receive a share of mining royalties.

**Code/Data Translation:**
```
struct CommunityBenefit {
  development_agreement: {
    required: true
    parties: ["mining_company", "community_representatives", "county_government"]
    content: []string {
      "Employment and training commitments",
      "Local procurement targets",
      "Community projects (roads, schools, health facilities)",
      "Revenue sharing mechanism",
      "Grievance mechanism"
    }
  }
  revenue_sharing: {
    national_government: 0.70    // 70% of royalties
    county_government: 0.20      // 20% of royalties
    community: 0.10              // 10% of royalties
    // Note: exact splits may vary; verify current regulations
  }
  employment: {
    local_quota: 0.60            // target % local hires
    skills_training: true
    artisanal_miner_integration: true  // formalizing ASM into company operations
  }
  monitoring: {
    annual_community_report: true
    independent_monitoring: true
    grievance_tracking: true
  }
}
```

**Where in platform:** Community relations module, benefit tracking dashboard, grievance management system, stakeholder engagement reporting.

---

## PLATFORM ARCHITECTURE MAPPING

### How Modules Connect

```
┌─────────────────────────────────────────────────────────────┐
│                    AfriMine AI Platform                      │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  ┌──────────┐    ┌──────────┐    ┌──────────┐              │
│  │ Geological│───→│ Resource │───→│   Mine   │              │
│  │   Data    │    │ Estimation│    │ Planning │              │
│  │  (A1-A5)  │    │  Module  │    │  (C1-C4) │              │
│  └──────────┘    └──────────┘    └─────┬────┘              │
│       │                                 │                    │
│       ▼                                 ▼                    │
│  ┌──────────┐    ┌──────────┐    ┌──────────┐              │
│  │  Mining  │───→│Processing│───→│ Economics│              │
│  │ Methods  │    │ /Metall. │    │  (E1-E5) │              │
│  │  (B1-B5) │    │  (D1-D5) │    │          │              │
│  └──────────┘    └──────────┘    └─────┬────┘              │
│       │                                 │                    │
│       ▼                                 ▼                    │
│  ┌──────────┐    ┌──────────┐    ┌──────────┐              │
│  │  Safety  │    │   Kenya  │    │ Reporting│              │
│  │  & Env.  │    │Regulatory│    │Dashboard │              │
│  │  (F1-F4) │    │  (G1-G5) │    │          │              │
│  └──────────┘    └──────────┘    └──────────┘              │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

### Core Data Flow

1. **Geological Data → Resource Estimation**: Drill holes, assays, and geological mapping feed into kriging/block modeling
2. **Resource Estimation → Mine Planning**: Block model + cut-off grade determines mineable reserves → pit optimization
3. **Mine Planning → Processing**: Production schedule drives plant throughput and ore characteristics
4. **Processing → Economics**: Recovery rates and costs feed into NPV/IRR calculations
5. **All Modules → Regulatory**: Every module generates compliance data for NEMA, Mining Act, and community reporting

### AI/ML Opportunities

| Module | AI Application |
|--------|---------------|
| Resource Estimation | Automated variogram modeling, grade estimation from sparse data |
| Block Model | Lithology prediction from geophysical data |
| Pit Optimization | Real-time pit redesign as prices change |
| Production Scheduling | Reinforcement learning for optimal scheduling |
| Processing | Real-time recovery optimization, anomaly detection |
| Economics | Monte Carlo simulation, probabilistic NPV |
| Safety | Slope stability prediction from monitoring data |
| Compliance | Automated report generation, deadline tracking |

---

## KEY FORMULAS QUICK REFERENCE

| Concept | Formula |
|---------|---------|
| Cut-off Grade | `(mining + processing + admin cost) / (price × recovery × payability)` |
| Strip Ratio | `waste tonnes / ore tonnes` |
| Block Tonnage | `volume (m³) × density (t/m³)` |
| Overall Recovery | `mining_recovery × processing_recovery × smelting_recovery × payability` |
| NPV | `Σ [cashflow_t / (1+r)^t]` |
| IRR | Rate where NPV = 0 (iterative solve) |
| Payback Period | Years until cumulative cashflows ≥ capex |
| Royalty | `gross_revenue × royalty_rate (5% Kenya)` |
| Factor of Safety | `resisting_forces / driving_forces` (target ≥ 1.3) |
| Diluted Grade | `vein_grade × vein_width / (vein_width + dilution_width)` |

---

*End of reference document. Each section is designed to be directly implementable as a software module specification.*
