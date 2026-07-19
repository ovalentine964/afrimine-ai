package models

import (
	"time"

	"github.com/google/uuid"
)

// ReportType represents the kind of report generated.
type ReportType string

const (
	ReportTypeInvestor    ReportType = "investor"
	ReportTypeTechnical   ReportType = "technical"
	ReportTypeRegulatory  ReportType = "regulatory"
	ReportTypeCompliance  ReportType = "compliance"
)

// Report represents a generated report document.
type Report struct {
	ID         uuid.UUID  `json:"id"`
	AnalysisID uuid.UUID  `json:"analysis_id"`
	UserID     uuid.UUID  `json:"user_id"`
	Type       ReportType `json:"type"`
	Title      string     `json:"title"`
	Summary    string     `json:"summary"`
	PDFURL     string     `json:"pdf_url,omitempty"`
	FileSize   int64      `json:"file_size,omitempty"`
	CreatedAt  time.Time  `json:"created_at"`
}

// GenerateReportRequest triggers report generation for an analysis.
type GenerateReportRequest struct {
	AnalysisID uuid.UUID  `json:"analysis_id" validate:"required"`
	Type       ReportType `json:"type" validate:"required"`
	Title      string     `json:"title,omitempty"`
}

// ReportListResponse is a paginated list of reports.
type ReportListResponse struct {
	Reports  []Report `json:"reports"`
	Total    int      `json:"total"`
	Page     int      `json:"page"`
	PageSize int      `json:"page_size"`
}
