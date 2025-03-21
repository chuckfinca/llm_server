from typing import Any, List, Optional, Dict
from app.core.protocols import ModelBackend, PipelineStep
from app.core.types import MediaType, PipelineData
from app.core import logging
import time
import uuid

class PerformanceMetrics:
    """Tracks performance metrics throughout request processing"""
    
    def __init__(self):
        """Initialize a new metrics tracker with start time"""
        self.start_time = time.time()
        self.trace_id = str(uuid.uuid4())
        self.checkpoints = {"request_start": self.start_time}
        self.token_usage = {"input": 0, "output": 0, "total": 0}
        self.model_id = None
        self.model_info = {}
        self.metadata = {}
        self._latest_checkpoint = self.start_time
    
    def mark_checkpoint(self, name: str) -> float:
        """
        Mark a timing checkpoint and return elapsed time since last checkpoint
        
        Args:
            name: Name of the checkpoint
            
        Returns:
            Seconds elapsed since last checkpoint
        """
        now = time.time()
        elapsed = now - self._latest_checkpoint
        self.checkpoints[name] = now
        duration_key = f"{name}_duration"
        self.metadata[duration_key] = elapsed
        self._latest_checkpoint = now
        return elapsed
    
    def record_token_usage(self, input_tokens: int, output_tokens: int) -> None:
        """Record token usage information"""
        self.token_usage["input"] = input_tokens
        self.token_usage["output"] = output_tokens
        self.token_usage["total"] = input_tokens + output_tokens
        
        # Store in metadata too
        self.metadata["input_tokens"] = input_tokens
        self.metadata["output_tokens"] = output_tokens
        self.metadata["total_tokens"] = input_tokens + output_tokens
        
        # Calculate cost if we have the model info
        if self.model_id:
            self._calculate_cost()
    
    def set_model_info(self, model_id: str, model_info: Optional[Dict[str, Any]] = None) -> None:
        """Set model information for cost calculation"""
        self.model_id = model_id
        if model_info:
            self.model_info = model_info
        
        # Store in metadata
        self.metadata["model_id"] = model_id
        
        # Recalculate cost if we have token usage
        if self.token_usage["total"] > 0:
            self._calculate_cost()
    
    def add_metadata(self, key: str, value: Any) -> None:
        """Add custom metadata"""
        self.metadata[key] = value
    
    def _calculate_cost(self) -> None:
        """Calculate the estimated cost based on token usage and model"""
        # Cost rates per 1K tokens (input, output) in USD as of March 2025
        pricing = {
            "gpt-4o-mini": (0.15, 0.60),
            "gpt-4o": (0.5, 1.5),
            "claude-3.7-sonnet": (3.0, 15.0),
            "gemini-2.0-flash": (0.35, 1.05),
            # Fallback rates for unknown models
            "default": (0.0015, 0.002)
        }
        
        # Get rate for the model, default to fallback rate if not found
        input_rate, output_rate = pricing.get(self.model_id, pricing["default"])
        
        # Calculate cost
        input_cost = (self.token_usage["input"] / 1000) * input_rate
        output_cost = (self.token_usage["output"] / 1000) * output_rate
        total_cost = input_cost + output_cost
        
        # Store in metadata
        self.metadata["estimated_cost_usd"] = round(total_cost, 6)
    
    def get_summary(self) -> Dict[str, Any]:
        """Get a summary of the metrics for API responses"""
        # Calculate total time
        total_time = time.time() - self.start_time
        
        # Create summary
        summary = {
            "timing": {
                "total_ms": round(total_time * 1000, 2),
            },
            "tokens": self.token_usage.copy(),
            "estimated_cost_usd": self.metadata.get("estimated_cost_usd", 0)
        }
        
        # Add detailed timing if available
        for name, timestamp in self.checkpoints.items():
            if name != "request_start" and f"{name}_duration" in self.metadata:
                summary["timing"][f"{name}_ms"] = round(self.metadata[f"{name}_duration"] * 1000, 2)
        
        return summary
    
    def get_all_metrics(self) -> Dict[str, Any]:
        """Get all collected metrics for logging"""
        all_metrics = {
            "trace_id": self.trace_id,
            "start_time": self.start_time,
            "total_time": time.time() - self.start_time,
            "checkpoints": self.checkpoints.copy(),
            "token_usage": self.token_usage.copy(),
            "model_id": self.model_id,
        }
        
        # Add all metadata
        all_metrics.update(self.metadata)
        
        return all_metrics

