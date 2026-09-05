from fastapi import APIRouter, Depends, File, UploadFile, HTTPException, Request
from fastapi.responses import JSONResponse
from app.ai.inference.image_processing import validate_and_decode_image, preprocess_for_cnn
from app.ai.models.pneumonia_cnn import predict_pneumonia
from app.api.v1.deps import get_current_user
from app.models.prediction import DiabetesPredictionInput, RiskPredictionOut
from app.models.user import UserOut
from app.services import prediction_service

router = APIRouter()

@router.post("/pneumonia", summary="Predict Pneumonia from X-Ray Image")
async def predict_pneumonia_endpoint(request: Request, file: UploadFile = File(...)):
    try:
        # Read file contents
        contents = await file.read()
        
        # 1. Validate and decode into OpenCV numpy array
        image_np = validate_and_decode_image(contents, file.content_type)
        
        # 2. Preprocess specifically for the CNN architecture
        preprocessed_img = preprocess_for_cnn(image_np)
        
        # 3. Fetch pre-loaded model from application state
        model = getattr(request.app.state, "pneumonia_model", None)
        if model is None:
            raise HTTPException(status_code=503, detail="Pneumonia model is not loaded or currently unavailable")
            
        # 4. Run inference
        result = predict_pneumonia(model, preprocessed_img)
        
        return JSONResponse(status_code=200, content=result)
        
    except ValueError as ve:
        # Handled validation errors (e.g., unsupported format, too large)
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Prediction failed: {str(e)}")


@router.post("/diabetes", summary="Predict Diabetes Risk from Health Parameters", response_model=RiskPredictionOut)
async def predict_diabetes_endpoint(
    payload: DiabetesPredictionInput,
    request: Request,
    current_user: UserOut = Depends(get_current_user),
):
    model = getattr(request.app.state, "diabetes_model", None)
    if model is None:
        raise HTTPException(status_code=503, detail="Diabetes risk model is not loaded or currently unavailable")

    try:
        return await prediction_service.predict_diabetes_risk(current_user.id, payload, model)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Prediction failed: {str(e)}")
