package routes

import (
	"os"
	"strings"

	"github.com/go-chi/chi/v5"
	chimw "github.com/go-chi/chi/v5/middleware"
	"github.com/go-chi/cors"
	"log/slog"

	"github.com/ovalentine964/afrimine-ai/backend/internal/ai"
	"github.com/ovalentine964/afrimine-ai/backend/internal/api/handlers"
	"github.com/ovalentine964/afrimine-ai/backend/internal/api/middleware"
	"github.com/ovalentine964/afrimine-ai/backend/internal/auth"
	"github.com/ovalentine964/afrimine-ai/backend/internal/database"
	"github.com/ovalentine964/afrimine-ai/backend/internal/storage"
)

// NewRouter creates and configures the main chi router with all routes
func NewRouter(db *database.DB, jwtService *auth.JWTService, gemini *ai.GeminiClient, store *storage.SupabaseStorage, logger *slog.Logger) *chi.Mux {
	r := chi.NewRouter()

	// Global middleware
	r.Use(chimw.RequestID)
	r.Use(chimw.RealIP)
	r.Use(middleware.Logger(logger))
	r.Use(chimw.Recoverer)
	r.Use(chimw.Heartbeat("/ping"))

	// CORS — read allowed origins from env, default to empty (deny all cross-origin)
	allowedOrigins := getOriginsFromEnv("CORS_ALLOWED_ORIGINS")
	r.Use(cors.Handler(cors.Options{
		AllowedOrigins:   allowedOrigins,
		AllowedMethods:   []string{"GET", "POST", "PUT", "DELETE", "OPTIONS"},
		AllowedHeaders:   []string{"Accept", "Authorization", "Content-Type", "X-CSRF-Token"},
		ExposedHeaders:   []string{"Link"},
		AllowCredentials: true,
		MaxAge:           300,
	}))

	// Rate limiting: 30 requests/second per IP, burst of 50
	rateLimiter := middleware.NewRateLimiter(30, 50)
	r.Use(rateLimiter.RateLimit)

	// Stricter rate limit for auth endpoints: 5 requests/second, burst of 10
	authRateLimiter := middleware.NewRateLimiter(5, 10)

	// Create handler
	h := handlers.NewHandler(db, jwtService, gemini, store, logger)

	// Public routes
	r.Route("/v1", func(r chi.Router) {
		// Health check
		r.Get("/health", h.HealthCheck)

		// Auth routes (public) — with stricter rate limiting
		r.Group(func(r chi.Router) {
			r.Use(authRateLimiter.RateLimit)
			r.Post("/auth/phone", h.SendOTP)
			r.Post("/auth/verify", h.VerifyOTP)
			r.Post("/auth/refresh", h.RefreshToken)
		})

		// Market data (public)
		r.Get("/market/prices", h.GetMarketPrices)
		r.Get("/market/history", h.GetMarketHistory)

		// Protected routes
		r.Group(func(r chi.Router) {
			r.Use(middleware.JWTAuth(jwtService))

			// Samples
			r.Route("/samples", func(r chi.Router) {
				r.Get("/", h.ListSamples)
				r.Post("/", h.CreateSample)
				r.Get("/{id}", h.GetSample)
				r.Put("/{id}", h.UpdateSample)
				r.Delete("/{id}", h.DeleteSample)
			})

			// Analysis
			r.Post("/analyze", h.AnalyzeSample)
			r.Post("/analyze/batch", h.BatchAnalyze)
			r.Get("/analysis/{id}", h.GetAnalysis)

			// Reports
			r.Post("/reports/generate", h.GenerateReport)
			r.Get("/reports/{id}", h.GetReport)
			r.Get("/reports/{id}/pdf", h.DownloadReportPDF)

			// Sync
			r.Post("/sync", h.SyncUpload)
			r.Get("/sync/changes", h.SyncChanges)
		})
	})

	return r
}

// getOriginsFromEnv reads a comma-separated list of allowed origins from an env var.
// Returns nil (deny all cross-origin) if the env var is not set.
func getOriginsFromEnv(key string) []string {
	val := os.Getenv(key)
	if val == "" {
		return nil
	}
	parts := strings.Split(val, ",")
	origins := make([]string, 0, len(parts))
	for _, p := range parts {
		trimmed := strings.TrimSpace(p)
		if trimmed != "" {
			origins = append(origins, trimmed)
		}
	}
	if len(origins) == 0 {
		return nil
	}
	return origins
}
