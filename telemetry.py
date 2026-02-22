"""
Superactive — Centralized Telemetry

Initializes OpenTelemetry Tracer and Meter providers to export metrics and
traces to Jaeger/Prometheus (or DataDog/Grafana Cloud).
"""

import os
from opentelemetry import trace, metrics
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader

def init_telemetry(service_name: str):
    """Initialize OpenTelemetry Tracer and Meter providers globally."""
    resource = Resource.create({"service.name": service_name})
    
    # 1. Traces
    provider = TracerProvider(resource=resource)
    try:
        from opentelemetry.exporter.cloud_trace import CloudTraceSpanExporter
        span_exporter = CloudTraceSpanExporter(project_id=os.getenv("GCP_PROJECT_ID", "divine-apogee-480205-h8"))
    except ImportError:
        print("Warning: CloudTraceSpanExporter not found, falling back to ConsoleSpanExporter")
        from opentelemetry.sdk.trace.export import ConsoleSpanExporter
        span_exporter = ConsoleSpanExporter()
        
    processor = BatchSpanProcessor(span_exporter)
    provider.add_span_processor(processor)
    trace.set_tracer_provider(provider)
    
    # 2. Metrics
    try:
        from opentelemetry.exporter.cloud_monitoring import CloudMonitoringMetricsExporter
        metric_exporter = CloudMonitoringMetricsExporter(project_id=os.getenv("GCP_PROJECT_ID", "divine-apogee-480205-h8"))
    except ImportError:
        print("Warning: CloudMonitoringMetricsExporter not found, falling back to ConsoleMetricExporter")
        from opentelemetry.sdk.metrics.export import ConsoleMetricExporter
        metric_exporter = ConsoleMetricExporter()
        
    metric_reader = PeriodicExportingMetricReader(
        metric_exporter,
        export_interval_millis=5000  # Export every 5 seconds
    )
    meter_provider = MeterProvider(resource=resource, metric_readers=[metric_reader])
    metrics.set_meter_provider(meter_provider)

# Convenience accessors that can be imported anywhere
def get_tracer(name: str = "superactive.telephony"):
    return trace.get_tracer(name)

def get_meter(name: str = "superactive.telephony"):
    return metrics.get_meter(name)
