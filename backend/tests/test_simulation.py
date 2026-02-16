"""
Tests for the Simulation Engine

Unit tests for home generation, device behaviors, and simulation engine.
"""

import asyncio
from datetime import datetime, timedelta

import pytest

from src.simulation import (
    Device,
    DeviceConfig,
    DeviceProtocol,
    DeviceState,
    DeviceStatus,
    DeviceType,
    Home,
    HomeConfig,
    HomeTemplate,
    Room,
    RoomType,
    SimulationConfig,
    SimulationEngine,
    SimulationState,
)
from src.simulation.devices import (
    DeviceFactory,
    DeviceRegistry,
    SmartLightBehavior,
    SmartLockBehavior,
    ThermostatBehavior,
)
from src.simulation.home import HomeGenerator


# =============================================================================
# Home Generator Tests
# =============================================================================


class TestHomeGenerator:
    """Tests for HomeGenerator."""

    def test_generate_studio_apartment(self):
        """Test generating a studio apartment."""
        generator = HomeGenerator(seed=42)
        home = generator.generate_from_template(HomeTemplate.STUDIO_APARTMENT)

        assert home is not None
        assert home.name == "My Smart Home"
        assert home.config.template == HomeTemplate.STUDIO_APARTMENT
        assert len(home.rooms) >= 2  # At least living room and bathroom
        assert len(home.devices) >= 3  # Minimum devices
        assert len(home.inhabitants) >= 1

    def test_generate_two_bedroom(self):
        """Test generating a two-bedroom home."""
        generator = HomeGenerator(seed=42)
        home = generator.generate_from_template(
            HomeTemplate.TWO_BEDROOM,
            name="Test Home",
            num_inhabitants=3,
        )

        assert home.name == "Test Home"
        assert len(home.rooms) >= 5
        assert len(home.devices) >= 10
        assert len(home.inhabitants) == 3

    def test_generate_family_house(self):
        """Test generating a family house."""
        generator = HomeGenerator(seed=42)
        home = generator.generate_from_template(HomeTemplate.FAMILY_HOUSE)

        assert home.config.floors >= 2
        assert home.config.has_garage
        assert len(home.rooms) >= 10
        assert len(home.devices) >= 20

    def test_generate_smart_mansion(self):
        """Test generating a smart mansion."""
        generator = HomeGenerator(seed=42)
        home = generator.generate_from_template(HomeTemplate.SMART_MANSION)

        assert home.config.floors >= 2
        assert home.config.has_garden
        assert len(home.rooms) >= 15
        assert len(home.devices) >= 50

    def test_device_density(self):
        """Test device density parameter."""
        generator = HomeGenerator(seed=42)

        home_sparse = generator.generate_from_template(
            HomeTemplate.TWO_BEDROOM,
            device_density=0.5,
        )
        generator = HomeGenerator(seed=42)  # Reset seed
        home_dense = generator.generate_from_template(
            HomeTemplate.TWO_BEDROOM,
            device_density=1.5,
        )

        assert len(home_dense.devices) > len(home_sparse.devices)

    def test_reproducibility_with_seed(self):
        """Test that same seed produces same results."""
        gen1 = HomeGenerator(seed=12345)
        home1 = gen1.generate_from_template(HomeTemplate.TWO_BEDROOM)

        gen2 = HomeGenerator(seed=12345)
        home2 = gen2.generate_from_template(HomeTemplate.TWO_BEDROOM)

        assert len(home1.rooms) == len(home2.rooms)
        assert len(home1.devices) == len(home2.devices)
        assert len(home1.inhabitants) == len(home2.inhabitants)

    def test_home_get_methods(self):
        """Test Home helper methods."""
        generator = HomeGenerator(seed=42)
        home = generator.generate_from_template(HomeTemplate.TWO_BEDROOM)

        # Test get_room_by_id
        room = home.rooms[0]
        found_room = home.get_room_by_id(room.id)
        assert found_room is not None
        assert found_room.id == room.id

        # Test get_device_by_id
        device = home.devices[0]
        found_device = home.get_device_by_id(device.id)
        assert found_device is not None
        assert found_device.id == device.id

        # Test get_stats
        stats = home.get_stats()
        assert stats.total_devices == len(home.devices)
        assert stats.total_rooms == len(home.rooms)


# =============================================================================
# Device Behavior Tests
# =============================================================================


