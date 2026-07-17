package database

import (
	"context"
	"fmt"
	"time"

	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgxpool"
	"github.com/ovalentine964/afrimine-ai/backend/internal/models"
)

// DB wraps the PostgreSQL connection pool
type DB struct {
	pool *pgxpool.Pool
}

// Config holds database configuration
type Config struct {
	Host     string
	Port     int
	User     string
	Password string
	DBName   string
	SSLMode  string
}

// New creates a new database connection
func New(ctx context.Context, cfg Config) (*DB, error) {
	dsn := fmt.Sprintf(
		"host=%s port=%d user=%s password=%s dbname=%s sslmode=%s",
		cfg.Host, cfg.Port, cfg.User, cfg.Password, cfg.DBName, cfg.SSLMode,
	)

	poolCfg, err := pgxpool.ParseConfig(dsn)
	if err != nil {
		return nil, fmt.Errorf("failed to parse dsn: %w", err)
	}

	poolCfg.MaxConns = 25
	poolCfg.MinConns = 5
	poolCfg.MaxConnLifetime = time.Hour
	poolCfg.MaxConnIdleTime = 30 * time.Minute

	pool, err := pgxpool.NewWithConfig(ctx, poolCfg)
	if err != nil {
		return nil, fmt.Errorf("failed to create pool: %w", err)
	}

	if err := pool.Ping(ctx); err != nil {
		return nil, fmt.Errorf("failed to ping database: %w", err)
	}

	return &DB{pool: pool}, nil
}

// Close closes the database connection pool
func (db *DB) Close() {
	db.pool.Close()
}

// RunMigrations creates the database schema
func (db *DB) RunMigrations(ctx context.Context) error {
	schema := `
	CREATE TABLE IF NOT EXISTS users (
		id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
		phone VARCHAR(20) UNIQUE NOT NULL,
		name VARCHAR(255) NOT NULL DEFAULT '',
		created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
		updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
	);

	CREATE TABLE IF NOT EXISTS otps (
		id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
		phone VARCHAR(20) NOT NULL,
		code VARCHAR(6) NOT NULL,
		expires_at TIMESTAMP WITH TIME ZONE NOT NULL,
		used BOOLEAN DEFAULT FALSE,
		created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
	);

	CREATE INDEX IF NOT EXISTS idx_otps_phone ON otps(phone);

	CREATE TABLE IF NOT EXISTS samples (
		id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
		user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
		name VARCHAR(255) NOT NULL,
		description TEXT DEFAULT '',
		latitude DOUBLE PRECISION DEFAULT 0,
		longitude DOUBLE PRECISION DEFAULT 0,
		photo_url TEXT DEFAULT '',
		status VARCHAR(20) DEFAULT 'pending',
		created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
		updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
	);

	CREATE INDEX IF NOT EXISTS idx_samples_user_id ON samples(user_id);

	CREATE TABLE IF NOT EXISTS analyses (
		id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
		sample_id UUID NOT NULL REFERENCES samples(id) ON DELETE CASCADE,
		user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
		mineral_type VARCHAR(100) DEFAULT '',
		confidence DOUBLE PRECISION DEFAULT 0,
		description TEXT DEFAULT '',
		estimated_value DOUBLE PRECISION DEFAULT 0,
		currency VARCHAR(10) DEFAULT 'USD',
		raw_response TEXT DEFAULT '',
		status VARCHAR(20) DEFAULT 'processing',
		created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
	);

	CREATE INDEX IF NOT EXISTS idx_analyses_sample_id ON analyses(sample_id);
	CREATE INDEX IF NOT EXISTS idx_analyses_user_id ON analyses(user_id);

	CREATE TABLE IF NOT EXISTS reports (
		id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
		user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
		title VARCHAR(255) NOT NULL,
		summary TEXT DEFAULT '',
		pdf_path TEXT DEFAULT '',
		status VARCHAR(20) DEFAULT 'generating',
		created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
	);

	CREATE INDEX IF NOT EXISTS idx_reports_user_id ON reports(user_id);
	`

	_, err := db.pool.Exec(ctx, schema)
	if err != nil {
		return fmt.Errorf("failed to run migrations: %w", err)
	}

	return nil
}

// User queries