class ModelBackendTracker:
    """
    Wrapper that adds performance tracking to any ModelBackend implementation
    using composition rather than inheritance
    """
    
    def __init__(self, backend: ModelBackend, metrics: Optional[PerformanceMetrics] = None):
        """
        Initialize tracker with a backend and optional metrics instance
        
        Args:
            backend: The ModelBackend to wrap
            metrics: Optional PerformanceMetrics instance (creates new one if None)
        """
        self.backend = backend
        self.metrics = metrics or PerformanceMetrics()
        
        # Pass through model ID if available
        if hasattr(backend, 'model_id'):
            self.model_id = backend.model_id
            self.metrics.set_model_info(backend.model_id)
    
    async def predict(self, input_data: Any) -> Any:
        """
        Execute prediction with metrics tracking
        
        Args:
            input_data: The input data for the model
            
        Returns:
            Model output from the wrapped backend
        """
        # Mark preparation complete
        self.metrics.mark_checkpoint("preparation_complete")
        
        # Preserve token counts if the backend exposes them
        pre_prompt_tokens = getattr(self.backend, 'total_prompt_tokens', 0)
        pre_completion_tokens = getattr(self.backend, 'total_completion_tokens', 0)
        
        # Mark model start
        self.metrics.mark_checkpoint("model_start")
        
        try:
            # Execute prediction on wrapped backend
            result = await self.backend.predict(input_data)
            
            # Mark model complete
            self.metrics.mark_checkpoint("model_complete")
            
            # Try to capture token usage
            # Method 1: Check for token info in result metadata
            if hasattr(result, 'metadata') and result.metadata and 'usage' in result.metadata:
                usage = result.metadata['usage']
                if 'prompt_tokens' in usage and 'completion_tokens' in usage:
                    self.metrics.record_token_usage(
                        input_tokens=usage['prompt_tokens'],
                        output_tokens=usage['completion_tokens']
                    )
            
            # Method 2: Check backend attributes
            elif hasattr(self.backend, 'last_prompt_tokens') and hasattr(self.backend, 'last_completion_tokens'):
                self.metrics.record_token_usage(
                    input_tokens=self.backend.last_prompt_tokens,
                    output_tokens=self.backend.last_completion_tokens
                )
            
            # Method 3: Calculate difference in token counts
            elif hasattr(self.backend, 'total_prompt_tokens') and hasattr(self.backend, 'total_completion_tokens'):
                post_prompt_tokens = getattr(self.backend, 'total_prompt_tokens', 0)
                post_completion_tokens = getattr(self.backend, 'total_completion_tokens', 0)
                
                prompt_tokens = max(0, post_prompt_tokens - pre_prompt_tokens)
                completion_tokens = max(0, post_completion_tokens - pre_completion_tokens)
                
                if prompt_tokens > 0 or completion_tokens > 0:
                    self.metrics.record_token_usage(
                        input_tokens=prompt_tokens,
                        output_tokens=completion_tokens
                    )
            
            # Method 4: Estimate based on input length if no other methods work
            else:
                # Very rough estimate based on input length
                input_str = str(input_data)
                # Approximate tokens: ~4 chars per token for English
                estimated_input_tokens = len(input_str) // 4
                
                # If the result has text we can estimate
                if hasattr(result, 'output') and isinstance(result.output, str):
                    estimated_output_tokens = len(result.output) // 4
                else:
                    # Default to a reasonable ratio
                    estimated_output_tokens = estimated_input_tokens // 2
                
                self.metrics.add_metadata("token_count_estimated", True)
                self.metrics.record_token_usage(
                    input_tokens=estimated_input_tokens,
                    output_tokens=estimated_output_tokens
                )
            
            # Add metrics to result if possible
            if hasattr(result, 'metadata'):
                # Create a new dict if needed
                if not isinstance(result.metadata, dict):
                    result.metadata = {}
                
                # Add metrics summary to metadata
                result.metadata['performance_metrics'] = self.metrics.get_summary()
            
            return result
            
        except Exception as e:
            # Mark error in metrics
            self.metrics.add_metadata("error", str(e))
            self.metrics.add_metadata("error_type", type(e).__name__)
            self.metrics.mark_checkpoint("error")
            
            # Log the error with metrics context
            logging.error(
                f"Error in model execution: {str(e)}",
                extra={"performance_metrics": self.metrics.get_all_metrics()}
            )
            
            # Re-raise the exception
            raise

