package middleware

import (
	"context"
	"fmt"
	"net/http"
	"strings"

	"github.com/golang-jwt/jwt/v5"
	"github.com/ovalentine964/afrimine-ai/backend/models"
)

// contextKey is a private type for context keys to avoid collisions.
type contextKey string

const (
	// UserIDKey is the context key for the authenticated user ID.
	UserIDKey contextKey = "user_id"
	// UserRoleKey is the context key for the user's role.
	UserRoleKey contextKey = "user_role"
	// UserEmailKey is the context key for the user's email.
	UserEmailKey contextKey = "user_email"
)

// SupabaseClaims extends JWT claims with Supabase-specific fields.
type SupabaseClaims struct {
	jwt.RegisteredClaims
	Role  string `json:"role"`
	Email string `json:"email"`
	Sub   string `json:"sub"`
}

// AuthConfig holds configuration for the JWT middleware.
type AuthConfig struct {
	// JWTSecret is the Supabase JWT secret (from SUPABASE_JWT_SECRET env var).
	JWTSecret string
	// OptionalRoles, if non-empty, restricts access to only these roles.
	// If empty, any valid JWT is accepted.
	OptionalRoles []models.Role
}

// Auth returns a middleware that validates Supabase JWTs and injects user context.
func Auth(cfg AuthConfig) func(http.Handler) http.Handler {
	return func(next http.Handler) http.Handler {
		return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
			tokenStr := extractBearerToken(r)
			if tokenStr == "" {
				http.Error(w, `{"error":"missing or invalid Authorization header"}`, http.StatusUnauthorized)
				return
			}

			claims, err := validateToken(tokenStr, cfg.JWTSecret)
			if err != nil {
				http.Error(w, fmt.Sprintf(`{"error":"invalid token: %s"}`, err.Error()), http.StatusUnauthorized)
				return
			}

			// Check role restriction if configured.
			if len(cfg.OptionalRoles) > 0 {
				userRole := models.Role(claims.Role)
				allowed := false
				for _, r := range cfg.OptionalRoles {
					if r == userRole {
						allowed = true
						break
					}
				}
				if !allowed {
					http.Error(w, `{"error":"insufficient permissions"}`, http.StatusForbidden)
					return
				}
			}

			// Inject user info into request context.
			ctx := context.WithValue(r.Context(), UserIDKey, claims.Sub)
			ctx = context.WithValue(ctx, UserRoleKey, claims.Role)
			ctx = context.WithValue(ctx, UserEmailKey, claims.Email)
			next.ServeHTTP(w, r.WithContext(ctx))
		})
	}
}

// RequireRoles returns a middleware that restricts access to specific roles.
// This is a convenience wrapper that can be chained after Auth.
func RequireRoles(roles ...models.Role) func(http.Handler) http.Handler {
	return func(next http.Handler) http.Handler {
		return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
			role := GetUserRole(r)
			if role == "" {
				http.Error(w, `{"error":"unauthenticated"}`, http.StatusUnauthorized)
				return
			}

			allowed := false
			for _, r := range roles {
				if r == models.Role(role) {
					allowed = true
					break
				}
			}
			if !allowed {
				http.Error(w, `{"error":"insufficient permissions"}`, http.StatusForbidden)
				return
			}

			next.ServeHTTP(w, r)
		})
	}
}

// GetUserID extracts the user ID from the request context.
func GetUserID(r *http.Request) string {
	if v, ok := r.Context().Value(UserIDKey).(string); ok {
		return v
	}
	return ""
}

// GetUserRole extracts the user role from the request context.
func GetUserRole(r *http.Request) string {
	if v, ok := r.Context().Value(UserRoleKey).(string); ok {
		return v
	}
	return ""
}

// GetUserEmail extracts the user email from the request context.
func GetUserEmail(r *http.Request) string {
	if v, ok := r.Context().Value(UserEmailKey).(string); ok {
		return v
	}
	return ""
}

// extractBearerToken pulls the JWT from the Authorization header.
func extractBearerToken(r *http.Request) string {
	auth := r.Header.Get("Authorization")
	if auth == "" {
		return ""
	}
	parts := strings.SplitN(auth, " ", 2)
	if len(parts) != 2 || !strings.EqualFold(parts[0], "bearer") {
		return ""
	}
	return strings.TrimSpace(parts[1])
}

// validateToken parses and validates a Supabase JWT.
func validateToken(tokenStr, secret string) (*SupabaseClaims, error) {
	token, err := jwt.ParseWithClaims(tokenStr, &SupabaseClaims{}, func(t *jwt.Token) (interface{}, error) {
		if _, ok := t.Method.(*jwt.SigningMethodHMAC); !ok {
			return nil, fmt.Errorf("unexpected signing method: %v", t.Header["alg"])
		}
		return []byte(secret), nil
	})
	if err != nil {
		return nil, err
	}

	claims, ok := token.Claims.(*SupabaseClaims)
	if !ok || !token.Valid {
		return nil, fmt.Errorf("invalid token claims")
	}

	return claims, nil
}
