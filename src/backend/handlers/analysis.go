package handlers

import (
	"context"
	"encoding/json"
	"fmt"
	"net/http"
	"strconv"
	"sync"
	"time"

	"github.com/go-chi/chi/v5"
	"github.com/google/uuid"
	"github.com/ovalentine964/afrimine-ai/backend/a2a"
	"github.com/ovalentine964/afrimine-ai/backend/middleware"
	"github.com/ovalentine964/afrimine-ai/backend/models"
	"go.uber.org/zap"
)

// AnalysisHandler handles analysis pipeline operations.
type AnalysisHandler struct {
	a2aClient *a2a.Client
	logger    *zap.Logger

	// In-memory results cache (replace with Supabase in production)
	results   map[string]*models.Analysis
	resultsMu sync.RWMutex
}

// NewAnalysisHandler creates a new analysis handler.
func NewAnalysisHandler(a2aClient *a2a.Client, logger *zap.Logger) *AnalysisHandler {
	return &AnalysisHandler{
		a2aClient: a2aClient,
		logger:    logger,
		results:   make(map[string]*models.Analysis),
	}
}

// Routes registers analysis routes on the given router.
func (h *AnalysisHandler) Routes(r chi.Router) {
	r.Post("/", h.CreateAnalysis)
	r.Get("/", h.ListAnalyses)
	r.Get("/{analysisID}", h.GetAnalysis)
	r.Get("/{analysisID}/stream", h.StreamAnalysis)
	r.Post("/{analysisID}/cancel", h.CancelAnalysis)
}

// CreateAnalysis handles POST /v1/analyses — triggers the full 6-agent pipeline.
func (h *AnalysisHandler) CreateAnalysis(w http.ResponseWriter, r *http.Request) {
	userID := middleware.GetUserID(r)
	if userID == "" {
		writeError(w, http.StatusUnauthorized, "not authenticated")
		return
	}

	var req models.CreateAnalysisRequest
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		writeError(w, http.StatusBadRequest, "invalid request body")
		return
	}

	if len(req.SampleIDs) == 0 {
		writeError(w, http.StatusBadRequest, "at least one sample_id is required")
		return
	}

	analysisID := uuid.New()
	now := time.Now().UTC()

	h.logger.Info("analysis triggered",
		zap.String("analysis_id", analysisID.String()),
		zap.String("user_id", userID),
		zap.Int("sample_count", len(req.SampleIDs)),
	)

	// In production: look up samples from Supabase to get location + data.
	// For now, build the A2A input from request.
	// The A2A client will send this to the LangGraph bridge which runs the full pipeline:
	// Sampling → Analysis → Geology/Market (parallel) → Report → Compliance.

	analysis := models.Analysis{
		ID:        analysisID,
		UserID:    uuid.MustParse(userID),
		SampleIDs: req.SampleIDs,
		Status:    models.StatusPending,
		CreatedAt: now,
		UpdatedAt: now,
	}

	// Store the pending analysis in cache (and Supabase in production).
	h.resultsMu.Lock()
	h.results[analysisID.String()] = &analysis
	h.resultsMu.Unlock()

	go func() {
		// Run the pipeline asynchronously.
		h.runPipeline(analysisID, userID, req.SampleIDs)
	}()

	// Return 202 Accepted — client should poll or use SSE for updates.
	w.Header().Set("Location", fmt.Sprintf("/v1/analyses/%s", analysisID))
	writeJSON(w, http.StatusAccepted, analysis)
}

