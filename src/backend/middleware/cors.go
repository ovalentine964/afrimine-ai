package middleware

import (
	"github.com/go-chi/cors"
)

// CORSConfig returns a CORS handler configured for Flutter web clients.
// Allows the Flutter web app to communicate with the API from any origin
// during development; tighten for production.
func CORSConfig() cors.Options {
	return cors.Options{
		// Allowed origins — in production, restrict to your domain:
		// AllowedOrigins: []string{"https://afrimine.com", "https://www.afrimine.com"},
		AllowedOrigins: []string{"*"},
		AllowedMethods: []string{"GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"},
		AllowedHeaders: []string{
			"Accept",
			"Authorization",
			"Content-Type",
			"X-Request-ID",
			"X-Device-ID",
			"X-Sync-Version",
		},
		ExposedHeaders: []string{
			"X-Request-ID",
			"Content-Disposition",
		},
		AllowCredentials: true,
		MaxAge:           300, // 5 minutes preflight cache
	}
}