class PipelineStepTracker:
    """
    Wrapper that adds performance tracking to any PipelineStep implementation
    using composition rather than inheritance
    """
    
    def __init__(self, step: PipelineStep, metrics: Optional[PerformanceMetrics] = None, step_name: Optional[str] = None):
        """
        Initialize tracker with a pipeline step and optional metrics instance
        
        Args:
            step: The PipelineStep to wrap
            metrics: Optional PerformanceMetrics instance (creates new one if None)
            step_name: Optional name for this step (defaults to class name)
        """
        self.step = step
        self.metrics = metrics or PerformanceMetrics()
        self.step_name = step_name or step.__class__.__name__
    
    @property
    def accepted_media_types(self) -> List[MediaType]:
        """Pass through to wrapped step"""
        return self.step.accepted_media_types
    
    async def process(self, data: PipelineData) -> PipelineData:
        """
        Process data with metrics tracking
        
        Args:
            data: The PipelineData to process
            
        Returns:
            Processed PipelineData from the wrapped step
        """
        # Mark step start
        self.metrics.mark_checkpoint(f"{self.step_name}_start")
        
        try:
            # Execute the wrapped step
            result = await self.step.process(data)
            
            # Mark step complete
            self.metrics.mark_checkpoint(f"{self.step_name}_complete")
            
            # Create new metadata dictionary that includes our metrics
            combined_metadata = {
                **result.metadata,
                "performance_metrics": self.metrics.get_summary()
            }
            
            # Add step-specific metrics if available
            if self.step_name == "ImageProcessor" and "original_size" in result.metadata:
                self.metrics.add_metadata("image_original_size", result.metadata["original_size"])
                self.metrics.add_metadata("image_processed_size", result.metadata.get("processed_size"))
            
            # Return new PipelineData with updated metadata
            return PipelineData(
                media_type=result.media_type,
                content=result.content,
                metadata=combined_metadata
            )
            
        except Exception as e:
            # Mark error in metrics
            self.metrics.add_metadata("error", str(e))
            self.metrics.add_metadata("error_type", type(e).__name__)
            self.metrics.add_metadata("error_step", self.step_name)
            self.metrics.mark_checkpoint(f"{self.step_name}_error")
            
            # Log the error with metrics context
            logging.error(
                f"Error in {self.step_name}: {str(e)}",
                extra={"performance_metrics": self.metrics.get_all_metrics()}
            )
            
            # Re-raise the exception
            raise

class TrackedPipeline:
    """
    A pipeline that tracks performance metrics for all steps
    """
    
    def __init__(self, pipeline, metrics: Optional[PerformanceMetrics] = None):
        """
        Initialize with a pipeline and optional metrics
        
        Args:
            pipeline: The Pipeline to wrap
            metrics: Optional PerformanceMetrics instance (creates new one if None)
        """
        self.pipeline = pipeline
        self.metrics = metrics or PerformanceMetrics()
    
    async def execute(self, data: PipelineData) -> PipelineData:
        """
        Execute the pipeline with performance tracking
        
        Args:
            data: Initial pipeline data
            
        Returns:
            Result from pipeline execution
        """
        # Add metrics to data metadata so steps can access it
        initial_data = PipelineData(
            media_type=data.media_type,
            content=data.content,
            metadata={
                **data.metadata,
                "metrics_collector": self.metrics
            }
        )
        
        # Mark pipeline start
        self.metrics.mark_checkpoint("pipeline_start")
        
        try:
            # Execute the pipeline
            result = await self.pipeline.execute(initial_data)
            
            # Mark pipeline complete
            self.metrics.mark_checkpoint("pipeline_complete")
            
            # Add metrics to result metadata
            combined_metadata = {
                **result.metadata,
                "performance_metrics": self.metrics.get_summary()
            }
            
            # Create new PipelineData with updated metadata
            return PipelineData(
                media_type=result.media_type,
                content=result.content,
                metadata=combined_metadata
            )
            
        except Exception as e:
            # Mark error in metrics
            self.metrics.add_metadata("error", str(e))
            self.metrics.add_metadata("error_type", type(e).__name__)
            self.metrics.mark_checkpoint("pipeline_error")
            
            # Log the error with metrics context
            logging.error(
                f"Error in pipeline execution: {str(e)}",
                extra={"performance_metrics": self.metrics.get_all_metrics()}
            )
            
            # Re-raise the exception
            raise

class TrackingFactory:
    """
    Factory to create tracking wrappers for various components
    """
    
    @staticmethod
    def track_backend(backend: ModelBackend, metrics: Optional[PerformanceMetrics] = None) -> ModelBackendTracker:
        """Create a tracked backend wrapper"""
        return ModelBackendTracker(backend, metrics)
    
    @staticmethod
    def track_step(step: PipelineStep, metrics: Optional[PerformanceMetrics] = None, step_name: Optional[str] = None) -> PipelineStepTracker:
        """Create a tracked pipeline step wrapper"""
        return PipelineStepTracker(step, metrics, step_name)
    
    @staticmethod
    def track_pipeline(pipeline, metrics: Optional[PerformanceMetrics] = None) -> TrackedPipeline:
        """Create a tracked pipeline wrapper"""
        return TrackedPipeline(pipeline, metrics)