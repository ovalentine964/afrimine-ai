package ai

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"time"
)

// GeminiConfig holds Gemini API configuration
type GeminiConfig struct {
	APIKey  string
	Model   string
	BaseURL string
}

// GeminiClient handles communication with Google's Gemini API
type GeminiClient struct {
	config     GeminiConfig
	httpClient *http.Client
}

// NewGeminiClient creates a new Gemini API client
func NewGeminiClient(config GeminiConfig) *GeminiClient {
	if config.Model == "" {
		config.Model = "gemini-2.0-flash"
	}
	if config.BaseURL == "" {
		config.BaseURL = "https://generativelanguage.googleapis.com/v1beta"
	}

	return &GeminiClient{
		config: config,
		httpClient: &http.Client{
			Timeout: 60 * time.Second,
		},
	}
}

// GeminiRequest represents the Gemini API request structure
type GeminiRequest struct {
	Contents         []GeminiContent         `json:"contents"`
	GenerationConfig *GenerationConfig       `json:"generationConfig,omitempty"`
}

type GeminiContent struct {
	Parts []GeminiPart `json:"parts"`
}

type GeminiPart struct {
	Text       string      `json:"text,omitempty"`
	InlineData *InlineData `json:"inlineData,omitempty"`
}

type InlineData struct {
	MimeType string `json:"mimeType"`
	Data     string `json:"data"` // base64 encoded
}

type GenerationConfig struct {
	Temperature     float64 `json:"temperature,omitempty"`
	MaxOutputTokens int     `json:"maxOutputTokens,omitempty"`
}

// GeminiResponse represents the Gemini API response
type GeminiResponse struct {
	Candidates []struct {
		Content struct {
			Parts []struct {
				Text string `json:"text"`
			} `json:"parts"`
		} `json:"content"`
		FinishReason string `json:"finishReason"`
	} `json:"candidates"`
	Error *struct {
		Code    int    `json:"code"`
		Message string `json:"message"`
	} `json:"error,omitempty"`
}

// AnalysisResult represents the parsed mineral analysis
type AnalysisResult struct {
	MineralType    string  `json:"mineral_type"`
	Confidence     float64 `json:"confidence"`
	Description    string  `json:"description"`
	EstimatedValue float64 `json:"estimated_value_usd"`
	Location       string  `json:"location"`
	Notes          string  `json:"notes"`
}

// AnalyzeImage sends an image to Gemini for mineral analysis
func (c *GeminiClient) AnalyzeImage(ctx context.Context, imageBase64, mimeType string) (*AnalysisResult, error) {
	prompt := `You are a mineralogist AI assistant for AfriMine, a mineral detection platform serving Kenyan mining families.

Analyze this image and identify any minerals or geological samples present. Provide your response in the following JSON format:

{
  "mineral_type": "name of the mineral identified",
  "confidence": 0.85,
  "description": "detailed description of the mineral, its properties, and characteristics",
  "estimated_value_usd": 150.00,
  "location": "likely geological origin or formation type",
  "notes": "any additional notes about quality, potential uses, or recommendations for the miner"
}

Important guidelines:
- Be specific about mineral identification
- Confidence should be between 0.0 and 1.0
- Estimated value should be realistic per kilogram in USD
- Consider that this is for Kenyan mining families - be practical and helpful
- If the image quality is poor or you cannot identify a mineral, set confidence below 0.3
- Only respond with valid JSON, no additional text`

	req := GeminiRequest{
		Contents: []GeminiContent{
			{
				Parts: []GeminiPart{
					{Text: prompt},
					{
						InlineData: &InlineData{
							MimeType: mimeType,
							Data:     imageBase64,
						},
					},
				},
			},
		},
		GenerationConfig: &GenerationConfig{
			Temperature:     0.2,
			MaxOutputTokens: 2048,
		},
	}

	resp, err := c.sendRequest(ctx, req)
	if err != nil {
		return nil, fmt.Errorf("gemini API error: %w", err)
	}

	if resp.Error != nil {
		return nil, fmt.Errorf("gemini API error %d: %s", resp.Error.Code, resp.Error.Message)
	}

	if len(resp.Candidates) == 0 || len(resp.Candidates[0].Content.Parts) == 0 {
		return nil, fmt.Errorf("no response from Gemini API")
	}

	text := resp.Candidates[0].Content.Parts[0].Text

	// Parse the JSON response
	var result AnalysisResult
	if err := json.Unmarshal([]byte(text), &result); err != nil {
		// Try to extract JSON from the response
		return nil, fmt.Errorf("failed to parse analysis result: %w (raw: %s)", err, text)
	}

	return &result, nil
}

