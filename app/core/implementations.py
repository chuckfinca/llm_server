import asyncio
from typing import Any, List, Union
import dspy
from enum import Enum
from pathlib import Path
import base64
import pydantic
from typing import Any

from app.core.types import MediaType, PipelineData
from app.core.model_interfaces import ModelOutput
from app.core.protocols import ModelBackend
from app.core.model_interfaces import Signature, ModelOutput
from app.core import logging

from typing import Any
import dspy
from app.core.model_interfaces import ModelOutput
from app.core.protocols import ModelBackend
from app.core import logging

class DSPyModelBackend(ModelBackend):
    """DSPy model backend implementation with minimal retry logic and proper async handling"""
    def __init__(
        self,
        model_manager,
        model_id: str,
        signature_class: type[Signature],
    ):
        self.model_manager = model_manager
        self.model_id = model_id
        self.signature = signature_class
    
    async def predict(self, input_data: Any) -> ModelOutput:
        max_attempts = 3
        base_delay = 1  # seconds
        
        for attempt in range(max_attempts):
            try:
                # Get model without context manager
                lm = self.model_manager.models.get(self.model_id)
                if not lm:
                    raise ValueError(f"Model {self.model_id} not found")
                    
                dspy.configure(lm=lm)
                predictor = dspy.Predict(self.signature, lm)
                
                # Determine input key based on signature
                input_key = "image" if self.signature.__name__ == 'ContactExtractor' else "input"
                raw_result = predictor(**{input_key: input_data})
                
                return self.signature.process_output(raw_result)
                    
            except Exception as e:
                if attempt == max_attempts - 1:  # Last attempt
                    logging.error(f"Final attempt failed for model {self.model_id}: {str(e)}")
                    raise  # Re-raise the last error
                    
                delay = base_delay * (2 ** attempt)
                logging.warning(
                    f"API call failed: {str(e)}, "
                    f"retrying in {delay} seconds... "
                    f"(attempt {attempt + 1}/{max_attempts})"
                )
                await asyncio.sleep(delay)

class ModelProcessor:
    """Standard processor for model-based operations"""
    def __init__(self, backend: ModelBackend, accepted_types: list[MediaType], output_type: MediaType):
        self.backend = backend
        self._accepted_types = accepted_types
        self.output_type = output_type
    
    async def process(self, data: PipelineData) -> PipelineData:
        result = await self.backend.predict(data.content)
        return PipelineData(
            media_type=self.output_type,
            content=result,
            metadata={**data.metadata, "processed": True}
        )
    
    @property
    def accepted_media_types(self) -> list[MediaType]:
        return self._accepted_types

class ImageType(Enum):
    BASE64 = "base64"
    PNG = "png"
    JPEG = "jpeg"
    NONE = "none"
    
    def to_mime_type(self) -> str:
        """Convert image type to MIME type string"""
        mime_types = {
            ImageType.PNG: "image/png",
            ImageType.JPEG: "image/jpeg",
            ImageType.BASE64: "image/png",  # Default to PNG for base64
            ImageType.NONE: "application/octet-stream"
        }
        return mime_types[self]

class ImageTypeValidator:
    """Validates and detects image types in the pipeline"""
    
    def __init__(self):
        self._accepted_types = [MediaType.IMAGE]
    
    @property
    def accepted_media_types(self) -> List[MediaType]:
        """Implement accepted_media_types as required by PipelineStep protocol"""
        return self._accepted_types
    
    async def process(self, data: PipelineData) -> PipelineData:
        """Implement process method as required by PipelineStep protocol"""
        # Validate the image type
        image_type = self.detect_type(data.content)
        
        # Return data with updated metadata
        return PipelineData(
            media_type=MediaType.IMAGE,
            content=data.content,
            metadata={
                **data.metadata,
                'detected_image_type': image_type.value,
                'validated': True
            }
        )
    
    @staticmethod
    def detect_type(content: Union[str, bytes]) -> ImageType:
        if isinstance(content, bytes):
            return ImageTypeValidator._detect_from_bytes(content)
        return ImageTypeValidator._detect_from_str(content)
            
    @staticmethod
    def _detect_from_bytes(data: bytes) -> ImageType:
        if data.startswith(b'\x89PNG\r\n'):
            return ImageType.PNG
        if data.startswith(b'\xff\xd8\xff'):
            return ImageType.JPEG
        raise ValueError("Invalid image bytes")
    
    @staticmethod
    def _detect_from_str(data: str) -> ImageType:
        # First check if it's a reasonable length for a file path
        if len(data) < 1024:
            try:
                path = Path(data)
                if path.exists():
                    with open(path, 'rb') as f:
                        return ImageTypeValidator._detect_from_bytes(f.read(4))
            except (OSError, IOError):
                pass
                
        # If not a file path, treat as base64
        try:
            # Handle data URI format
            if ',' in data:
                data = data.split(',', 1)[1]
            decoded = base64.b64decode(data)
            return ImageType.BASE64
        except:
            return ImageType.BASE64  # Default to base64 for long strings


class ImageInput(pydantic.BaseModel):
    content: Union[str, bytes] 
    type: ImageType = pydantic.Field(default_factory=lambda: ImageType.NONE)
    
    def __init__(self, **data):
        super().__init__(**data)
        self.type = ImageTypeValidator.detect_type(self.content)
        

class ImageConverterStep:
    """Pipeline step that validates and converts images to the required format"""
    
    @property
    def accepted_media_types(self) -> List[MediaType]:
        return [MediaType.IMAGE]
    
    async def process(self, data: PipelineData) -> PipelineData:
        # Validate and determine image type
        image_input = ImageInput(content=data.content)
        
        # Convert to base64 if not already
        if image_input.type != ImageType.BASE64:
            if isinstance(image_input.content, str):
                # Read file content if path provided
                with open(image_input.content, 'rb') as f:
                    image_bytes = f.read()
            else:
                # Use bytes directly
                image_bytes = image_input.content
                
            # Convert to base64
            base64_data = base64.b64encode(image_bytes).decode('utf-8')
        else:
            base64_data = image_input.content
        
        mime_type = image_input.type.to_mime_type()
        data_uri = f"data:{mime_type};base64,{base64_data}"

        return PipelineData(
            media_type=MediaType.IMAGE,
            content=data_uri,  # Complete data URI
            metadata={
                **data.metadata,
                'original_type': image_input.type.value,
                'mime_type': mime_type,  # New field
                'converted_to': 'data_uri'
            }
        )