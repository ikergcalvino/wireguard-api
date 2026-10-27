# Contributing to wireguard-api

Thanks for your interest in contributing! Here's how to get started.

## Development setup

```bash
git clone https://github.com/ikergcalvino/wireguard-api.git
cd wireguard-api
python -m venv .venv && source .venv/bin/activate
make install-dev   # pip install -e ".[dev]"
```

## Workflow

1. Fork the repo and create a branch from `develop`.
2. Make your changes.
3. Run all checks:

   ```bash
   make check   # lint + type + test
   ```

4. Open a pull request against `develop`.

## Coding standards

- **Formatter / Linter**: [Ruff](https://docs.astral.sh/ruff/) — run `make format` before committing.
- **Type checking**: [ty](https://github.com/astral-sh/ty) — run `make type`.
- **Tests**: [pytest](https://docs.pytest.org/) — run `make test`. Add tests for new features and bug fixes.
- **Commits**: Use clear, concise commit messages.

## Reporting bugs

Please use the [Bug Report](https://github.com/ikergcalvino/wireguard-api/issues/new?template=bug_report.yml) issue template.

## Requesting features

Please use the [Feature Request](https://github.com/ikergcalvino/wireguard-api/issues/new?template=feature_request.yml) issue template.
