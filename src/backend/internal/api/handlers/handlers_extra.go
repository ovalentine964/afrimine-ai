package handlers

import (
	"context"
	"encoding/json"
	"fmt"
	"net/http"
	"os"
	"path/filepath"
	"strconv"
	"strings"
	"time"

	"github.com/ovalentine964/afrimine-ai/backend/internal/api/middleware"
	"github.com/ovalentine964/afrimine-ai/backend/internal/models"
	"github.com/ovalentine964/afrimine-ai/backend/internal/report"
)

// GenerateReport handles POST /v1/reports/generate
func (h *Handler) GenerateReport(w http.ResponseWriter, r *http.Request) {
	userID := middleware.GetUserID(r.Context())

	user, err := h.db.GetUserByID(r.Context(), userID)
	if err != nil || user == nil {
		sendError(w, http.StatusUnauthorized, "user not found")
		return
	}

	samples, _, err := h.db.ListSamples(r.Context(), userID, 1, 1000)
	if err != nil {
		h.logger.Error("failed to get samples", "error", err)
		sendError(w, http.StatusInternalServerError, "failed to get samples")
		return
	}

	if len(samples) == 0 {
		sendError(w, http.StatusBadRequest, "no samples found to generate report")
		return
	}

	var allAnalyses []models.Analysis
	for _, s := range samples {
		analyses, _ := h.db.GetAnalysesBySampleID(r.Context(), s.ID, userID)
		allAnalyses = append(allAnalyses, analyses...)
	}

	reportRecord := &models.Report{
		UserID:  userID,
		Title:   "Mineral Analysis Report - " + time.Now().Format("Jan 2, 2006"),
		Status:  "generating",
		Summary: "",
	}

	created, err := h.db.CreateReport(r.Context(), reportRecord)
	if err != nil {
		h.logger.Error("failed to create report", "error", err)
		sendError(w, http.StatusInternalServerError, "failed to create report")
		return
	}

	go func() {
		ctx := context.Background()
		gen := report.NewGenerator(h.gemini, "./reports")

		pdfPath, err := gen.GenerateReport(ctx, user, samples, allAnalyses)
		if err != nil {
			h.logger.Error("failed to generate report PDF", "error", err)
			created.Status = "failed"
			created.Summary = "Report generation failed: " + err.Error()
			h.db.UpdateReport(ctx, created)
			return
		}

		created.PDFPath = pdfPath
		created.Status = "ready"
		created.Summary = fmt.Sprintf("Report generated with %d samples and %d analyses", len(samples), len(allAnalyses))
		h.db.UpdateReport(ctx, created)
	}()

	sendJSON(w, http.StatusAccepted, models.APIResponse{
		Success: true,
		Data:    created,
	})
}

// GetReport handles GET /v1/reports/:id
func (h *Handler) GetReport(w http.ResponseWriter, r *http.Request) {
	userID := middleware.GetUserID(r.Context())
	reportID := r.PathValue("id")

	rep, err := h.db.GetReportByID(r.Context(), reportID, userID)
	if err != nil {
		h.logger.Error("failed to get report", "error", err)
		sendError(w, http.StatusInternalServerError, "failed to get report")
		return
	}

	if rep == nil {
		sendError(w, http.StatusNotFound, "report not found")
		return
	}

	sendSuccess(w, rep)
}

// DownloadReportPDF handles GET /v1/reports/:id/pdf
func (h *Handler) DownloadReportPDF(w http.ResponseWriter, r *http.Request) {
	userID := middleware.GetUserID(r.Context())
	reportID := r.PathValue("id")

	rep, err := h.db.GetReportByID(r.Context(), reportID, userID)
	if err != nil {
		sendError(w, http.StatusInternalServerError, "failed to get report")
		return
	}

	if rep == nil {
		sendError(w, http.StatusNotFound, "report not found")
		return
	}

	if rep.Status != "ready" || rep.PDFPath == "" {
		sendError(w, http.StatusBadRequest, "report PDF not ready yet")
		return
	}

	// Path traversal protection: resolve to absolute and verify it's within the reports directory
	absPath, err := filepath.Abs(rep.PDFPath)
	if err != nil {
		sendError(w, http.StatusBadRequest, "invalid file path")
		return
	}
	absReportsDir, _ := filepath.Abs("./reports")
	if !strings.HasPrefix(absPath, absReportsDir+string(os.PathSeparator)) && absPath != absReportsDir {
		h.logger.Warn("path traversal attempt blocked", "path", rep.PDFPath, "user_id", userID)
		sendError(w, http.StatusForbidden, "access denied")
		return
	}

	if _, err := os.Stat(absPath); os.IsNotExist(err) {
		sendError(w, http.StatusNotFound, "PDF file not found")
		return
	}

	w.Header().Set("Content-Type", "application/pdf")
	w.Header().Set("Content-Disposition", "attachment; filename="+rep.Title+".pdf")
	http.ServeFile(w, r, absPath)
}

