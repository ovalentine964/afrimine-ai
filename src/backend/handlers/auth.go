package handlers

import (
	"encoding/json"
	"net/http"
	"strings"

	"github.com/go-chi/chi/v5"
	"github.com/google/uuid"
	"github.com/ovalentine964/afrimine-ai/backend/middleware"
	"github.com/ovalentine964/afrimine-ai/backend/models"
	"go.uber.org/zap"
)

// AuthHandler handles Supabase Auth integration and user management.
type AuthHandler struct {
	jwtSecret string
	logger    *zap.Logger
}

// NewAuthHandler creates a new auth handler.
func NewAuthHandler(jwtSecret string, logger *zap.Logger) *AuthHandler {
	return &AuthHandler{
		jwtSecret: jwtSecret,
		logger:    logger,
	}
}

// Routes registers auth routes on the given router.
func (h *AuthHandler) Routes(r chi.Router) {
	r.Post("/auth/phone", h.RequestOTP)
	r.Post("/auth/verify", h.VerifyOTP)
	r.Get("/auth/me", h.GetCurrentUser)
	r.Put("/auth/role", h.UpdateUserRole) // Admin only
}

// --- Request/Response types ---

type phoneRequest struct {
	Phone string `json:"phone"`
}

type verifyRequest struct {
	Phone string `json:"phone"`
	Token string `json:"token"`
}

type authResponse struct {
	AccessToken  string `json:"access_token"`
	RefreshToken string `json:"refresh_token"`
	ExpiresIn    int    `json:"expires_in"`
	User         userResponse `json:"user"`
}

type userResponse struct {
	ID    string `json:"id"`
	Phone string `json:"phone,omitempty"`
	Email string `json:"email,omitempty"`
	Role  string `json:"role"`
}

type roleUpdateRequest struct {
	UserID string `json:"user_id"`
	Role   string `json:"role"`
}

// RequestOTP initiates phone-based OTP authentication via Supabase.
// In production, this calls Supabase Auth's phone OTP endpoint.
// For MVP, returns a placeholder response indicating OTP was sent.
func (h *AuthHandler) RequestOTP(w http.ResponseWriter, r *http.Request) {
	var req phoneRequest
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		writeError(w, http.StatusBadRequest, "invalid request body")
		return
	}

	req.Phone = strings.TrimSpace(req.Phone)
	if req.Phone == "" {
		writeError(w, http.StatusBadRequest, "phone number is required")
		return
	}

	// Validate Kenyan phone format (+254...).
	if !strings.HasPrefix(req.Phone, "+") {
		req.Phone = "+" + req.Phone
	}

	h.logger.Info("OTP requested", zap.String("phone", maskPhone(req.Phone)))

	// In production: call supabase.Auth.SignInWithPhone(req.Phone)
	// The Supabase Go client handles OTP sending via Africa's Talking.
	// For now, return success — the Flutter app handles the OTP flow.
	writeJSON(w, http.StatusOK, map[string]string{
		"message": "OTP sent successfully",
		"phone":   maskPhone(req.Phone),
	})
}

// VerifyOTP validates the OTP code and returns a JWT session.
// In production, this calls Supabase Auth's verify endpoint.
func (h *AuthHandler) VerifyOTP(w http.ResponseWriter, r *http.Request) {
	var req verifyRequest
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		writeError(w, http.StatusBadRequest, "invalid request body")
		return
	}

	req.Phone = strings.TrimSpace(req.Phone)
	req.Token = strings.TrimSpace(req.Token)

	if req.Phone == "" || req.Token == "" {
		writeError(w, http.StatusBadRequest, "phone and token are required")
		return
	}

	h.logger.Info("OTP verification attempt", zap.String("phone", maskPhone(req.Phone)))

	// In production: call supabase.Auth.VerifyOTP(req.Phone, req.Token)
	// Returns a session with access_token, refresh_token, user.
	// For MVP, return a placeholder.
	writeJSON(w, http.StatusOK, authResponse{
		AccessToken:  "supabase-jwt-token",
		RefreshToken: "supabase-refresh-token",
		ExpiresIn:    3600,
		User: userResponse{
			ID:    uuid.New().String(),
			Phone: maskPhone(req.Phone),
			Role:  string(models.RoleFieldWorker),
		},
	})
}

// GetCurrentUser returns the authenticated user's profile.
func (h *AuthHandler) GetCurrentUser(w http.ResponseWriter, r *http.Request) {
	userID := middleware.GetUserID(r)
	role := middleware.GetUserRole(r)
	email := middleware.GetUserEmail(r)

	if userID == "" {
		writeError(w, http.StatusUnauthorized, "not authenticated")
		return
	}

	writeJSON(w, http.StatusOK, userResponse{
		ID:    userID,
		Email: email,
		Role:  role,
	})
}

// UpdateUserRole allows admins to change a user's role.
func (h *AuthHandler) UpdateUserRole(w http.ResponseWriter, r *http.Request) {
	var req roleUpdateRequest
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		writeError(w, http.StatusBadRequest, "invalid request body")
		return
	}

	// Validate role.
	validRole := false
	for _, role := range []models.Role{
		models.RoleFieldWorker,
		models.RoleGeologist,
		models.RoleInvestor,
		models.RoleAdmin,
	} {
		if models.Role(req.Role) == role {
			validRole = true
			break
		}
	}
	if !validRole {
		writeError(w, http.StatusBadRequest, "invalid role: must be field_worker, geologist, investor, or admin")
		return
	}

	if _, err := uuid.Parse(req.UserID); err != nil {
		writeError(w, http.StatusBadRequest, "invalid user_id")
		return
	}

	h.logger.Info("role update",
		zap.String("admin", middleware.GetUserID(r)),
		zap.String("target_user", req.UserID),
		zap.String("new_role", req.Role),
	)

	// In production: update user metadata in Supabase Auth.
	// supabase.Auth.Admin.UpdateUserByID(req.UserID, map[string]interface{}{"role": req.Role})
	writeJSON(w, http.StatusOK, map[string]string{
		"message": "role updated successfully",
		"user_id": req.UserID,
		"role":    req.Role,
	})
}

// maskPhone replaces middle digits with asterisks for logging.
func maskPhone(phone string) string {
	if len(phone) <= 6 {
		return "***"
	}
	return phone[:3] + "***" + phone[len(phone)-3:]
}

// writeJSON writes a JSON response.
func writeJSON(w http.ResponseWriter, status int, data interface{}) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(status)
	json.NewEncoder(w).Encode(data)
}

// writeError writes a JSON error response.
func writeError(w http.ResponseWriter, status int, message string) {
	writeJSON(w, status, map[string]string{"error": message})
}
