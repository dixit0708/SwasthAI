import logging
from typing import Optional, List, Dict, Any
from pydantic import BaseModel

from fastapi import APIRouter, Depends, File, UploadFile, HTTPException, Request
from fastapi.responses import JSONResponse
from starlette.concurrency import run_in_threadpool

from datetime import datetime, timezone

from app.ai.inference.image_processing import validate_and_decode_image, preprocess_for_cnn
from app.ai.models.pneumonia_cnn import load_pneumonia_model, predict_pneumonia
from app.api.v1.deps import get_current_user, get_optional_current_user
from app.db.collections import prediction_repo
from app.models.prediction import (
    DiabetesPimaPredictionInput,
    DiabetesPredictionInput,
    HeartClinicalInput,
    HeartPredictionInput,
    HeartRiskPredictionOut,
    LiverIlpdPredictionInput,
    LiverLifestylePredictionInput,
    LiverPredictionInput,
    RiskPredictionOut,
)
from app.core.config import settings
from app.models.user import UserOut
from app.services import prediction_service


logger = logging.getLogger(__name__)

router = APIRouter()

class SaveSkinPredictionInput(BaseModel):
    label: str
    confidence: float
    confidence_level: str
    clinical_label: Optional[str] = None
    top_3: Optional[List[Dict[str, Any]]] = None
    differential_diagnosis: Optional[List[Dict[str, Any]]] = None
    family_member_id: Optional[str] = None
    family_member_name: Optional[str] = None
    notes: Optional[str] = None



async def _get_pneumonia_model(app):
    """Returns the cached pneumonia model, loading it (off the event loop
    thread) on the first call. Loading imports torch + torchvision and reads
    the ~43MB checkpoint, so it's deferred here instead of app startup — see
    app/main.py's lifespan for why. A lock prevents two concurrent
    first-requests from both loading a duplicate copy of the model.
    """
    if app.state.pneumonia_model is not None:
        return app.state.pneumonia_model, getattr(app.state, "pneumonia_ood_stats", None)

    async with app.state.pneumonia_model_lock:
        if app.state.pneumonia_model is None:  # re-check: lost the race to another request
            app.state.pneumonia_model = await run_in_threadpool(
                load_pneumonia_model, app.state.pneumonia_ckpt_path
            )
            
            # Load OOD Stats lazily alongside the model
            import os
            from app.ai.models.pneumonia_cnn import load_ood_stats
            ood_stats_path = app.state.pneumonia_ckpt_path.replace('pneumonia_cnn.pt', 'ood_stats.npz')
            if os.path.exists(ood_stats_path):
                app.state.pneumonia_ood_stats = await run_in_threadpool(
                    load_ood_stats, ood_stats_path
                )
            else:
                app.state.pneumonia_ood_stats = None
                
            logger.info(f"Lazily loaded Pneumonia CNN model from {app.state.pneumonia_ckpt_path}")
            
    return app.state.pneumonia_model, getattr(app.state, "pneumonia_ood_stats", None)


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
            model, ood_stats = await _get_pneumonia_model(request.app)
        except Exception as e:
            logger.error(f"Pneumonia model unavailable: {e}")
            raise HTTPException(status_code=503, detail="Pneumonia model is not loaded or currently unavailable")

        # 4. Run inference
        result = predict_pneumonia(model, preprocessed_img, original_image=image_np, ood_stats=ood_stats)
        
        # 5. Handle OOD gracefully
        if result.get("prediction") == "OOD":
            raise ValueError(result.get("message"))

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
    metadata = getattr(request.app.state, "diabetes_model_metadata", None)
    if model is None or metadata is None:
        raise HTTPException(status_code=503, detail="Diabetes risk model is not loaded or currently unavailable")

    try:
        return await prediction_service.predict_diabetes_risk(current_user.id, payload, model, metadata)
    except Exception as e:
        logger.error(f"Diabetes prediction failed: {e}")
        raise HTTPException(status_code=500, detail="Prediction failed. Please try again later.")


