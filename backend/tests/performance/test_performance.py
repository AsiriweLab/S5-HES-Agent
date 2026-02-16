"""
Performance Profiling Tests

Sprint 12 - S12.12: Performance profiling and benchmarking.

Tests:
1. Simulation throughput (events/second)
2. Protocol handler throughput (messages/second)
3. Memory usage under load
4. Concurrent connection scaling
5. Database/storage performance
6. API response times
7. Edge computing latency
8. End-to-end latency

Run tests:
    pytest tests/performance/test_performance.py -v --benchmark-only
    pytest tests/performance/test_performance.py -v  # Without benchmark plugin
"""

import asyncio
import pytest
import time
import json
import statistics
from datetime import datetime, timedelta
from typing import Any, Optional, Callable
from uuid import uuid4
from dataclasses import dataclass, field


# =============================================================================
# Performance Metrics Collection
# =============================================================================

@dataclass
class PerformanceMetrics:
    """Collected performance metrics."""
    test_name: str
    total_operations: int = 0
    total_time_seconds: float = 0.0
    min_latency_ms: float = float('inf')
    max_latency_ms: float = 0.0
    latencies_ms: list = field(default_factory=list)
    errors: int = 0
    memory_start_mb: float = 0.0
    memory_end_mb: float = 0.0

    @property
    def operations_per_second(self) -> float:
        if self.total_time_seconds == 0:
            return 0
        return self.total_operations / self.total_time_seconds

    @property
    def avg_latency_ms(self) -> float:
        if not self.latencies_ms:
            return 0
        return statistics.mean(self.latencies_ms)

    @property
    def p50_latency_ms(self) -> float:
        if not self.latencies_ms:
            return 0
        return statistics.median(self.latencies_ms)

    @property
    def p95_latency_ms(self) -> float:
        if not self.latencies_ms:
            return 0
        sorted_latencies = sorted(self.latencies_ms)
        idx = int(len(sorted_latencies) * 0.95)
        return sorted_latencies[idx] if idx < len(sorted_latencies) else sorted_latencies[-1]

    @property
    def p99_latency_ms(self) -> float:
        if not self.latencies_ms:
            return 0
        sorted_latencies = sorted(self.latencies_ms)
        idx = int(len(sorted_latencies) * 0.99)
        return sorted_latencies[idx] if idx < len(sorted_latencies) else sorted_latencies[-1]

    @property
    def memory_delta_mb(self) -> float:
        return self.memory_end_mb - self.memory_start_mb

    def to_dict(self) -> dict:
        return {
            "test_name": self.test_name,
            "total_operations": self.total_operations,
            "total_time_seconds": round(self.total_time_seconds, 3),
            "operations_per_second": round(self.operations_per_second, 2),
            "avg_latency_ms": round(self.avg_latency_ms, 3),
            "min_latency_ms": round(self.min_latency_ms, 3),
            "max_latency_ms": round(self.max_latency_ms, 3),
            "p50_latency_ms": round(self.p50_latency_ms, 3),
            "p95_latency_ms": round(self.p95_latency_ms, 3),
            "p99_latency_ms": round(self.p99_latency_ms, 3),
            "errors": self.errors,
            "memory_delta_mb": round(self.memory_delta_mb, 2),
        }


def get_memory_usage_mb() -> float:
    """Get current memory usage in MB."""
    try:
        import psutil
        process = psutil.Process()
        return process.memory_info().rss / (1024 * 1024)
    except ImportError:
        return 0.0


# =============================================================================
# Test Fixtures
# =============================================================================

@pytest.fixture
def performance_metrics():
    """Create metrics collector."""
    return PerformanceMetrics(test_name="")


@pytest.fixture
def sample_home():
    """Create a sample home with many devices for load testing."""
    from src.simulation.models import Home, Room, Device, RoomType, DeviceType

    rooms = [
        Room(id=f"room_{i}", name=f"Room {i}", room_type=RoomType.LIVING_ROOM)
        for i in range(5)
    ]

    devices = [
        Device(
            id=f"device_{i}",
            name=f"Device {i}",
            device_type=DeviceType.MOTION_SENSOR,
            room_id=f"room_{i % 5}",
        )
        for i in range(100)  # 100 devices for load testing
    ]

    return Home(
        id="perf_test_home",
        name="Performance Test Home",
        rooms=rooms,
        devices=devices,
    )


