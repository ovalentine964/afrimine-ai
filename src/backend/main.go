package main

import (
	"context"
	"encoding/json"
	"fmt"
	"net/http"
	"os"
	"os/signal"
	"syscall"
	"time"

	"github.com/go-chi/chi/v5"
	chimiddleware "github.com/go-chi/chi/v5/middleware"
	"github.com/go-chi/cors"
	"github.com/ovalentine964/afrimine-ai/backend/a2a"
	"github.com/ovalentine964/afrimine-ai/backend/handlers"
	mw "github.com/ovalentine964/afrimine-ai/backend/middleware"
	"github.com/ovalentine964/afrimine-ai/backend/models"
	"go.uber.org/zap"
	"go.uber.org/zap/zapcore"
)

// Build-time variables (set via -ldflags).
var (
	version   = "dev"
	commit    = "none"
	buildDate = "unknown"
)

// Config holds application configuration loaded from environment.
type Config struct {
	Port           string
	Env            string
	JWTSecret      string
	SupabaseURL    string
	SupabaseKey    string
	A2ABridgeURL   string
	A2ATimeout     time.Duration
	AllowedOrigins []string
}

// LoadConfig reads configuration from environment variables.
func LoadConfig() Config {
	port := os.Getenv("PORT")
	if port == "" {
		port = "8080"
	}

	env := os.Getenv("APP_ENV")
	if env == "" {
		env = "development"
	}

	a2aTimeout := 120 * time.Second // LangGraph pipeline can take 30-60s
	if t := os.Getenv("A2A_TIMEOUT"); t != "" {
		if d, err := time.ParseDuration(t); err == nil {
			a2aTimeout = d
		}
	}

	return Config{
		Port:         port,
		Env:          env,
		JWTSecret:    os.Getenv("SUPABASE_JWT_SECRET"),
		SupabaseURL:  os.Getenv("SUPABASE_URL"),
		SupabaseKey:  os.Getenv("SUPABASE_SERVICE_KEY"),
		A2ABridgeURL: os.Getenv("A2A_BRIDGE_URL"),
		A2ATimeout:   a2aTimeout,
	}
}

