package handlers

import (
	"context"
	"encoding/json"
	"log/slog"
	"net/http"
	"strconv"
	"time"

	"github.com/ovalentine964/afrimine-ai/backend/internal/ai"
	"github.com/ovalentine964/afrimine-ai/backend/internal/api/middleware"
	"github.com/ovalentine964/afrimine-ai/backend/internal/auth"
	"github.com/ovalentine964/afrimine-ai/backend/internal/database"
	"github.com/ovalentine964/afrimine-ai/backend/internal/models"
	"github.com/ovalentine964/afrimine-ai/backend/internal/storage"
)

// Handler holds all handler dependencies
type Handler struct {
	db         *database.DB
	jwtService *auth.JWTService
	gemini     *ai.GeminiClient
	storage    *storage.SupabaseStorage
	logger     *slog.Logger
}

// NewHandler creates a new handler
func NewHandler(db *database.DB, jwtService *auth.JWTService, gemini *ai.GeminiClient, store *storage.SupabaseStorage, logger *slog.Logger) *Handler {
	return &Handler{
		db:         db,
		jwtService: jwtService,
		gemini:     gemini,
		storage:    store,
		logger:     logger,
	}
}

func sendJSON(w http.ResponseWriter, status int, data interface{}) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(status)
	json.NewEncoder(w).Encode(data)
}

func sendError(w http.ResponseWriter, status int, message string) {
	sendJSON(w, status, models.APIResponse{Success: false, Error: message})
}

func sendSuccess(w http.ResponseWriter, data interface{}) {
	sendJSON(w, http.StatusOK, models.APIResponse{Success: true, Data: data})
}

// --- Auth Handlers ---

// SendOTP handles POST /v1/auth/phone
func (h *Handler) SendOTP(w http.ResponseWriter, r *http.Request) {
	var req struct {
		Phone string `json:"phone"`
	}
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		sendError(w, http.StatusBadRequest, "invalid request body")
		return
	}
	if req.Phone == "" {
		sendError(w, http.StatusBadRequest, "phone number is required")
		return
	}

	code, err := auth.GenerateOTP()
	if err != nil {
		h.logger.Error("failed to generate OTP", "error", err)
		sendError(w, http.StatusInternalServerError, "failed to generate OTP")
		return
	}

	expiresAt := time.Now().Add(10 * time.Minute)
	_, err = h.db.CreateOTP(r.Context(), req.Phone, code, expiresAt)
	if err != nil {
		h.logger.Error("failed to create OTP", "error", err)
		sendError(w, http.StatusInternalServerError, "failed to create OTP")
		return
	}

	h.logger.Info("OTP generated", "phone", req.Phone)
	sendSuccess(w, map[string]interface{}{
		"message":    "OTP sent successfully",
		"expires_in": 600,
	})
}

// VerifyOTP handles POST /v1/auth/verify
func (h *Handler) VerifyOTP(w http.ResponseWriter, r *http.Request) {
	var req struct {
		Phone string `json:"phone"`
		Code  string `json:"code"`
		Name  string `json:"name"`
	}
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		sendError(w, http.StatusBadRequest, "invalid request body")
		return
	}
	if req.Phone == "" || req.Code == "" {
		sendError(w, http.StatusBadRequest, "phone and code are required")
		return
	}

	otp, err := h.db.GetValidOTP(r.Context(), req.Phone, req.Code)
	if err != nil {
		h.logger.Error("failed to verify OTP", "error", err)
		sendError(w, http.StatusInternalServerError, "verification failed")
		return
	}
	if otp == nil {
		sendError(w, http.StatusUnauthorized, "invalid or expired OTP")
		return
	}

	h.db.MarkOTPUsed(r.Context(), otp.ID)

	user, err := h.db.CreateUser(r.Context(), req.Phone, req.Name)
	if err != nil {
		h.logger.Error("failed to create user", "error", err)
		sendError(w, http.StatusInternalServerError, "failed to create user")
		return
	}

	accessToken, err := h.jwtService.GenerateAccessToken(user.ID, user.Phone)
	if err != nil {
		sendError(w, http.StatusInternalServerError, "failed to generate token")
		return
	}

	refreshToken, err := h.jwtService.GenerateRefreshToken(user.ID, user.Phone)
	if err != nil {
		sendError(w, http.StatusInternalServerError, "failed to generate token")
		return
	}

	sendSuccess(w, models.AuthResponse{
		Token:        accessToken,
		RefreshToken: refreshToken,
		ExpiresIn:    3600,
		User:         *user,
	})
}

