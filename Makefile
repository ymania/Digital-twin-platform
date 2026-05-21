.PHONY: up down restart logs ps clean rebuild help

# Default target
help:
	@echo ""
	@echo "  Digital Twin – make targets"
	@echo ""
	@echo "  up        Start all services (detached)"
	@echo "  down      Stop and remove containers"
	@echo "  restart   Full stop + start cycle"
	@echo "  logs      Tail logs from all services"
	@echo "  ps        Show running containers"
	@echo "  rebuild   Rebuild Python images and restart"
	@echo "  clean     Remove containers, volumes, and built images"
	@echo ""

up:
	docker compose up -d

down:
	docker compose down

restart: down up

logs:
	docker compose logs -f

ps:
	docker compose ps

rebuild:
	docker compose build --no-cache simulator bridge
	docker compose up -d simulator bridge

clean:
	docker compose down -v --rmi local
