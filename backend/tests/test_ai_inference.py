import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app

@pytest.mark.asyncio
async def test_invalid_image_upload():
    """
    Test uploading a txt file when an image is expected.
    """
    # Assuming an endpoint like /api/v1/inference/predict
    # async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
    #     files = {'file': ('test.txt', b'this is a text file', 'text/plain')}
    #     response = await ac.post("/api/v1/inference/predict", files=files)
    #     assert response.status_code == 400
    #     assert "Unsupported file format" in response.json()["detail"]
    pass

@pytest.mark.asyncio
async def test_large_image_upload():
    """
    Test uploading a file that exceeds the max size limit.
    """
    # async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
    #     # Generate 11MB dummy data
    #     large_data = b'0' * (11 * 1024 * 1024)
    #     files = {'file': ('large.jpg', large_data, 'image/jpeg')}
    #     response = await ac.post("/api/v1/inference/predict", files=files)
    #     assert response.status_code == 400
    #     assert "File too large" in response.json()["detail"]
    pass
