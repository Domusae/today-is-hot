"""기상청 여름철 체감온도(2020 개정) 산식 검증."""
import pytest

from src.comfort import apparent_temperature, humidity_band, wet_bulb


class TestWetBulb:
    def test_saturated_air_equals_dry_bulb(self):
        # 습도 100%면 습구온도는 기온과 거의 같다.
        assert wet_bulb(30.0, 100.0) == pytest.approx(30.0, abs=0.5)

    def test_dry_air_is_much_lower(self):
        assert wet_bulb(30.0, 20.0) < 20.0

    def test_rises_with_humidity(self):
        assert wet_bulb(30.0, 40.0) < wet_bulb(30.0, 60.0) < wet_bulb(30.0, 80.0)


class TestApparentTemperature:
    def test_humidity_pushes_it_above_air_temperature(self):
        # 33도 습도 80%는 체감이 기온보다 확실히 높다.
        assert apparent_temperature(33.0, 80.0) > 35.0

    def test_dry_air_feels_close_to_air_temperature(self):
        feels = apparent_temperature(33.0, 30.0)
        assert 30.0 < feels < 34.0

    def test_monotonic_in_humidity(self):
        values = [apparent_temperature(32.0, rh) for rh in (30, 50, 70, 90)]
        assert values == sorted(values)

    def test_monotonic_in_temperature(self):
        values = [apparent_temperature(t, 60.0) for t in (28, 31, 34, 37)]
        assert values == sorted(values)

    def test_stays_in_a_plausible_range(self):
        # 기상청 공식 대조표로 검증한 값이 아니라, 산식이 상식적인 범위를
        # 벗어나지 않는지만 본다. 습하면 기온보다 높고, 터무니없이 높지는 않다.
        feels = apparent_temperature(31.0, 70.0)
        assert 31.0 < feels < 36.0


class TestHumidityBand:
    def test_bands_by_threshold(self):
        assert humidity_band(85)[0] == "매우 습함"
        assert humidity_band(75)[0] == "습함"
        assert humidity_band(60)[0] == "약간 습함"
        assert humidity_band(35)[0] == "쾌적"

    def test_boundaries_are_inclusive(self):
        assert humidity_band(80)[0] == "매우 습함"
        assert humidity_band(79.9)[0] == "습함"

    def test_every_band_has_messages(self):
        for rh in (10, 30, 55, 70, 80, 95, 100):
            name, notes = humidity_band(rh)
            assert name and notes

    def test_messages_accept_humidity_format(self):
        # 멘트에 {rh} 자리표시자가 들어가므로 format이 깨지면 안 된다.
        for rh in (25.0, 65.0, 75.0, 88.0):
            for note in humidity_band(rh)[1]:
                assert note.format(rh=rh)

    def test_zero_humidity_is_safe(self):
        assert humidity_band(0)[0] == "쾌적"
