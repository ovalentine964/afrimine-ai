package a2a

import (
	"context"
	"encoding/json"
	"fmt"
	"net/http"
	"time"

	"go.uber.org/zap"
)

// AgentCard represents an A2A agent's metadata (from /.well-known/agent.json).
type AgentCard struct {
	Name               string                 `json:"name"`
	Description        string                 `json:"description"`
	URL                string                 `json:"url"`
	Version            string                 `json:"version"`
	Capabilities       AgentCapabilities      `json:"capabilities"`
	DefaultInputModes  []string               `json:"defaultInputModes,omitempty"`
	DefaultOutputModes []string               `json:"defaultOutputModes,omitempty"`
	Skills             []AgentSkill           `json:"skills,omitempty"`
	Authentication     *AgentAuthentication   `json:"authentication,omitempty"`
}

// AgentCapabilities describes what an agent can do.
type AgentCapabilities struct {
	Streaming             bool `json:"streaming"`
	PushNotifications     bool `json:"pushNotifications,omitempty"`
	StateTransitionHistory bool `json:"stateTransitionHistory,omitempty"`
}

// AgentSkill is a specific capability of an agent.
type AgentSkill struct {
	ID          string      `json:"id"`
	Name        string      `json:"name"`
	Description string      `json:"description,omitempty"`
	InputSchema interface{} `json:"inputSchema,omitempty"`
}

// AgentAuthentication describes auth requirements.
type AgentAuthentication struct {
	Schemes []string `json:"schemes"`
}

// Registry holds discovered agent cards.
type Registry struct {
	baseURL string
	cards   map[string]*AgentCard
	client  *http.Client
	logger  *zap.Logger
}

// NewRegistry creates an agent card registry for the given A2A bridge URL.
func NewRegistry(baseURL string, logger *zap.Logger) *Registry {
	return &Registry{
		baseURL: baseURL,
		cards:   make(map[string]*AgentCard),
		client: &http.Client{
			Timeout: 10 * time.Second,
		},
		logger: logger,
	}
}

// Discover fetches all agent cards from the A2A bridge.
func (r *Registry) Discover(ctx context.Context) error {
	// Fetch the primary pipeline card.
	card, err := r.fetchCard(ctx, "/.well-known/agent.json")
	if err != nil {
		return fmt.Errorf("fetch primary agent card: %w", err)
	}
	r.cards["afrimine-pipeline"] = card

	// Fetch the agents list endpoint.
	agents, err := r.fetchAgentList(ctx)
	if err != nil {
		r.logger.Warn("failed to fetch agent list, using primary card only", zap.Error(err))
		return nil
	}

	for _, agent := range agents {
		if agent.Name != "" {
			r.cards[agent.Name] = &agent
		}
	}

	r.logger.Info("agent cards discovered",
		zap.Int("count", len(r.cards)),
	)

	return nil
}

// GetCard returns the agent card for the given agent ID.
func (r *Registry) GetCard(agentID string) (*AgentCard, bool) {
	card, ok := r.cards[agentID]
	return card, ok
}

// ListCards returns all discovered agent cards.
func (r *Registry) ListCards() map[string]*AgentCard {
	result := make(map[string]*AgentCard, len(r.cards))
	for k, v := range r.cards {
		result[k] = v
	}
	return result
}

// IsStreamingSupported checks if the pipeline supports streaming.
func (r *Registry) IsStreamingSupported() bool {
	card, ok := r.cards["afrimine-pipeline"]
	if !ok {
		return false
	}
	return card.Capabilities.Streaming
}

// fetchCard retrieves a single agent card by URL path.
func (r *Registry) fetchCard(ctx context.Context, path string) (*AgentCard, error) {
	req, err := http.NewRequestWithContext(ctx, http.MethodGet, r.baseURL+path, nil)
	if err != nil {
		return nil, err
	}
	req.Header.Set("Accept", "application/json")

	resp, err := r.client.Do(req)
	if err != nil {
		return nil, err
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		return nil, fmt.Errorf("agent card at %s returned %d", path, resp.StatusCode)
	}

	var card AgentCard
	if err := json.NewDecoder(resp.Body).Decode(&card); err != nil {
		return nil, fmt.Errorf("decode agent card: %w", err)
	}

	return &card, nil
}

// fetchAgentList retrieves all available agents from the /agents endpoint.
func (r *Registry) fetchAgentList(ctx context.Context) ([]AgentCard, error) {
	req, err := http.NewRequestWithContext(ctx, http.MethodGet, r.baseURL+"/agents", nil)
	if err != nil {
		return nil, err
	}
	req.Header.Set("Accept", "application/json")

	resp, err := r.client.Do(req)
	if err != nil {
		return nil, err
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		return nil, fmt.Errorf("/agents returned %d", resp.StatusCode)
	}

	var wrapper struct {
		Agents []AgentCard `json:"agents"`
	}
	if err := json.NewDecoder(resp.Body).Decode(&wrapper); err != nil {
		return nil, fmt.Errorf("decode agents list: %w", err)
	}

	return wrapper.Agents, nil
}