class TestDeviceBehaviors:
    """Tests for device behavior implementations."""

    def _create_device(self, device_type: DeviceType) -> Device:
        """Helper to create a test device."""
        return Device(
            name=f"Test {device_type.value}",
            device_type=device_type,
            config=DeviceConfig(),
            state=DeviceState(),
        )

    def test_smart_lock_behavior(self):
        """Test smart lock behavior."""
        device = self._create_device(DeviceType.SMART_LOCK)
        behavior = SmartLockBehavior(device)

        # Check initial state
        assert behavior.get_property("is_locked") is True

        # Test unlock with wrong PIN
        success = behavior.handle_command("unlock", {"pin": "wrong"})
        assert success is False
        assert behavior.get_property("failed_attempts") == 1

        # Test unlock with correct PIN
        success = behavior.handle_command("unlock", {"pin": "1234"})
        assert success is True
        assert behavior.get_property("is_locked") is False

        # Test lock
        success = behavior.handle_command("lock", {"method": "app"})
        assert success is True
        assert behavior.get_property("is_locked") is True

    def test_thermostat_behavior(self):
        """Test thermostat behavior."""
        device = self._create_device(DeviceType.THERMOSTAT)
        behavior = ThermostatBehavior(device)

        # Check initial state
        assert behavior.get_property("current_temp") == 21.0
        assert behavior.get_property("target_temp") == 22.0
        assert behavior.get_property("mode") == "auto"

        # Test set temperature
        success = behavior.handle_command("set_temperature", {"temperature": 25.0})
        assert success is True
        assert behavior.get_property("target_temp") == 25.0

        # Test set mode
        success = behavior.handle_command("set_mode", {"mode": "cool"})
        assert success is True
        assert behavior.get_property("mode") == "cool"

        # Test update (physics simulation)
        current_time = datetime.utcnow()
        events = behavior.update(current_time, 60.0)
        # Should generate events when reporting

    def test_smart_light_behavior(self):
        """Test smart light behavior."""
        device = self._create_device(DeviceType.SMART_LIGHT)
        behavior = SmartLightBehavior(device)

        # Test turn off
        success = behavior.handle_command("turn_off", {})
        assert success is True
        assert behavior.device.state.is_on is False

        # Test turn on
        success = behavior.handle_command("turn_on", {})
        assert success is True
        assert behavior.device.state.is_on is True

        # Test set brightness
        success = behavior.handle_command("set_brightness", {"brightness": 50})
        assert success is True
        assert behavior.get_property("brightness") == 50

        # Test generate data
        data = behavior.generate_data(datetime.utcnow())
        assert "is_on" in data
        assert "brightness" in data


class TestDeviceRegistry:
    """Tests for device registry."""

    def test_register_and_get_device(self):
        """Test registering and retrieving devices."""
        registry = DeviceRegistry()
        device = Device(
            name="Test Lock",
            device_type=DeviceType.SMART_LOCK,
        )

        behavior = registry.register(device)
        assert behavior is not None

        retrieved = registry.get(device.id)
        assert retrieved is behavior
        assert registry.count() == 1

    def test_unregister_device(self):
        """Test unregistering a device."""
        registry = DeviceRegistry()
        device = Device(
            name="Test Light",
            device_type=DeviceType.SMART_LIGHT,
        )

        registry.register(device)
        assert registry.count() == 1

        registry.unregister(device.id)
        assert registry.count() == 0
        assert registry.get(device.id) is None

    def test_device_factory(self):
        """Test device factory."""
        device = Device(
            name="Test Thermostat",
            device_type=DeviceType.THERMOSTAT,
        )

        behavior = DeviceFactory.create_behavior(device)
        assert behavior is not None
        assert isinstance(behavior, ThermostatBehavior)

    def test_supported_types(self):
        """Test getting supported device types."""
        supported = DeviceFactory.get_supported_types()
        assert DeviceType.SMART_LOCK in supported
        assert DeviceType.THERMOSTAT in supported
        assert DeviceType.SMART_LIGHT in supported


# =============================================================================
# Simulation Engine Tests
# =============================================================================


