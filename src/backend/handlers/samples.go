package handlers

import (
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"strconv"
	"time"

	"github.com/go-chi/chi/v5"
	"github.com/google/uuid"
	"github.com/ovalentine964/afrimine-ai/backend/middleware"
	"github.com/ovalentine964/afrimine-ai/backend/models"
	"go.uber.org/zap"
)

// SampleHandler handles CRUD operations for mineral samples.
type SampleHandler struct {
	supabaseURL    string
	supabaseKey    string
	storageBaseURL string
	logger         *zap.Logger
}

// NewSampleHandler creates a new sample handler.
func NewSampleHandler(supabaseURL, supabaseKey string, logger *zap.Logger) *SampleHandler {
	return &SampleHandler{
		supabaseURL:    supabaseURL,
		supabaseKey:    supabaseKey,
		storageBaseURL: supabaseURL + "/storage/v1/object",
		logger:         logger,
	}
}

// Routes registers sample routes on the given router.
func (h *SampleHandler) Routes(r chi.Router) {
	r.Get("/", h.ListSamples)
	r.Post("/", h.CreateSample)
	r.Get("/{sampleID}", h.GetSample)
	r.Put("/{sampleID}", h.UpdateSample)
	r.Delete("/{sampleID}", h.DeleteSample)
	r.Post("/{sampleID}/photo", h.UploadPhoto)
}

// CreateSample handles POST /v1/samples — creates a new mineral sample.
func (h *SampleHandler) CreateSample(w http.ResponseWriter, r *http.Request) {
	userID := middleware.GetUserID(r)
	if userID == "" {
		writeError(w, http.StatusUnauthorized, "not authenticated")
		return
	}

	var req models.CreateSampleRequest
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		writeError(w, http.StatusBadRequest, "invalid request body")
		return
	}

	// Validate required fields.
	if req.Location.Lat == 0 && req.Location.Lon == 0 {
		writeError(w, http.StatusBadRequest, "location with lat/lon is required")
		return
	}

	sampleID := uuid.New()
	now := time.Now().UTC()

	sample := models.MineralSample{
		ID:          sampleID,
		UserID:      uuid.MustParse(userID),
		Location:    req.Location,
		PhotoURLs:   []string{},
		XRFReadings: req.XRFReadings,
		FieldNotes:  req.FieldNotes,
		Synced:      false,
		CreatedAt:   now,
		UpdatedAt:   now,
	}

	h.logger.Info("sample created",
		zap.String("sample_id", sampleID.String()),
		zap.String("user_id", userID),
		zap.Float64("lat", req.Location.Lat),
		zap.Float64("lon", req.Location.Lon),
		zap.String("region", req.Location.Region),
	)

	// In production: insert into Supabase mineral_samples table.
	// result, err := supabaseClient.From("mineral_samples").Insert(sample).Execute()
	writeJSON(w, http.StatusCreated, sample)
}

// GetSample handles GET /v1/samples/{sampleID}.
func (h *SampleHandler) GetSample(w http.ResponseWriter, r *http.Request) {
	sampleID := chi.URLParam(r, "sampleID")
	if _, err := uuid.Parse(sampleID); err != nil {
		writeError(w, http.StatusBadRequest, "invalid sample ID")
		return
	}

	userID := middleware.GetUserID(r)
	role := middleware.GetUserRole(r)

	h.logger.Info("sample retrieved",
		zap.String("sample_id", sampleID),
		zap.String("user_id", userID),
	)

	// In production: query Supabase with RLS.
	// Non-admins can only view their own samples.
	// Geologists can view all samples in their region.
	_ = role // Used for RLS policy selection in production.

	// Placeholder: return a sample structure.
	sample := models.MineralSample{
		ID:     uuid.MustParse(sampleID),
		UserID: uuid.MustParse(userID),
		Location: models.Location{
			Lat:    -1.05,
			Lon:    34.55,
			Region: "Nyatike",
			County: "Migori",
		},
		PhotoURLs: []string{},
		CreatedAt: time.Now().UTC(),
		UpdatedAt: time.Now().UTC(),
	}

	writeJSON(w, http.StatusOK, sample)
}