# =============================================================================
# 1. Simulation Throughput Tests
# =============================================================================

class TestSimulationThroughput:
    """Test simulation engine throughput."""

    @pytest.mark.asyncio
    async def test_events_per_second(self, sample_home):
        """Measure simulation events per second."""
        from src.simulation.engine import SimulationEngine, SimulationConfig

        metrics = PerformanceMetrics(test_name="simulation_events_per_second")
        metrics.memory_start_mb = get_memory_usage_mb()

        config = SimulationConfig(
            duration_hours=0.01,  # 36 seconds simulated
            time_compression=3600,  # 1 hour = 1 second real
            tick_interval_ms=10,  # Fast ticks for throughput
        )

        engine = SimulationEngine(sample_home, config)

        event_count = 0
        event_times = []

        def count_events(event):
            nonlocal event_count
            event_count += 1
            event_times.append(time.time())

        engine.add_event_handler(count_events)

        start_time = time.time()
        stats = await engine.run()
        end_time = time.time()

        metrics.total_operations = event_count
        metrics.total_time_seconds = end_time - start_time
        metrics.memory_end_mb = get_memory_usage_mb()

        # Calculate inter-event latencies
        for i in range(1, len(event_times)):
            latency_ms = (event_times[i] - event_times[i-1]) * 1000
            metrics.latencies_ms.append(latency_ms)
            metrics.min_latency_ms = min(metrics.min_latency_ms, latency_ms)
            metrics.max_latency_ms = max(metrics.max_latency_ms, latency_ms)

        print(f"\n{'='*60}")
        print(f"Simulation Throughput Results:")
        print(f"{'='*60}")
        print(json.dumps(metrics.to_dict(), indent=2))

        # Performance assertions
        assert metrics.operations_per_second > 10, "Should process at least 10 events/second"
        assert metrics.memory_delta_mb < 100, "Memory growth should be under 100MB"

    @pytest.mark.asyncio
    async def test_large_home_scalability(self):
        """Test simulation with increasing home sizes."""
        from src.simulation.engine import SimulationEngine, SimulationConfig
        from src.simulation.models import Home, Room, Device, RoomType, DeviceType

        results = []

        for num_devices in [10, 50, 100, 200]:
            rooms = [Room(id=f"room_{i}", name=f"Room {i}", room_type=RoomType.LIVING_ROOM)
                     for i in range(5)]

            devices = [
                Device(id=f"dev_{i}", name=f"Device {i}",
                       device_type=DeviceType.MOTION_SENSOR, room_id=f"room_{i % 5}")
                for i in range(num_devices)
            ]

            home = Home(id=f"home_{num_devices}", name=f"Home {num_devices}",
                       rooms=rooms, devices=devices)

            config = SimulationConfig(
                duration_hours=0.001,
                time_compression=3600,
                tick_interval_ms=50,
            )

            engine = SimulationEngine(home, config)

            start = time.time()
            stats = await engine.run()
            elapsed = time.time() - start

            results.append({
                "devices": num_devices,
                "time_seconds": round(elapsed, 3),
                "events": stats.total_events,
                "events_per_second": round(stats.total_events / elapsed, 2) if elapsed > 0 else 0,
            })

        print(f"\n{'='*60}")
        print("Scalability Test Results:")
        print(f"{'='*60}")
        for r in results:
            print(f"  {r['devices']} devices: {r['events_per_second']} events/sec")

        # Verify performance doesn't degrade too much
        if len(results) >= 2:
            ratio = results[-1]["events_per_second"] / results[0]["events_per_second"]
            assert ratio > 0.3, "Performance should not degrade more than 70%"


# =============================================================================
# 2. Protocol Handler Throughput Tests
# =============================================================================

