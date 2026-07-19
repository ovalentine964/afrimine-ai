package a2a

import (
	"bufio"
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"strings"
	"time"

	"github.com/google/uuid"
	"go.uber.org/zap"
)

// Client communicates with the Python LangGraph A2A bridge via JSON-RPC 2.0.
type Client struct {
	baseURL    string
	httpClient *http.Client
	logger     *zap.Logger
}

// NewClient creates an A2A client pointing at the LangGraph bridge.
func NewClient(baseURL string, timeout time.Duration, logger *zap.Logger) *Client {
	return &Client{
		baseURL: strings.TrimRight(baseURL, "/"),
		httpClient: &http.Client{
			Timeout: timeout,
		},
		logger: logger,
	}
}

// --- JSON-RPC 2.0 types ---

type jsonrpcRequest struct {
	JSONRPC string      `json:"jsonrpc"`
	Method  string      `json:"method"`
	Params  interface{} `json:"params"`
	ID      string      `json:"id"`
}

type jsonrpcResponse struct {
	JSONRPC string          `json:"jsonrpc"`
	ID      string          `json:"id"`
	Result  json.RawMessage `json:"result,omitempty"`
	Error   *jsonrpcError   `json:"error,omitempty"`
}

type jsonrpcError struct {
	Code    int    `json:"code"`
	Message string `json:"message"`
}

// --- A2A task types ---

// TaskMessage is the A2A message format.
type TaskMessage struct {
	Role  string      `json:"role"`
	Parts []MessagePart `json:"parts"`
}

// MessagePart represents a single part of an A2A message.
type MessagePart struct {
	Type     string      `json:"type"`
	Text     string      `json:"text,omitempty"`
	Data     interface{} `json:"data,omitempty"`
	MimeType string      `json:"mimeType,omitempty"`
}

// TaskSendParams are params for tasks/send.
type TaskSendParams struct {
	ID      string       `json:"id"`
	Message TaskMessage  `json:"message"`
}

// TaskResult is the A2A task result.
type TaskResult struct {
	ID       string      `json:"id"`
	Status   TaskStatus  `json:"status"`
	Artifacts []Artifact `json:"artifacts,omitempty"`
}

// TaskStatus represents the state of an A2A task.
type TaskStatus struct {
	State   string `json:"state"`
	Message string `json:"message,omitempty"`
}

// Artifact holds output parts from an A2A task.
type Artifact struct {
	Parts []MessagePart `json:"parts"`
}

// --- Public API ---

// InvokeResult is the parsed result of an A2A invocation.
type InvokeResult struct {
	TaskID       string                 `json:"task_id"`
	State        string                 `json:"state"`
	Message      string                 `json:"message,omitempty"`
	AgentOutputs map[string]interface{} `json:"agent_outputs,omitempty"`
	TextOutput   string                 `json:"text_output,omitempty"`
}

