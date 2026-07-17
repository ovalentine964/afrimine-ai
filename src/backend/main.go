package main

import (
	"context"
	"fmt"
	"log/slog"
	"net/http"
	"os"
	"os/signal"
	"syscall"
	"time"

	"github.com/ovalentine964/afrimine-ai/backend/internal/ai"
	"github.com/ovalentine964/afrimine-ai/backend/internal/api/routes"
	"github.com/ovalentine964/afrimine-ai/backend/internal/auth"
	"github.com/ovalentine964/afrimine-ai/backend/internal/database"
	"github.com/ovalentine964/afrimine-ai/backend/internal/storage"
)

func main() {
	// Structured logger
	logger := slog.New(slog.NewJSONHandler(os.Stdout, &slog.HandlerOptions{
		Level: slog.LevelInfo,
	}))
	slog.SetDefault(logger)

	logger.Info("starting AfriMine AI server")

	// Configuration from environment
	cfg := loadConfig()

	// Validate required configuration
	if cfg.JWTSecret == "" {
		logger.Error("JWT_SECRET environment variable is required")
		os.Exit(1)
	}
	if cfg.GeminiAPIKey == "" {
		logger.Error("GEMINI_API_KEY environment variable is required")
		os.Exit(1)
	}

	// Database connection
	ctx := context.Background()
	db, err := database.New(ctx, database.Config{
		URL:      cfg.DatabaseURL,
		Host:     cfg.DBHost,
		Port:     cfg.DBPort,
		User:     cfg.DBUser,
		Password: cfg.DBPassword,
		DBName:   cfg.DBName,
		SSLMode:  cfg.DBSSLMode,
	})
	if err != nil {
		logger.Error("failed to connect to database", "error", err)
		os.Exit(1)
	}
	defer db.Close()
	logger.Info("database connected")

	// Run migrations
	if err := db.RunMigrations(ctx); err != nil {
		logger.Error("failed to run migrations", "error", err)
		os.Exit(1)
	}
	logger.Info("migrations applied")

	// JWT service
	jwtService := auth.NewJWTService(auth.JWTConfig{
		Secret:     []byte(cfg.JWTSecret),
		Issuer:     "afrimine-ai",
		AccessTTL:  1 * time.Hour,
		RefreshTTL: 7 * 24 * time.Hour,
	})

	// Gemini AI client
	gemini := ai.NewGeminiClient(ai.GeminiConfig{
		APIKey: cfg.GeminiAPIKey,
		Model:  cfg.GeminiModel,
	})

	// Supabase storage
	store := storage.NewSupabaseStorage(storage.SupabaseConfig{
		ProjectURL: cfg.SupabaseURL,
		APIKey:     cfg.SupabaseKey,
		BucketName: cfg.StorageBucket,
	})

	// Create router
	router := routes.NewRouter(db, jwtService, gemini, store, logger)

	// HTTP server
	srv := &http.Server{
		Addr:         fmt.Sprintf(":%d", cfg.Port),
		Handler:      router,
		ReadTimeout:  15 * time.Second,
		WriteTimeout: 60 * time.Second,
		IdleTimeout:  120 * time.Second,
	}

	// Graceful shutdown
	done := make(chan os.Signal, 1)
	signal.Notify(done, os.Interrupt, syscall.SIGINT, syscall.SIGTERM)

	go func() {
		logger.Info("server listening", "port", cfg.Port)
		if err := srv.ListenAndServe(); err != nil && err != http.ErrServerClosed {
			logger.Error("server error", "error", err)
			os.Exit(1)
		}
	}()

	<-done
	logger.Info("shutting down server")

	shutdownCtx, cancel := context.WithTimeout(context.Background(), 30*time.Second)
	defer cancel()

	if err := srv.Shutdown(shutdownCtx); err != nil {
		logger.Error("server forced to shutdown", "error", err)
		os.Exit(1)
	}

	logger.Info("server stopped gracefully")
}

// Config holds application configuration
type Config struct {
	Port          int
	DatabaseURL   string // Preferred: full DATABASE_URL
	DBHost        string
	DBPort        int
	DBUser        string
	DBPassword    string
	DBName        string
	DBSSLMode     string
	JWTSecret     string
	GeminiAPIKey  string
	GeminiModel   string
	SupabaseURL   string
	SupabaseKey   string
	StorageBucket string
}

func loadConfig() Config {
	return Config{
		Port:          getEnvInt("PORT", 8080),
		DatabaseURL:   getEnv("DATABASE_URL", ""),
		DBHost:        getEnv("DB_HOST", "localhost"),
		DBPort:        getEnvInt("DB_PORT", 5432),
		DBUser:        getEnv("DB_USER", ""),
		DBPassword:    getEnv("DB_PASSWORD", ""),
		DBName:        getEnv("DB_NAME", "afrimine"),
		DBSSLMode:     getEnv("DB_SSLMODE", "require"),
		JWTSecret:     getEnv("JWT_SECRET", ""),
		GeminiAPIKey:  getEnv("GEMINI_API_KEY", ""),
		GeminiModel:   getEnv("GEMINI_MODEL", "gemini-2.0-flash"),
		SupabaseURL:   getEnv("SUPABASE_URL", ""),
		SupabaseKey:   getEnv("SUPABASE_KEY", ""),
		StorageBucket: getEnv("STORAGE_BUCKET", "samples"),
	}
}

func getEnv(key, defaultVal string) string {
	if val := os.Getenv(key); val != "" {
		return val
	}
	return defaultVal
}

func getEnvInt(key string, defaultVal int) int {
	if val := os.Getenv(key); val != "" {
		var n int
		if _, err := fmt.Sscanf(val, "%d", &n); err == nil {
			return n
		}
	}
	return defaultVal
}