// GetMarketPrices handles GET /v1/market/prices
func (h *Handler) GetMarketPrices(w http.ResponseWriter, r *http.Request) {
	prices := []models.MarketPrice{
		{Mineral: "gold", Price: 2350.00, Currency: "USD", Unit: "oz", Change: 1.2, Timestamp: time.Now()},
		{Mineral: "copper", Price: 8800.00, Currency: "USD", Unit: "ton", Change: -0.5, Timestamp: time.Now()},
		{Mineral: "titanium", Price: 4700.00, Currency: "USD", Unit: "ton", Change: 0.8, Timestamp: time.Now()},
		{Mineral: "soda_ash", Price: 220.00, Currency: "USD", Unit: "ton", Change: 0.3, Timestamp: time.Now()},
		{Mineral: "fluorspar", Price: 340.00, Currency: "USD", Unit: "ton", Change: -0.2, Timestamp: time.Now()},
	}
	sendSuccess(w, prices)
}

// GetMarketHistory handles GET /v1/market/history
func (h *Handler) GetMarketHistory(w http.ResponseWriter, r *http.Request) {
	mineral := r.URL.Query().Get("mineral")
	if mineral == "" {
		mineral = "gold"
	}

	days := 30
	if d, err := strconv.Atoi(r.URL.Query().Get("days")); err == nil && d > 0 && d <= 365 {
		days = d
	}

	basePrice := 2350.0
	switch mineral {
	case "copper":
		basePrice = 8800.0
	case "titanium":
		basePrice = 4700.0
	case "soda_ash":
		basePrice = 220.0
	case "fluorspar":
		basePrice = 340.0
	}

	history := &models.PriceHistory{
		Mineral: mineral,
		Data:    make([]models.PricePoint, days),
	}

	now := time.Now()
	for i := 0; i < days; i++ {
		date := now.AddDate(0, 0, -(days - 1 - i))
		variation := (float64(i%7) - 3) / 100
		history.Data[i] = models.PricePoint{
			Date:  date.Format("2006-01-02"),
			Price: basePrice * (1 + variation),
		}
	}

	sendSuccess(w, history)
}

// SyncUpload handles POST /v1/sync
func (h *Handler) SyncUpload(w http.ResponseWriter, r *http.Request) {
	userID := middleware.GetUserID(r.Context())

	var payload models.SyncPayload
	if err := json.NewDecoder(r.Body).Decode(&payload); err != nil {
		sendError(w, http.StatusBadRequest, "invalid request body")
		return
	}

	created, failed := 0, 0
	for _, sample := range payload.Samples {
		sample.UserID = userID
		sample.Status = "pending"
		if _, err := h.db.CreateSample(r.Context(), &sample); err != nil {
			h.logger.Error("failed to sync sample", "error", err, "name", sample.Name)
			failed++
			continue
		}
		created++
	}

	sendSuccess(w, map[string]interface{}{
		"created": created,
		"failed":  failed,
		"total":   len(payload.Samples),
	})
}

// SyncChanges handles GET /v1/sync/changes
func (h *Handler) SyncChanges(w http.ResponseWriter, r *http.Request) {
	userID := middleware.GetUserID(r.Context())

	sinceStr := r.URL.Query().Get("since")
	var since time.Time

	if sinceStr != "" {
		var err error
		since, err = time.Parse(time.RFC3339, sinceStr)
		if err != nil {
			sendError(w, http.StatusBadRequest, "invalid 'since' parameter, use RFC3339 format")
			return
		}
	} else {
		since = time.Now().Add(-24 * time.Hour)
	}

	samples, err := h.db.GetSamplesSince(r.Context(), userID, since)
	if err != nil {
		h.logger.Error("failed to get samples since", "error", err)
		sendError(w, http.StatusInternalServerError, "failed to get changes")
		return
	}

	analyses, err := h.db.GetAnalysesSince(r.Context(), userID, since)
	if err != nil {
		h.logger.Error("failed to get analyses since", "error", err)
		sendError(w, http.StatusInternalServerError, "failed to get changes")
		return
	}

	if samples == nil {
		samples = []models.Sample{}
	}
	if analyses == nil {
		analyses = []models.Analysis{}
	}

	sendSuccess(w, models.SyncChanges{
		Samples:    samples,
		Analyses:   analyses,
		ServerTime: time.Now(),
	})
}

// HealthCheck handles GET /v1/health
func (h *Handler) HealthCheck(w http.ResponseWriter, r *http.Request) {
	dbStatus := "ok"
	if err := h.db.Ping(r.Context()); err != nil {
		dbStatus = "degraded"
	}

	sendSuccess(w, map[string]interface{}{
		"status":    "healthy",
		"version":   "1.0.0",
		"database":  dbStatus,
		"timestamp": time.Now().UTC().Format(time.RFC3339),
	})
}
