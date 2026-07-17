package handlers

import (
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

// sendJSON sends a JSON response
func sendJSON(w http.ResponseWriter, status int, data interface{}) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(status)
	json.NewEncoder(w).Encode(data)
}

// sendError sends an error response
func sendError(w http.ResponseWriter, status int, message string) {
	sendJSON(w, status, models.APIResponse{
		Success: false,
		Error:   message,
	})
}

// sendSuccess sends a success response
func sendSuccess(w http.ResponseWriter, data interface{}) {
	sendJSON(w, http.StatusOK, models.APIResponse{
		Success: true,
		Data:    data,
	})
}

// Auth handlers

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

	// Generate OTP
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

	// In production, send SMS via Twilio/Africa's Talking
	// For development, return the code in the response
	h.logger.Info("OTP generated", "phone", req.Phone, "code", code)

	sendSuccess(w, map[string]interface{}{
		"message":    "OTP sent successfully",
		"expires_in": 600,
		// Remove this in production:
		"debug_code": code,
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

	// Verify OTP
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

	// Mark OTP as used
	if err := h.db.MarkOTPUsed(r.Context(), otp.ID); err != nil {
		h.logger.Error("failed to mark OTP used", "error", err)
	}

	// Create or get user
	user, err := h.db.CreateUser(r.Context(), req.Phone, req.Name)
	if err != nil {
		h.logger.Error("failed to create user", "error", err)
		sendError(w, http.StatusInternalServerError, "failed to create user")
		return
	}

	// Generate tokens
	accessToken, err := h.jwtService.GenerateAccessToken(user.ID, user.Phone)
	if err != nil {
		h.logger.Error("failed to generate access token", "error", err)
		sendError(w, http.StatusInternalServerError, "failed to generate token")
		return
	}

	refreshToken, err := h.jwtService.GenerateRefreshToken(user.ID, user.Phone)
	if err != nil {
		h.logger.Error("failed to generate refresh token", "error", err)
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

	// Validate refresh token
	claims, err := h.jwtService.ValidateToken(req.RefreshToken)
	if err != nil {
		sendError(w, http.StatusUnauthorized, "invalid refresh token")
		return
	}

	// Verify user exists
	user, err := h.db.GetUserByID(r.Context(), claims.UserID)
	if err != nil || user == nil {
		sendError(w, http.StatusUnauthorized, "user not found")
		return
	}

	// Generate new tokens
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

// Sample handlers

// ListSamples handles GET /v1/samples
func (h *Handler) ListSamples(w http.ResponseWriter, r *http.Request) {
	userID := middleware.GetUserID(r.Context())

	page, _ := strconv.Atoi(r.URL.Query().Get("page"))
	if page < 1 {
		page = 1
	}

	perPage, _ := strconv.Atoi(r.URL.Query().Get("per_page"))
	if perPage < 1 || perPage > 100 {
		perPage = 20
	}

	samples, total, err := h.db.ListSamples(r.Context(), userID, page, perPage)
	if err != nil {
		h.logger.Error("failed to list samples", "error", err, "user_id", userID)
		sendError(w, http.StatusInternalServerError, "failed to list samples")
		return
	}

	if samples == nil {
		samples = []models.Sample{}
	}

	totalPages := (total + perPage - 1) / perPage

	sendSuccess(w, models.PaginatedResponse{
		Items:      samples,
		Total:      total,
		Page:       page,
		PerPage:    perPage,
		TotalPages: totalPages,
	})
}

// CreateSample handles POST /v1/samples
func (h *Handler) CreateSample(w http.ResponseWriter, r *http.Request) {
	userID := middleware.GetUserID(r.Context())

	// Parse multipart form
	if err := r.ParseMultipartForm(32 << 20); err != nil { // 32MB max
		sendError(w, http.StatusBadRequest, "invalid form data")
		return
	}

	name := r.FormValue("name")
	description := r.FormValue("description")
	latStr := r.FormValue("latitude")
	lonStr := r.FormValue("longitude")

	if name == "" {
		sendError(w, http.StatusBadRequest, "name is required")
		return
	}

	latitude, _ := strconv.ParseFloat(latStr, 64)
	longitude, _ := strconv.ParseFloat(lonStr, 64)

	sample := &models.Sample{
		UserID:      userID,
		Name:        name,
		Description: description,
		Latitude:    latitude,
		Longitude:   longitude,
	}

	// Handle photo upload
	file, header, err := r.FormFile("photo")
	if err == nil {
		defer file.Close()
		result, err := h.storage.UploadFile(r.Context(), file, header, userID)
		if err != nil {
			h.logger.Error("failed to upload photo", "error", err)
			// Continue without photo
		} else {
			sample.PhotoURL = result.URL
		}
	}

	created, err := h.db.CreateSample(r.Context(), sample)
	if err != nil {
		h.logger.Error("failed to create sample", "error", err)
		sendError(w, http.StatusInternalServerError, "failed to create sample")
		return
	}

	sendJSON(w, http.StatusCreated, models.APIResponse{
		Success: true,
		Data:    created,
	})
}

// GetSample handles GET /v1/samples/:id
func (h *Handler) GetSample(w http.ResponseWriter, r *http.Request) {
	userID := middleware.GetUserID(r.Context())
	sampleID := r.PathValue("id")

	sample, err := h.db.GetSampleByID(r.Context(), sampleID, userID)
	if err != nil {
		h.logger.Error("failed to get sample", "error", err)
		sendError(w, http.StatusInternalServerError, "failed to get sample")
		return
	}

	if sample == nil {
		sendError(w, http.StatusNotFound, "sample not found")
		return
	}

	// Also get analyses for this sample
	analyses, _ := h.db.GetAnalysesBySampleID(r.Context(), sampleID, userID)

	sendSuccess(w, map[string]interface{}{
		"sample":    sample,
		"analyses":  analyses,
	})
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
		ID:          sampleID,
		UserID:      userID,
		Name:        req.Name,
		Description: req.Description,
		Latitude:    req.Latitude,
		Longitude:   req.Longitude,
		PhotoURL:    req.PhotoURL,
	}

	updated, err := h.db.UpdateSample(r.Context(), sample)
	if err != nil {
		h.logger.Error("failed to update sample", "error", err)
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
		h.logger.Error("failed to delete sample", "error", err)
		sendError(w, http.StatusInternalServerError, "failed to delete sample")
		return
	}

	sendSuccess(w, map[string]string{"message": "sample deleted"})
}

// Analysis handlers

// AnalyzeSample handles POST /v1/analyze
func (h *Handler) AnalyzeSample(w http.ResponseWriter, r *http.Request) {
	userID := middleware.GetUserID(r.Context())

	var req struct {
		SampleID string `json:"sample_id"`
		ImageURL string `json:"image_url,omitempty"` // Optional: analyze by URL
	}

	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		sendError(w, http.StatusBadRequest, "invalid request body")
		return
	}

	if req.SampleID == "" {
		sendError(w, http.StatusBadRequest, "sample_id is required")
		return
	}

	// Get the sample
	sample, err := h.db.GetSampleByID(r.Context(), req.SampleID, userID)
	if err != nil {
		h.logger.Error("failed to get sample", "error", err)
		sendError(w, http.StatusInternalServerError, "failed to get sample")
		return
	}
	if sample == nil {
		sendError(w, http.StatusNotFound, "sample not found")
		return
	}

	// Create analysis record
	analysis := &models.Analysis{
		SampleID: sample.ID,
		UserID:   userID,
		Status:   "processing",
	}

	created, err := h.db.CreateAnalysis(r.Context(), analysis)
	if err != nil {
		h.logger.Error("failed to create analysis", "error", err)
		sendError(w, http.StatusInternalServerError, "failed to create analysis")
		return
	}

	// Update sample status
	sample.Status = "analyzing"
	h.db.UpdateSample(r.Context(), sample)

	// Run analysis asynchronously
	go func() {
		ctx := r.Context()
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

		// For URL-based images, we'd need to download and convert to base64
		// This is a simplified version - in production, handle URL fetching
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

	sendJSON(w, http.StatusAccepted, models.APIResponse{
		Success: true,
		Data:    created,
	})
}

// GetAnalysis handles GET /v1/analysis/:id
func (h *Handler) GetAnalysis(w http.ResponseWriter, r *http.Request) {
	userID := middleware.GetUserID(r.Context())
	analysisID := r.PathValue("id")

	analysis, err := h.db.GetAnalysisByID(r.Context(), analysisID, userID)
	if err != nil {
		h.logger.Error("failed to get analysis", "error", err)
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
			results = append(results, batchResult{
				SampleID: sampleID,
				Status:   "error",
				Error:    "sample not found",
			})
			continue
		}

		// Create analysis record
		analysis := &models.Analysis{
			SampleID: sample.ID,
			UserID:   userID,
			Status:   "processing",
		}

		created, err := h.db.CreateAnalysis(r.Context(), analysis)
		if err != nil {
			results = append(results, batchResult{
				SampleID: sampleID,
				Status:   "error",
				Error:    "failed to create analysis",
			})
			continue
		}

		sample.Status = "analyzing"
		h.db.UpdateSample(r.Context(), sample)

		// Run analysis asynchronously
		go func(s *models.Sample, a *models.Analysis) {
			ctx := r.Context()
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

		results = append(results, batchResult{
			SampleID: sampleID,
			Status:   "processing",
		})
	}

	sendJSON(w, http.StatusAccepted, models.APIResponse{
		Success: true,
		Data:    results,
	})
}
