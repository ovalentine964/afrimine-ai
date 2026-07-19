package handlers

import (
	"net/http"
	"time"

	"github.com/go-chi/chi/v5"
	"github.com/ovalentine964/afrimine-ai/backend/middleware"
	"go.uber.org/zap"
)

// MarketHandler handles market data and commodity price endpoints.
type MarketHandler struct {
	logger *zap.Logger
}

// NewMarketHandler creates a new market handler.
func NewMarketHandler(logger *zap.Logger) *MarketHandler {
	return &MarketHandler{logger: logger}
}

// Routes registers market routes on the given router.
func (h *MarketHandler) Routes(r chi.Router) {
	r.Get("/prices", h.GetPrices)
	r.Get("/prices/{commodity}", h.GetCommodityPrice)
	r.Get("/valuation/{analysisID}", h.GetValuation)
}

// CommodityPrice represents a single commodity price.
type CommodityPrice struct {
	Commodity string    `json:"commodity"`
	PriceUSD  float64   `json:"price_usd"`
	Unit      string    `json:"unit"`
	Change24h float64   `json:"change_24h_pct"`
	Timestamp time.Time `json:"timestamp"`
	Source    string    `json:"source"`
}

// GetPrices handles GET /v1/market/prices — current commodity prices.
func (h *MarketHandler) GetPrices(w http.ResponseWriter, r *http.Request) {
	userID := middleware.GetUserID(r)

	h.logger.Info("market prices requested", zap.String("user_id", userID))

	// In production: fetch from metals.live API or Supabase cache.
	// Prices are cached in Supabase and refreshed hourly.
	now := time.Now().UTC()

	prices := []CommodityPrice{
		{
			Commodity: "gold",
			PriceUSD:  2350.00,
			Unit:      "USD/oz",
			Change24h: 0.5,
			Timestamp: now,
			Source:    "metals.live",
		},
		{
			Commodity: "copper",
			PriceUSD:  9200.00,
			Unit:      "USD/tonne",
			Change24h: -0.3,
			Timestamp: now,
			Source:    "LME",
		},
		{
			Commodity: "silver",
			PriceUSD:  28.50,
			Unit:      "USD/oz",
			Change24h: 1.2,
			Timestamp: now,
			Source:    "metals.live",
		},
		{
			Commodity: "titanium",
			PriceUSD:  7500.00,
			Unit:      "USD/tonne",
			Change24h: 0.0,
			Timestamp: now,
			Source:    "Kitco",
		},
	}

	writeJSON(w, http.StatusOK, map[string]interface{}{
		"prices":    prices,
		"cached_at": now,
		"source":    "metals.live + LME",
	})
}

// GetCommodityPrice handles GET /v1/market/prices/{commodity}.
func (h *MarketHandler) GetCommodityPrice(w http.ResponseWriter, r *http.Request) {
	commodity := chi.URLParam(r, "commodity")

	h.logger.Info("commodity price requested", zap.String("commodity", commodity))

	// In production: fetch specific commodity from cache or API.
	now := time.Now().UTC()

	price := CommodityPrice{
		Commodity: commodity,
		PriceUSD:  0,
		Unit:      "USD",
		Timestamp: now,
		Source:    "metals.live",
	}

	switch commodity {
	case "gold":
		price.PriceUSD = 2350.00
		price.Unit = "USD/oz"
	case "copper":
		price.PriceUSD = 9200.00
		price.Unit = "USD/tonne"
	case "silver":
		price.PriceUSD = 28.50
		price.Unit = "USD/oz"
	case "titanium":
		price.PriceUSD = 7500.00
		price.Unit = "USD/tonne"
	default:
		writeError(w, http.StatusNotFound, "commodity not found: "+commodity)
		return
	}

	writeJSON(w, http.StatusOK, price)
}

// ValuationResponse represents a deposit valuation.
type ValuationResponse struct {
	AnalysisID         string             `json:"analysis_id"`
	CommodityPrices    map[string]float64 `json:"commodity_prices"`
	EstimatedGrade     float64            `json:"estimated_grade"`
	GradeUnit          string             `json:"grade_unit"`
	DepositValueUSD    float64            `json:"deposit_value_usd"`
	CutOffGrade        float64            `json:"cut_off_grade"`
	RoyaltyEstimateUSD float64            `json:"royalty_estimate_usd"`
	PriceTrend         string             `json:"price_trend"`
	CalculatedAt       time.Time          `json:"calculated_at"`
}

// GetValuation handles GET /v1/market/valuation/{analysisID}.
func (h *MarketHandler) GetValuation(w http.ResponseWriter, r *http.Request) {
	analysisID := chi.URLParam(r, "analysisID")
	userID := middleware.GetUserID(r)

	h.logger.Info("valuation requested",
		zap.String("analysis_id", analysisID),
		zap.String("user_id", userID),
	)

	// In production:
	// 1. Fetch analysis results from Supabase
	// 2. Get current commodity prices
	// 3. Calculate NPV, DCF, royalty per Kenya Mining Act
	// This is the Market Agent's job — could also be done server-side for simple cases.

	writeJSON(w, http.StatusOK, ValuationResponse{
		AnalysisID: analysisID,
		CommodityPrices: map[string]float64{
			"gold": 2350.00,
		},
		EstimatedGrade:     5.2,
		GradeUnit:          "g/t",
		DepositValueUSD:    125000,
		CutOffGrade:        1.0,
		RoyaltyEstimateUSD: 6250,
		PriceTrend:         "stable",
		CalculatedAt:       time.Now().UTC(),
	})
}
