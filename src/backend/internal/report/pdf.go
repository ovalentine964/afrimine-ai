package report

import (
	"context"
	"fmt"
	"os"
	"path/filepath"
	"time"

	"github.com/google/uuid"
	"github.com/jung-kurt/gofpdf"
	"github.com/ovalentine964/afrimine-ai/backend/internal/ai"
	"github.com/ovalentine964/afrimine-ai/backend/internal/models"
)

// Generator handles PDF report generation
type Generator struct {
	gemini     *ai.GeminiClient
	outputDir  string
}

// NewGenerator creates a new report generator
func NewGenerator(gemini *ai.GeminiClient, outputDir string) *Generator {
	if outputDir == "" {
		outputDir = "./reports"
	}
	os.MkdirAll(outputDir, 0755)

	return &Generator{
		gemini:    gemini,
		outputDir: outputDir,
	}
}

// GenerateReport generates an investor PDF report from samples and analyses
func (g *Generator) GenerateReport(ctx context.Context, user *models.User, samples []models.Sample, analyses []models.Analysis) (string, error) {
	reportID := uuid.New().String()
	filename := fmt.Sprintf("report_%s_%s.pdf", user.ID[:8], reportID[:8])
	filePath := filepath.Join(g.outputDir, filename)

	// Generate AI summary if Gemini is available
	summary := g.generateDefaultSummary(samples, analyses)
	if g.gemini != nil {
		sampleData := makeSampleData(samples, analyses)
		if aiSummary, err := g.gemini.GenerateReportSummary(ctx, sampleData); err == nil && aiSummary != "" {
			summary = aiSummary
		}
	}

	// Generate PDF
	err := g.createPDF(filePath, user, samples, analyses, summary)
	if err != nil {
		return "", fmt.Errorf("failed to generate PDF: %w", err)
	}

	return filePath, nil
}

func (g *Generator) createPDF(filePath string, user *models.User, samples []models.Sample, analyses []models.Analysis, summary string) error {
	pdf := gofpdf.New("P", "mm", "A4", "")
	pdf.SetAutoPageBreak(true, 20)

	// Title page
	pdf.AddPage()
	pdf.SetFont("Helvetica", "B", 28)
	pdf.SetTextColor(30, 60, 120)
	pdf.CellFormat(0, 40, "", "", 0, "C", false, 0, "")
	pdf.Ln(10)
	pdf.CellFormat(0, 15, "AfriMine AI", "", 0, "C", false, 0, "")
	pdf.Ln(10)
	pdf.SetFont("Helvetica", "", 16)
	pdf.SetTextColor(80, 80, 80)
	pdf.CellFormat(0, 10, "Mineral Analysis Report", "", 0, "C", false, 0, "")
	pdf.Ln(20)

	pdf.SetFont("Helvetica", "", 12)
	pdf.SetTextColor(60, 60, 60)
	pdf.CellFormat(0, 8, fmt.Sprintf("Prepared for: %s", user.Name), "", 0, "C", false, 0, "")
	pdf.Ln(6)
	pdf.CellFormat(0, 8, fmt.Sprintf("Date: %s", time.Now().Format("January 2, 2006")), "", 0, "C", false, 0, "")
	pdf.Ln(6)
	pdf.CellFormat(0, 8, fmt.Sprintf("Total Samples: %d", len(samples)), "", 0, "C", false, 0, "")

	// Summary page
	pdf.AddPage()
	pdf.SetFont("Helvetica", "B", 18)
	pdf.SetTextColor(30, 60, 120)
	pdf.CellFormat(0, 12, "Executive Summary", "", 0, "L", false, 0, "")
	pdf.Ln(10)

	pdf.SetFont("Helvetica", "", 11)
	pdf.SetTextColor(40, 40, 40)
	pdf.MultiCell(0, 6, summary, "", "L", false)
	pdf.Ln(8)

	// Mineral statistics
	pdf.SetFont("Helvetica", "B", 18)
	pdf.SetTextColor(30, 60, 120)
	pdf.CellFormat(0, 12, "Mineral Statistics", "", 0, "L", false, 0, "")
	pdf.Ln(10)

	mineralStats := calculateStats(analyses)
	pdf.SetFont("Helvetica", "B", 11)
	pdf.SetFillColor(230, 240, 250)
	pdf.CellFormat(60, 8, "Mineral", "1", 0, "C", true, 0, "")
	pdf.CellFormat(30, 8, "Samples", "1", 0, "C", true, 0, "")
	pdf.CellFormat(40, 8, "Avg Confidence", "1", 0, "C", true, 0, "")
	pdf.CellFormat(40, 8, "Est. Value (USD)", "1", 0, "C", true, 0, "")
	pdf.Ln(-1)

	pdf.SetFont("Helvetica", "", 10)
	totalValue := 0.0
	for mineral, stat := range mineralStats {
		pdf.CellFormat(60, 7, mineral, "1", 0, "L", false, 0, "")
		pdf.CellFormat(30, 7, fmt.Sprintf("%d", stat.Count), "1", 0, "C", false, 0, "")
		pdf.CellFormat(40, 7, fmt.Sprintf("%.1f%%", stat.AvgConfidence*100), "1", 0, "C", false, 0, "")
		pdf.CellFormat(40, 7, fmt.Sprintf("$%.2f", stat.TotalValue), "1", 0, "R", false, 0, "")
		pdf.Ln(-1)
		totalValue += stat.TotalValue
	}

	pdf.SetFont("Helvetica", "B", 11)
	pdf.CellFormat(130, 8, "TOTAL ESTIMATED VALUE", "1", 0, "R", true, 0, "")
	pdf.CellFormat(40, 8, fmt.Sprintf("$%.2f", totalValue), "1", 0, "R", true, 0, "")
	pdf.Ln(12)

	// Detailed analysis pages
	pdf.AddPage()
	pdf.SetFont("Helvetica", "B", 18)
	pdf.SetTextColor(30, 60, 120)
	pdf.CellFormat(0, 12, "Detailed Analysis", "", 0, "L", false, 0, "")
	pdf.Ln(10)

	sampleMap := make(map[string]models.Sample)
	for _, s := range samples {
		sampleMap[s.ID] = s
	}

	for i, analysis := range analyses {
		if pdf.GetY() > 250 {
			pdf.AddPage()
		}

		sample := sampleMap[analysis.SampleID]

		pdf.SetFont("Helvetica", "B", 13)
		pdf.SetTextColor(30, 60, 120)
		pdf.CellFormat(0, 8, fmt.Sprintf("#%d - %s", i+1, sample.Name), "", 0, "L", false, 0, "")
		pdf.Ln(6)

		pdf.SetFont("Helvetica", "", 10)
		pdf.SetTextColor(40, 40, 40)

		fields := []struct{ label, value string }{
			{"Mineral Type", analysis.MineralType},
			{"Confidence", fmt.Sprintf("%.1f%%", analysis.Confidence*100)},
			{"Estimated Value", fmt.Sprintf("$%.2f %s", analysis.EstimatedValue, analysis.Currency)},
			{"Location", fmt.Sprintf("%.4f, %.4f", sample.Latitude, sample.Longitude)},
			{"Status", analysis.Status},
			{"Date", analysis.CreatedAt.Format("Jan 2, 2006 15:04")},
		}

		for _, f := range fields {
			pdf.SetFont("Helvetica", "B", 10)
			pdf.CellFormat(35, 6, f.label+":", "", 0, "L", false, 0, "")
			pdf.SetFont("Helvetica", "", 10)
			pdf.CellFormat(0, 6, f.value, "", 0, "L", false, 0, "")
			pdf.Ln(5)
		}

		if analysis.Description != "" {
			pdf.Ln(2)
			pdf.SetFont("Helvetica", "I", 9)
			pdf.MultiCell(0, 5, analysis.Description, "", "L", false)
		}

		pdf.Ln(6)
		pdf.SetDrawColor(200, 200, 200)
		pdf.Line(10, pdf.GetY(), 200, pdf.GetY())
		pdf.Ln(6)
	}

	// Footer disclaimer
	pdf.AddPage()
	pdf.SetFont("Helvetica", "B", 18)
	pdf.SetTextColor(30, 60, 120)
	pdf.CellFormat(0, 12, "Disclaimer", "", 0, "L", false, 0, "")
	pdf.Ln(10)

	pdf.SetFont("Helvetica", "", 10)
	pdf.SetTextColor(80, 80, 80)
	disclaimer := `This report is generated by AfriMine AI's mineral analysis system. The analysis results are based on AI image recognition and should be verified by professional geologists before making investment decisions.

The estimated values are approximations based on current market prices and may vary significantly based on actual mineral quality, quantity, extraction costs, and market conditions.

AfriMine AI and its operators make no guarantees regarding the accuracy of these analyses or the actual value of any mineral deposits identified.

For professional geological assessment, please consult a certified geologist or mining engineer.`
	pdf.MultiCell(0, 5, disclaimer, "", "L", false)

	return pdf.OutputFileAndClose(filePath)
}

