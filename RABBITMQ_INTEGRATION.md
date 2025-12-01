# RabbitMQ Integration Guide

## Overview

This document explains the RabbitMQ integration for the X-Ray Weapons Detection system, which enables asynchronous processing of image predictions for better scalability and user experience.

## 🚀 STARTUP COMMANDS (After Laptop Restart)

**Run these commands in order to get all services running:**

### Step 1: Start RabbitMQ (Docker Container)

```bash
cd /Users/rajadroja/Desktop/Projects/xray_weapons_detection
docker-compose up -d
```

_Wait ~10 seconds for RabbitMQ to fully start_

### Step 2: Start Python Backend API Server (Terminal 1)

```bash
cd /Users/rajadroja/Desktop/Projects/xray_weapons_detection
source yolov5_api_venv/bin/activate
python -m uvicorn main:app --reload --port 8000
```

### Step 3: Start Python Worker Process (Terminal 2 - New Terminal)

```bash
cd /Users/rajadroja/Desktop/Projects/xray_weapons_detection
source yolov5_api_venv/bin/activate
python worker.py
```

### Step 4: Start React Frontend (Terminal 3 - New Terminal)

```bash
cd /Users/rajadroja/Desktop/Projects/xray_weapons_detection/yolo-predictor
npm start
```

### Step 5: Access the Application

- **Main App**: http://localhost:3000
- **Backend API**: http://localhost:8000
- **API Docs**: http://localhost:8000/docs
- **RabbitMQ Admin**: http://localhost:15672 (username: `guest`, password: `guest`)

### Step 6: Test Both Modes

1. **Synchronous**: Select "Synchronous" mode, upload images → immediate results
2. **Asynchronous**: Select "Asynchronous" mode, upload images → real-time status updates

---

## Architecture

The system now supports two processing modes:

### 1. Synchronous Processing (Original)

- Direct HTTP request/response
- User waits for all predictions to complete
- Good for small batches or testing

### 2. Asynchronous Processing (New)

- Uses RabbitMQ message queue
- Background processing with workers
- Real-time status updates via polling
- Better for large batches and production use

## Components

### Backend Services

- **FastAPI API Server**: Handles HTTP requests and serves results
- **RabbitMQ Message Broker**: Manages task queues
- **Worker Processes**: Process prediction tasks in background
- **Task Manager**: Tracks job status and results
- **Redis** (optional): For caching and session storage

### Frontend

- **React Application**: Updated with async processing support
- **Processing Mode Toggle**: Switch between sync/async modes
- **Real-time Status Updates**: Shows progress for background jobs

## Installation & Setup

### Prerequisites

- Docker and Docker Compose
- Python 3.9+
- Node.js 16+ (for frontend development)

### Quick Start

1. **Clone and Setup**:

   ```bash
   git clone <repository>
   cd xray_weapons_detection
   ```

2. **Start Services**:

   ```bash
   ./start.sh
   ```

   Choose option 1 for Docker deployment or option 2 for local development.

3. **Access Applications**:
   - Frontend: http://localhost:3000
   - API: http://localhost:8000
   - RabbitMQ Management: http://localhost:15672 (admin/password123)

### Local Development Setup

If you prefer local development:

1. **Start RabbitMQ**:

   ```bash
   docker run -d --name rabbitmq-dev \
     -p 5672:5672 -p 15672:15672 \
     -e RABBITMQ_DEFAULT_USER=admin \
     -e RABBITMQ_DEFAULT_PASS=password123 \
     rabbitmq:3-management
   ```

2. **Install Dependencies**:

   ```bash
   source yolov5_api_venv/bin/activate
   pip install -r requirements.txt
   ```

3. **Start Services**:

   ```bash
   # Terminal 1: API Server
   uvicorn main:app --reload

   # Terminal 2: Worker Process
   python worker.py

   # Terminal 3: Frontend
   cd yolo-predictor
   npm start
   ```

## API Endpoints

### New Async Endpoints

