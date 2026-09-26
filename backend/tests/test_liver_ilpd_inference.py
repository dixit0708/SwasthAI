from pathlib import Path

from app.ai.models.liver_ilpd_model import load_liver_ilpd_model, predict_liver_ilpd
from app.models.prediction import LiverIlpdPredictionInput


def test_model_direct_inference():
    base_dir = Path(__file__).parent.parent.parent
    artifacts_dir = base_dir / "ml_pipeline" / "liver" / "artifacts"

    pipeline, metadata = load_liver_ilpd_model(
        artifacts_dir / "liver_ilpd_logistic_v1.pkl",
        artifacts_dir / "liver_ilpd_logistic_metadata_v1.json",
    )
    assert metadata["model_version"] == "liver-ilpd-logistic-v1"
    assert metadata["selected_threshold"] == 0.35

    # Low-risk sample: young, normal LFT values
    sample_healthy = {
        "age_years": 28, "gender": "Female", "total_bilirubin_mg_dl": 0.6,
        "direct_bilirubin_mg_dl": 0.15, "alkaline_phosphatase_u_l": 180,
        "alanine_aminotransferase_u_l": 22, "aspartate_aminotransferase_u_l": 24,
        "total_proteins_g_dl": 7.0, "albumin_g_dl": 4.0, "albumin_globulin_ratio": 1.3,
    }
    res_healthy = predict_liver_ilpd(pipeline, metadata, sample_healthy)
    assert res_healthy["is_elevated"] is False

    # High-risk sample: elevated bilirubin/enzymes, low albumin
    sample_elevated = {
        "age_years": 58, "gender": "Male", "total_bilirubin_mg_dl": 8.5,
        "direct_bilirubin_mg_dl": 4.2, "alkaline_phosphatase_u_l": 450,
        "alanine_aminotransferase_u_l": 180, "aspartate_aminotransferase_u_l": 210,
        "total_proteins_g_dl": 6.0, "albumin_g_dl": 2.4, "albumin_globulin_ratio": 0.6,
    }
    res_elevated = predict_liver_ilpd(pipeline, metadata, sample_elevated)
    assert res_elevated["is_elevated"] is True

    # Missing value (None) for one numeric field — pipeline's SimpleImputer
    # must handle it without raising.
    sample_missing = dict(sample_healthy)
    sample_missing["albumin_globulin_ratio"] = None
    res_missing = predict_liver_ilpd(pipeline, metadata, sample_missing)
    assert res_missing["is_elevated"] is False

    # Feature order enforcement: a dict built in a different key order must
    # produce an identical prediction, since the row is always rebuilt from
    # metadata['feature_names'].
    scrambled = {
        "albumin_globulin_ratio": 1.3, "albumin_g_dl": 4.0, "total_proteins_g_dl": 7.0,
        "aspartate_aminotransferase_u_l": 24, "alanine_aminotransferase_u_l": 22,
        "alkaline_phosphatase_u_l": 180, "direct_bilirubin_mg_dl": 0.15,
        "total_bilirubin_mg_dl": 0.6, "gender": "Female", "age_years": 28,
    }
    res_scrambled = predict_liver_ilpd(pipeline, metadata, scrambled)
    assert abs(res_scrambled["risk_probability"] - res_healthy["risk_probability"]) < 1e-9


def test_pydantic_validation():
    valid = LiverIlpdPredictionInput(
        age=28, gender="Female", total_bilirubin=0.6, direct_bilirubin=0.15,
        alkaline_phosphatase=180, alt_sgpt=22, ast_sgot=24,
        total_proteins=7.0, albumin=4.0, albumin_globulin_ratio=1.3,
    )
    assert valid.age == 28

    # Supported missing-value pathway: numeric fields (except age) may be null.
    valid_with_missing = LiverIlpdPredictionInput(
        age=28, gender="Female", total_bilirubin=0.6, direct_bilirubin=0.15,
        alkaline_phosphatase=180, alt_sgpt=22, ast_sgot=24,
        total_proteins=7.0, albumin=4.0, albumin_globulin_ratio=None,
    )
    assert valid_with_missing.albumin_globulin_ratio is None

    # Missing required field
    try:
        LiverIlpdPredictionInput(age=28)
        assert False, "Should have raised for missing required fields"
    except Exception as e:
        assert "gender" in str(e) or "Field required" in str(e)

    # Invalid gender
    try:
        LiverIlpdPredictionInput(
            age=28, gender="Unknown", total_bilirubin=0.6, direct_bilirubin=0.15,
            alkaline_phosphatase=180, alt_sgpt=22, ast_sgot=24,
            total_proteins=7.0, albumin=4.0, albumin_globulin_ratio=1.3,
        )
        assert False, "Should have raised for invalid gender"
    except Exception:
        pass

    # Out-of-range value
    try:
        LiverIlpdPredictionInput(
            age=200, gender="Female", total_bilirubin=0.6, direct_bilirubin=0.15,
            alkaline_phosphatase=180, alt_sgpt=22, ast_sgot=24,
            total_proteins=7.0, albumin=4.0, albumin_globulin_ratio=1.3,
        )
        assert False, "Should have raised for out-of-range age"
    except Exception:
        pass

    # Target/extra field rejected (extra="forbid")
    try:
        LiverIlpdPredictionInput(
            age=28, gender="Female", total_bilirubin=0.6, direct_bilirubin=0.15,
            alkaline_phosphatase=180, alt_sgpt=22, ast_sgot=24,
            total_proteins=7.0, albumin=4.0, albumin_globulin_ratio=1.3,
            selector=1,
        )
        assert False, "Should have raised for an unexpected extra field (e.g. the target column)"
    except Exception:
        pass


def test_artifact_checksum_locked():
    """The artifact and metadata are locked per an explicit integration
    task — this guards against either file silently drifting later."""
    from app.ai.models.liver_ilpd_model import EXPECTED_PIPELINE_SHA256, EXPECTED_METADATA_SHA256, _sha256_of

    base_dir = Path(__file__).parent.parent.parent
    artifacts_dir = base_dir / "ml_pipeline" / "liver" / "artifacts"
    assert _sha256_of(artifacts_dir / "liver_ilpd_logistic_v1.pkl") == EXPECTED_PIPELINE_SHA256
    assert _sha256_of(artifacts_dir / "liver_ilpd_logistic_metadata_v1.json") == EXPECTED_METADATA_SHA256


if __name__ == "__main__":
    test_model_direct_inference()
    test_pydantic_validation()
    test_artifact_checksum_locked()
    print("All liver-ilpd-logistic-v1 inference tests passed.")
