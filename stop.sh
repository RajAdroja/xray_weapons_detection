#!/bin/bash

echo "🛑 Stopping X-Ray Weapons Detection services..."

# Stop Docker Compose services
if command -v docker-compose &> /dev/null; then
    docker-compose down
elif docker compose version &> /dev/null 2>&1; then
    docker compose down
fi

# Stop individual containers if they exist
docker stop rabbitmq-dev 2>/dev/null && docker rm rabbitmq-dev 2>/dev/null

echo "✅ All services stopped."