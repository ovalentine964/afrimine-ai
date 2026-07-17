package storage

import (
	"bytes"
	"context"
	"encoding/base64"
	"fmt"
	"io"
	"mime/multipart"
	"net/http"
	"path/filepath"
	"strings"
	"time"

	"github.com/google/uuid"
)

// SupabaseConfig holds Supabase storage configuration
type SupabaseConfig struct {
	ProjectURL string
	APIKey     string
	BucketName string
}

// SupabaseStorage handles file uploads to Supabase Storage
type SupabaseStorage struct {
	config     SupabaseConfig
	httpClient *http.Client
}

// NewSupabaseStorage creates a new Supabase storage client
func NewSupabaseStorage(config SupabaseConfig) *SupabaseStorage {
	if config.BucketName == "" {
		config.BucketName = "samples"
	}

	return &SupabaseStorage{
		config: config,
		httpClient: &http.Client{
			Timeout: 30 * time.Second,
		},
	}
}

// UploadResult contains the result of a file upload
type UploadResult struct {
	URL      string `json:"url"`
	Path     string `json:"path"`
	Size     int64  `json:"size"`
	MimeType string `json:"mime_type"`
}

// UploadFile uploads a file to Supabase Storage from a multipart file
func (s *SupabaseStorage) UploadFile(ctx context.Context, file multipart.File, header *multipart.FileHeader, userID string) (*UploadResult, error) {
	// Read file content
	content, err := io.ReadAll(file)
	if err != nil {
		return nil, fmt.Errorf("failed to read file: %w", err)
	}

	// Determine content type
	contentType := header.Header.Get("Content-Type")
	if contentType == "" {
		contentType = http.DetectContentType(content)
	}

	// Generate unique filename
	ext := filepath.Ext(header.Filename)
	if ext == "" {
		ext = getExtFromMime(contentType)
	}
	path := fmt.Sprintf("%s/%s%s", userID, uuid.New().String(), ext)

	return s.upload(ctx, path, content, contentType)
}

// UploadBase64 uploads a base64-encoded file to Supabase Storage
func (s *SupabaseStorage) UploadBase64(ctx context.Context, data, mimeType, userID string) (*UploadResult, error) {
	content, err := base64.StdEncoding.DecodeString(data)
	if err != nil {
		return nil, fmt.Errorf("failed to decode base64: %w", err)
	}

	ext := getExtFromMime(mimeType)
	path := fmt.Sprintf("%s/%s%s", userID, uuid.New().String(), ext)

	return s.upload(ctx, path, content, mimeType)
}

func (s *SupabaseStorage) upload(ctx context.Context, path string, content []byte, contentType string) (*UploadResult, error) {
	url := fmt.Sprintf("%s/storage/v1/object/%s/%s", s.config.ProjectURL, s.config.BucketName, path)

	req, err := http.NewRequestWithContext(ctx, "POST", url, bytes.NewReader(content))
	if err != nil {
		return nil, fmt.Errorf("failed to create request: %w", err)
	}

	req.Header.Set("Authorization", fmt.Sprintf("Bearer %s", s.config.APIKey))
	req.Header.Set("Content-Type", contentType)
	req.Header.Set("x-upsert", "true")

	resp, err := s.httpClient.Do(req)
	if err != nil {
		return nil, fmt.Errorf("failed to upload file: %w", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK && resp.StatusCode != http.StatusCreated {
		body, _ := io.ReadAll(resp.Body)
		return nil, fmt.Errorf("upload failed with status %d: %s", resp.StatusCode, string(body))
	}

	publicURL := fmt.Sprintf("%s/storage/v1/object/public/%s/%s", s.config.ProjectURL, s.config.BucketName, path)

	return &UploadResult{
		URL:      publicURL,
		Path:     path,
		Size:     int64(len(content)),
		MimeType: contentType,
	}, nil
}

// DeleteFile deletes a file from Supabase Storage
func (s *SupabaseStorage) DeleteFile(ctx context.Context, path string) error {
	url := fmt.Sprintf("%s/storage/v1/object/%s/%s", s.config.ProjectURL, s.config.BucketName, path)

	req, err := http.NewRequestWithContext(ctx, "DELETE", url, nil)
	if err != nil {
		return fmt.Errorf("failed to create request: %w", err)
	}

	req.Header.Set("Authorization", fmt.Sprintf("Bearer %s", s.config.APIKey))

	resp, err := s.httpClient.Do(req)
	if err != nil {
		return fmt.Errorf("failed to delete file: %w", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK && resp.StatusCode != http.StatusNoContent {
		body, _ := io.ReadAll(resp.Body)
		return fmt.Errorf("delete failed with status %d: %s", resp.StatusCode, string(body))
	}

	return nil
}

func getExtFromMime(mimeType string) string {
	switch {
	case strings.Contains(mimeType, "jpeg"), strings.Contains(mimeType, "jpg"):
		return ".jpg"
	case strings.Contains(mimeType, "png"):
		return ".png"
	case strings.Contains(mimeType, "webp"):
		return ".webp"
	case strings.Contains(mimeType, "gif"):
		return ".gif"
	default:
		return ".bin"
	}
}