- **POST /predict-async/**: Submit images for background processing
  - Returns: `{task_id, status, files_count, message}`
- **GET /task-status/{task_id}**: Check task processing status
  - Returns: Task details including progress and status
- **GET /task-results/{task_id}**: Get completed task results
  - Returns: Prediction results in same format as sync endpoint

### Existing Endpoints (Still Available)

- **POST /predict-all/**: Synchronous processing (original)
- **POST /save-approved/**: Save approved predictions
- **GET /health/**: Health check
- **GET /version/**: API version info
- **GET /classes/**: Available classes

## Configuration

### Environment Variables

Create `.env` file:

```env
RABBITMQ_URL=amqp://admin:password123@localhost:5672/
REDIS_URL=redis://localhost:6379
API_PORT=8000
WORKER_CONCURRENCY=2
ENVIRONMENT=development
```

### RabbitMQ Configuration

The system uses these queues:

- `prediction_queue`: For incoming prediction tasks
- `result_queue`: For completed results
- `prediction_exchange`: Direct exchange for routing

## Usage

### Frontend Usage

1. **Upload Images**: Drag & drop or select multiple images
2. **Choose Processing Mode**:
   - **Synchronous**: Wait for immediate results
   - **Asynchronous**: Submit for background processing
3. **Monitor Progress**: For async jobs, see real-time status updates
4. **Review Results**: Approve or reject predictions as before

### Programmatic Usage

#### Submit Async Job

```python
import requests

files = [('files', open('image1.jpg', 'rb'))]
response = requests.post('http://localhost:8000/predict-async/', files=files)
task_id = response.json()['task_id']
```

#### Check Status

```python
status = requests.get(f'http://localhost:8000/task-status/{task_id}')
print(status.json())
```

#### Get Results

```python
results = requests.get(f'http://localhost:8000/task-results/{task_id}')
print(results.json())
```

## Scaling

### Worker Scaling

Scale worker processes in docker-compose.yml:

```yaml
worker:
  deploy:
    replicas: 4 # Increase for more parallel processing
```

Or run additional workers manually:

```bash
python worker.py  # Run in separate terminals/processes
```

### Load Balancing

For production, add load balancer in front of API servers:

```yaml
nginx:
  image: nginx:alpine
  ports:
    - "80:80"
  depends_on:
    - api
```

## Monitoring

### RabbitMQ Management UI

- URL: http://localhost:15672
- Username: admin
- Password: password123

Monitor:

- Queue lengths
- Message rates
- Consumer status
- Memory usage

### Application Logs

```bash
# View all services
docker-compose logs -f

# View specific service
docker-compose logs -f worker
docker-compose logs -f api
```

## Troubleshooting

### Common Issues

1. **RabbitMQ Connection Failed**:

   - Check if RabbitMQ is running: `docker ps`
   - Verify connection URL in environment variables
   - Check network connectivity

2. **Worker Not Processing Tasks**:

   - Check worker logs: `docker-compose logs worker`
   - Verify model files exist in `/model` directory
   - Check RabbitMQ queue status in management UI

3. **Frontend Not Polling**:

   - Check browser console for JavaScript errors
   - Verify API endpoints are accessible
   - Check CORS configuration

4. **Memory Issues with Large Images**:
   - Increase Docker memory limits
   - Implement image resizing in worker
   - Add batch size limits

### Performance Tuning

1. **Adjust Worker Concurrency**:

   ```yaml
   worker:
     deploy:
       replicas: 4 # Increase based on CPU cores
   ```

2. **Tune RabbitMQ**:

   ```yaml
   rabbitmq:
     environment:
       - RABBITMQ_VM_MEMORY_HIGH_WATERMARK=0.8
       - RABBITMQ_DISK_FREE_LIMIT=1GB
   ```

3. **Enable Result Caching**:
   - Use Redis for caching results
   - Implement cache-based deduplication

## Security Considerations

1. **Change Default Credentials**:

   ```yaml
   rabbitmq:
     environment:
       - RABBITMQ_DEFAULT_USER=your_username
       - RABBITMQ_DEFAULT_PASS=secure_password
   ```

2. **Network Security**:

   - Use internal Docker networks
   - Implement authentication for API endpoints
   - Add rate limiting

3. **Data Protection**:
   - Encrypt sensitive data in messages
   - Implement secure file handling
   - Add audit logging

## Support

For issues or questions:

1. Check logs: `docker-compose logs`
2. Review RabbitMQ management UI
3. Verify environment configuration
4. Test with smaller image batches first