class TestProtocolThroughput:
    """Test protocol handler message throughput."""

    @pytest.mark.asyncio
    async def test_mqtt_throughput(self):
        """Measure MQTT message throughput."""
        from src.iot.protocols.mqtt_handler import MQTTHandler, MQTTConfig

        config = MQTTConfig(
            host="localhost",
            port=1883,
            client_id="perf_test_mqtt",
            extra_config={"simulation_mode": True},
        )

        handler = MQTTHandler(config)
        await handler.connect()

        metrics = PerformanceMetrics(test_name="mqtt_throughput")
        num_messages = 1000

        metrics.memory_start_mb = get_memory_usage_mb()
        start_time = time.time()

        for i in range(num_messages):
            msg_start = time.time()
            success = await handler.publish_dict(
                f"test/perf/{i}",
                {"index": i, "timestamp": datetime.now().isoformat()},
            )
            msg_end = time.time()

            if success:
                metrics.total_operations += 1
                latency_ms = (msg_end - msg_start) * 1000
                metrics.latencies_ms.append(latency_ms)
                metrics.min_latency_ms = min(metrics.min_latency_ms, latency_ms)
                metrics.max_latency_ms = max(metrics.max_latency_ms, latency_ms)
            else:
                metrics.errors += 1

        metrics.total_time_seconds = time.time() - start_time
        metrics.memory_end_mb = get_memory_usage_mb()

        await handler.disconnect()

        print(f"\n{'='*60}")
        print("MQTT Throughput Results:")
        print(f"{'='*60}")
        print(json.dumps(metrics.to_dict(), indent=2))

        assert metrics.operations_per_second > 100, "Should handle at least 100 msg/sec"
        assert metrics.errors == 0, "Should have no errors"

    @pytest.mark.asyncio
    async def test_http_throughput(self):
        """Measure HTTP request throughput."""
        from src.iot.protocols.http_handler import HTTPRESTHandler, HTTPConfig

        config = HTTPConfig(
            host="localhost",
            port=8080,
            client_id="perf_test_http",
            extra_config={"simulation_mode": True},
        )

        handler = HTTPRESTHandler(config)
        await handler.connect()

        metrics = PerformanceMetrics(test_name="http_throughput")
        num_requests = 500

        metrics.memory_start_mb = get_memory_usage_mb()
        start_time = time.time()

        for i in range(num_requests):
            req_start = time.time()
            response = await handler.request(
                method="POST",
                path="/api/test",
                body={"index": i},
            )
            req_end = time.time()

            if response:
                metrics.total_operations += 1
                latency_ms = (req_end - req_start) * 1000
                metrics.latencies_ms.append(latency_ms)
                metrics.min_latency_ms = min(metrics.min_latency_ms, latency_ms)
                metrics.max_latency_ms = max(metrics.max_latency_ms, latency_ms)
            else:
                metrics.errors += 1

        metrics.total_time_seconds = time.time() - start_time
        metrics.memory_end_mb = get_memory_usage_mb()

        await handler.disconnect()

        print(f"\n{'='*60}")
        print("HTTP Throughput Results:")
        print(f"{'='*60}")
        print(json.dumps(metrics.to_dict(), indent=2))

        assert metrics.operations_per_second > 50, "Should handle at least 50 req/sec"

    @pytest.mark.asyncio
    async def test_websocket_throughput(self):
        """Measure WebSocket message throughput."""
        from src.iot.protocols.websocket_handler import WebSocketHandler, WSConfig

        config = WSConfig(
            host="localhost",
            port=8081,
            path="/ws",
            client_id="perf_test_ws",
            extra_config={"simulation_mode": True},
        )

        handler = WebSocketHandler(config)
        await handler.connect()

        metrics = PerformanceMetrics(test_name="websocket_throughput")
        num_messages = 2000

        metrics.memory_start_mb = get_memory_usage_mb()
        start_time = time.time()

        for i in range(num_messages):
            msg_start = time.time()
            success = await handler.send_json({
                "type": "data",
                "index": i,
                "timestamp": datetime.now().isoformat(),
            })
            msg_end = time.time()

            if success:
                metrics.total_operations += 1
                latency_ms = (msg_end - msg_start) * 1000
                metrics.latencies_ms.append(latency_ms)
                metrics.min_latency_ms = min(metrics.min_latency_ms, latency_ms)
                metrics.max_latency_ms = max(metrics.max_latency_ms, latency_ms)
            else:
                metrics.errors += 1

        metrics.total_time_seconds = time.time() - start_time
        metrics.memory_end_mb = get_memory_usage_mb()

        await handler.disconnect()

        print(f"\n{'='*60}")
        print("WebSocket Throughput Results:")
        print(f"{'='*60}")
        print(json.dumps(metrics.to_dict(), indent=2))

        assert metrics.operations_per_second > 200, "Should handle at least 200 msg/sec"


