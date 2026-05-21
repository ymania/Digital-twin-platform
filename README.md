# Room Digital Twin

A minimal but end-to-end **digital twin** of a smart room. A Python simulator mimics physical IoT sensors (temperature, humidity, fan, light, power) and publishes readings over MQTT every 5 seconds. A bridge persists those readings to InfluxDB. Grafana renders live dashboards. A Three.js app renders the room in 3D and animates it in real time. Fan speed can be controlled remotely through the twin.

```
Simulator ──MQTT──► Bridge ──► InfluxDB ──► Grafana
                │                               (dashboards)
                └──WebSocket──► 3D Viz
                                (live room render)
Host
  └── control.py ──MQTT──► Simulator  (fan commands)
```

Built as a learning project to understand digital twin patterns end-to-end — not just the data, but the feedback loop between the virtual model and the "physical" device.

---

## Features

| What | How |
|---|---|
| 6 simulated sensors | temperature, humidity, fan state, fan speed, light, power |
| Physics model | daily sine-wave temperature curve, fan cooling effect, humidity drift |
| Auto-thermostat | fan turns ON > 25 °C, OFF < 22 °C |
| Remote control | send `ON`/`OFF` to the fan from the host |
| Time-series storage | InfluxDB 2.7 with Flux queries |
| Live dashboards | Grafana 10.4 — 8 panels, auto-refresh every 5 s |
| 3D visualisation | Three.js room with animated fan blades, temperature colour map, live sensor overlay |
| Architecture diagrams | Mermaid diagrams in `viz3d/diagrams.html` |
| Fully containerised | One `docker compose up` starts everything |

---

## Architecture

Six Docker services communicate over an internal bridge network:

```
┌─────────────────────────────────────────────────────────────┐
│  Docker network: digital-twin_default                       │
│                                                             │
│  ┌───────────┐  MQTT   ┌───────────┐  HTTP   ┌──────────┐  │
│  │ simulator │────────►│ mosquitto │◄────────│  bridge  │  │
│  └───────────┘ :1883   └───────────┘         └──────────┘  │
│                         :9001 (WS)                │         │
│                             ▲                     ▼         │
│                             │                ┌──────────┐   │
│                             │                │ influxdb │   │
│                             │                └──────────┘   │
│                             │                     │         │
│                          ┌──┴───┐            ┌────▼─────┐   │
│                          │viz3d │            │ grafana  │   │
│                          │nginx │            └──────────┘   │
│                          └──────┘                           │
└─────────────────────────────────────────────────────────────┘
  Host ports: 1883, 9001, 8086, 3000, 8080
```

See `viz3d/diagrams.html` (served at `http://localhost:8080/diagrams.html`) for interactive Mermaid diagrams showing the full data flow and message sequence.

---

## Prerequisites

| Tool | Version | Notes |
|---|---|---|
| Docker Desktop | 4.x or later | Includes Docker Compose v2 |
| Python | 3.9+ | Only for `control.py` on the host |
| Git | any | To clone the repo |

> **Windows users**: all Docker commands work in PowerShell or CMD. The `Makefile` targets require WSL2, Git Bash, or any POSIX shell. You can always use the `docker compose` commands directly (shown in each step below).

---

## Quick Start

### 1 — Clone the repository

```bash
git clone https://github.com/<your-username>/room-digital-twin.git
cd room-digital-twin
```

### 2 — Create your environment file

```bash
cp .env.example .env
```

Open `.env` and set your own values. The defaults work for local development, but **change the passwords and token before exposing any port to the internet**.

```env
INFLUXDB_USERNAME=admin
INFLUXDB_PASSWORD=your-strong-password
INFLUXDB_ORG=digital-twin
INFLUXDB_BUCKET=room_sensors
INFLUXDB_TOKEN=your-long-random-token

GRAFANA_ADMIN_USER=admin
GRAFANA_ADMIN_PASSWORD=your-strong-password
```

### 3 — Start the stack

```bash
docker compose up -d
# or: make up
```

Docker builds the two Python images on first run. This takes about 60 seconds.

Check everything is up:

```bash
docker compose ps
# or: make ps
```

You should see six services all in `running` state:

```
NAME         STATUS
mosquitto    running
influxdb     running
grafana      running
simulator    running
bridge       running
viz3d        running
```

### 4 — Open the interfaces

| Interface | URL | Credentials |
|---|---|---|
| Grafana dashboards | http://localhost:3000 | `GRAFANA_ADMIN_USER` / `GRAFANA_ADMIN_PASSWORD` from `.env` |
| 3D visualisation | http://localhost:8080 | no login |
| Architecture diagrams | http://localhost:8080/diagrams.html | no login |
| InfluxDB UI | http://localhost:8086 | `INFLUXDB_USERNAME` / `INFLUXDB_PASSWORD` from `.env` |

**Grafana**: navigate to **Dashboards → Digital Twin → Room Digital Twin**. Panels auto-refresh every 5 seconds. If the InfluxDB datasource shows a red error on first boot, wait 10–15 seconds for InfluxDB to finish initialising, then refresh the page.

**3D viz**: the green dot in the top-left indicates a live MQTT WebSocket connection. Fan blades spin when the fan is on; the ambient light shifts from cool to warm as temperature rises.

### 5 — Watch the logs (optional)

```bash
docker compose logs -f simulator bridge
# or: make logs
```

You will see the simulator printing a one-line summary every 5 seconds:

```
[simulator] tick=  42 | temp=24.31°C | hum=58.4% | fan=OFF @   0rpm | light=487.2lux | power=  5.3W
```

---

## Controlling the Fan

`control.py` publishes a command to the `room/fan/control` MQTT topic. The simulator receives it, applies the state immediately, and suppresses the auto-thermostat for 60 seconds.

