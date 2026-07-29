"""습도 등급 분류.

체감온도 계산은 제거했다. 단기예보 API가 체감온도를 주지 않아
직접 계산하면 기상청 공식 값과 어긋날 수 있기 때문이다.
"""
from src.comfort import humidity_band


class TestHumidityBand:
    def test_bands_by_threshold(self):
        assert humidity_band(85)[0] == "매우 습함"
        assert humidity_band(75)[0] == "습함"
        assert humidity_band(60)[0] == "약간 습함"
        assert humidity_band(35)[0] == "쾌적"

    def test_boundaries_are_inclusive(self):
        assert humidity_band(80)[0] == "매우 습함"
        assert humidity_band(79.9)[0] == "습함"
        assert humidity_band(70)[0] == "습함"
        assert humidity_band(55)[0] == "약간 습함"

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

    def test_no_temperature_is_invented(self):
        # 이 모듈은 숫자를 만들어내지 않는다. 분류와 문구만 담당한다.
        import src.comfort as comfort

        assert not hasattr(comfort, "apparent_temperature")
        assert not hasattr(comfort, "wet_bulb")