// runPipeline executes the A2A pipeline in the background.
func (h *AnalysisHandler) runPipeline(analysisID uuid.UUID, userID string, sampleIDs []uuid.UUID) {
	// In production: fetch sample data from Supabase.
	input := map[string]interface{}{
		"location": map[string]interface{}{
			"lat":    -1.05,
			"lon":    34.55,
			"region": "Nyatike",
			"county": "Migori",
		},
		"sample_data": map[string]interface{}{
			"sample_id": sampleIDs[0].String(),
		},
		"user_id": userID,
	}

	startTime := time.Now()

	// Update status to running.
	h.resultsMu.Lock()
	if a, ok := h.results[analysisID.String()]; ok {
		a.Status = models.StatusRunning
		a.UpdatedAt = time.Now().UTC()
	}
	h.resultsMu.Unlock()

	result, err := h.a2aClient.Invoke(context.Background(), "afrimine-pipeline", input, userID)
	duration := time.Since(startTime)

	if err != nil {
		h.logger.Error("pipeline failed",
			zap.String("analysis_id", analysisID.String()),
			zap.Duration("duration", duration),
			zap.Error(err),
		)
		// Update status to failed.
		h.resultsMu.Lock()
		if a, ok := h.results[analysisID.String()]; ok {
			a.Status = models.StatusFailed
			a.UpdatedAt = time.Now().UTC()
		}
		h.resultsMu.Unlock()
		return
	}

	h.logger.Info("pipeline completed",
		zap.String("analysis_id", analysisID.String()),
		zap.String("task_id", result.TaskID),
		zap.String("state", result.State),
		zap.Duration("duration", duration),
		zap.Int64("duration_ms", duration.Milliseconds()),
	)

	// Store pipeline results in cache.
	h.resultsMu.Lock()
	if a, ok := h.results[analysisID.String()]; ok {
		a.Status = models.StatusCompleted
		a.UpdatedAt = time.Now().UTC()
		a.PipelineDurationMs = int(duration.Milliseconds())

		// Parse agent outputs if available.
		if result.AgentOutputs != nil {
			if analysisOut, ok := result.AgentOutputs["analysis_result"].(map[string]interface{}); ok {
				a.AgentOutputs.Analysis = &models.AnalysisResult{
					DominantMineral:   fmt.Sprintf("%v", analysisOut["dominant_mineral"]),
					OverallConfidence: parseFloat(analysisOut["overall_confidence"]),
				}
			}
			if marketOut, ok := result.AgentOutputs["market_result"].(map[string]interface{}); ok {
				a.EstimatedValueUSD = parseInt(marketOut["deposit_value_estimate_usd"])
			}
			if complianceOut, ok := result.AgentOutputs["compliance_result"].(map[string]interface{}); ok {
				compliant, _ := complianceOut["is_compliant"].(bool)
				a.AgentOutputs.Compliance = &models.ComplianceResult{
					IsCompliant: compliant,
				}
			}
		}
	}
	h.resultsMu.Unlock()
}

// parseFloat safely extracts a float64 from an interface{} value.
func parseFloat(v interface{}) float64 {
	switch n := v.(type) {
	case float64:
		return n
	case int:
		return float64(n)
	case int64:
		return float64(n)
	default:
		return 0.0
	}
}

// parseInt safely extracts an int from an interface{} value.
func parseInt(v interface{}) int {
	switch n := v.(type) {
	case float64:
		return int(n)
	case int:
		return n
	case int64:
		return int(n)
	default:
		return 0
	}
}

// GetAnalysis handles GET /v1/analyses/{analysisID}.
func (h *AnalysisHandler) GetAnalysis(w http.ResponseWriter, r *http.Request) {
	analysisID := chi.URLParam(r, "analysisID")
	if _, err := uuid.Parse(analysisID); err != nil {
		writeError(w, http.StatusBadRequest, "invalid analysis ID")
		return
	}

	userID := middleware.GetUserID(r)
	role := middleware.GetUserRole(r)

	h.logger.Info("analysis retrieved",
		zap.String("analysis_id", analysisID),
		zap.String("user_id", userID),
		zap.String("role", role),
	)

	// Look up from results cache (in production: query Supabase with RLS).
	h.resultsMu.RLock()
	analysis, ok := h.results[analysisID]
	h.resultsMu.RUnlock()

	if !ok {
		writeError(w, http.StatusNotFound, "analysis not found")
		return
	}

	writeJSON(w, http.StatusOK, analysis)
}

// ListAnalyses handles GET /v1/analyses — paginated list.
func (h *AnalysisHandler) ListAnalyses(w http.ResponseWriter, r *http.Request) {
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

	status := r.URL.Query().Get("status")

	h.logger.Info("analyses listed",
		zap.String("user_id", userID),
		zap.String("role", role),
		zap.Int("page", page),
		zap.String("status", status),
	)

	// In production: query Supabase with RLS and filters.
	writeJSON(w, http.StatusOK, models.AnalysisListResponse{
		Analyses: []models.Analysis{},
		Total:    0,
		Page:     page,
		PageSize: pageSize,
	})
}

