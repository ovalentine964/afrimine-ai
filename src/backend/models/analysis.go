package models

import (
	"time"

	"github.com/google/uuid"
)

// AnalysisStatus represents the current state of an analysis.
type AnalysisStatus string

const (
	StatusPending   AnalysisStatus = "pending"
	StatusRunning   AnalysisStatus = "running"
	StatusCompleted AnalysisStatus = "completed"
	StatusFailed    AnalysisStatus = "failed"
)

// DetectedMineral holds information about a classified mineral.
type DetectedMineral struct {
	Name       string  `json:"name"`
	Confidence float64 `json:"confidence"`
	Grade      float64 `json:"grade,omitempty"`
	GradeUnit  string  `json:"grade_unit,omitempty"`
}

// SamplingResult is the output from the Sampling Agent.
type SamplingResult struct {
	Waypoints      []Location `json:"waypoints"`
	FieldRoute     string     `json:"field_route,omitempty"`
	GridSpacing    float64    `json:"grid_spacing,omitempty"`
	Strategy       string     `json:"strategy,omitempty"`
	Recommendations []string  `json:"recommendations,omitempty"`
}

// AnalysisResult is the output from the Analysis Agent.
type AnalysisResult struct {
	DetectedMinerals       []DetectedMineral `json:"detected_minerals"`
	DominantMineral        string            `json:"dominant_mineral"`
	OverallConfidence      float64           `json:"overall_confidence"`
	RockType               string            `json:"rock_type,omitempty"`
	Alteration             string            `json:"alteration,omitempty"`
	RequiresGeologyContext bool              `json:"requires_geology_context"`
	RoutingDecision        string            `json:"routing_decision,omitempty"`
	EstimatedGrade         float64           `json:"estimated_grade,omitempty"`
	GradeUnit              string            `json:"grade_unit,omitempty"`
}

// GeologyResult is the output from the Geology Agent.
type GeologyResult struct {
	BeltName        string   `json:"belt_name,omitempty"`
	Formation       string   `json:"formation,omitempty"`
	DepositModel    string   `json:"deposit_model,omitempty"`
	ResourcePotential string `json:"resource_potential,omitempty"`
	Pathfinders     []string `json:"pathfinders,omitempty"`
	StructuralContext string `json:"structural_context,omitempty"`
	Recommendations []string `json:"recommendations,omitempty"`
}

// MarketResult is the output from the Market Agent.
type MarketResult struct {
	CommodityPrices       map[string]float64 `json:"commodity_prices"`
	DepositValueEstimateUSD float64           `json:"deposit_value_estimate_usd"`
	CutOffGrade           float64            `json:"cut_off_grade,omitempty"`
	PriceTrend            string             `json:"price_trend,omitempty"`
	RoyaltyEstimate       float64            `json:"royalty_estimate,omitempty"`
	Currency              string             `json:"currency"`
	PriceTimestamp        time.Time          `json:"price_timestamp"`
}

// ReportResult is the output from the Report Agent.
type ReportResult struct {
	Title           string   `json:"title"`
	ExecutiveSummary string  `json:"executive_summary"`
	Sections        []string `json:"sections,omitempty"`
	PDFURL          string   `json:"pdf_url,omitempty"`
	HTMLContent     string   `json:"html_content,omitempty"`
	GeneratedAt     time.Time `json:"generated_at"`
}

// ComplianceResult is the output from the Compliance Agent.
type ComplianceResult struct {
	IsCompliant      bool     `json:"is_compliant"`
	LicenseType      string   `json:"license_type,omitempty"`
	EIAStatus        string   `json:"eia_status,omitempty"`
	ComplianceIssues []string `json:"compliance_issues,omitempty"`
	RoyaltyRate      float64  `json:"royalty_rate,omitempty"`
	RequiresHumanReview bool  `json:"requires_human_review"`
}

// AgentOutputs aggregates results from all 6 agents.
type AgentOutputs struct {
	Sampling   *SamplingResult   `json:"sampling,omitempty"`
	Analysis   *AnalysisResult   `json:"analysis,omitempty"`
	Geology    *GeologyResult    `json:"geology,omitempty"`
	Market     *MarketResult     `json:"market,omitempty"`
	Report     *ReportResult     `json:"report,omitempty"`
	Compliance *ComplianceResult `json:"compliance,omitempty"`
}

// Analysis represents a complete analysis pipeline run.
type Analysis struct {
	ID                 uuid.UUID     `json:"id"`
	UserID             uuid.UUID     `json:"user_id"`
	SampleIDs          []uuid.UUID   `json:"sample_ids"`
	Status             AnalysisStatus `json:"status"`
	AgentOutputs       AgentOutputs  `json:"agent_outputs"`
	DetectedMinerals   []string      `json:"detected_minerals,omitempty"`
	EstimatedGrade     float64       `json:"estimated_grade,omitempty"`
	ConfidenceScore    float64       `json:"confidence_score,omitempty"`
	EstimatedValueUSD  float64       `json:"estimated_value_usd,omitempty"`
	PipelineDurationMs int64         `json:"pipeline_duration_ms,omitempty"`
	CreatedAt          time.Time     `json:"created_at"`
	UpdatedAt          time.Time     `json:"updated_at"`
}

// CreateAnalysisRequest triggers a new analysis pipeline.
type CreateAnalysisRequest struct {
	SampleIDs []uuid.UUID `json:"sample_ids" validate:"required,min=1"`
}

// AnalysisListResponse is a paginated list of analyses.
type AnalysisListResponse struct {
	Analyses []Analysis `json:"analyses"`
	Total    int        `json:"total"`
	Page     int        `json:"page"`
	PageSize int        `json:"page_size"`
}

// AnalysisStreamEvent is an SSE event during pipeline execution.
type AnalysisStreamEvent struct {
	ID     string      `json:"id"`
	Status string      `json:"status"`
	Node   string      `json:"node,omitempty"`
	Output interface{} `json:"output,omitempty"`
	Error  string      `json:"error,omitempty"`
}