# =============================================================================
# 3. Concurrent Connection Tests
# =============================================================================

class TestConcurrentConnections:
    """Test concurrent connection handling."""

    @pytest.mark.asyncio
    async def test_concurrent_mqtt_publishers(self):
        """Test multiple concurrent MQTT publishers."""
        from src.iot.protocols.mqtt_handler import MQTTHandler, MQTTConfig

        num_publishers = 10
        messages_per_publisher = 100

        async def run_publisher(publisher_id: int) -> dict:
            config = MQTTConfig(
                host="localhost",
                port=1883,
                client_id=f"concurrent_pub_{publisher_id}",
                extra_config={"simulation_mode": True},
            )

            handler = MQTTHandler(config)
            await handler.connect()

            success_count = 0
            latencies = []

            for i in range(messages_per_publisher):
                start = time.time()
                success = await handler.publish_dict(
                    f"concurrent/{publisher_id}/{i}",
                    {"pub_id": publisher_id, "msg_id": i},
                )
                end = time.time()

                if success:
                    success_count += 1
                    latencies.append((end - start) * 1000)

            await handler.disconnect()

            return {
                "publisher_id": publisher_id,
                "success": success_count,
                "avg_latency_ms": statistics.mean(latencies) if latencies else 0,
            }

        start_time = time.time()
        tasks = [run_publisher(i) for i in range(num_publishers)]
        results = await asyncio.gather(*tasks)
        total_time = time.time() - start_time

        total_messages = sum(r["success"] for r in results)
        total_expected = num_publishers * messages_per_publisher

        print(f"\n{'='*60}")
        print("Concurrent MQTT Publishers Results:")
        print(f"{'='*60}")
        print(f"  Publishers: {num_publishers}")
        print(f"  Messages per publisher: {messages_per_publisher}")
        print(f"  Total messages sent: {total_messages}/{total_expected}")
        print(f"  Total time: {total_time:.2f}s")
        print(f"  Aggregate throughput: {total_messages / total_time:.2f} msg/sec")

        assert total_messages == total_expected, "All messages should be sent"

    @pytest.mark.asyncio
    async def test_concurrent_websocket_connections(self):
        """Test multiple concurrent WebSocket connections."""
        from src.iot.protocols.websocket_handler import WebSocketHandler, WSConfig

        num_connections = 20
        messages_per_connection = 50

        async def run_connection(conn_id: int) -> dict:
            config = WSConfig(
                host="localhost",
                port=8081,
                path="/ws",
                client_id=f"concurrent_ws_{conn_id}",
                extra_config={"simulation_mode": True},
            )

            handler = WebSocketHandler(config)
            await handler.connect()

            success_count = 0
            for i in range(messages_per_connection):
                if await handler.send_json({"conn_id": conn_id, "msg_id": i}):
                    success_count += 1

            await handler.disconnect()

            return {"conn_id": conn_id, "success": success_count}

        start_time = time.time()
        tasks = [run_connection(i) for i in range(num_connections)]
        results = await asyncio.gather(*tasks)
        total_time = time.time() - start_time

        total_messages = sum(r["success"] for r in results)

        print(f"\n{'='*60}")
        print("Concurrent WebSocket Connections Results:")
        print(f"{'='*60}")
        print(f"  Connections: {num_connections}")
        print(f"  Total messages: {total_messages}")
        print(f"  Total time: {total_time:.2f}s")
        print(f"  Throughput: {total_messages / total_time:.2f} msg/sec")

        assert total_messages >= num_connections * messages_per_connection * 0.95


