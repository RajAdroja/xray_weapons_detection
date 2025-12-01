#!/bin/zsh

echo "🚀 Starting X-Ray Weapons Detection with RabbitMQ..."

# Check if Docker is installed
if ! command -v docker &> /dev/null; then
    echo "❌ Docker is not installed. Installing with Homebrew..."
    brew install docker
fi

# Check if Docker Compose is available
if ! command -v docker-compose &> /dev/null && ! docker compose version &> /dev/null; then
    echo "❌ Docker Compose is not available. Please install Docker Desktop."
    exit 1
fi

# Use the appropriate docker compose command
DOCKER_COMPOSE_CMD="docker-compose"
if ! command -v docker-compose &> /dev/null; then
    DOCKER_COMPOSE_CMD="docker compose"
fi

# Create virtual environment for local development
if [ ! -d "yolov5_api_venv" ]; then
    echo "📦 Creating virtual environment..."
    python3 -m venv yolov5_api_venv
fi

source yolov5_api_venv/bin/activate

# Install dependencies
echo "📥 Installing Python dependencies..."
pip install --upgrade pip
pip install -r requirements.txt

# Create directory structure
mkdir -p static model approved_predictions/Approved/images approved_predictions/NotApproved/images

echo ""
echo "Choose deployment method:"
echo "1) Docker (Recommended for production)"
echo "2) Local development"
echo -n "Enter choice (1 or 2): "
read choice

if [ "$choice" = "1" ]; then
    # Start with Docker
    echo "📦 Starting services with Docker..."
    $DOCKER_COMPOSE_CMD up -d
    
    # Wait for services
    echo "⏳ Waiting for services to start..."
    sleep 10
    
    # Show status
    echo "📊 Service Status:"
    $DOCKER_COMPOSE_CMD ps
    
    echo ""
    echo "✅ Services started successfully!"
    echo ""
    echo "🌐 Access URLs:"
    echo "   - API: http://localhost:8000"
    echo "   - Frontend: http://localhost:3000"
    echo "   - RabbitMQ Management: http://localhost:15672 (admin/password123)"
    echo ""
    echo "🏃‍♂️ To stop services: $DOCKER_COMPOSE_CMD down"
    
elif [ "$choice" = "2" ]; then
    # Local development
    echo "🔧 Starting RabbitMQ for local development..."
    
    # Start RabbitMQ with Docker (lightweight)
    docker run -d --name rabbitmq-dev \
        -p 5672:5672 \
        -p 15672:15672 \
        -e RABBITMQ_DEFAULT_USER=admin \
        -e RABBITMQ_DEFAULT_PASS=password123 \
        rabbitmq:3-management
    
    echo ""
    echo "✅ RabbitMQ started! You can now:"
    echo "   1. Start API: uvicorn main:app --reload"
    echo "   2. Start Worker: python worker.py"
    echo "   3. Start Frontend: cd yolo-predictor && npm start"
    echo ""
    echo "🌐 Access URLs:"
    echo "   - API: http://localhost:8000"
    echo "   - RabbitMQ Management: http://localhost:15672 (admin/password123)"
    echo ""
    echo "🏃‍♂️ To stop RabbitMQ: docker stop rabbitmq-dev && docker rm rabbitmq-dev"
    
else
    echo "❌ Invalid choice. Exiting..."
    exit 1
fi

# Install development tools (optional)
pip install mypy black flake8

echo "Setup complete. Activate with: source yolov5_api_venv/bin/activate"
echo "Place your model at: model/best.pt"
echo "Run with: uvicorn main:app --reload"

python -m uvicorn main:app --reload &

echo "Starting frontend..."
cd yolo-predictor
npm install
npm start
cd ..