// Invoke sends a synchronous tasks/send request to the A2A bridge.
func (c *Client) Invoke(ctx context.Context, agentID string, input map[string]interface{}, userID string) (*InvokeResult, error) {
	taskID := uuid.New().String()

	params := TaskSendParams{
		ID: taskID,
		Message: TaskMessage{
			Role: "user",
			Parts: []MessagePart{
				{
					Type: "data",
					Data: map[string]interface{}{
						"location":     input["location"],
						"sample_data":  input["sample_data"],
						"user_id":      userID,
					},
				},
			},
		},
	}

	// Add optional fields.
	if notes, ok := input["notes"].(string); ok && notes != "" {
		params.Message.Parts = append(params.Message.Parts, MessagePart{
			Type: "text",
			Text: notes,
		})
	}

	if sat, ok := input["satellite_imagery"].(string); ok && sat != "" {
		params.Message.Parts[0].Data.(map[string]interface{})["satellite_imagery"] = sat
	}

	rpcReq := jsonrpcRequest{
		JSONRPC: "2.0",
		Method:  "tasks/send",
		Params:  params,
		ID:      taskID,
	}

	body, err := json.Marshal(rpcReq)
	if err != nil {
		return nil, fmt.Errorf("marshal request: %w", err)
	}

	endpoint := c.baseURL + "/a2a"
	if agentID != "" && agentID != "afrimine-pipeline" {
		endpoint = c.baseURL + "/a2a/" + agentID
	}

	c.logger.Info("A2A invoke",
		zap.String("task_id", taskID),
		zap.String("agent", agentID),
		zap.String("endpoint", endpoint),
	)

	req, err := http.NewRequestWithContext(ctx, http.MethodPost, endpoint, bytes.NewReader(body))
	if err != nil {
		return nil, fmt.Errorf("create request: %w", err)
	}
	req.Header.Set("Content-Type", "application/json")

	resp, err := c.httpClient.Do(req)
	if err != nil {
		return nil, fmt.Errorf("A2A request failed: %w", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		respBody, _ := io.ReadAll(resp.Body)
		return nil, fmt.Errorf("A2A bridge returned %d: %s", resp.StatusCode, string(respBody))
	}

	var rpcResp jsonrpcResponse
	if err := json.NewDecoder(resp.Body).Decode(&rpcResp); err != nil {
		return nil, fmt.Errorf("decode response: %w", err)
	}

	if rpcResp.Error != nil {
		return nil, fmt.Errorf("A2A error %d: %s", rpcResp.Error.Code, rpcResp.Error.Message)
	}

	return c.parseResult(rpcResp.Result)
}

// StreamEvent represents an SSE event from the A2A bridge.
type StreamEvent struct {
	TaskID string                 `json:"id"`
	Status string                 `json:"status"`
	Node   string                 `json:"node,omitempty"`
	Output map[string]interface{} `json:"output,omitempty"`
}

// InvokeStream sends a tasks/send_stream request and yields SSE events.
func (c *Client) InvokeStream(ctx context.Context, agentID string, input map[string]interface{}, userID string, callback func(StreamEvent)) (*InvokeResult, error) {
	taskID := uuid.New().String()

	params := TaskSendParams{
		ID: taskID,
		Message: TaskMessage{
			Role: "user",
			Parts: []MessagePart{
				{
					Type: "data",
					Data: map[string]interface{}{
						"location":    input["location"],
						"sample_data": input["sample_data"],
						"user_id":     userID,
					},
				},
			},
		},
	}

	if notes, ok := input["notes"].(string); ok && notes != "" {
		params.Message.Parts = append(params.Message.Parts, MessagePart{
			Type: "text",
			Text: notes,
		})
	}

	rpcReq := jsonrpcRequest{
		JSONRPC: "2.0",
		Method:  "tasks/send_stream",
		Params:  params,
		ID:      taskID,
	}

	body, err := json.Marshal(rpcReq)
	if err != nil {
		return nil, fmt.Errorf("marshal request: %w", err)
	}

	endpoint := c.baseURL + "/a2a"
	if agentID != "" && agentID != "afrimine-pipeline" {
		endpoint = c.baseURL + "/a2a/" + agentID
	}

	req, err := http.NewRequestWithContext(ctx, http.MethodPost, endpoint, bytes.NewReader(body))
	if err != nil {
		return nil, fmt.Errorf("create request: %w", err)
	}
	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("Accept", "text/event-stream")

	resp, err := c.httpClient.Do(req)
	if err != nil {
		return nil, fmt.Errorf("A2A stream request failed: %w", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		respBody, _ := io.ReadAll(resp.Body)
		return nil, fmt.Errorf("A2A bridge returned %d: %s", resp.StatusCode, string(respBody))
	}

	// Parse SSE events.
	var lastResult *InvokeResult
	scanner := bufio.NewScanner(resp.Body)
	for scanner.Scan() {
		line := scanner.Text()
		if !strings.HasPrefix(line, "data: ") {
			continue
		}

		data := strings.TrimPrefix(line, "data: ")
		var event StreamEvent
		if err := json.Unmarshal([]byte(data), &event); err != nil {
			c.logger.Warn("failed to parse SSE event", zap.String("data", data), zap.Error(err))
			continue
		}

		if callback != nil {
			callback(event)
		}

		// Check for terminal states.
		if event.Status == "completed" || event.Status == "failed" {
			lastResult = &InvokeResult{
				TaskID: event.TaskID,
				State:  event.Status,
			}
		}
	}

	if err := scanner.Err(); err != nil {
		return nil, fmt.Errorf("SSE read error: %w", err)
	}

	if lastResult == nil {
		return &InvokeResult{TaskID: taskID, State: "unknown"}, nil
	}

	return lastResult, nil
}

// GetTask retrieves the result of a previously submitted task.
func (c *Client) GetTask(ctx context.Context, taskID string) (*InvokeResult, error) {
	rpcReq := jsonrpcRequest{
		JSONRPC: "2.0",
		Method:  "tasks/get",
		Params:  map[string]string{"id": taskID},
		ID:      uuid.New().String(),
	}

	body, err := json.Marshal(rpcReq)
	if err != nil {
		return nil, fmt.Errorf("marshal request: %w", err)
	}

	req, err := http.NewRequestWithContext(ctx, http.MethodPost, c.baseURL+"/a2a", bytes.NewReader(body))
	if err != nil {
		return nil, fmt.Errorf("create request: %w", err)
	}
	req.Header.Set("Content-Type", "application/json")

	resp, err := c.httpClient.Do(req)
	if err != nil {
		return nil, fmt.Errorf("A2A request failed: %w", err)
	}
	defer resp.Body.Close()

	var rpcResp jsonrpcResponse
	if err := json.NewDecoder(resp.Body).Decode(&rpcResp); err != nil {
		return nil, fmt.Errorf("decode response: %w", err)
	}

	if rpcResp.Error != nil {
		return nil, fmt.Errorf("A2A error %d: %s", rpcResp.Error.Code, rpcResp.Error.Message)
	}

	return c.parseResult(rpcResp.Result)
}

// HealthCheck verifies the A2A bridge is reachable.
func (c *Client) HealthCheck(ctx context.Context) error {
	req, err := http.NewRequestWithContext(ctx, http.MethodGet, c.baseURL+"/health", nil)
	if err != nil {
		return err
	}

	resp, err := c.httpClient.Do(req)
	if err != nil {
		return fmt.Errorf("A2A bridge unreachable: %w", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		return fmt.Errorf("A2A bridge unhealthy: %d", resp.StatusCode)
	}

	return nil
}

// parseResult extracts structured data from a JSON-RPC result.
func (c *Client) parseResult(raw json.RawMessage) (*InvokeResult, error) {
	var task TaskResult
	if err := json.Unmarshal(raw, &task); err != nil {
		return nil, fmt.Errorf("unmarshal task result: %w", err)
	}

	result := &InvokeResult{
		TaskID: task.ID,
		State:  task.Status.State,
		Message: task.Status.Message,
	}

	// Extract artifacts.
	for _, artifact := range task.Artifacts {
		for _, part := range artifact.Parts {
			switch part.Type {
			case "text":
				result.TextOutput = part.Text
			case "data":
				if dataMap, ok := part.Data.(map[string]interface{}); ok {
					result.AgentOutputs = dataMap
				}
			}
		}
	}

	return result, nil
}
