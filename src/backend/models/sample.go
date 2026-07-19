package models

import (
	"time"

	"github.com/google/uuid"
)

// Role represents a user role in the system.
type Role string

const (
	RoleFieldWorker Role = "field_worker"
	RoleGeologist   Role = "geologist"
	RoleInvestor    Role = "investor"
	RoleAdmin       Role = "admin"
)

// Location represents GPS coordinates with metadata.
type Location struct {
	Lat       float64 `json:"lat"`
	Lon       float64 `json:"lon"`
	Elevation float64 `json:"elevation,omitempty"`
	Accuracy  float64 `json:"accuracy,omitempty"`
	Region    string  `json:"region,omitempty"`
	County    string  `json:"county,omitempty"`
	Country   string  `json:"country,omitempty"`
}

// XRFReadings holds X-ray fluorescence element readings in ppm.
type XRFReadings map[string]float64

// MineralSample represents a mineral sample collected in the field.
type MineralSample struct {
	ID          uuid.UUID   `json:"id"`
	UserID      uuid.UUID   `json:"user_id"`
	Location    Location    `json:"location"`
	PhotoURLs   []string    `json:"photo_urls"`
	XRFReadings XRFReadings `json:"xrf_readings,omitempty"`
	FieldNotes  string      `json:"field_notes,omitempty"`
	VoiceNoteURL string    `json:"voice_note_url,omitempty"`
	Synced      bool        `json:"synced"`
	CreatedAt   time.Time   `json:"created_at"`
	UpdatedAt   time.Time   `json:"updated_at"`
}

// CreateSampleRequest is the payload for creating a new mineral sample.
type CreateSampleRequest struct {
	Location    Location    `json:"location" validate:"required"`
	XRFReadings XRFReadings `json:"xrf_readings,omitempty"`
	FieldNotes  string      `json:"field_notes,omitempty"`
}

// UpdateSampleRequest is the payload for updating an existing sample.
type UpdateSampleRequest struct {
	Location    *Location    `json:"location,omitempty"`
	XRFReadings *XRFReadings `json:"xrf_readings,omitempty"`
	FieldNotes  *string      `json:"field_notes,omitempty"`
	Synced      *bool        `json:"synced,omitempty"`
}

// SampleListResponse is a paginated list of samples.
type SampleListResponse struct {
	Samples  []MineralSample `json:"samples"`
	Total    int             `json:"total"`
	Page     int             `json:"page"`
	PageSize int             `json:"page_size"`
}