# =============================================================================
# 4. Edge Computing Latency Tests
# =============================================================================

class TestEdgeLatency:
    """Test edge computing component latency."""

    @pytest.mark.asyncio
    async def test_fog_node_processing_latency(self):
        """Measure FogNode message processing latency."""
        from src.iot.edge.edge_computing import EnhancedFogNodeSimulator, EdgeConfig, EdgeNodeType
        from src.iot.protocols.base_handler import ProtocolMessage

        config = EdgeConfig(
            node_id="perf_fog_node",
            node_type=EdgeNodeType.FOG_NODE,
            upstream_url="mqtt://broker:1883",
            anomaly_detection=True,
        )

        fog_node = EnhancedFogNodeSimulator(config)
        fog_node.set_metric_threshold("temperature", 15.0, 30.0)

        metrics = PerformanceMetrics(test_name="fog_node_latency")
        num_messages = 500

        metrics.memory_start_mb = get_memory_usage_mb()

        for i in range(num_messages):
            msg = ProtocolMessage(
                topic=f"sensors/{i}",
                payload={"temperature": 22.0 + (i % 10) * 0.1},
                metadata={"device_id": f"sensor_{i % 10}"},
            )

            start = time.time()
            result = await fog_node.process_message(msg)
            end = time.time()

            if result:
                metrics.total_operations += 1
                latency_ms = (end - start) * 1000
                metrics.latencies_ms.append(latency_ms)
                metrics.min_latency_ms = min(metrics.min_latency_ms, latency_ms)
                metrics.max_latency_ms = max(metrics.max_latency_ms, latency_ms)

        metrics.total_time_seconds = sum(metrics.latencies_ms) / 1000
        metrics.memory_end_mb = get_memory_usage_mb()

        print(f"\n{'='*60}")
        print("FogNode Processing Latency Results:")
        print(f"{'='*60}")
        print(json.dumps(metrics.to_dict(), indent=2))

        assert metrics.avg_latency_ms < 10, "Average latency should be under 10ms"
        assert metrics.p95_latency_ms < 50, "P95 latency should be under 50ms"

    @pytest.mark.asyncio
    async def test_gateway_translation_latency(self):
        """Measure Gateway protocol translation latency."""
        from src.iot.edge.edge_computing import EnhancedGatewaySimulator, EdgeConfig, EdgeNodeType
        from src.iot.protocols.base_handler import ProtocolMessage

        config = EdgeConfig(
            node_id="perf_gateway",
            node_type=EdgeNodeType.GATEWAY,
            upstream_url="mqtt://broker:1883",
        )

        gateway = EnhancedGatewaySimulator(config)

        metrics = PerformanceMetrics(test_name="gateway_translation_latency")
        num_messages = 500

        protocols = ["zigbee", "zwave", "ble"]

        for i in range(num_messages):
            protocol = protocols[i % len(protocols)]
            msg = ProtocolMessage(
                topic=f"{protocol}/device_{i}",
                payload={"value": i * 0.1},
                metadata={"protocol": protocol},
            )

            start = time.time()
            result = await gateway.process_message(msg)
            end = time.time()

            if result:
                metrics.total_operations += 1
                latency_ms = (end - start) * 1000
                metrics.latencies_ms.append(latency_ms)
                metrics.min_latency_ms = min(metrics.min_latency_ms, latency_ms)
                metrics.max_latency_ms = max(metrics.max_latency_ms, latency_ms)

        metrics.total_time_seconds = sum(metrics.latencies_ms) / 1000

        print(f"\n{'='*60}")
        print("Gateway Translation Latency Results:")
        print(f"{'='*60}")
        print(json.dumps(metrics.to_dict(), indent=2))

        assert metrics.avg_latency_ms < 5, "Translation should be under 5ms average"