// RefreshToken handles POST /v1/auth/refresh
func (h *Handler) RefreshToken(w http.ResponseWriter, r *http.Request) {
	var req struct {
		RefreshToken string `json:"refresh_token"`
	}
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		sendError(w, http.StatusBadRequest, "invalid request body")
		return
	}
	if req.RefreshToken == "" {
		sendError(w, http.StatusBadRequest, "refresh token is required")
		return
	}

	claims, err := h.jwtService.ValidateRefreshToken(req.RefreshToken)
	if err != nil {
		sendError(w, http.StatusUnauthorized, "invalid refresh token")
		return
	}

	user, err := h.db.GetUserByID(r.Context(), claims.UserID)
	if err != nil || user == nil {
		sendError(w, http.StatusUnauthorized, "user not found")
		return
	}

	accessToken, _ := h.jwtService.GenerateAccessToken(user.ID, user.Phone)
	refreshToken, _ := h.jwtService.GenerateRefreshToken(user.ID, user.Phone)

	sendSuccess(w, models.AuthResponse{
		Token:        accessToken,
		RefreshToken: refreshToken,
		ExpiresIn:    3600,
		User:         *user,
	})
}

// --- Sample Handlers ---

// ListSamples handles GET /v1/samples
func (h *Handler) ListSamples(w http.ResponseWriter, r *http.Request) {
	userID := middleware.GetUserID(r.Context())

	page, _ := strconv.Atoi(r.URL.Query().Get("page"))
	if page < 1 {
		page = 1
	}
	perPage, _ := strconv.Atoi(r.URL.Query().Get("per_page"))
	if perPage < 1 {
		perPage = 20
	}
	if perPage > 100 {
		perPage = 100
	}

	samples, total, err := h.db.ListSamples(r.Context(), userID, page, perPage)
	if err != nil {
		h.logger.Error("failed to list samples", "error", err)
		sendError(w, http.StatusInternalServerError, "failed to list samples")
		return
	}
	if samples == nil {
		samples = []models.Sample{}
	}

	sendSuccess(w, models.PaginatedResponse{
		Items:      samples,
		Total:      total,
		Page:       page,
		PerPage:    perPage,
		TotalPages: (total + perPage - 1) / perPage,
	})
}

// CreateSample handles POST /v1/samples
func (h *Handler) CreateSample(w http.ResponseWriter, r *http.Request) {
	userID := middleware.GetUserID(r.Context())

	if err := r.ParseMultipartForm(32 << 20); err != nil {
		sendError(w, http.StatusBadRequest, "invalid form data")
		return
	}

	name := r.FormValue("name")
	if name == "" {
		sendError(w, http.StatusBadRequest, "name is required")
		return
	}

	latitude, _ := strconv.ParseFloat(r.FormValue("latitude"), 64)
	longitude, _ := strconv.ParseFloat(r.FormValue("longitude"), 64)

	sample := &models.Sample{
		UserID:      userID,
		Name:        name,
		Description: r.FormValue("description"),
		Latitude:    latitude,
		Longitude:   longitude,
	}

	file, header, err := r.FormFile("photo")
	if err == nil {
		defer file.Close()
		if result, err := h.storage.UploadFile(r.Context(), file, header, userID); err == nil {
			sample.PhotoURL = result.URL
		} else {
			h.logger.Error("failed to upload photo", "error", err)
		}
	}

	created, err := h.db.CreateSample(r.Context(), sample)
	if err != nil {
		h.logger.Error("failed to create sample", "error", err)
		sendError(w, http.StatusInternalServerError, "failed to create sample")
		return
	}

	sendJSON(w, http.StatusCreated, models.APIResponse{Success: true, Data: created})
}

