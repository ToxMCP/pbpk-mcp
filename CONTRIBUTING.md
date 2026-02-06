# Contributing

Thanks for contributing to PBPK MCP.

## Development Setup

1. Clone the repository.
2. Create a virtual environment.
3. Install dependencies:

```bash
python -m pip install --upgrade pip
python -m pip install -e '.[dev]'
```

## Local Quality Gates

Run these before opening a pull request:

```bash
make lint
make type
make test
```

Optional heavier checks:

```bash
make test-e2e
make compliance
make benchmark
```

## Pull Request Guidelines

- Keep changes focused and small where possible.
- Add or update tests for behavior changes.
- Update docs when APIs, config, or workflows change.
- Include a concise summary and validation notes in the PR description.

## Commit Style

Conventional commit prefixes are recommended (`feat:`, `fix:`, `docs:`, `chore:`, `test:`).

## License

By submitting a contribution, you agree that your contributions are licensed under the Apache License 2.0 in this repository.
