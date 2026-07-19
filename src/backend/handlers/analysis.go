package handlers

import (
	"encoding/json"
	"fmt"
	"net/http"
	"strconv"
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
}

// NewAnalysisHandler creates a new analysis handler.
func NewAnalysisHandler(a2aClient *a2a.Client, logger *zap.Logger) *AnalysisHandler {
	return &AnalysisHandler{
		a2aClient: a2aClient,
		logger:    logger,
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

	// Store the pending analysis in Supabase.
	// In production: supabaseClient.From("analyses").Insert(analysis).Execute()

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
	// For now, use placeholder input.
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

	result, err := h.a2aClient.Invoke(nil, "afrimine-pipeline", input, userID)
	duration := time.Since(startTime)

	if err != nil {
		h.logger.Error("pipeline failed",
			zap.String("analysis_id", analysisID.String()),
			zap.Duration("duration", duration),
			zap.Error(err),
		)
		// Update analysis status to failed in Supabase.
		return
	}

	h.logger.Info("pipeline completed",
		zap.String("analysis_id", analysisID.String()),
		zap.String("task_id", result.TaskID),
		zap.String("state", result.State),
		zap.Duration("duration", duration),
		zap.Int64("duration_ms", duration.Milliseconds()),
	)

	// In production: update the analysis record in Supabase with full results.
	// Parse result.AgentOutputs into models.AgentOutputs and store.
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

	// In production: query Supabase with RLS.
	// Investors see only completed analyses with summaries.
	// Field workers see their own analyses.
	// Geologists see analyses in their region.
	// Admins see all.

	// Placeholder response.
	analysis := models.Analysis{
		ID:     uuid.MustParse(analysisID),
		UserID: uuid.MustParse(userID),
		Status: models.StatusCompleted,
		AgentOutputs: models.AgentOutputs{
			Analysis: &models.AnalysisResult{
				DominantMineral:   "gold",
				OverallConfidence: 0.85,
				RockType:          "quartz vein",
				Alteration:        "sericitization",
			},
		},
		DetectedMinerals:  []string{"gold", "arsenopyrite", "pyrite"},
		EstimatedGrade:    5.2,
		ConfidenceScore:   0.85,
		EstimatedValueUSD: 125000,
		CreatedAt:         time.Now().UTC(),
		UpdatedAt:         time.Now().UTC(),
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

	// In production: subscribe to Supabase Realtime channel for this analysis.
	// Or use the A2A streaming endpoint.
	// For now, send a progress event and complete.

	// Send initial status.
	sendSSE(w, flusher, models.AnalysisStreamEvent{
		ID:     analysisID,
		Status: "working",
		Node:   "sampling",
		Output: map[string]string{"agent": "Sampling Agent", "status": "started"},
	})

	// Simulate agent progress (in production, this comes from the A2A stream).
	agents := []string{"analysis", "geology", "market", "report", "compliance"}
	for _, agent := range agents {
		select {
		case <-r.Context().Done():
			return
		default:
		}

		sendSSE(w, flusher, models.AnalysisStreamEvent{
			ID:     analysisID,
			Status: "working",
			Node:   agent,
			Output: map[string]string{"agent": agent, "status": "completed"},
		})
	}

	// Final event.
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