// GetSample handles GET /v1/samples/:id
func (h *Handler) GetSample(w http.ResponseWriter, r *http.Request) {
	userID := middleware.GetUserID(r.Context())
	sampleID := r.PathValue("id")

	sample, err := h.db.GetSampleByID(r.Context(), sampleID, userID)
	if err != nil {
		sendError(w, http.StatusInternalServerError, "failed to get sample")
		return
	}
	if sample == nil {
		sendError(w, http.StatusNotFound, "sample not found")
		return
	}

	analyses, _ := h.db.GetAnalysesBySampleID(r.Context(), sampleID, userID)
	sendSuccess(w, map[string]interface{}{"sample": sample, "analyses": analyses})
}

// UpdateSample handles PUT /v1/samples/:id
func (h *Handler) UpdateSample(w http.ResponseWriter, r *http.Request) {
	userID := middleware.GetUserID(r.Context())
	sampleID := r.PathValue("id")

	var req struct {
		Name        string  `json:"name"`
		Description string  `json:"description"`
		Latitude    float64 `json:"latitude"`
		Longitude   float64 `json:"longitude"`
		PhotoURL    string  `json:"photo_url"`
	}
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		sendError(w, http.StatusBadRequest, "invalid request body")
		return
	}

	sample := &models.Sample{
		ID: sampleID, UserID: userID,
		Name: req.Name, Description: req.Description,
		Latitude: req.Latitude, Longitude: req.Longitude, PhotoURL: req.PhotoURL,
	}

	updated, err := h.db.UpdateSample(r.Context(), sample)
	if err != nil {
		sendError(w, http.StatusInternalServerError, "failed to update sample")
		return
	}
	if updated == nil {
		sendError(w, http.StatusNotFound, "sample not found")
		return
	}

	sendSuccess(w, updated)
}

// DeleteSample handles DELETE /v1/samples/:id
func (h *Handler) DeleteSample(w http.ResponseWriter, r *http.Request) {
	userID := middleware.GetUserID(r.Context())
	sampleID := r.PathValue("id")

	if err := h.db.DeleteSample(r.Context(), sampleID, userID); err != nil {
		if err.Error() == "sample not found" {
			sendError(w, http.StatusNotFound, "sample not found")
			return
		}
		sendError(w, http.StatusInternalServerError, "failed to delete sample")
		return
	}

	sendSuccess(w, map[string]string{"message": "sample deleted"})
}

// --- Analysis Handlers ---

// AnalyzeSample handles POST /v1/analyze
func (h *Handler) AnalyzeSample(w http.ResponseWriter, r *http.Request) {
	userID := middleware.GetUserID(r.Context())

	var req struct {
		SampleID string `json:"sample_id"`
		ImageURL string `json:"image_url,omitempty"`
	}
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		sendError(w, http.StatusBadRequest, "invalid request body")
		return
	}
	if req.SampleID == "" {
		sendError(w, http.StatusBadRequest, "sample_id is required")
		return
	}

	sample, err := h.db.GetSampleByID(r.Context(), req.SampleID, userID)
	if err != nil {
		sendError(w, http.StatusInternalServerError, "failed to get sample")
		return
	}
	if sample == nil {
		sendError(w, http.StatusNotFound, "sample not found")
		return
	}

	analysis := &models.Analysis{SampleID: sample.ID, UserID: userID, Status: "processing"}
	created, err := h.db.CreateAnalysis(r.Context(), analysis)
	if err != nil {
		sendError(w, http.StatusInternalServerError, "failed to create analysis")
		return
	}

	sample.Status = "analyzing"
	h.db.UpdateSample(r.Context(), sample)

	go func() {
		ctx := context.Background()
		photoURL := sample.PhotoURL
		if req.ImageURL != "" {
			photoURL = req.ImageURL
		}

		if photoURL == "" {
			created.Status = "failed"
			created.Description = "No image available for analysis"
			h.db.UpdateAnalysis(ctx, created)
			sample.Status = "failed"
			h.db.UpdateSample(ctx, sample)
			return
		}

		result, err := h.gemini.AnalyzeImage(ctx, photoURL, "image/jpeg")
		if err != nil {
			h.logger.Error("analysis failed", "error", err, "sample_id", sample.ID)
			created.Status = "failed"
			created.Description = "Analysis failed: " + err.Error()
			h.db.UpdateAnalysis(ctx, created)
			sample.Status = "failed"
			h.db.UpdateSample(ctx, sample)
			return
		}

		created.MineralType = result.MineralType
		created.Confidence = result.Confidence
		created.Description = result.Description
		created.EstimatedValue = result.EstimatedValue
		created.Currency = "USD"
		created.Status = "completed"
		h.db.UpdateAnalysis(ctx, created)

		sample.Status = "analyzed"
		h.db.UpdateSample(ctx, sample)
	}()

	sendJSON(w, http.StatusAccepted, models.APIResponse{Success: true, Data: created})
}