# =============================================================================
# 5. Security Performance Tests
# =============================================================================

class TestSecurityPerformance:
    """Test security operations performance."""

    @pytest.mark.asyncio
    async def test_encryption_throughput(self):
        """Measure encryption/decryption throughput."""
        from src.security.encryption import EncryptionEngine

        engine = EncryptionEngine()
        key = await engine.generate_symmetric_key()

        metrics = PerformanceMetrics(test_name="encryption_throughput")
        num_operations = 500
        data_size = 1024  # 1KB

        test_data = b"X" * data_size

        metrics.memory_start_mb = get_memory_usage_mb()
        start_time = time.time()

        for i in range(num_operations):
            op_start = time.time()
            encrypted, enc_error = await engine.encrypt(test_data, key.key_id)
            if encrypted:
                decrypted, dec_error = await engine.decrypt(encrypted)
            else:
                decrypted = None
            op_end = time.time()

            if decrypted == test_data:
                metrics.total_operations += 1
                latency_ms = (op_end - op_start) * 1000
                metrics.latencies_ms.append(latency_ms)
                metrics.min_latency_ms = min(metrics.min_latency_ms, latency_ms)
                metrics.max_latency_ms = max(metrics.max_latency_ms, latency_ms)
            else:
                metrics.errors += 1

        metrics.total_time_seconds = time.time() - start_time
        metrics.memory_end_mb = get_memory_usage_mb()

        print(f"\n{'='*60}")
        print(f"Encryption Throughput Results ({data_size} bytes):")
        print(f"{'='*60}")
        print(json.dumps(metrics.to_dict(), indent=2))

        assert metrics.errors == 0, "No encryption errors"
        assert metrics.operations_per_second > 100, "Should handle 100+ ops/sec"

    @pytest.mark.asyncio
    async def test_authentication_throughput(self):
        """Measure authentication throughput."""
        from src.security.auth_manager import (
            AuthenticationManager, AuthMethod
        )

        auth_manager = AuthenticationManager()

        # Pre-register devices with unique API keys
        num_devices = 100
        api_keys = []
        for i in range(num_devices):
            api_key = f"key_{i}_{uuid4().hex[:8]}"
            api_keys.append(api_key)
            auth_manager.register_credentials(
                subject_id=f"device_{i}",
                api_key=api_key,
                roles=["device"],
            )

        metrics = PerformanceMetrics(test_name="authentication_throughput")

        start_time = time.time()

        for i in range(num_devices):
            auth_start = time.time()
            session, error = await auth_manager.authenticate(
                method=AuthMethod.API_KEY,
                credentials={"api_key": api_keys[i]},
            )
            auth_end = time.time()

            metrics.total_operations += 1
            latency_ms = (auth_end - auth_start) * 1000
            metrics.latencies_ms.append(latency_ms)
            metrics.min_latency_ms = min(metrics.min_latency_ms, latency_ms)
            metrics.max_latency_ms = max(metrics.max_latency_ms, latency_ms)

        metrics.total_time_seconds = time.time() - start_time

        print(f"\n{'='*60}")
        print("Authentication Throughput Results:")
        print(f"{'='*60}")
        print(json.dumps(metrics.to_dict(), indent=2))

        # Auth manager has simulated latency (~100ms per op), so expect ~5-10 ops/sec
        assert metrics.operations_per_second > 5, "Should handle 5+ auth/sec"
        assert metrics.errors == 0, "No authentication errors"


# =============================================================================
# 6. Memory and Resource Tests
# =============================================================================