@router.post(
    "/heart",
    summary="Predict Heart Disease Risk from Health Parameters",
    response_model=HeartRiskPredictionOut,
)
async def predict_heart_endpoint(
    payload: HeartPredictionInput,
    request: Request,
    current_user: UserOut = Depends(get_current_user),
):
    model    = getattr(request.app.state, "heart_model", None)
    metadata = getattr(request.app.state, "heart_model_metadata", None)
    if model is None or metadata is None:
        raise HTTPException(
            status_code=503,
            detail="Heart disease risk model is not loaded or currently unavailable",
        )

    try:
        return await prediction_service.predict_heart_disease(
            current_user.id, payload, model, metadata
        )
    except ValueError as ve:
        # Encoding validation errors (bad categorical value) -> 422-equivalent
        logger.warning(f"Heart prediction input error: {ve}")
        raise HTTPException(status_code=422, detail=str(ve))
    except Exception as e:
        logger.error(f"Heart prediction failed: {e}")
        raise HTTPException(status_code=500, detail="Prediction failed. Please try again later.")

@router.post(
    "/heart/clinical",
    summary="Predict Heart Disease Risk from Clinical Lab Parameters",
    response_model=HeartRiskPredictionOut,
)
async def predict_heart_clinical_endpoint(
    payload: HeartClinicalInput,
    request: Request,
    current_user: UserOut = Depends(get_current_user),
):
    model = getattr(request.app.state, "heart_clinical_model", None)
    scaler = getattr(request.app.state, "heart_clinical_scaler", None)
    if model is None or scaler is None:
        raise HTTPException(
            status_code=503,
            detail="Heart clinical risk model is not loaded or currently unavailable",
        )

    # Temporary print statement for debugging
    print(f"=== [DEBUG] Incoming HeartClinicalInput payload: {payload.model_dump()} ===")

    try:
        return await prediction_service.predict_heart_clinical(
            current_user.id, payload, model, scaler
        )
    except ValueError as ve:
        raise HTTPException(status_code=422, detail=str(ve))
    except Exception as e:
        logger.error(f"Heart clinical prediction failed: {e}")
        raise HTTPException(status_code=500, detail="Prediction failed. Please try again later.")


@router.post("/liver", summary="Predict Liver Disease Risk", response_model=RiskPredictionOut)
async def predict_liver_endpoint(
    payload: LiverPredictionInput,
    request: Request,
    current_user: UserOut = Depends(get_current_user),
):
    model = getattr(request.app.state, "liver_model", None)
    metadata = getattr(request.app.state, "liver_model_metadata", None)
    if model is None or metadata is None:
        raise HTTPException(status_code=503, detail="Liver risk model is not loaded or currently unavailable")

    try:
        return await prediction_service.predict_liver_risk(current_user.id, payload, model, metadata)
    except Exception as e:
        logger.error(f"Liver disease prediction failed: {e}")
        raise HTTPException(status_code=500, detail="Prediction failed. Please try again later.")

@router.post(
    "/diabetes-pima",
    summary="Predict Diabetes Risk from Lab Results (Pima)",
    response_model=RiskPredictionOut,
)
async def predict_diabetes_pima_endpoint(
    payload: DiabetesPimaPredictionInput,
    request: Request,
    current_user: UserOut = Depends(get_current_user),
):
    """Independent of /diabetes above: a second, separate model
    (diabetes-pima-v1) trained on the Pima Indians Diabetes Database, for
    users who already have a recent glucose reading, blood pressure, BMI,
    and skinfold measurement — not lab-free. See
    ml_pipeline/diabetes_pima/reports/evaluation.md.
    """
    model = getattr(request.app.state, "diabetes_pima_model", None)
    metadata = getattr(request.app.state, "diabetes_pima_model_metadata", None)
    if model is None or metadata is None:
        raise HTTPException(
            status_code=503, detail="Diabetes (lab-based) risk model is not loaded or currently unavailable"
        )

    try:
        return await prediction_service.predict_diabetes_pima_risk(current_user.id, payload, model, metadata)
    except Exception as e:
        logger.error(f"Diabetes (Pima) prediction failed: {e}")
        raise HTTPException(status_code=500, detail="Prediction failed. Please try again later.")


