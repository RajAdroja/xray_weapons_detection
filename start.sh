#!/bin/zsh

# Create virtual environment
python3 -m venv yolov5_api_venv
source yolov5_api_venv/bin/activate

# Install base dependencies
pip install --upgrade pip
pip install fastapi uvicorn python-multipart python-dotenv

# Install PyTorch (macOS specific)
pip install torch torchvision torchaudio

# Install YOLOv5 requirements
pip install ultralytics opencv-python-headless Pillow

# Create directory structure
mkdir -p static model
touch static/upload.html  # Place your HTML file here
touch main.py  # Your FastAPI code goes here

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
