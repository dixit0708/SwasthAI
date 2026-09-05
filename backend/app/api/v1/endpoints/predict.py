import logging

from fastapi import APIRouter, Depends, File, UploadFile, HTTPException, Request
from fastapi.responses import JSONResponse
from starlette.concurrency import run_in_threadpool

from app.ai.inference.image_processing import validate_and_decode_image, preprocess_for_cnn
from app.ai.models.pneumonia_cnn import load_pneumonia_model, predict_pneumonia
from app.api.v1.deps import get_current_user
from app.models.prediction import DiabetesPredictionInput, RiskPredictionOut
from app.models.user import UserOut
from app.services import prediction_service

logger = logging.getLogger(__name__)

router = APIRouter()


async def _get_pneumonia_model(app):
    """Returns the cached pneumonia model, loading it (off the event loop
    thread) on the first call. Loading imports torch + torchvision and reads
    the ~43MB checkpoint, so it's deferred here instead of app startup — see
    app/main.py's lifespan for why. A lock prevents two concurrent
    first-requests from both loading a duplicate copy of the model.
    """
    if app.state.pneumonia_model is not None:
        return app.state.pneumonia_model

    async with app.state.pneumonia_model_lock:
        if app.state.pneumonia_model is None:  # re-check: lost the race to another request
            app.state.pneumonia_model = await run_in_threadpool(
                load_pneumonia_model, app.state.pneumonia_ckpt_path
            )
            logger.info(f"Lazily loaded Pneumonia CNN model from {app.state.pneumonia_ckpt_path}")
    return app.state.pneumonia_model


@router.post("/pneumonia", summary="Predict Pneumonia from X-Ray Image")
async def predict_pneumonia_endpoint(request: Request, file: UploadFile = File(...)):
    try:
        # Read file contents
        contents = await file.read()

        # 1. Validate and decode into OpenCV numpy array
        image_np = validate_and_decode_image(contents, file.content_type)

        # 2. Preprocess specifically for the CNN architecture
        preprocessed_img = preprocess_for_cnn(image_np)

        # 3. Fetch the model, loading it lazily on first use
        try:
            model = await _get_pneumonia_model(request.app)
        except Exception as e:
            logger.error(f"Pneumonia model unavailable: {e}")
            raise HTTPException(status_code=503, detail="Pneumonia model is not loaded or currently unavailable")

        # 4. Run inference
        result = predict_pneumonia(model, preprocessed_img)

        return JSONResponse(status_code=200, content=result)

    except HTTPException:
        raise
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
