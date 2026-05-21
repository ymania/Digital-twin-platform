# Contributing

Thank you for your interest in contributing! This is a learning project, so contributions that improve clarity, correctness, or educational value are especially welcome.

## Getting Started

1. Fork the repository and clone your fork.
2. Follow the [Quick Start](README.md#quick-start) to get the stack running locally.
3. Create a feature branch: `git checkout -b feature/your-idea`

## What to Work On

Good first contributions:
- Additional sensors (CO₂, noise, motion)
- Unit tests for `simulator.py` physics model
- Additional Grafana panels
- Alerts (e.g. Grafana alerting when temperature exceeds threshold)
- Improved 3D room furniture / layout in `viz3d/index.html`

## Conventions

- **MQTT topics**: follow the `room/<sensor>` pattern; add the new topic to the bridge's `TOPIC_MAP`.
- **InfluxDB measurement**: all data goes into `room_environment` with tag `location=room1`.
- **Python style**: PEP 8, no external formatters required — just keep it readable.
- **Docker**: any new service belongs in `docker-compose.yml` and should read config from environment variables (never hardcode credentials).

## Pull Request Checklist

- [ ] Stack starts cleanly with `docker compose up -d` after your changes
- [ ] No secrets or `.env` files committed
- [ ] `README.md` updated if you've added a new service or changed a port
- [ ] Short, descriptive commit messages

## Reporting Issues

Open a GitHub issue with:
- Your OS and Docker version
- The exact command you ran
- The full error output (use a code block)