// CreateUser creates a new user or returns existing one
func (db *DB) CreateUser(ctx context.Context, phone, name string) (*models.User, error) {
	user := &models.User{}
	err := db.pool.QueryRow(ctx,
		`INSERT INTO users (phone, name) VALUES ($1, $2)
		 ON CONFLICT (phone) DO UPDATE SET name = COALESCE(NULLIF($2, ''), users.name), updated_at = NOW()
		 RETURNING id, phone, name, created_at, updated_at`,
		phone, name,
	).Scan(&user.ID, &user.Phone, &user.Name, &user.CreatedAt, &user.UpdatedAt)
	if err != nil {
		return nil, fmt.Errorf("failed to create user: %w", err)
	}
	return user, nil
}

// GetUserByPhone finds a user by phone number
func (db *DB) GetUserByPhone(ctx context.Context, phone string) (*models.User, error) {
	user := &models.User{}
	err := db.pool.QueryRow(ctx,
		`SELECT id, phone, name, created_at, updated_at FROM users WHERE phone = $1`,
		phone,
	).Scan(&user.ID, &user.Phone, &user.Name, &user.CreatedAt, &user.UpdatedAt)
	if err != nil {
		if err == pgx.ErrNoRows {
			return nil, nil
		}
		return nil, fmt.Errorf("failed to get user: %w", err)
	}
	return user, nil
}

// GetUserByID finds a user by ID
func (db *DB) GetUserByID(ctx context.Context, id string) (*models.User, error) {
	user := &models.User{}
	err := db.pool.QueryRow(ctx,
		`SELECT id, phone, name, created_at, updated_at FROM users WHERE id = $1`,
		id,
	).Scan(&user.ID, &user.Phone, &user.Name, &user.CreatedAt, &user.UpdatedAt)
	if err != nil {
		if err == pgx.ErrNoRows {
			return nil, nil
		}
		return nil, fmt.Errorf("failed to get user: %w", err)
	}
	return user, nil
}

// OTP queries

// CreateOTP creates a new OTP record
func (db *DB) CreateOTP(ctx context.Context, phone, code string, expiresAt time.Time) (*models.OTP, error) {
	otp := &models.OTP{}
	err := db.pool.QueryRow(ctx,
		`INSERT INTO otps (phone, code, expires_at) VALUES ($1, $2, $3)
		 RETURNING id, phone, code, expires_at, used, created_at`,
		phone, code, expiresAt,
	).Scan(&otp.ID, &otp.Phone, &otp.Code, &otp.ExpiresAt, &otp.Used, &otp.CreatedAt)
	if err != nil {
		return nil, fmt.Errorf("failed to create OTP: %w", err)
	}
	return otp, nil
}

// GetValidOTP retrieves a valid, unused OTP for a phone number
func (db *DB) GetValidOTP(ctx context.Context, phone, code string) (*models.OTP, error) {
	otp := &models.OTP{}
	err := db.pool.QueryRow(ctx,
		`SELECT id, phone, code, expires_at, used, created_at 
		 FROM otps 
		 WHERE phone = $1 AND code = $2 AND used = FALSE AND expires_at > NOW()
		 ORDER BY created_at DESC LIMIT 1`,
		phone, code,
	).Scan(&otp.ID, &otp.Phone, &otp.Code, &otp.ExpiresAt, &otp.Used, &otp.CreatedAt)
	if err != nil {
		if err == pgx.ErrNoRows {
			return nil, nil
		}
		return nil, fmt.Errorf("failed to get OTP: %w", err)
	}
	return otp, nil
}

// MarkOTPUsed marks an OTP as used
func (db *DB) MarkOTPUsed(ctx context.Context, id string) error {
	_, err := db.pool.Exec(ctx,
		`UPDATE otps SET used = TRUE WHERE id = $1`,
		id,
	)
	return err
}

// Sample queries

// CreateSample creates a new sample
func (db *DB) CreateSample(ctx context.Context, s *models.Sample) (*models.Sample, error) {
	sample := &models.Sample{}
	err := db.pool.QueryRow(ctx,
		`INSERT INTO samples (user_id, name, description, latitude, longitude, photo_url, status)
		 VALUES ($1, $2, $3, $4, $5, $6, $7)
		 RETURNING id, user_id, name, description, latitude, longitude, photo_url, status, created_at, updated_at`,
		s.UserID, s.Name, s.Description, s.Latitude, s.Longitude, s.PhotoURL, "pending",
	).Scan(&sample.ID, &sample.UserID, &sample.Name, &sample.Description,
		&sample.Latitude, &sample.Longitude, &sample.PhotoURL, &sample.Status,
		&sample.CreatedAt, &sample.UpdatedAt)
	if err != nil {
		return nil, fmt.Errorf("failed to create sample: %w", err)
	}
	return sample, nil
}

