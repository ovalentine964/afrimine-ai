package models

import "time"

// User represents a registered user (phone-based auth)
type User struct {
	ID        string    `json:"id" db:"id"`
	Phone     string    `json:"phone" db:"phone"`
	Name      string    `json:"name" db:"name"`
	CreatedAt time.Time `json:"created_at" db:"created_at"`
	UpdatedAt time.Time `json:"updated_at" db:"updated_at"`
}

// OTP represents a one-time password for phone verification
type OTP struct {
	ID        string    `json:"id" db:"id"`
	Phone     string    `json:"phone" db:"phone"`
	Code      string    `json:"code" db:"code"`
	ExpiresAt time.Time `json:"expires_at" db:"expires_at"`
	Used      bool      `json:"used" db:"used"`
	CreatedAt time.Time `json:"created_at" db:"created_at"`
}

// Sample represents a mineral sample submitted by a user
type Sample struct {
	ID          string    `json:"id" db:"id"`
	UserID      string    `json:"user_id" db:"user_id"`
	Name        string    `json:"name" db:"name"`
	Description string    `json:"description" db:"description"`
	Latitude    float64   `json:"latitude" db:"latitude"`
	Longitude   float64   `json:"longitude" db:"longitude"`
	PhotoURL    string    `json:"photo_url" db:"photo_url"`
	Status      string    `json:"status" db:"status"` // pending, analyzed, failed
	CreatedAt   time.Time `json:"created_at" db:"created_at"`
	UpdatedAt   time.Time `json:"updated_at" db:"updated_at"`
}

// Analysis represents an AI analysis result for a sample
type Analysis struct {
	ID             string    `json:"id" db:"id"`
	SampleID       string    `json:"sample_id" db:"sample_id"`
	UserID         string    `json:"user_id" db:"user_id"`
	MineralType    string    `json:"mineral_type" db:"mineral_type"`
	Confidence     float64   `json:"confidence" db:"confidence"`
	Description    string    `json:"description" db:"description"`
	EstimatedValue float64   `json:"estimated_value" db:"estimated_value"`
	Currency       string    `json:"currency" db:"currency"`
	RawResponse    string    `json:"raw_response" db:"raw_response"`
	Status         string    `json:"status" db:"status"` // processing, completed, failed
	CreatedAt      time.Time `json:"created_at" db:"created_at"`
}

// Report represents an investor report
type Report struct {
	ID        string    `json:"id" db:"id"`
	UserID    string    `json:"user_id" db:"user_id"`
	Title     string    `json:"title" db:"title"`
	Summary   string    `json:"summary" db:"summary"`
	PDFPath   string    `json:"pdf_path" db:"pdf_path"`
	Status    string    `json:"status" db:"status"` // generating, ready, failed
	CreatedAt time.Time `json:"created_at" db:"created_at"`
}

// MarketPrice represents current mineral price
type MarketPrice struct {
	Mineral   string    `json:"mineral"`
	Price     float64   `json:"price"`
	Currency  string    `json:"currency"`
	Unit      string    `json:"unit"`
	Change    float64   `json:"change"` // percentage change
	Timestamp time.Time `json:"timestamp"`
}

// PriceHistory represents historical price data
type PriceHistory struct {
	Mineral string          `json:"mineral"`
	Data    []PricePoint    `json:"data"`
}

type PricePoint struct {
	Date  string  `json:"date"`
	Price float64 `json:"price"`
}

// SyncPayload represents offline data sync
type SyncPayload struct {
	Samples  []Sample `json:"samples"`
	LastSync string   `json:"last_sync"`
}

// SyncChanges represents changes since last sync
type SyncChanges struct {
	Samples    []Sample   `json:"samples"`
	Analyses   []Analysis `json:"analyses"`
	ServerTime time.Time  `json:"server_time"`
}

// API Response wrappers
type APIResponse struct {
	Success bool        `json:"success"`
	Data    interface{} `json:"data,omitempty"`
	Error   string      `json:"error,omitempty"`
}

type AuthResponse struct {
	Token        string `json:"token"`
	RefreshToken string `json:"refresh_token"`
	ExpiresIn    int    `json:"expires_in"`
	User         User   `json:"user"`
}

type PaginatedResponse struct {
	Items      interface{} `json:"items"`
	Total      int         `json:"total"`
	Page       int         `json:"page"`
	PerPage    int         `json:"per_page"`
	TotalPages int         `json:"total_pages"`
}
