# Contributing to AfriMine AI

Thank you for your interest in contributing to AfriMine AI!

## How to Contribute

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## Development Setup

### Prerequisites
- Go 1.22+
- Flutter 3.19+
- Python 3.11+
- PostgreSQL 16+
- Docker (optional)

### Running Locally
```bash
# Backend
cd src/backend && go run main.go

# Frontend
cd src/frontend && flutter pub get && flutter run

# AI Engine
cd src/ai-engine && pip install -r requirements.txt && python main.py
```

## Code Standards

### Go
- Follow [Effective Go](https://go.dev/doc/effective_go)
- Use `gofmt` and `golangci-lint`
- Write tests for all public functions

### Dart/Flutter
- Follow [Flutter style guide](https://flutter.dev/docs/development/tools/formatting)
- Use `flutter analyze` and `flutter format`
- Write widget tests for UI components

### Python
- Follow PEP 8
- Use type hints
- Write docstrings for all functions

## Commit Messages

Use conventional commits:
- `feat:` new feature
- `fix:` bug fix
- `docs:` documentation
- `style:` formatting
- `refactor:` code restructuring
- `test:` adding tests
- `chore:` maintenance

## Issues

- Use issue templates for bug reports and feature requests
- Include steps to reproduce for bugs
- Include use case for feature requests

## Code of Conduct

Be respectful. We're building this for mining communities in Africa. Every decision should serve their interests first.