// GetSampleByID retrieves a sample by ID, scoped to user
func (db *DB) GetSampleByID(ctx context.Context, id, userID string) (*models.Sample, error) {
	sample := &models.Sample{}
	err := db.pool.QueryRow(ctx,
		`SELECT id, user_id, name, description, latitude, longitude, photo_url, status, created_at, updated_at
		 FROM samples WHERE id = $1 AND user_id = $2`,
		id, userID,
	).Scan(&sample.ID, &sample.UserID, &sample.Name, &sample.Description,
		&sample.Latitude, &sample.Longitude, &sample.PhotoURL, &sample.Status,
		&sample.CreatedAt, &sample.UpdatedAt)
	if err != nil {
		if err == pgx.ErrNoRows {
			return nil, nil
		}
		return nil, fmt.Errorf("failed to get sample: %w", err)
	}
	return sample, nil
}

// ListSamples lists samples for a user with pagination
func (db *DB) ListSamples(ctx context.Context, userID string, page, perPage int) ([]models.Sample, int, error) {
	// Get total count
	var total int
	err := db.pool.QueryRow(ctx,
		`SELECT COUNT(*) FROM samples WHERE user_id = $1`, userID,
	).Scan(&total)
	if err != nil {
		return nil, 0, fmt.Errorf("failed to count samples: %w", err)
	}

	offset := (page - 1) * perPage
	rows, err := db.pool.Query(ctx,
		`SELECT id, user_id, name, description, latitude, longitude, photo_url, status, created_at, updated_at
		 FROM samples WHERE user_id = $1
		 ORDER BY created_at DESC LIMIT $2 OFFSET $3`,
		userID, perPage, offset,
	)
	if err != nil {
		return nil, 0, fmt.Errorf("failed to list samples: %w", err)
	}
	defer rows.Close()

	var samples []models.Sample
	for rows.Next() {
		var s models.Sample
		if err := rows.Scan(&s.ID, &s.UserID, &s.Name, &s.Description,
			&s.Latitude, &s.Longitude, &s.PhotoURL, &s.Status,
			&s.CreatedAt, &s.UpdatedAt); err != nil {
			return nil, 0, fmt.Errorf("failed to scan sample: %w", err)
		}
		samples = append(samples, s)
	}

	return samples, total, nil
}

// UpdateSample updates a sample
func (db *DB) UpdateSample(ctx context.Context, s *models.Sample) (*models.Sample, error) {
	sample := &models.Sample{}
	err := db.pool.QueryRow(ctx,
		`UPDATE samples SET name = $1, description = $2, latitude = $3, longitude = $4, 
		 photo_url = COALESCE(NULLIF($5, ''), photo_url), status = $6, updated_at = NOW()
		 WHERE id = $7 AND user_id = $8
		 RETURNING id, user_id, name, description, latitude, longitude, photo_url, status, created_at, updated_at`,
		s.Name, s.Description, s.Latitude, s.Longitude, s.PhotoURL, s.Status, s.ID, s.UserID,
	).Scan(&sample.ID, &sample.UserID, &sample.Name, &sample.Description,
		&sample.Latitude, &sample.Longitude, &sample.PhotoURL, &sample.Status,
		&sample.CreatedAt, &sample.UpdatedAt)
	if err != nil {
		if err == pgx.ErrNoRows {
			return nil, nil
		}
		return nil, fmt.Errorf("failed to update sample: %w", err)
	}
	return sample, nil
}

// DeleteSample deletes a sample
func (db *DB) DeleteSample(ctx context.Context, id, userID string) error {
	tag, err := db.pool.Exec(ctx,
		`DELETE FROM samples WHERE id = $1 AND user_id = $2`,
		id, userID,
	)
	if err != nil {
		return fmt.Errorf("failed to delete sample: %w", err)
	}
	if tag.RowsAffected() == 0 {
		return fmt.Errorf("sample not found")
	}
	return nil
}

// Analysis queries