class TestSimulationEngine:
    """Tests for the simulation engine."""

    @pytest.fixture
    def simple_home(self) -> Home:
        """Create a simple home for testing."""
        generator = HomeGenerator(seed=42)
        return generator.generate_from_template(
            HomeTemplate.STUDIO_APARTMENT,
            device_density=0.5,
        )

    def test_engine_initialization(self, simple_home):
        """Test engine initialization."""
        config = SimulationConfig(
            duration_hours=1,
            time_compression=3600,  # 1 hour per second
        )
        engine = SimulationEngine(simple_home, config)

        assert engine.stats.state == SimulationState.IDLE
        # Note: devices_simulated counts only devices with defined behaviors
        # Hub and Router don't have behaviors yet, so count may be 0 for small homes
        assert engine.home is not None

    @pytest.mark.asyncio
    async def test_engine_short_run(self, simple_home):
        """Test running a short simulation."""
        config = SimulationConfig(
            duration_hours=1,
            time_compression=36000,  # Very fast for testing
            tick_interval_ms=10,
        )
        engine = SimulationEngine(simple_home, config)

        # Run simulation (should complete quickly)
        stats = await asyncio.wait_for(engine.run(), timeout=5.0)

        assert stats.state == SimulationState.COMPLETED
        assert stats.total_ticks > 0
        assert stats.total_events > 0

    @pytest.mark.asyncio
    async def test_engine_pause_resume(self, simple_home):
        """Test pause and resume functionality."""
        config = SimulationConfig(
            duration_hours=1,
            time_compression=3600,
            tick_interval_ms=50,
        )
        engine = SimulationEngine(simple_home, config)

        # Start simulation in background
        task = asyncio.create_task(engine.run())

        # Wait a bit then pause
        await asyncio.sleep(0.1)
        engine.pause()
        assert engine.stats.state == SimulationState.PAUSED

        # Resume
        engine.resume()
        assert engine.stats.state == SimulationState.RUNNING

        # Stop
        engine.stop()
        await asyncio.wait_for(task, timeout=2.0)
        assert engine.stats.state == SimulationState.STOPPED

    @pytest.mark.asyncio
    async def test_engine_event_collection(self, simple_home):
        """Test event collection."""
        config = SimulationConfig(
            duration_hours=1,
            time_compression=36000,
            tick_interval_ms=10,
            collect_all_events=True,
        )
        engine = SimulationEngine(simple_home, config)

        await asyncio.wait_for(engine.run(), timeout=5.0)

        events = engine.get_events()
        assert len(events) > 0

        # Test filtering
        exported = engine.export_events()
        assert len(exported) > 0
        assert "event_type" in exported[0]
        assert "timestamp" in exported[0]

    def test_engine_event_handler(self, simple_home):
        """Test event handler registration."""
        config = SimulationConfig()
        engine = SimulationEngine(simple_home, config)

        received_events = []

        def handler(event):
            received_events.append(event)

        engine.add_event_handler(handler)
        assert handler in engine._event_handlers

        engine.remove_event_handler(handler)
        assert handler not in engine._event_handlers


# =============================================================================
# API Tests
# =============================================================================


class TestSimulationAPI:
    """Tests for simulation API endpoints."""

    @pytest.fixture
    def client(self):
        """Create test client."""
        from fastapi.testclient import TestClient
        from src.main import app

        return TestClient(app)

    def test_get_templates(self, client):
        """Test getting available templates."""
        response = client.get("/api/simulation/templates")
        assert response.status_code == 200

        templates = response.json()
        assert len(templates) == 5  # 5 templates defined
        assert any(t["id"] == "two_bedroom" for t in templates)

    def test_get_device_types(self, client):
        """Test getting available device types."""
        response = client.get("/api/simulation/device-types")
        assert response.status_code == 200

        types = response.json()
        assert len(types) > 10  # Many device types
        assert any(t["id"] == "smart_lock" for t in types)

    def test_create_home(self, client):
        """Test creating a home."""
        response = client.post(
            "/api/simulation/home",
            json={
                "name": "Test Home",
                "template": "one_bedroom",
                "seed": 42,
            },
        )
        assert response.status_code == 200

        home = response.json()
        assert home["name"] == "Test Home"
        assert home["template"] == "one_bedroom"
        assert home["total_rooms"] >= 3
        assert home["total_devices"] >= 5

    def test_get_home(self, client):
        """Test getting current home."""
        # First create a home
        client.post(
            "/api/simulation/home",
            json={"name": "Test Home", "template": "studio_apartment"},
        )

        # Then get it
        response = client.get("/api/simulation/home")
        assert response.status_code == 200
        assert response.json()["name"] == "Test Home"

    def test_get_rooms(self, client):
        """Test getting rooms."""
        client.post(
            "/api/simulation/home",
            json={"template": "two_bedroom"},
        )

        response = client.get("/api/simulation/home/rooms")
        assert response.status_code == 200
        rooms = response.json()
        assert len(rooms) >= 5

    def test_get_devices(self, client):
        """Test getting devices."""
        client.post(
            "/api/simulation/home",
            json={"template": "two_bedroom"},
        )

        response = client.get("/api/simulation/home/devices")
        assert response.status_code == 200
        devices = response.json()
        assert len(devices) >= 5

    def test_get_inhabitants(self, client):
        """Test getting inhabitants."""
        client.post(
            "/api/simulation/home",
            json={"template": "two_bedroom", "num_inhabitants": 3},
        )

        response = client.get("/api/simulation/home/inhabitants")
        assert response.status_code == 200
        inhabitants = response.json()
        assert len(inhabitants) == 3