### Install the host dependency (once)

```bash
pip install -r requirements.txt
```

### Send commands

```bash
python control.py fan on
python control.py fan off
```

You will see the fan state change in the Grafana dashboard and the 3D visualisation within one 5-second tick.

---

## Stopping the Stack

```bash
docker compose down
# or: make down
```

Data volumes (`influxdb_data`, `grafana_data`, etc.) are preserved so your history survives a restart.

To remove everything including volumes:

```bash
docker compose down -v
# or: make clean
```

---

## Project Structure

```
room-digital-twin/
├── docker-compose.yml          # Orchestrates all six services
├── .env.example                # Environment variable template (commit this)
├── .env                        # Your local secrets (never commit)
├── requirements.txt            # Host dependencies for control.py
├── control.py                  # CLI: send fan commands to the twin
├── Makefile                    # Convenience targets (up/down/logs/clean)
│
├── mosquitto/
│   └── config/
│       └── mosquitto.conf      # MQTT broker config (TCP + WebSocket)
│
├── sensor_simulator/
│   ├── simulator.py            # Physics model + MQTT publisher
│   ├── requirements.txt
│   └── Dockerfile
│
├── mqtt_bridge/
│   ├── bridge.py               # MQTT subscriber → InfluxDB writer
│   ├── requirements.txt
│   └── Dockerfile
│
├── grafana/
│   └── provisioning/
│       ├── datasources/
│       │   └── influxdb.yml    # Auto-provisions InfluxDB datasource
│       └── dashboards/
│           ├── dashboard.yml   # Dashboard loader config
│           └── room_twin.json  # Pre-built Grafana dashboard (8 panels)
│
└── viz3d/
    ├── index.html              # Three.js 3D room visualisation
    └── diagrams.html           # Mermaid architecture + data-flow diagrams
```

---

## Configuration Reference

All tuneable values are environment variables. Set them in `.env` (Docker Compose picks them up automatically).

| Variable | Default | Used by |
|---|---|---|
| `INFLUXDB_USERNAME` | `admin` | InfluxDB init |
| `INFLUXDB_PASSWORD` | — | InfluxDB init |
| `INFLUXDB_ORG` | `digital-twin` | InfluxDB, bridge, Grafana |
| `INFLUXDB_BUCKET` | `room_sensors` | InfluxDB, bridge, Grafana |
| `INFLUXDB_TOKEN` | — | InfluxDB init, bridge, Grafana |
| `GRAFANA_ADMIN_USER` | `admin` | Grafana |
| `GRAFANA_ADMIN_PASSWORD` | — | Grafana |

The simulator and bridge also accept `MQTT_HOST` and `MQTT_PORT`, which are set inside `docker-compose.yml` to the internal service names and do not need to be in `.env`.

---

## MQTT Topics

| Topic | Direction | Payload | Description |
|---|---|---|---|
| `room/temperature` | simulator → broker | `{"value": 23.5}` | °C |
| `room/humidity` | simulator → broker | `{"value": 58.4}` | % |
| `room/fan_state` | simulator → broker | `{"value": "ON"}` | `"ON"` or `"OFF"` |
| `room/fan_speed` | simulator → broker | `{"value": 1198}` | RPM (0 when off) |
| `room/light` | simulator → broker | `{"value": 412.0}` | lux |
| `room/power` | simulator → broker | `{"value": 85.3}` | watts |
| `room/fan/control` | host → broker → simulator | `ON` or `OFF` | remote fan command |

---

## How the Physics Model Works

The simulator (`sensor_simulator/simulator.py`) advances a simple state machine every 5 seconds:

1. **Ambient temperature** follows a sine wave: 19 °C at 05:00, 28 °C at 14:00.
2. **Room temperature** drifts toward ambient; the fan applies a −3 °C cooling offset and adds Gaussian noise.
3. **Auto-thermostat** turns the fan on above 25 °C and off below 22 °C — unless a manual command was received in the last 60 seconds.
4. **Humidity** moves toward 60 % (fan off) or 50 % (fan on) with a small random walk.
5. **Light** follows a daylight sine curve clipped to daylight hours.
6. **Power** draws ~5 W at idle and ~85 W when the fan runs.

Time is simulated: each tick counts as 5 real seconds but advances the 24-hour clock so you can observe the full diurnal cycle in about 2 minutes of wall time.

---

## Rebuilding After Code Changes

If you edit `simulator.py` or `bridge.py`, rebuild and restart just those services:

```bash
docker compose build simulator bridge
docker compose up -d simulator bridge
# or: make rebuild
```

---

## Troubleshooting

**Grafana datasource shows "connection refused"**
InfluxDB takes a few seconds to initialise on first boot. Wait 15 seconds and refresh the Grafana page.

**3D visualisation shows "MQTT disconnected" (red dot)**
Mosquitto exposes WebSocket on port 9001. Make sure port 9001 is not blocked by a firewall and that the stack is running (`docker compose ps`).

**`docker compose up` fails with "port already in use"**
Another process is using one of the ports (1883, 8086, 3000, 8080, 9001). Stop the conflicting process or change the host port in `docker-compose.yml`.

**bridge service keeps restarting**
This usually means InfluxDB has not finished initialising. The bridge retries automatically every 3 seconds. Check `docker compose logs bridge` — it should connect within 30 seconds of stack start.

**`control.py` raises `ConnectionRefusedError`**
Mosquitto must be running and port 1883 must be reachable from the host. Run `docker compose ps mosquitto` to verify.

---

## Licence

[MIT](LICENSE) — free to use, modify, and redistribute with attribution.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for how to add sensors, panels, or features.