type mineralStat struct {
	Count         int
	AvgConfidence float64
	TotalValue    float64
}

func calculateStats(analyses []models.Analysis) map[string]*mineralStat {
	stats := make(map[string]*mineralStat)

	for _, a := range analyses {
		mt := a.MineralType
		if mt == "" {
			mt = "Unknown"
		}

		if _, ok := stats[mt]; !ok {
			stats[mt] = &mineralStat{}
		}
		stats[mt].Count++
		stats[mt].AvgConfidence += a.Confidence
		stats[mt].TotalValue += a.EstimatedValue
	}

	for _, s := range stats {
		if s.Count > 0 {
			s.AvgConfidence /= float64(s.Count)
		}
	}

	return stats
}

func makeSampleData(samples []models.Sample, analyses []models.Analysis) []map[string]interface{} {
	analysisMap := make(map[string]models.Analysis)
	for _, a := range analyses {
		analysisMap[a.SampleID] = a
	}

	var data []map[string]interface{}
	for _, s := range samples {
		d := map[string]interface{}{
			"name":        s.Name,
			"description": s.Description,
			"latitude":    s.Latitude,
			"longitude":   s.Longitude,
		}
		if a, ok := analysisMap[s.ID]; ok {
			d["mineral_type"] = a.MineralType
			d["confidence"] = a.Confidence
			d["estimated_value"] = a.EstimatedValue
			d["analysis_description"] = a.Description
		}
		data = append(data, d)
	}
	return data
}

func (g *Generator) generateDefaultSummary(samples []models.Sample, analyses []models.Analysis) string {
	totalValue := 0.0
	mineralCount := make(map[string]int)

	for _, a := range analyses {
		totalValue += a.EstimatedValue
		if a.MineralType != "" {
			mineralCount[a.MineralType]++
		}
	}

	summary := fmt.Sprintf("This report covers %d mineral samples submitted by the user. ", len(samples))
	summary += fmt.Sprintf("A total of %d analyses have been completed. ", len(analyses))
	summary += fmt.Sprintf("The combined estimated value of all analyzed minerals is $%.2f USD. ", totalValue)

	if len(mineralCount) > 0 {
		summary += "Minerals identified include: "
		first := true
		for mineral, count := range mineralCount {
			if !first {
				summary += ", "
			}
			summary += fmt.Sprintf("%s (%d samples)", mineral, count)
			first = false
		}
		summary += "."
	}

	return summary
}