func main() {
	// ── Logger ────────────────────────────────────────────────────────
	logCfg := zap.NewProductionConfig()
	logCfg.EncoderConfig.TimeKey = "ts"
	logCfg.EncoderConfig.EncodeTime = zapcore.ISO8601TimeEncoder

	if os.Getenv("APP_ENV") == "development" {
		logCfg = zap.NewDevelopmentConfig()
	}

	logger, err := logCfg.Build()
	if err != nil {
		fmt.Fprintf(os.Stderr, "failed to initialize logger: %v\n", err)
		os.Exit(1)
	}
	defer logger.Sync()

	// ── Config ────────────────────────────────────────────────────────
	cfg := LoadConfig()

	logger.Info("starting AfriMine AI backend",
		zap.String("version", version),
		zap.String("commit", commit),
		zap.String("env", cfg.Env),
		zap.String("port", cfg.Port),
	)

	// ── A2A Client ────────────────────────────────────────────────────
	a2aBridgeURL := cfg.A2ABridgeURL
	if a2aBridgeURL == "" {
		a2aBridgeURL = "http://localhost:8000" // Default: local Python bridge
	}

	a2aClient := a2a.NewClient(a2aBridgeURL, cfg.A2ATimeout, logger)

	// Discover agent cards on startup.
	cardRegistry := a2a.NewRegistry(a2aBridgeURL, logger)
	discoverCtx, discoverCancel := context.WithTimeout(context.Background(), 10*time.Second)
	defer discoverCancel()

	if err := cardRegistry.Discover(discoverCtx); err != nil {
		logger.Warn("agent card discovery failed (bridge may be offline)",
			zap.Error(err),
			zap.String("bridge_url", a2aBridgeURL),
		)
	}

	// ── Handlers ──────────────────────────────────────────────────────
	authHandler := handlers.NewAuthHandler(cfg.JWTSecret, logger)
	sampleHandler := handlers.NewSampleHandler(cfg.SupabaseURL, cfg.SupabaseKey, logger)
	analysisHandler := handlers.NewAnalysisHandler(a2aClient, logger)
	reportHandler := handlers.NewReportHandler(cfg.SupabaseURL, cfg.SupabaseKey, logger)
	marketHandler := handlers.NewMarketHandler(logger)

	// ── Router ────────────────────────────────────────────────────────
	r := chi.NewRouter()

	// Global middleware.
	r.Use(chimiddleware.RequestID)
	r.Use(chimiddleware.RealIP)
	r.Use(chimiddleware.Recoverer)
	r.Use(chimiddleware.Timeout(180 * time.Second)) // Generous for long pipelines

	// CORS — configured for Flutter web clients.
	r.Use(cors.Handler(cors.Options{
		AllowedOrigins:   []string{"*"},
		AllowedMethods:   []string{"GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"},
		AllowedHeaders:   []string{"Accept", "Authorization", "Content-Type", "X-Request-ID", "X-Device-ID"},
		ExposedHeaders:   []string{"X-Request-ID", "Content-Disposition", "X-RateLimit-Limit", "X-RateLimit-Remaining"},
		AllowCredentials: true,
		MaxAge:           300,
	}))

	// Custom structured logging middleware.
	r.Use(requestLogger(logger))

	// Rate limiting (per-role).
	rlCfg := mw.DefaultRateLimitConfig()
	r.Use(mw.RateLimit(rlCfg, logger))

	// ── Public Routes (no auth required) ─────────────────────────────
	r.Get("/health", func(w http.ResponseWriter, r *http.Request) {
		health := map[string]interface{}{
			"status":  "ok",
			"service": "afrimine-backend",
			"version": version,
			"commit":  commit,
		}

		// Check A2A bridge health.
		if err := a2aClient.HealthCheck(r.Context()); err != nil {
			health["a2a_bridge"] = "unreachable"
			health["status"] = "degraded"
		} else {
			health["a2a_bridge"] = "ok"
		}

		// Include discovered agent cards.
		if cards := cardRegistry.ListCards(); len(cards) > 0 {
			agentNames := make([]string, 0, len(cards))
			for name := range cards {
				agentNames = append(agentNames, name)
			}
			health["agents"] = agentNames
		}

		writeHealthJSON(w, health)
	})

	r.Get("/version", func(w http.ResponseWriter, r *http.Request) {
		writeHealthJSON(w, map[string]string{
			"version":    version,
			"commit":     commit,
			"build_date": buildDate,
		})
	})

	// ── Auth Routes (public endpoints for login flow) ─────────────────
	r.Route("/v1", func(r chi.Router) {
		authHandler.Routes(r)
	})

	// ── Protected Routes (JWT required) ───────────────────────────────
	r.Group(func(r chi.Router) {
		// All protected routes require valid JWT.
		r.Use(mw.Auth(mw.AuthConfig{
			JWTSecret: cfg.JWTSecret,
		}))

		// /v1/samples — CRUD for mineral samples
		r.Route("/v1/samples", func(r chi.Router) {
			sampleHandler.Routes(r)
		})

		// /v1/analyses — trigger and manage analysis pipelines
		r.Route("/v1/analyses", func(r chi.Router) {
			analysisHandler.Routes(r)
		})

		// /v1/reports — generate and download reports
		r.Route("/v1/reports", func(r chi.Router) {
			reportHandler.Routes(r)
		})

		// /v1/market — market data and valuations
		r.Route("/v1/market", func(r chi.Router) {
			marketHandler.Routes(r)
		})

		// /v1/agents — agent card discovery (read-only)
		r.Get("/v1/agents", func(w http.ResponseWriter, r *http.Request) {
			cards := cardRegistry.ListCards()
			writeHealthJSON(w, map[string]interface{}{
				"agents": cards,
			})
		})

		r.Get("/v1/agents/{agentID}", func(w http.ResponseWriter, r *http.Request) {
			agentID := chi.URLParam(r, "agentID")
			card, ok := cardRegistry.GetCard(agentID)
			if !ok {
				writeHealthJSON(w, map[string]string{"error": "agent not found"})
				return
			}
			writeHealthJSON(w, card)
		})
	})

	// ── Admin Routes (admin role required) ────────────────────────────
	r.Group(func(r chi.Router) {
		r.Use(mw.Auth(mw.AuthConfig{JWTSecret: cfg.JWTSecret}))
		r.Use(mw.RequireRoles(models.RoleAdmin))

		r.Get("/v1/admin/health", func(w http.ResponseWriter, r *http.Request) {
			writeHealthJSON(w, map[string]interface{}{
				"status":        "ok",
				"a2a_bridge":    a2aBridgeURL,
				"agent_cards":   len(cardRegistry.ListCards()),
				"config_env":    cfg.Env,
				"streaming":     cardRegistry.IsStreamingSupported(),
			})
		})
	})

	// ── Server ────────────────────────────────────────────────────────
	srv := &http.Server{
		Addr:         ":" + cfg.Port,
		Handler:      r,
		ReadTimeout:  30 * time.Second,
		WriteTimeout: 180 * time.Second, // Long for SSE and pipeline responses
		IdleTimeout:  120 * time.Second,
	}

	// ── Graceful Shutdown ─────────────────────────────────────────────
	done := make(chan os.Signal, 1)
	signal.Notify(done, os.Interrupt, syscall.SIGINT, syscall.SIGTERM)

	go func() {
		logger.Info("server listening", zap.String("addr", srv.Addr))
		if err := srv.ListenAndServe(); err != nil && err != http.ErrServerClosed {
			logger.Fatal("server error", zap.Error(err))
		}
	}()

	<-done
	logger.Info("shutting down gracefully...")

	shutdownCtx, shutdownCancel := context.WithTimeout(context.Background(), 30*time.Second)
	defer shutdownCancel()

	if err := srv.Shutdown(shutdownCtx); err != nil {
		logger.Error("shutdown error", zap.Error(err))
	}

	logger.Info("server stopped")
}

// requestLogger is a Chi middleware that logs each request with structured fields.
func requestLogger(logger *zap.Logger) func(http.Handler) http.Handler {
	return func(next http.Handler) http.Handler {
		return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
			start := time.Now()
			ww := chimiddleware.NewWrapResponseWriter(w, r.ProtoMajor)

			defer func() {
				logger.Info("request",
					zap.String("method", r.Method),
					zap.String("path", r.URL.Path),
					zap.String("query", r.URL.RawQuery),
					zap.Int("status", ww.Status()),
					zap.Int("bytes", ww.BytesWritten()),
					zap.Duration("duration", time.Since(start)),
					zap.String("request_id", chimiddleware.GetReqID(r.Context())),
					zap.String("remote", r.RemoteAddr),
					zap.String("user_agent", r.UserAgent()),
				)
			}()

			next.ServeHTTP(ww, r)
		})
	}
}

// writeHealthJSON writes a JSON response for health/version endpoints (no Content-Type negotiation).
func writeHealthJSON(w http.ResponseWriter, data interface{}) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	enc := json.NewEncoder(w)
	enc.SetIndent("", "  ")
	enc.Encode(data)
}
