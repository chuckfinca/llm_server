# tests/core/test_factories.py
import pytest
from app.core.types import MediaType
from app.core.factories import create_text_processor, create_ocr_processor
from app.core.protocols import Processor

@pytest.fixture
def mock_model_manager(monkeypatch):
    """Create a mock model manager for testing"""
    class MockLM:
        def __enter__(self):
            return self
        def __exit__(self, *args):
            pass
    
    class MockModelManager:
        def get_model(self, model_id):
            return MockLM()
    
    # Mock dspy configuration
    monkeypatch.setattr("dspy.configure", lambda lm: None)
    monkeypatch.setattr("dspy.Predict", 
        lambda module, lm: lambda input: type('obj', (), {'output': f"{input}_processed"})())
    
    return MockModelManager()

def test_create_text_processor(mock_model_manager):
    """Test creation of text processor"""
    processor = create_text_processor(mock_model_manager, "test-model")
    
    # Verify it implements the Processor protocol
    assert isinstance(processor, Processor)
    assert MediaType.TEXT in processor.accepted_media_types

def test_create_ocr_processor(mock_model_manager):
    """Test creation of OCR processor"""
    processor = create_ocr_processor(mock_model_manager, "test-model")
    
    # Verify it implements the Processor protocol
    assert isinstance(processor, Processor)
    assert MediaType.IMAGE in processor.accepted_media_types

@pytest.mark.asyncio
async def test_text_processor_functionality(mock_model_manager):
    """Test the created text processor actually works"""
    from app.core.types import PipelineData
    
    processor = create_text_processor(mock_model_manager, "test-model")
    
    result = await processor.process(PipelineData(
        media_type=MediaType.TEXT,
        content="test input",
        metadata={}
    ))
    
    assert result.content == "test input_processed"
    assert result.metadata.get("processed") is True

@pytest.mark.asyncio
async def test_ocr_processor_functionality(mock_model_manager):
    """Test the created OCR processor actually works"""
    from app.core.types import PipelineData
    
    processor = create_ocr_processor(mock_model_manager, "test-model")
    
    result = await processor.process(PipelineData(
        media_type=MediaType.IMAGE,
        content=b"fake image bytes",
        metadata={}
    ))
    
    assert isinstance(result.content, str)  # OCR should return text
    assert result.metadata.get("processed") is True