// ListSamples handles GET /v1/samples — paginated list.
func (h *SampleHandler) ListSamples(w http.ResponseWriter, r *http.Request) {
	userID := middleware.GetUserID(r)
	role := middleware.GetUserRole(r)

	// Parse pagination params.
	page, _ := strconv.Atoi(r.URL.Query().Get("page"))
	if page < 1 {
		page = 1
	}
	pageSize, _ := strconv.Atoi(r.URL.Query().Get("page_size"))
	if pageSize < 1 || pageSize > 100 {
		pageSize = 20
	}

	// Parse optional filters.
	region := r.URL.Query().Get("region")
	synced := r.URL.Query().Get("synced")

	h.logger.Info("samples listed",
		zap.String("user_id", userID),
		zap.String("role", role),
		zap.Int("page", page),
		zap.Int("page_size", pageSize),
		zap.String("region", region),
		zap.String("synced", synced),
	)

	// In production: query Supabase with filters and RLS.
	// Field workers see only their own samples.
	// Geologists see samples in their region.
	// Admins see all samples.
	_ = region
	_ = synced

	writeJSON(w, http.StatusOK, models.SampleListResponse{
		Samples:  []models.MineralSample{},
		Total:    0,
		Page:     page,
		PageSize: pageSize,
	})
}

// UpdateSample handles PUT /v1/samples/{sampleID}.
func (h *SampleHandler) UpdateSample(w http.ResponseWriter, r *http.Request) {
	sampleID := chi.URLParam(r, "sampleID")
	if _, err := uuid.Parse(sampleID); err != nil {
		writeError(w, http.StatusBadRequest, "invalid sample ID")
		return
	}

	userID := middleware.GetUserID(r)

	var req models.UpdateSampleRequest
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		writeError(w, http.StatusBadRequest, "invalid request body")
		return
	}

	h.logger.Info("sample updated",
		zap.String("sample_id", sampleID),
		zap.String("user_id", userID),
	)

	// In production: update in Supabase with RLS (owner only).
	// Build dynamic update from non-nil fields.
	writeJSON(w, http.StatusOK, map[string]string{
		"message":    "sample updated",
		"sample_id": sampleID,
	})
}

// DeleteSample handles DELETE /v1/samples/{sampleID}.
func (h *SampleHandler) DeleteSample(w http.ResponseWriter, r *http.Request) {
	sampleID := chi.URLParam(r, "sampleID")
	if _, err := uuid.Parse(sampleID); err != nil {
		writeError(w, http.StatusBadRequest, "invalid sample ID")
		return
	}

	userID := middleware.GetUserID(r)
	role := middleware.GetUserRole(r)

	h.logger.Info("sample deleted",
		zap.String("sample_id", sampleID),
		zap.String("user_id", userID),
		zap.String("role", role),
	)

	// In production: delete from Supabase (owner or admin only).
	// Also delete associated photos from storage.
	w.WriteHeader(http.StatusNoContent)
}

// UploadPhoto handles POST /v1/samples/{sampleID}/photo — uploads a photo to Supabase Storage.
func (h *SampleHandler) UploadPhoto(w http.ResponseWriter, r *http.Request) {
	sampleID := chi.URLParam(r, "sampleID")
	if _, err := uuid.Parse(sampleID); err != nil {
		writeError(w, http.StatusBadRequest, "invalid sample ID")
		return
	}

	userID := middleware.GetUserID(r)

	// Parse multipart form (max 10MB).
	if err := r.ParseMultipartForm(10 << 20); err != nil {
		writeError(w, http.StatusBadRequest, "file too large (max 10MB)")
		return
	}

	file, header, err := r.FormFile("photo")
	if err != nil {
		writeError(w, http.StatusBadRequest, "photo file is required")
		return
	}
	defer file.Close()

	// Validate file type.
	contentType := header.Header.Get("Content-Type")
	if contentType != "image/jpeg" && contentType != "image/png" && contentType != "image/webp" {
		writeError(w, http.StatusBadRequest, "only JPEG, PNG, and WebP images are accepted")
		return
	}

	// Read file for upload.
	fileBytes, err := io.ReadAll(file)
	if err != nil {
		writeError(w, http.StatusInternalServerError, "failed to read file")
		return
	}

	// Generate storage path: samples/{user_id}/{sample_id}/{filename}
	ext := ".jpg"
	switch contentType {
	case "image/png":
		ext = ".png"
	case "image/webp":
		ext = ".webp"
	}
	storagePath := fmt.Sprintf("samples/%s/%s/%s%s",
		userID, sampleID, uuid.New().String(), ext,
	)

	h.logger.Info("photo uploaded",
		zap.String("sample_id", sampleID),
		zap.String("storage_path", storagePath),
		zap.Int("size_bytes", len(fileBytes)),
		zap.String("content_type", contentType),
	)

	// In production: upload to Supabase Storage.
	// storageClient.UploadFile("sample-photos", storagePath, fileBytes)
	photoURL := fmt.Sprintf("%s/sample-photos/%s", h.storageBaseURL, storagePath)

	writeJSON(w, http.StatusCreated, map[string]string{
		"photo_url":    photoURL,
		"storage_path": storagePath,
		"size_bytes":   strconv.Itoa(len(fileBytes)),
	})
}