@router.post(
    "/liver-ilpd",
    summary="Predict Liver Disease Risk from Lab Results (ILPD)",
    response_model=RiskPredictionOut,
)
async def predict_liver_ilpd_endpoint(
    payload: LiverIlpdPredictionInput,
    request: Request,
    current_user: UserOut = Depends(get_current_user),
):
    """Independent of /liver above: a second, separate model
    (liver-ilpd-logistic-v1) trained on the canonical UCI ILPD dataset, for
    users who already have a Liver Function Test (LFT) panel — not
    lab-free. See ml_pipeline/liver/reports/ilpd_final_model_report.md.
    """
    model = getattr(request.app.state, "liver_ilpd_model", None)
    metadata = getattr(request.app.state, "liver_ilpd_model_metadata", None)
    if model is None or metadata is None:
        raise HTTPException(
            status_code=503, detail="Liver risk model (lab-based) is not loaded or currently unavailable"
        )

    try:
        return await prediction_service.predict_liver_ilpd_risk(current_user.id, payload, model, metadata)
    except Exception as e:
        logger.error(f"Liver (ILPD) prediction failed: {e}")
        raise HTTPException(status_code=500, detail="Prediction failed. Please try again later.")


@router.post("/skin", summary="Predict Skin Disease from Image")
async def predict_skin_endpoint(
    request: Request, 
    file: UploadFile = File(...),
    current_user: UserOut | None = Depends(get_optional_current_user)
):
    try:
        # Read file contents
        contents = await file.read()

        # 1. Fetch the eagerly loaded model from app state (return 503 early if unavailable)
        model = getattr(request.app.state, "skin_model", None)
        idx_to_class = getattr(request.app.state, "skin_idx_to_class", None)
        if model is None or idx_to_class is None:
            logger.error("Skin Disease model is not loaded in app state.")
            raise HTTPException(status_code=503, detail="Skin Disease model is currently unavailable")

        # 2. Validate and decode into OpenCV numpy array
        image_np = validate_and_decode_image(contents, file.content_type)

        # 3. Guardrail: Validate that image contains human skin before CNN inference
        from app.ai.inference.image_processing import validate_skin_guardrail
        is_valid, reason, meta = validate_skin_guardrail(image_np)
        if not is_valid:
            logger.warning(f"Skin image rejected by guardrail: {meta.get('rejection_type')} - {reason}")
            raise HTTPException(status_code=400, detail=reason)

        # 4. Preprocess specifically for the Skin Disease CNN
        from app.ai.inference.image_processing import preprocess_for_skin
        preprocessed_img = preprocess_for_skin(image_np)

        # 5. Run inference with Grad-CAM visual heatmap generation
        from app.ai.models.skin_model import predict_skin
        result = predict_skin(model, idx_to_class, preprocessed_img, original_image_bgr=image_np)

        # 6. Secondary gating for ambiguous borderline cases
        skin_cov = meta.get("skin_coverage", 100.0)
        conf = result.get("confidence", 0.0)
        label = result.get("label", "")

        # Catch default-class confusion (DenseNet-121 defaults to Pigmentation when confused on non-medical photos)
        if "pigmentation" in label.lower() and conf < 0.65 and skin_cov < 60.0:
            raise HTTPException(
                status_code=400,
                detail="Unable to identify clear skin patterns. Please upload a closer, well-lit photo focused on the affected skin lesion."
            )
        if skin_cov < 35.0 and conf < 0.50:
            raise HTTPException(
                status_code=400,
                detail="Unable to identify clear skin patterns. Please upload a closer, well-lit photo focused on the affected skin lesion."
            )
        # Low-confidence / healthy skin check
        if conf < 0.42:
            raise HTTPException(
                status_code=400,
                detail=f"No distinct dermatological condition identified (AI confidence: {conf*100:.1f}%). The image does not show clear clinical disease patterns. Please upload a clear, focused photo of the affected area."
            )

        result["skin_coverage"] = skin_cov

        # Categorize confidence level: High >= 70%, Medium 40-70%, Low < 40%
        if conf >= 0.70:
            result["confidence_level"] = "High"
        elif conf >= 0.40:
            result["confidence_level"] = "Medium"
        else:
            result["confidence_level"] = "Low"

        # Note: In accordance with privacy & single-save architecture,
        # predictions are not automatically saved during inference.
        # Authenticated users explicitly save via /skin/save.

        return JSONResponse(status_code=200, content=result)

    except HTTPException:
        raise
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        logger.error(f"Skin Prediction failed: {e}")
        raise HTTPException(status_code=500, detail=f"Prediction failed: {str(e)}")