// AnalyzeBatch processes multiple images in sequence
func (c *GeminiClient) AnalyzeBatch(ctx context.Context, images []struct {
	ImageBase64 string
	MimeType    string
}) ([]*AnalysisResult, error) {
	results := make([]*AnalysisResult, len(images))

	for i, img := range images {
		result, err := c.AnalyzeImage(ctx, img.ImageBase64, img.MimeType)
		if err != nil {
			results[i] = &AnalysisResult{
				MineralType: "unknown",
				Confidence:  0,
				Description: fmt.Sprintf("Analysis failed: %s", err.Error()),
				Notes:       "Batch analysis error",
			}
			continue
		}
		results[i] = result
	}

	return results, nil
}

// GenerateReportSummary generates a summary for an investor report
func (c *GeminiClient) GenerateReportSummary(ctx context.Context, samples []map[string]interface{}) (string, error) {
	samplesJSON, err := json.Marshal(samples)
	if err != nil {
		return "", fmt.Errorf("failed to marshal samples: %w", err)
	}

	prompt := fmt.Sprintf(`You are a mining investment analyst for AfriMine, a mineral detection platform in Kenya.

Based on the following sample analysis data, generate a concise investor report summary. The summary should cover:
1. Overview of minerals detected
2. Total estimated value
3. Quality assessment
4. Investment potential and risks
5. Recommendations

Sample data:
%s

Write a professional but accessible summary suitable for potential investors. Keep it under 500 words.`, string(samplesJSON))

	req := GeminiRequest{
		Contents: []GeminiContent{
			{
				Parts: []GeminiPart{
					{Text: prompt},
				},
			},
		},
		GenerationConfig: &GenerationConfig{
			Temperature:     0.4,
			MaxOutputTokens: 2048,
		},
	}

	resp, err := c.sendRequest(ctx, req)
	if err != nil {
		return "", fmt.Errorf("gemini API error: %w", err)
	}

	if resp.Error != nil {
		return "", fmt.Errorf("gemini API error %d: %s", resp.Error.Code, resp.Error.Message)
	}

	if len(resp.Candidates) == 0 || len(resp.Candidates[0].Content.Parts) == 0 {
		return "", fmt.Errorf("no response from Gemini API")
	}

	return resp.Candidates[0].Content.Parts[0].Text, nil
}

func (c *GeminiClient) sendRequest(ctx context.Context, req GeminiRequest) (*GeminiResponse, error) {
	body, err := json.Marshal(req)
	if err != nil {
		return nil, fmt.Errorf("failed to marshal request: %w", err)
	}

	url := fmt.Sprintf("%s/models/%s:generateContent?key=%s", c.config.BaseURL, c.config.Model, c.config.APIKey)

	httpReq, err := http.NewRequestWithContext(ctx, "POST", url, bytes.NewReader(body))
	if err != nil {
		return nil, fmt.Errorf("failed to create request: %w", err)
	}
	httpReq.Header.Set("Content-Type", "application/json")

	httpResp, err := c.httpClient.Do(httpReq)
	if err != nil {
		return nil, fmt.Errorf("failed to send request: %w", err)
	}
	defer httpResp.Body.Close()

	respBody, err := io.ReadAll(httpResp.Body)
	if err != nil {
		return nil, fmt.Errorf("failed to read response: %w", err)
	}

	if httpResp.StatusCode != http.StatusOK {
		return nil, fmt.Errorf("API returned status %d: %s", httpResp.StatusCode, string(respBody))
	}

	var geminiResp GeminiResponse
	if err := json.Unmarshal(respBody, &geminiResp); err != nil {
		return nil, fmt.Errorf("failed to unmarshal response: %w", err)
	}

	return &geminiResp, nil
}
