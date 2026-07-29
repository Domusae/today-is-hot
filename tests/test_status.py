"""probe-msg로 확인한 실제 t6 형식을 기준으로 작성했다."""
from src.status import heat_warnings_for, is_included, parse_status, split_top_level

# 2026-07-29 10:00 본청 통보문 t6에서 발췌한 실제 문자열.
REAL_T6 = (
    "o 폭염중대경보 : 경상남도(양산, 김해, 밀양, 의령, 창녕)\r\n"
    "o 폭염경보 : 경기도(고양, 남양주, 오산), 충청남도(아산, 부여), "
    "전라남도(완도(여서도 제외), 무안북부), 서울(서울서북권 제외), 인천(인천북부), 대전\r\n"
    "o 폭염주의보 : 경기도(광명, 과천), 서울(서울서북권), 인천(인천북부 제외)\r\n"
    "o 열대야주의보 : 서울, 인천(옹진 제외), 대전"
)

GANGNAM = ("서울", "서울동남권")  # 강남·서초·송파·강동
SEODAEMUN = ("서울", "서울서북권")  # 은평·서대문·마포·종로·중구·용산


class TestSplitTopLevel:
    def test_splits_on_top_level_commas(self):
        assert split_top_level("서울, 인천, 대전") == ["서울", "인천", "대전"]

    def test_ignores_commas_inside_parentheses(self):
        assert split_top_level("경기도(고양, 남양주), 서울") == ["경기도(고양, 남양주)", "서울"]

    def test_handles_nested_parentheses(self):
        # 전라남도(완도(여서도 제외), 무안북부) 처럼 괄호가 겹친다.
        assert split_top_level("전라남도(완도(여서도 제외), 무안북부), 서울") == [
            "전라남도(완도(여서도 제외), 무안북부)",
            "서울",
        ]

    def test_empty_input(self):
        assert split_top_level("") == []


class TestParseStatus:
    def test_reads_every_warning_line(self):
        status = parse_status(REAL_T6)
        assert set(status) == {"폭염중대경보", "폭염경보", "폭염주의보", "열대야주의보"}

    def test_skips_none_lines(self):
        assert parse_status("o 없음") == {}

    def test_ignores_non_status_text(self):
        assert parse_status("설명 문단입니다\no 폭염경보 : 대전") == {"폭염경보": "대전"}


class TestIsIncluded:
    def test_bare_area_means_everywhere(self):
        assert is_included("서울, 대전", *GANGNAM)

    def test_exclusion_covers_everyone_else(self):
        # 서울(서울서북권 제외) → 동남권은 포함
        assert is_included("서울(서울서북권 제외)", *GANGNAM)
        assert not is_included("서울(서울서북권 제외)", *SEODAEMUN)

    def test_explicit_list_only_covers_listed(self):
        assert is_included("서울(서울서북권)", *SEODAEMUN)
        assert not is_included("서울(서울서북권)", *GANGNAM)

    def test_absent_area_is_false(self):
        assert not is_included("경기도(고양), 인천(인천북부)", *GANGNAM)

    def test_other_area_with_similar_name_does_not_match(self):
        assert not is_included("서울시(서울동남권)", *GANGNAM)

    def test_region_without_sub_area(self):
        assert is_included("대전, 세종(세종남부)", "대전", None)
        assert is_included("세종(세종남부)", "세종", None)

    def test_nested_parentheses_do_not_confuse_matching(self):
        areas = "전라남도(완도(여서도 제외), 무안북부), 서울(서울서북권 제외)"
        assert is_included(areas, *GANGNAM)


class TestHeatWarningsFor:
    def test_gangnam_gets_the_warning_not_the_advisory(self):
        # 실제 데이터상 강남(동남권)은 폭염경보, 서북권만 폭염주의보다.
        assert heat_warnings_for(REAL_T6, *GANGNAM) == ["폭염경보"]

    def test_seodaemun_gets_the_advisory(self):
        assert heat_warnings_for(REAL_T6, *SEODAEMUN) == ["폭염주의보"]

    def test_excludes_tropical_night(self):
        # 열대야주의보는 서울 전역이지만 이 캠페인 범위 밖이다.
        assert "열대야주의보" not in heat_warnings_for(REAL_T6, *GANGNAM)

    def test_severe_warning_is_detected(self):
        assert heat_warnings_for(REAL_T6, "경상남도", "김해") == ["폭염중대경보"]

    def test_sorted_strongest_first(self):
        t6 = "o 폭염주의보 : 대전\r\no 폭염중대경보 : 대전\r\no 폭염경보 : 대전"
        assert heat_warnings_for(t6, "대전", None) == [
            "폭염중대경보",
            "폭염경보",
            "폭염주의보",
        ]

    def test_no_warning_returns_empty(self):
        assert heat_warnings_for("o 폭염경보 : 부산", *GANGNAM) == []

    def test_empty_input_is_safe(self):
        assert heat_warnings_for("", *GANGNAM) == []