// GetAnalysis handles GET /v1/analysis/:id
func (h *Handler) GetAnalysis(w http.ResponseWriter, r *http.Request) {
	userID := middleware.GetUserID(r.Context())
	analysisID := r.PathValue("id")

	analysis, err := h.db.GetAnalysisByID(r.Context(), analysisID, userID)
	if err != nil {
		sendError(w, http.StatusInternalServerError, "failed to get analysis")
		return
	}
	if analysis == nil {
		sendError(w, http.StatusNotFound, "analysis not found")
		return
	}

	sendSuccess(w, analysis)
}

// BatchAnalyze handles POST /v1/analyze/batch
func (h *Handler) BatchAnalyze(w http.ResponseWriter, r *http.Request) {
	userID := middleware.GetUserID(r.Context())

	var req struct {
		SampleIDs []string `json:"sample_ids"`
	}
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		sendError(w, http.StatusBadRequest, "invalid request body")
		return
	}
	if len(req.SampleIDs) == 0 {
		sendError(w, http.StatusBadRequest, "sample_ids is required")
		return
	}
	if len(req.SampleIDs) > 10 {
		sendError(w, http.StatusBadRequest, "maximum 10 samples per batch")
		return
	}

	type batchResult struct {
		SampleID string `json:"sample_id"`
		Status   string `json:"status"`
		Error    string `json:"error,omitempty"`
	}

	results := make([]batchResult, 0, len(req.SampleIDs))

	for _, sampleID := range req.SampleIDs {
		sample, err := h.db.GetSampleByID(r.Context(), sampleID, userID)
		if err != nil || sample == nil {
			results = append(results, batchResult{SampleID: sampleID, Status: "error", Error: "sample not found"})
			continue
		}

		analysis := &models.Analysis{SampleID: sample.ID, UserID: userID, Status: "processing"}
		created, err := h.db.CreateAnalysis(r.Context(), analysis)
		if err != nil {
			results = append(results, batchResult{SampleID: sampleID, Status: "error", Error: "failed to create analysis"})
			continue
		}

		sample.Status = "analyzing"
		h.db.UpdateSample(r.Context(), sample)

		go func(s *models.Sample, a *models.Analysis) {
			ctx := context.Background()
			if s.PhotoURL == "" {
				a.Status = "failed"
				a.Description = "No image available"
				h.db.UpdateAnalysis(ctx, a)
				s.Status = "failed"
				h.db.UpdateSample(ctx, s)
				return
			}

			result, err := h.gemini.AnalyzeImage(ctx, s.PhotoURL, "image/jpeg")
			if err != nil {
				a.Status = "failed"
				a.Description = "Analysis failed: " + err.Error()
				h.db.UpdateAnalysis(ctx, a)
				s.Status = "failed"
				h.db.UpdateSample(ctx, s)
				return
			}

			a.MineralType = result.MineralType
			a.Confidence = result.Confidence
			a.Description = result.Description
			a.EstimatedValue = result.EstimatedValue
			a.Currency = "USD"
			a.Status = "completed"
			h.db.UpdateAnalysis(ctx, a)

			s.Status = "analyzed"
			h.db.UpdateSample(ctx, s)
		}(sample, created)

		results = append(results, batchResult{SampleID: sampleID, Status: "processing"})
	}

	sendJSON(w, http.StatusAccepted, models.APIResponse{Success: true, Data: results})
}
