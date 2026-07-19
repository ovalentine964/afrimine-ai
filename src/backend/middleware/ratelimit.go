package middleware

import (
	"net/http"
	"sync"
	"time"

	"github.com/ovalentine964/afrimine-ai/backend/models"
	"go.uber.org/zap"
)

// RateLimitConfig defines per-role rate limits.
type RateLimitConfig struct {
	// Requests per window per role.
	FieldWorker int
	Geologist   int
	Investor    int
	Admin       int
	// Window duration (e.g., 1 minute).
	Window time.Duration
}

// DefaultRateLimitConfig returns sensible defaults per the architecture doc.
func DefaultRateLimitConfig() RateLimitConfig {
	return RateLimitConfig{
		FieldWorker: 30,  // 30 req/min — field workers upload frequently
		Geologist:   60,  // 60 req/min — geologists do more analysis
		Investor:    20,  // 20 req/min — investors mostly read
		Admin:       120, // 120 req/min — admin operations
		Window:      time.Minute,
	}
}

type rateLimitEntry struct {
	count    int
	resetAt  time.Time
}

// RateLimit returns a middleware that enforces per-role rate limits.
func RateLimit(cfg RateLimitConfig, logger *zap.Logger) func(http.Handler) http.Handler {
	var (
		mu      sync.Mutex
		entries = make(map[string]*rateLimitEntry)
	)

	// Background cleanup of expired entries.
	go func() {
		ticker := time.NewTicker(time.Minute)
		defer ticker.Stop()
		for range ticker.C {
			mu.Lock()
			now := time.Now()
			for k, v := range entries {
				if now.After(v.resetAt) {
					delete(entries, k)
				}
			}
			mu.Unlock()
		}
	}()

	getLimit := func(role string) int {
		switch models.Role(role) {
		case models.RoleFieldWorker:
			return cfg.FieldWorker
		case models.RoleGeologist:
			return cfg.Geologist
		case models.RoleInvestor:
			return cfg.Investor
		case models.RoleAdmin:
			return cfg.Admin
		default:
			return 10 // Unauthenticated: very conservative
		}
	}

	return func(next http.Handler) http.Handler {
		return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
			role := GetUserRole(r)
		 userID := GetUserID(r)
			if userID == "" {
				// Fall back to IP-based limiting for unauthenticated requests.
				userID = r.RemoteAddr
				role = ""
			}

			key := userID + ":" + role
			limit := getLimit(role)

			mu.Lock()
			entry, exists := entries[key]
			now := time.Now()

			if !exists || now.After(entry.resetAt) {
				entry = &rateLimitEntry{
					count:   1,
					resetAt: now.Add(cfg.Window),
				}
				entries[key] = entry
			} else {
				entry.count++
			}

			remaining := limit - entry.count
			if remaining < 0 {
				remaining = 0
			}

			mu.Unlock()

			// Set rate limit headers (draft-ietf-httpapi-ratelimit-headers).
			w.Header().Set("X-RateLimit-Limit", itoa(limit))
			w.Header().Set("X-RateLimit-Remaining", itoa(remaining))
			w.Header().Set("X-RateLimit-Reset", itoa(int(entry.resetAt.Unix())))

			if entry.count > limit {
				if logger != nil {
					logger.Warn("rate limit exceeded",
						zap.String("user_id", userID),
						zap.String("role", role),
						zap.Int("count", entry.count),
						zap.Int("limit", limit),
					)
				}
				w.Header().Set("Retry-After", itoa(int(cfg.Window.Seconds())))
				http.Error(w, `{"error":"rate limit exceeded"}`, http.StatusTooManyRequests)
				return
			}

			next.ServeHTTP(w, r)
		})
	}
}

func itoa(n int) string {
	if n == 0 {
		return "0"
	}
	s := ""
	neg := false
	if n < 0 {
		neg = true
		n = -n
	}
	for n > 0 {
		s = string(rune('0'+n%10)) + s
		n /= 10
	}
	if neg {
		s = "-" + s
	}
	return s
}