// CreateAnalysis creates a new analysis record
func (db *DB) CreateAnalysis(ctx context.Context, a *models.Analysis) (*models.Analysis, error) {
	analysis := &models.Analysis{}
	err := db.pool.QueryRow(ctx,
		`INSERT INTO analyses (sample_id, user_id, mineral_type, confidence, description, estimated_value, currency, raw_response, status)
		 VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
		 RETURNING id, sample_id, user_id, mineral_type, confidence, description, estimated_value, currency, raw_response, status, created_at`,
		a.SampleID, a.UserID, a.MineralType, a.Confidence, a.Description,
		a.EstimatedValue, a.Currency, a.RawResponse, a.Status,
	).Scan(&analysis.ID, &analysis.SampleID, &analysis.UserID, &analysis.MineralType,
		&analysis.Confidence, &analysis.Description, &analysis.EstimatedValue,
		&analysis.Currency, &analysis.RawResponse, &analysis.Status, &analysis.CreatedAt)
	if err != nil {
		return nil, fmt.Errorf("failed to create analysis: %w", err)
	}
	return analysis, nil
}

// UpdateAnalysis updates an analysis record
func (db *DB) UpdateAnalysis(ctx context.Context, a *models.Analysis) (*models.Analysis, error) {
	analysis := &models.Analysis{}
	err := db.pool.QueryRow(ctx,
		`UPDATE analyses SET mineral_type = $1, confidence = $2, description = $3,
		 estimated_value = $4, currency = $5, raw_response = $6, status = $7
		 WHERE id = $8 AND user_id = $9
		 RETURNING id, sample_id, user_id, mineral_type, confidence, description, estimated_value, currency, raw_response, status, created_at`,
		a.MineralType, a.Confidence, a.Description,
		a.EstimatedValue, a.Currency, a.RawResponse, a.Status, a.ID, a.UserID,
	).Scan(&analysis.ID, &analysis.SampleID, &analysis.UserID, &analysis.MineralType,
		&analysis.Confidence, &analysis.Description, &analysis.EstimatedValue,
		&analysis.Currency, &analysis.RawResponse, &analysis.Status, &analysis.CreatedAt)
	if err != nil {
		if err == pgx.ErrNoRows {
			return nil, nil
		}
		return nil, fmt.Errorf("failed to update analysis: %w", err)
	}
	return analysis, nil
}

// GetAnalysisByID retrieves an analysis by ID, scoped to user
func (db *DB) GetAnalysisByID(ctx context.Context, id, userID string) (*models.Analysis, error) {
	analysis := &models.Analysis{}
	err := db.pool.QueryRow(ctx,
		`SELECT id, sample_id, user_id, mineral_type, confidence, description, estimated_value, currency, raw_response, status, created_at
		 FROM analyses WHERE id = $1 AND user_id = $2`,
		id, userID,
	).Scan(&analysis.ID, &analysis.SampleID, &analysis.UserID, &analysis.MineralType,
		&analysis.Confidence, &analysis.Description, &analysis.EstimatedValue,
		&analysis.Currency, &analysis.RawResponse, &analysis.Status, &analysis.CreatedAt)
	if err != nil {
		if err == pgx.ErrNoRows {
			return nil, nil
		}
		return nil, fmt.Errorf("failed to get analysis: %w", err)
	}
	return analysis, nil
}

// GetAnalysesBySampleID retrieves analyses for a sample
func (db *DB) GetAnalysesBySampleID(ctx context.Context, sampleID, userID string) ([]models.Analysis, error) {
	rows, err := db.pool.Query(ctx,
		`SELECT id, sample_id, user_id, mineral_type, confidence, description, estimated_value, currency, raw_response, status, created_at
		 FROM analyses WHERE sample_id = $1 AND user_id = $2 ORDER BY created_at DESC`,
		sampleID, userID,
	)
	if err != nil {
		return nil, fmt.Errorf("failed to get analyses: %w", err)
	}
	defer rows.Close()

	var analyses []models.Analysis
	for rows.Next() {
		var a models.Analysis
		if err := rows.Scan(&a.ID, &a.SampleID, &a.UserID, &a.MineralType,
			&a.Confidence, &a.Description, &a.EstimatedValue,
			&a.Currency, &a.RawResponse, &a.Status, &a.CreatedAt); err != nil {
			return nil, fmt.Errorf("failed to scan analysis: %w", err)
		}
		analyses = append(analyses, a)
	}
	return analyses, nil
}

// Report queries