// StreamAnalysis handles GET /v1/analyses/{analysisID}/stream — SSE for real-time progress.
func (h *AnalysisHandler) StreamAnalysis(w http.ResponseWriter, r *http.Request) {
	analysisID := chi.URLParam(r, "analysisID")
	if _, err := uuid.Parse(analysisID); err != nil {
		writeError(w, http.StatusBadRequest, "invalid analysis ID")
		return
	}

	userID := middleware.GetUserID(r)

	h.logger.Info("analysis stream started",
		zap.String("analysis_id", analysisID),
		zap.String("user_id", userID),
	)

	// Set SSE headers.
	w.Header().Set("Content-Type", "text/event-stream")
	w.Header().Set("Cache-Control", "no-cache")
	w.Header().Set("Connection", "keep-alive")
	w.Header().Set("X-Accel-Buffering", "no")

	flusher, ok := w.(http.Flusher)
	if !ok {
		writeError(w, http.StatusInternalServerError, "streaming not supported")
		return
	}

	// Send initial status.
	sendSSE(w, flusher, models.AnalysisStreamEvent{
		ID:     analysisID,
		Status: "working",
		Node:   "sampling",
		Output: map[string]string{"agent": "Sampling Agent", "status": "started"},
	})

	// Build A2A input for real streaming.
	input := map[string]interface{}{
		"location": map[string]interface{}{
			"lat":    -1.05,
			"lon":    34.55,
			"region": "Nyatike",
			"county": "Migori",
		},
		"sample_data": map[string]interface{}{
			"sample_id": analysisID,
		},
	}

	// Stream real events from the A2A bridge.
	_, err := h.a2aClient.InvokeStream(r.Context(), "afrimine-pipeline", input, userID, func(event a2a.StreamEvent) {
		select {
		case <-r.Context().Done():
			return
		default:
		}

		h.logger.Debug("SSE forwarding event",
			zap.String("analysis_id", analysisID),
			zap.String("node", event.Node),
			zap.String("status", event.Status),
		)

		eventStatus := "working"
		if event.Status == "completed" || event.Status == "failed" {
			eventStatus = event.Status
		}

		outputMap := make(map[string]string)
		for k, v := range event.Output {
			if s, ok := v.(string); ok {
				outputMap[k] = s
			} else {
				b, _ := json.Marshal(v)
				outputMap[k] = string(b)
			}
		}

		sendSSE(w, flusher, models.AnalysisStreamEvent{
			ID:     analysisID,
			Status: eventStatus,
			Node:   event.Node,
			Output: outputMap,
		})
	})

	if err != nil {
		h.logger.Error("SSE stream error",
			zap.String("analysis_id", analysisID),
			zap.Error(err),
		)
		sendSSE(w, flusher, models.AnalysisStreamEvent{
			ID:      analysisID,
			Status:  "failed",
			Output:  map[string]string{"error": err.Error()},
		})
		return
	}

	// Final completion event.
	sendSSE(w, flusher, models.AnalysisStreamEvent{
		ID:     analysisID,
		Status: "completed",
	})
}

// CancelAnalysis handles POST /v1/analyses/{analysisID}/cancel.
func (h *AnalysisHandler) CancelAnalysis(w http.ResponseWriter, r *http.Request) {
	analysisID := chi.URLParam(r, "analysisID")
	if _, err := uuid.Parse(analysisID); err != nil {
		writeError(w, http.StatusBadRequest, "invalid analysis ID")
		return
	}

	userID := middleware.GetUserID(r)

	h.logger.Info("analysis cancelled",
		zap.String("analysis_id", analysisID),
		zap.String("user_id", userID),
	)

	// In production: update status in Supabase, potentially interrupt LangGraph pipeline.
	writeJSON(w, http.StatusOK, map[string]string{
		"message":     "analysis cancelled",
		"analysis_id": analysisID,
	})
}

// sendSSE writes a Server-Sent Event to the response.
func sendSSE(w http.ResponseWriter, flusher http.Flusher, event models.AnalysisStreamEvent) {
	data, _ := json.Marshal(event)
	fmt.Fprintf(w, "data: %s\n\n", data)
	flusher.Flush()
}
