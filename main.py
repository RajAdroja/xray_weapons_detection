from fastapi import FastAPI, UploadFile, File, Query, Body
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

import torch
import io
import base64
import os
import json
from PIL import Image
from pathlib import Path
from typing import List, Dict, Any
from ultralytics import YOLO

app = FastAPI()

# CORS middleware for frontend integration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve static files (e.g., upload.html)
app.mount("/static", StaticFiles(directory=Path(__file__).parent / "static"), name="static")

# Define paths
MODEL_DIR = Path(__file__).parent / "model"
SAVE_DIR = Path(__file__).parent / "approved_predictions"

# Create the predictions directory if it doesn't exist
os.makedirs(SAVE_DIR, exist_ok=True)

# Model loading block
try:
    yolov5_path = MODEL_DIR / "yolov5.pt"
    yolov8_path = MODEL_DIR / "yolov8.pt"
    best_model_path = MODEL_DIR / "best.pt"

    if not yolov5_path.exists():
        raise FileNotFoundError(f"{yolov5_path} not found.")
    if not yolov8_path.exists():
        raise FileNotFoundError(f"{yolov8_path} not found.")
    if not best_model_path.exists():
        raise FileNotFoundError(f"{best_model_path} not found.")

    MODELS = {
        "yolov5": torch.hub.load('ultralytics/yolov5', 'custom', path=str(yolov5_path)),
        "yolov8": YOLO(str(yolov8_path)),
        "best": YOLO(str(best_model_path)),
    }

    MODELS["yolov5"].eval()
except Exception as e:
    print("❌ Error loading models:", e)
    MODELS = {}

# Helper: safely get model names for enum
def get_model_names():
    return list(MODELS.keys()) if MODELS else ["yolov5"]

# Inference helper
def run_inference(model_name: str, img: Image.Image):
    model = MODELS.get(model_name)
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

def save_prediction_data(image_data: str, filename: str, model_name: str, detections: List[Dict], save_dir: Path):
    img_dir = save_dir / "images"
    os.makedirs(img_dir, exist_ok=True)
    image_save_path = img_dir / filename

    if not image_save_path.exists():
        try:
            if "," in image_data:
                image_data = image_data.split(",", 1)[1]

            image_bytes = base64.b64decode(image_data)
            with open(image_save_path, "wb") as f:
                f.write(image_bytes)
        except Exception as e:
            print(f"Error saving image: {e}")
            return False

    txt_filename = f"{model_name}_{Path(filename).stem}.txt"
    txt_path = save_dir / txt_filename

    try:
        with open(txt_path, "w") as f:
            for det in detections:
                cls = det["class"]
                bbox = det["bbox"]
                f.write(f"{filename} {cls} {bbox[0]} {bbox[1]} {bbox[2]} {bbox[3]}\n")
        return True
    except Exception as e:
        print(f"Error saving detection data: {e}")
        return False

@app.get("/", response_class=HTMLResponse)
async def root():
    return FileResponse(Path(__file__).parent / "static" / "upload.html")

@app.post("/predict-all/")
async def predict_all(files: List[UploadFile] = File(...)) -> List[Dict]:
    results_data = []

    for file in files:
        contents = await file.read()
        img = Image.open(io.BytesIO(contents)).convert("RGB")

        per_model_results = {}

        for model_name in MODELS.keys():
            try:
                rendered, preds, class_names = run_inference(model_name, img)

                output_buffer = io.BytesIO()
                rendered.save(output_buffer, format="JPEG")
                base64_image = base64.b64encode(output_buffer.getvalue()).decode("utf-8")

                original_buffer = io.BytesIO()
                img.save(original_buffer, format="JPEG")
                original_base64 = base64.b64encode(original_buffer.getvalue()).decode("utf-8")

                detections = []
                for pred in preds:
                    x1, y1, x2, y2, conf, cls = pred
                    detection = {
                        "class": class_names[int(cls)],
                        "confidence": round(float(conf), 4),
                        "bbox": [round(float(x1), 2), round(float(y1), 2), round(float(x2), 2), round(float(y2), 2)]
                    }
                    detections.append(detection)

                per_model_results[model_name] = {
                    "detections": detections,
                    "image_base64": base64_image,
                    "original_base64": original_base64
                }

            except Exception as e:
                per_model_results[model_name] = {
                    "error": str(e),
                    "detections": [],
                    "image_base64": "",
                    "original_base64": ""
                }

        results_data.append({
            "filename": file.filename,
            "results": per_model_results
        })

    return results_data

@app.post("/save-approved/")
async def save_approved(approval_data: Dict[str, Any] = Body(...)) -> Dict:
    try:
        filename        = approval_data.get("filename")
        model_name      = approval_data.get("model_name")
        original_base64 = approval_data.get("original_base64")
        detections      = approval_data.get("detections", [])
        approved        = approval_data.get("approved")

        if not all([filename, model_name, original_base64]) or approved is None:
            return JSONResponse(
                status_code=400,
                content={"success": False, "error": "Missing required data"}
            )

        subfolder = "Approved" if approved else "NotApproved"
        base_path = os.path.join(SAVE_DIR, subfolder)
        img_path  = os.path.join(base_path, "images")
        txt_path  = base_path

        os.makedirs(img_path, exist_ok=True)
        os.makedirs(txt_path, exist_ok=True)


        # --- UNIQUE FILENAMES PER MODEL ---
        stem, ext = os.path.splitext(filename)
        unique_img_filename = f"{stem}_{model_name}{ext}"
        unique_txt_filename = f"{stem}_{model_name}.txt"

        img_data = base64.b64decode(original_base64)
        full_img_path = os.path.join(img_path, unique_img_filename)
        with open(full_img_path, "wb") as img_file:
            img_file.write(img_data)

        full_txt_path = os.path.join(txt_path, unique_txt_filename)
        with open(full_txt_path, "w") as txt_file:
            txt_file.write(json.dumps({
                "model": model_name,
                "approved": approved,
                "detections": detections
            }, indent=2))

        return {
            "success": True,
            "message": f"Saved {'approved' if approved else 'not approved'} data for {unique_img_filename}"
        }

    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"success": False, "error": str(e)}
        )

@app.get("/classes/")
async def get_classes(model_name: str = Query("yolov5", enum=get_model_names())) -> Dict:
    model = MODELS.get(model_name)
    if model is None:
        return {"error": "Model not found"}

    return {"classes": list(model.names.values())}

@app.get("/health/")
async def health() -> Dict:
    return {
        "status": "ok",
        "models_loaded": list(MODELS.keys()),
    }

@app.get("/version/")
async def version() -> Dict:
    return {
        "api_version": "1.0.0",
        "torch_version": torch.__version__,
        "models_available": list(MODELS.keys())
    }
