import asyncio
import base64
import io
import json
from PIL import Image
from pathlib import Path
import torch
from ultralytics import YOLO
import logging
from rabbitmq_service import rabbitmq_service
from task_manager import task_manager, TaskStatus

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class PredictionWorker:
    def __init__(self):
        self.models = {}
        self.load_models()
    
    def load_models(self):
        """Load YOLO models"""
        MODEL_DIR = Path(__file__).parent / "model"
        
        try:
            yolov5_path = MODEL_DIR / "yolov5.pt"
            yolov8_path = MODEL_DIR / "yolov8.pt"
            best_model_path = MODEL_DIR / "best.pt"

            if yolov5_path.exists():
                self.models["yolov5"] = torch.hub.load('ultralytics/yolov5', 'custom', path=str(yolov5_path))
                self.models["yolov5"].eval()
                
            if yolov8_path.exists():
                self.models["yolov8"] = YOLO(str(yolov8_path))
                
            if best_model_path.exists():
                self.models["best"] = YOLO(str(best_model_path))

            logger.info(f"Loaded models: {list(self.models.keys())}")
            
        except Exception as e:
            logger.error(f"Error loading models: {e}")
    
    def run_inference(self, model_name: str, img: Image.Image):
        """Run inference on image with specified model"""
        model = self.models.get(model_name)
        if model is None:
            raise ValueError(f"Model '{model_name}' not found.")

        if model_name == "yolov5":
            results = model(img)
            results.render()
            rendered = Image.fromarray(results.ims[0])
            preds = results.pred[0].tolist()
            class_names = model.names

        elif model_name in ["yolov8", "best"]:
            results = model.predict(img, verbose=False)
            rendered = results[0].plot(pil=True)
            preds = results[0].boxes.data.tolist()
            class_names = results[0].names

        else:
            raise ValueError(f"Unsupported model: {model_name}")

        return rendered, preds, class_names
    
    async def process_prediction_task(self, task_data: dict, correlation_id: str, reply_to: str):
        """Process a single prediction task"""
        try:
            # Get the actual task_id from the task data
            task_id = task_data.get("task_id", correlation_id)
            filename = task_data["filename"]
            
            logger.info(f"Processing task {correlation_id} (task_id: {task_id})")
            
            # Publish status update via RabbitMQ instead of local task manager
            await rabbitmq_service.publish_status_update(task_id, TaskStatus.PROCESSING.value)
            
            file_data = task_data["file_data"]
            
            # Decode base64 image
            image_bytes = base64.b64decode(file_data)
            img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
            
            per_model_results = {}
            
            # Process with each model
            for model_name in self.models.keys():
                try:
                    rendered, preds, class_names = self.run_inference(model_name, img)
                    
                    # Convert rendered image to base64
                    output_buffer = io.BytesIO()
                    rendered.save(output_buffer, format="JPEG")
                    base64_image = base64.b64encode(output_buffer.getvalue()).decode("utf-8")
                    
                    # Convert original image to base64
                    original_buffer = io.BytesIO()
                    img.save(original_buffer, format="JPEG")
                    original_base64 = base64.b64encode(original_buffer.getvalue()).decode("utf-8")
                    
                    # Format detections
                    detections = []
                    for pred in preds:
                        x1, y1, x2, y2, conf, cls = pred
                        detection = {
                            "class": class_names[int(cls)],
                            "confidence": round(float(conf), 4),
                            "bbox": [round(float(x1), 2), round(float(y1), 2), 
                                   round(float(x2), 2), round(float(y2), 2)]
                        }
                        detections.append(detection)
                    
                    per_model_results[model_name] = {
                        "detections": detections,
                        "image_base64": base64_image,
                        "original_base64": original_base64
                    }
                    
                except Exception as e:
                    logger.error(f"Error processing {filename} with {model_name}: {e}")
                    per_model_results[model_name] = {
                        "error": str(e),
                        "detections": [],
                        "image_base64": "",
                        "original_base64": ""
                    }
            
            # Create result
            result = {
                "filename": filename,
                "results": per_model_results
            }
            
            # Add result to task manager using the correct task_id
            task_manager.add_result(task_id, result)
            
            # Log result size for debugging
            result_json = json.dumps(result)
            result_size_kb = len(result_json) / 1024
            logger.info(f"Result size for {correlation_id}: {result_size_kb:.1f} KB")
            
            # Publish result back
            await rabbitmq_service.publish_result(result, correlation_id, reply_to)
            
            logger.info(f"Completed processing task {correlation_id} (task_id: {task_id})")
            
        except Exception as e:
            logger.error(f"Error processing task {correlation_id}: {e}")
            await rabbitmq_service.publish_status_update(task_id, TaskStatus.FAILED.value, str(e))
            
            # Publish error result
            error_result = {
                "filename": task_data.get("filename", "unknown"),
                "error": str(e),
                "results": {}
            }
            await rabbitmq_service.publish_result(error_result, correlation_id, reply_to)

async def main():
    """Main worker process"""
    worker = PredictionWorker()
    
    logger.info("Starting prediction worker...")
    
    # Connect to RabbitMQ
    await rabbitmq_service.connect()
    
    # Start consuming tasks
    await rabbitmq_service.consume_prediction_tasks(worker.process_prediction_task)
    
    # Keep the worker running
    try:
        while True:
            await asyncio.sleep(1)
    except KeyboardInterrupt:
        logger.info("Shutting down worker...")
    finally:
        await rabbitmq_service.close()

if __name__ == "__main__":
    asyncio.run(main())