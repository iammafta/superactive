import pytest
import asyncio
from pipecat.frames.frames import AudioRawFrame, TranscriptionFrame, ErrorFrame
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import InMemoryMetricReader
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from opentelemetry import metrics, trace

from routes.telephony import TelemetryFrameProcessor, stt_latency_histogram, pipeline_lag_histogram, stt_failure_counter
from pipecat.processors.frame_processor import FrameDirection

@pytest.fixture(scope="session", autouse=True)
def otel_setup():
    """Setup InMemory exporters for testing OpenTelemetry metrics and traces once."""
    metric_reader = InMemoryMetricReader()
    meter_provider = MeterProvider(metric_readers=[metric_reader])
    
    try:
        metrics.set_meter_provider(meter_provider)
    except Exception:
        pass  # Ignore if it was somehow already set

    # Re-bind the module-level instruments for testing to the new provider
    import routes.telephony
    routes.telephony.meter = metrics.get_meter("superactive.pipecat.test")

    # Setup Traces
    tracer_provider = TracerProvider()
    span_exporter = InMemorySpanExporter()
    tracer_provider.add_span_processor(SimpleSpanProcessor(span_exporter))
    try:
        trace.set_tracer_provider(tracer_provider)
    except Exception:
        pass

    yield metric_reader, span_exporter

@pytest.fixture(autouse=True)
def otel_clear_metrics(otel_setup):
    """Clear memory exporters between test functions."""
    metric_reader, span_exporter = otel_setup
    span_exporter.clear()
    # Metrics don't have a simple clear(), but we can force flush to clear delta state or just ignore stale ones.
    yield metric_reader, span_exporter


@pytest.mark.asyncio
async def test_stt_latency_metric(otel_clear_metrics):
    """Verify that TelemetryFrameProcessor records STT latency when a TranscriptionFrame follows an AudioRawFrame."""
    metric_reader, _ = otel_clear_metrics
    
    processor = TelemetryFrameProcessor()
    
    # Mock push_frame to avoid pipeline hanging when no downstream processor exists
    async def mock_push_frame(frame, direction):
        pass
    processor.push_frame = mock_push_frame
    
    # 1. Simulate Audio entering pipeline
    audio_frame = AudioRawFrame(audio=b"dummy", sample_rate=16000, num_channels=1)
    await processor.process_frame(audio_frame, FrameDirection.DOWNSTREAM)
    
    # 2. Simulate small delay (STT processing time)
    await asyncio.sleep(0.1)
    
    # 3. Simulate Transcription arriving
    transcription_frame = TranscriptionFrame(text="hello world", user_id="user_1", timestamp="")
    await processor.process_frame(transcription_frame, FrameDirection.DOWNSTREAM)
    
    # 4. Verify Metrics
    metric_reader.force_flush()
    metrics_data = metric_reader.get_metrics_data()
    
    # Find latency histogram
    latency_data = None
    lag_data = None
    if metrics_data:
        for resource_metrics in metrics_data.resource_metrics:
            for scope_metrics in resource_metrics.scope_metrics:
                for metric in scope_metrics.metrics:
                    if metric.name == "pipecat.stt.latency":
                        latency_data = metric
                    elif metric.name == "pipecat.pipeline.lag":
                        lag_data = metric

    assert latency_data is not None, "Latency metric was not recorded"
    
    histogram_point = list(latency_data.data.data_points)[0]
    recorded_sum = histogram_point.sum
    recorded_count = histogram_point.count
    
    assert recorded_count == 1
    assert recorded_sum > 0  # Should be ~100ms
    assert lag_data is not None, "Pipeline lag was not recorded"


@pytest.mark.asyncio
async def test_stt_failure_metric_and_trace(otel_clear_metrics):
    """Verify that STT Error frames increment the failure counter and create a trace span."""
    metric_reader, span_exporter = otel_clear_metrics
    
    processor = TelemetryFrameProcessor()
    
    async def mock_push_frame(frame, direction):
        pass
    processor.push_frame = mock_push_frame
    
    # Simulate an error frame from Google STT
    error_frame = ErrorFrame(error="Google Cloud Speech API exception: Failed to recognize audio", fatal=False)
    await processor.process_frame(error_frame, FrameDirection.DOWNSTREAM)
    
    # Verify Metrics Counter
    metric_reader.force_flush()
    metrics_data = metric_reader.get_metrics_data()
    counter_data = None
    if metrics_data:
        for resource_metrics in metrics_data.resource_metrics:
            for scope_metrics in resource_metrics.scope_metrics:
                for metric in scope_metrics.metrics:
                    if metric.name == "pipecat.stt.failures":
                        counter_data = metric

    assert counter_data is not None, "STT failure counter was not recorded"
    
    counter_point = list(counter_data.data.data_points)[0]
    assert counter_point.value == 1

    # Verify Traces
    spans = span_exporter.get_finished_spans()
    assert len(spans) == 1
    
    span = spans[0]
    assert span.name == "pipeline_error_frame"
    assert span.attributes["fatal"] is False
    assert span.attributes["error.type"] == "stt_failure"
