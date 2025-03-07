import pytest
from app.core.types import MediaType, PipelineData
from app.core.protocols import ModelBackend
from app.core.implementations import ModelProcessor
from app.core.pipeline import Pipeline

# Test Data
@pytest.fixture
def text_data():
    return PipelineData(
        media_type=MediaType.TEXT,
        content="test content",
        metadata={}
    )

@pytest.fixture
def image_data():
    return PipelineData(
        media_type=MediaType.IMAGE,
        content=b"fake image bytes",
        metadata={}
    )

# Mock Implementations
class MockPipelineStep:
    """Simple processor that adds a prefix to text content"""
    def __init__(self, prefix: str = "processed_"):
        self.prefix = prefix
        self._accepted_types = [MediaType.TEXT]
    
    async def process(self, data: PipelineData) -> PipelineData:
        return PipelineData(
            media_type=MediaType.TEXT,
            content=f"{self.prefix}{data.content}",
            metadata={**data.metadata, "processed": True}
        )
    
    @property
    def accepted_media_types(self):
        return self._accepted_types

class MockModelBackend:
    """Simple mock model that appends text"""
    async def predict(self, input: str) -> str:
        return f"{input}_predicted"

# Protocol Conformance Tests
def test_processor_protocol_conformance():
    """Test that our implementations properly satisfy the PipelineStep protocol"""
    # This will fail type checking if MockPipelineStep doesn't implement Protocol
    processor: PipelineStep = MockPipelineStep()
    assert hasattr(processor, 'process')
    assert hasattr(processor, 'accepted_media_types')

def test_model_backend_protocol_conformance():
    """Test that our model backend implements the ModelBackend protocol"""
    backend: ModelBackend = MockModelBackend()
    assert hasattr(backend, 'predict')

# Pipeline Tests
@pytest.mark.asyncio
async def test_pipeline_single_processor(text_data):
    """Test pipeline with a single processor"""
    processor = MockPipelineStep()
    pipeline = Pipeline([processor])
    
    result = await pipeline.execute(text_data)
    
    assert result.content == "processed_test content"
    assert result.metadata["processed"] is True

@pytest.mark.asyncio
async def test_pipeline_multiple_processors(text_data):
    """Test pipeline with multiple processors in sequence"""
    processors = [
        MockPipelineStep("first_"),
        MockPipelineStep("second_")
    ]
    pipeline = Pipeline(processors)
    
    result = await pipeline.execute(text_data)
    
    assert result.content == "second_first_test content"

@pytest.mark.asyncio
async def test_pipeline_validation():
    """Test that pipeline validates media type compatibility"""
    text_processor = MockPipelineStep()
    image_processor = ImagePreprocessor()
    
    # Should raise ValueError due to incompatible media types
    with pytest.raises(ValueError):
        Pipeline([text_processor, image_processor])

# Implementation Tests
class TestModelProcessor:
    @pytest.mark.asyncio
    async def test_model_processor_basic(self, text_data):
        """Test basic model processor functionality"""
        backend = MockModelBackend()
        processor = ModelProcessor(
            backend=backend,
            accepted_types=[MediaType.TEXT],
            output_type=MediaType.TEXT
        )
        
        result = await processor.process(text_data)
        
        assert result.content == "test content_predicted"
        assert result.metadata["processed"] is True
    
    def test_model_processor_media_types(self):
        """Test model processor media type handling"""
        backend = MockModelBackend()
        processor = ModelProcessor(
            backend=backend,
            accepted_types=[MediaType.TEXT],
            output_type=MediaType.TEXT
        )
        
        assert MediaType.TEXT in processor.accepted_media_types

class TestImagePreprocessor:
    @pytest.mark.asyncio
    async def test_image_preprocessing(self, image_data):
        """Test image preprocessor functionality"""
        from PIL import Image
        import io
        
        # Create a real test image
        test_image = Image.new('RGB', (1000, 1000))
        img_byte_arr = io.BytesIO()
        test_image.save(img_byte_arr, format='PNG')
        
        data = PipelineData(
            media_type=MediaType.IMAGE,
            content=img_byte_arr.getvalue(),
            metadata={}
        )
        
        processor = ImagePreprocessor(target_size=(800, 800))
        result = await processor.process(data)
        
        # Verify the processed image
        processed_image = Image.open(io.BytesIO(result.content))
        assert processed_image.size == (800, 800)
        assert result.metadata["preprocessed"] is True
    
    def test_image_processor_media_types(self):
        """Test image processor media type handling"""
        processor = ImagePreprocessor()
        assert MediaType.IMAGE in processor.accepted_media_types