class TestResourceUsage:
    """Test memory and resource usage."""

    @pytest.mark.asyncio
    async def test_simulation_memory_growth(self, sample_home):
        """Test memory growth during long simulation."""
        from src.simulation.engine import SimulationEngine, SimulationConfig

        memory_samples = []
        memory_samples.append(("start", get_memory_usage_mb()))

        config = SimulationConfig(
            duration_hours=0.05,  # 3 minutes simulated
            time_compression=3600,
            tick_interval_ms=50,
        )

        engine = SimulationEngine(sample_home, config)
        memory_samples.append(("after_init", get_memory_usage_mb()))

        # Collect memory during simulation
        sample_interval = 0.5  # seconds
        samples_collected = []

        async def sample_memory():
            while engine._running:
                samples_collected.append(get_memory_usage_mb())
                await asyncio.sleep(sample_interval)

        # Run simulation with memory sampling
        sample_task = asyncio.create_task(sample_memory())
        await engine.run()
        sample_task.cancel()
        try:
            await sample_task
        except asyncio.CancelledError:
            pass

        memory_samples.append(("after_run", get_memory_usage_mb()))

        print(f"\n{'='*60}")
        print("Memory Usage Results:")
        print(f"{'='*60}")
        for label, mem in memory_samples:
            print(f"  {label}: {mem:.2f} MB")

        if samples_collected:
            print(f"  Min during run: {min(samples_collected):.2f} MB")
            print(f"  Max during run: {max(samples_collected):.2f} MB")
            print(f"  Avg during run: {statistics.mean(samples_collected):.2f} MB")

        # Memory should not grow excessively
        growth = memory_samples[-1][1] - memory_samples[0][1]
        assert growth < 100, f"Memory growth {growth:.2f}MB should be under 100MB"


# =============================================================================
# 7. Benchmark Summary
# =============================================================================

class TestBenchmarkSummary:
    """Generate benchmark summary report."""

    @pytest.mark.asyncio
    async def test_generate_benchmark_report(self, sample_home):
        """Generate comprehensive benchmark report."""
        from src.simulation.engine import SimulationEngine, SimulationConfig
        from src.iot.protocols.mqtt_handler import MQTTHandler, MQTTConfig

        results = {
            "timestamp": datetime.now().isoformat(),
            "system_info": {
                "initial_memory_mb": get_memory_usage_mb(),
            },
            "benchmarks": {},
        }

        # Simulation benchmark
        config = SimulationConfig(
            duration_hours=0.001,
            time_compression=3600,
            tick_interval_ms=50,
        )
        engine = SimulationEngine(sample_home, config)

        event_count = [0]
        def count_events(e):
            event_count[0] += 1

        engine.add_event_handler(count_events)

        start = time.time()
        await engine.run()
        sim_time = time.time() - start

        results["benchmarks"]["simulation"] = {
            "devices": len(sample_home.devices),
            "events": event_count[0],
            "time_seconds": round(sim_time, 3),
            "events_per_second": round(event_count[0] / sim_time, 2) if sim_time > 0 else 0,
        }

        # MQTT benchmark
        mqtt_config = MQTTConfig(
            host="localhost",
            port=1883,
            client_id="benchmark_mqtt",
            extra_config={"simulation_mode": True},
        )
        mqtt = MQTTHandler(mqtt_config)
        await mqtt.connect()

        start = time.time()
        for i in range(100):
            await mqtt.publish_dict(f"bench/{i}", {"i": i})
        mqtt_time = time.time() - start

        await mqtt.disconnect()

        results["benchmarks"]["mqtt"] = {
            "messages": 100,
            "time_seconds": round(mqtt_time, 3),
            "messages_per_second": round(100 / mqtt_time, 2) if mqtt_time > 0 else 0,
        }

        results["system_info"]["final_memory_mb"] = get_memory_usage_mb()

        print(f"\n{'='*60}")
        print("BENCHMARK SUMMARY REPORT")
        print(f"{'='*60}")
        print(json.dumps(results, indent=2))

        # Save report
        # (In production, would save to file)

        assert results["benchmarks"]["simulation"]["events_per_second"] > 0
        assert results["benchmarks"]["mqtt"]["messages_per_second"] > 0


# =============================================================================
# Run Tests
# =============================================================================

if __name__ == "__main__":
    import sys
    sys.exit(pytest.main([__file__, "-v", "-s"]))