// CreateReport creates a new report
func (db *DB) CreateReport(ctx context.Context, r *models.Report) (*models.Report, error) {
	report := &models.Report{}
	err := db.pool.QueryRow(ctx,
		`INSERT INTO reports (user_id, title, summary, pdf_path, status)
		 VALUES ($1, $2, $3, $4, $5)
		 RETURNING id, user_id, title, summary, pdf_path, status, created_at`,
		r.UserID, r.Title, r.Summary, r.PDFPath, r.Status,
	).Scan(&report.ID, &report.UserID, &report.Title, &report.Summary,
		&report.PDFPath, &report.Status, &report.CreatedAt)
	if err != nil {
		return nil, fmt.Errorf("failed to create report: %w", err)
	}
	return report, nil
}

// UpdateReport updates a report
func (db *DB) UpdateReport(ctx context.Context, r *models.Report) (*models.Report, error) {
	report := &models.Report{}
	err := db.pool.QueryRow(ctx,
		`UPDATE reports SET title = $1, summary = $2, pdf_path = $3, status = $4
		 WHERE id = $5 AND user_id = $6
		 RETURNING id, user_id, title, summary, pdf_path, status, created_at`,
		r.Title, r.Summary, r.PDFPath, r.Status, r.ID, r.UserID,
	).Scan(&report.ID, &report.UserID, &report.Title, &report.Summary,
		&report.PDFPath, &report.Status, &report.CreatedAt)
	if err != nil {
		if err == pgx.ErrNoRows {
			return nil, nil
		}
		return nil, fmt.Errorf("failed to update report: %w", err)
	}
	return report, nil
}

// GetReportByID retrieves a report by ID
func (db *DB) GetReportByID(ctx context.Context, id, userID string) (*models.Report, error) {
	report := &models.Report{}
	err := db.pool.QueryRow(ctx,
		`SELECT id, user_id, title, summary, pdf_path, status, created_at
		 FROM reports WHERE id = $1 AND user_id = $2`,
		id, userID,
	).Scan(&report.ID, &report.UserID, &report.Title, &report.Summary,
		&report.PDFPath, &report.Status, &report.CreatedAt)
	if err != nil {
		if err == pgx.ErrNoRows {
			return nil, nil
		}
		return nil, fmt.Errorf("failed to get report: %w", err)
	}
	return report, nil
}

// GetSamplesSince gets samples updated since a given time
func (db *DB) GetSamplesSince(ctx context.Context, userID string, since time.Time) ([]models.Sample, error) {
	rows, err := db.pool.Query(ctx,
		`SELECT id, user_id, name, description, latitude, longitude, photo_url, status, created_at, updated_at
		 FROM samples WHERE user_id = $1 AND updated_at > $2 ORDER BY updated_at`,
		userID, since,
	)
	if err != nil {
		return nil, fmt.Errorf("failed to get samples since: %w", err)
	}
	defer rows.Close()

	var samples []models.Sample
	for rows.Next() {
		var s models.Sample
		if err := rows.Scan(&s.ID, &s.UserID, &s.Name, &s.Description,
			&s.Latitude, &s.Longitude, &s.PhotoURL, &s.Status,
			&s.CreatedAt, &s.UpdatedAt); err != nil {
			return nil, fmt.Errorf("failed to scan sample: %w", err)
		}
		samples = append(samples, s)
	}
	return samples, nil
}

// GetAnalysesSince gets analyses created since a given time
func (db *DB) GetAnalysesSince(ctx context.Context, userID string, since time.Time) ([]models.Analysis, error) {
	rows, err := db.pool.Query(ctx,
		`SELECT id, sample_id, user_id, mineral_type, confidence, description, estimated_value, currency, raw_response, status, created_at
		 FROM analyses WHERE user_id = $1 AND created_at > $2 ORDER BY created_at`,
		userID, since,
	)
	if err != nil {
		return nil, fmt.Errorf("failed to get analyses since: %w", err)
	}
	defer rows.Close()

	var analyses []models.Analysis
	for rows.Next() {
		var a models.Analysis
		if err := rows.Scan(&a.ID, &a.SampleID, &a.UserID, &a.MineralType,
			&a.Confidence, &a.Description, &a.EstimatedValue,
			&a.Currency, &a.RawResponse, &a.Status, &a.CreatedAt); err != nil {
			return nil, fmt.Errorf("failed to scan analysis: %w", err)
		}
		analyses = append(analyses, a)
	}
	return analyses, nil
}
