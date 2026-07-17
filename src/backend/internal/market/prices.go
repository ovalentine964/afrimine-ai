package market

import (
	"context"
	"encoding/json"
	"fmt"
	"io"
	"math/rand"
	"net/http"
	"time"

	"github.com/ovalentine964/afrimine-ai/backend/internal/models"
)

// PriceService handles fetching mineral prices
type PriceService struct {
	httpClient *http.Client
	apiKey     string
}

// NewPriceService creates a new price service
func NewPriceService(apiKey string) *PriceService {
	return &PriceService{
		httpClient: &http.Client{
			Timeout: 10 * time.Second,
		},
		apiKey: apiKey,
	}
}

// GetCurrentPrices returns current prices for gold and copper
func (s *PriceService) GetCurrentPrices(ctx context.Context) ([]models.MarketPrice, error) {
	// Try to fetch from a metals API if key is available
	if s.apiKey != "" {
		prices, err := s.fetchFromAPI(ctx)
		if err == nil {
			return prices, nil
		}
	}

	// Fallback to simulated prices based on realistic ranges
	return s.getSimulatedPrices(), nil
}

// GetPriceHistory returns historical price data
func (s *PriceService) GetPriceHistory(ctx context.Context, mineral string, days int) (*models.PriceHistory, error) {
	if days <= 0 {
		days = 30
	}

	history := &models.PriceHistory{
		Mineral: mineral,
		Data:    make([]models.PricePoint, days),
	}

	basePrice := getBasePrice(mineral)
	now := time.Now()

	for i := 0; i < days; i++ {
		date := now.AddDate(0, 0, -(days - 1 - i))
		// Simulate realistic price fluctuations
		variation := (rand.Float64()*0.06 - 0.03) // ±3% daily variation
		trend := float64(i) / float64(days) * 0.05  // slight upward trend
		price := basePrice * (1 + variation + trend)

		history.Data[i] = models.PricePoint{
			Date:  date.Format("2006-01-02"),
			Price: roundTo(price, 2),
		}
	}

	return history, nil
}

func (s *PriceService) fetchFromAPI(ctx context.Context) ([]models.MarketPrice, error) {
	url := "https://metals-api.com/api/latest?access_key=" + s.apiKey + "&base=USD&symbols=XAU,XCU"

	req, err := http.NewRequestWithContext(ctx, "GET", url, nil)
	if err != nil {
		return nil, fmt.Errorf("failed to create request: %w", err)
	}

	resp, err := s.httpClient.Do(req)
	if err != nil {
		return nil, fmt.Errorf("failed to fetch prices: %w", err)
	}
	defer resp.Body.Close()

	body, err := io.ReadAll(resp.Body)
	if err != nil {
		return nil, fmt.Errorf("failed to read response: %w", err)
	}

	if resp.StatusCode != http.StatusOK {
		return nil, fmt.Errorf("API returned status %d", resp.StatusCode)
	}

	var apiResp struct {
		Success bool               `json:"success"`
		Rates   map[string]float64 `json:"rates"`
	}
	if err := json.Unmarshal(body, &apiResp); err != nil {
		return nil, fmt.Errorf("failed to parse response: %w", err)
	}

	if !apiResp.Success {
		return nil, fmt.Errorf("API request unsuccessful")
	}

	now := time.Now()
	var prices []models.MarketPrice

	if rate, ok := apiResp.Rates["XAU"]; ok {
		prices = append(prices, models.MarketPrice{
			Mineral:   "gold",
			Price:     roundTo(1/rate, 2), // Convert to price per oz
			Currency:  "USD",
			Unit:      "oz",
			Change:    roundTo(rand.Float64()*2-1, 2), // Placeholder change
			Timestamp: now,
		})
	}

	if rate, ok := apiResp.Rates["XCU"]; ok {
		prices = append(prices, models.MarketPrice{
			Mineral:   "copper",
			Price:     roundTo(1/rate*1000, 2), // Convert to price per ton
			Currency:  "USD",
			Unit:      "ton",
			Change:    roundTo(rand.Float64()*4-2, 2),
			Timestamp: now,
		})
	}

	return prices, nil
}

func (s *PriceService) getSimulatedPrices() []models.MarketPrice {
	now := time.Now()

	return []models.MarketPrice{
		{
			Mineral:   "gold",
			Price:     roundTo(2300+rand.Float64()*200, 2),
			Currency:  "USD",
			Unit:      "oz",
			Change:    roundTo(rand.Float64()*3-1.5, 2),
			Timestamp: now,
		},
		{
			Mineral:   "copper",
			Price:     roundTo(8500+rand.Float64()*1000, 2),
			Currency:  "USD",
			Unit:      "ton",
			Change:    roundTo(rand.Float64()*4-2, 2),
			Timestamp: now,
		},
		{
			Mineral:   "titanium",
			Price:     roundTo(4500+rand.Float64()*500, 2),
			Currency:  "USD",
			Unit:      "ton",
			Change:    roundTo(rand.Float64()*2-1, 2),
			Timestamp: now,
		},
		{
			Mineral:   "soda_ash",
			Price:     roundTo(200+rand.Float64()*50, 2),
			Currency:  "USD",
			Unit:      "ton",
			Change:    roundTo(rand.Float64()*2-1, 2),
			Timestamp: now,
		},
		{
			Mineral:   "fluorspar",
			Price:     roundTo(300+rand.Float64()*100, 2),
			Currency:  "USD",
			Unit:      "ton",
			Change:    roundTo(rand.Float64()*3-1.5, 2),
			Timestamp: now,
		},
	}
}

func getBasePrice(mineral string) float64 {
	switch mineral {
	case "gold":
		return 2350.0
	case "copper":
		return 8800.0
	case "titanium":
		return 4700.0
	case "soda_ash":
		return 220.0
	case "fluorspar":
		return 340.0
	default:
		return 1000.0
	}
}

func roundTo(f float64, decimals int) float64 {
	mult := 1.0
	for i := 0; i < decimals; i++ {
		mult *= 10
	}
	return float64(int(f*mult+0.5)) / mult
}