@router.post("/skin/save", summary="Explicitly Save Skin Prediction to Health Records")
async def save_skin_prediction_endpoint(
    payload: SaveSkinPredictionInput,
    current_user: UserOut = Depends(get_current_user),
):
    """Saves a skin prediction result (label, top-3, confidence level, timestamp) to the predictions collection."""
    # Verify family member belongs to current user before saving
    family_id = None
    if payload.family_member_id and payload.family_member_id != "self":
        from bson import ObjectId
        from app.db.collections import family_member_repo
        if not ObjectId.is_valid(payload.family_member_id):
            raise HTTPException(
                status_code=403,
                detail="Forbidden: Invalid family profile ID."
            )
        member = await family_member_repo.collection.find_one({
            "_id": ObjectId(payload.family_member_id),
            "user_id": current_user.id
        })
        if not member:
            raise HTTPException(
                status_code=403,
                detail="Forbidden: Family profile does not belong to the authenticated user."
            )
        family_id = payload.family_member_id

    try:
        diff = payload.top_3 or payload.differential_diagnosis or []
        record = {
            "user_id": current_user.id,
            "condition": "skin",
            "model_version": settings.SKIN_MODEL_VERSION,
            "result": {
                "label": payload.label,
                "clinical_label": payload.clinical_label or payload.label,
                "confidence": payload.confidence,
                "confidence_level": payload.confidence_level,
                "top_3": diff,
                "differential_diagnosis": diff,
            },
            "family_member_id": family_id,
            "family_member_name": payload.family_member_name,
            "notes": payload.notes,
            "created_at": datetime.now(timezone.utc),
        }
        created_id = await prediction_repo.create(record)
        return {"status": "saved", "id": created_id}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to save skin prediction to health records: {e}")
        raise HTTPException(status_code=500, detail="Could not save prediction to health records.")


@router.get("/family-profiles", summary="Get User and Family Profiles for Saving")
async def get_family_profiles_endpoint(
    current_user: UserOut = Depends(get_current_user),
):
    """Returns available profiles for the current user (personal self profile and any registered family members)."""
    from app.db.collections import family_member_repo
    profiles = [{"id": "self", "name": "Myself (Personal Profile)", "relation": "Self"}]
    try:
        family_docs = await family_member_repo.collection.find({"user_id": current_user.id}).to_list(length=100)
        for f in family_docs:
            profiles.append({
                "id": str(f.get("_id")),
                "name": f.get("name", "Family Member"),
                "relation": f.get("relation", "Family"),
            })
    except Exception as e:
        logger.warning(f"Could not fetch family profiles for user {current_user.id}: {e}")
    return {"profiles": profiles}



@router.post("/liver-lifestyle", summary="Predict Liver Disease Risk from Lifestyle", response_model=RiskPredictionOut)
async def predict_liver_lifestyle_endpoint(
    payload: LiverLifestylePredictionInput,
    request: Request,
    current_user: UserOut = Depends(get_current_user),
):
    try:
        return await prediction_service.predict_liver_lifestyle_risk(current_user.id, payload)
    except Exception as e:
        logger.error(f"Liver lifestyle prediction failed: {e}")
        raise HTTPException(status_code=500, detail="Prediction failed. Please try again later.")

