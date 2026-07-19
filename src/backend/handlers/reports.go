package handlers

import (
	"encoding/json"
	"fmt"
	"net/http"
	"strconv"
	"time"

	"github.com/go-chi/chi/v5"
	"github.com/google/uuid"
	"github.com/ovalentine964/afrimine-ai/backend/middleware"
	"github.com/ovalentine964/afrimine-ai/backend/models"
	"go.uber.org/zap"
)

// ReportHandler handles report generation and download.
type ReportHandler struct {
	supabaseURL string
	supabaseKey string
	logger      *zap.Logger
}

// NewReportHandler creates a new report handler.
func NewReportHandler(supabaseURL, supabaseKey string, logger *zap.Logger) *ReportHandler {
	return &ReportHandler{
		supabaseURL: supabaseURL,
		supabaseKey: supabaseKey,
		logger:      logger,
	}
}

// Routes registers report routes on the given router.
func (h *ReportHandler) Routes(r chi.Router) {
	r.Post("/generate", h.GenerateReport)
	r.Get("/", h.ListReports)
	r.Get("/{reportID}", h.GetReport)
	r.Get("/{reportID}/download", h.DownloadReport)
}

// GenerateReport handles POST /v1/reports/generate — triggers report generation via the Report Agent.
func (h *ReportHandler) GenerateReport(w http.ResponseWriter, r *http.Request) {
	userID := middleware.GetUserID(r)
	role := middleware.GetUserRole(r)
	if userID == "" {
		writeError(w, http.StatusUnauthorized, "not authenticated")
		return
	}

	// Only geologists, admins, and field workers can generate reports.
	// Investors can only view existing reports.
	if role == string(models.RoleInvestor) {
		writeError(w, http.StatusForbidden, "investors cannot generate reports")
		return
	}

	var req models.GenerateReportRequest
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		writeError(w, http.StatusBadRequest, "invalid request body")
		return
	}

	if req.AnalysisID == uuid.Nil {
		writeError(w, http.StatusBadRequest, "analysis_id is required")
		return
	}

	// Validate report type.
	validTypes := map[models.ReportType]bool{
		models.ReportTypeInvestor:   true,
		models.ReportTypeTechnical:  true,
		models.ReportTypeRegulatory: true,
		models.ReportTypeCompliance: true,
	}
	if !validTypes[req.Type] {
		writeError(w, http.StatusBadRequest, "invalid report type: must be investor, technical, regulatory, or compliance")
		return
	}

	reportID := uuid.New()
	now := time.Now().UTC()

	h.logger.Info("report generation triggered",
		zap.String("report_id", reportID.String()),
		zap.String("analysis_id", req.AnalysisID.String()),
		zap.String("type", string(req.Type)),
		zap.String("user_id", userID),
	)

	report := models.Report{
		ID:         reportID,
		AnalysisID: req.AnalysisID,
		UserID:     uuid.MustParse(userID),
		Type:       req.Type,
		Title:      req.Title,
		CreatedAt:  now,
	}

	// In production:
	// 1. Fetch analysis results from Supabase
	// 2. Call A2A bridge with tasks/send targeting the report agent
	// 3. Store generated PDF in Supabase Storage
	// 4. Update report record with PDF URL

	if report.Title == "" {
		report.Title = fmt.Sprintf("%s Report — %s", req.Type, now.Format("2006-01-02"))
	}

	writeJSON(w, http.StatusAccepted, report)
}

// GetReport handles GET /v1/reports/{reportID}.
func (h *ReportHandler) GetReport(w http.ResponseWriter, r *http.Request) {
	reportID := chi.URLParam(r, "reportID")
	if _, err := uuid.Parse(reportID); err != nil {
		writeError(w, http.StatusBadRequest, "invalid report ID")
		return
	}

	userID := middleware.GetUserID(r)
	role := middleware.GetUserRole(r)

	h.logger.Info("report retrieved",
		zap.String("report_id", reportID),
		zap.String("user_id", userID),
		zap.String("role", role),
	)

	// In production: query Supabase with RLS.
	// Investors can view reports for analyses they have access to.
	// Field workers can view reports for their own analyses.

	report := models.Report{
		ID:     uuid.MustParse(reportID),
		UserID: uuid.MustParse(userID),
		Type:   models.ReportTypeInvestor,
		Title:  "Mineral Analysis Report — Nyatike Site A",
		Summary: "Gold-bearing quartz vein with 5.2 g/t average grade. " +
			"Estimated deposit value: $125,000. Kenya Mining Act compliant.",
		CreatedAt: time.Now().UTC(),
	}

	writeJSON(w, http.StatusOK, report)
}

// ListReports handles GET /v1/reports — paginated list.
func (h *ReportHandler) ListReports(w http.ResponseWriter, r *http.Request) {
	userID := middleware.GetUserID(r)
	role := middleware.GetUserRole(r)

	page, _ := strconv.Atoi(r.URL.Query().Get("page"))
	if page < 1 {
		page = 1
	}
	pageSize, _ := strconv.Atoi(r.URL.Query().Get("page_size"))
	if pageSize < 1 || pageSize > 100 {
		pageSize = 20
	}

	reportType := r.URL.Query().Get("type")

	h.logger.Info("reports listed",
		zap.String("user_id", userID),
		zap.String("role", role),
		zap.Int("page", page),
		zap.String("type", reportType),
	)

	// In production: query Supabase with RLS.
	writeJSON(w, http.StatusOK, models.ReportListResponse{
		Reports:  []models.Report{},
		Total:    0,
		Page:     page,
		PageSize: pageSize,
	})
}

// DownloadReport handles GET /v1/reports/{reportID}/download — returns the PDF file.
func (h *ReportHandler) DownloadReport(w http.ResponseWriter, r *http.Request) {
	reportID := chi.URLParam(r, "reportID")
	if _, err := uuid.Parse(reportID); err != nil {
		writeError(w, http.StatusBadRequest, "invalid report ID")
		return
	}

	userID := middleware.GetUserID(r)

	h.logger.Info("report download",
		zap.String("report_id", reportID),
		zap.String("user_id", userID),
	)

	// In production:
	// 1. Look up report in Supabase to get PDF URL
	// 2. Fetch PDF from Supabase Storage
	// 3. Stream it back with appropriate headers

	// For now, return a placeholder indicating where the PDF would be.
	w.Header().Set("Content-Type", "application/pdf")
	w.Header().Set("Content-Disposition", fmt.Sprintf(`attachment; filename="report-%s.pdf"`, reportID))
	w.Header().Set("X-Report-ID", reportID)

	// Placeholder: in production, stream the actual PDF bytes.
	w.WriteHeader(http.StatusOK)
	fmt.Fprintf(w, "PDF content for report %s would be streamed here", reportID)
}
