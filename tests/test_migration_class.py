"""migration class เป็นสัญญาของ plugin — ประกาศครบ ตรงกับ port และถูกบังคับตอนโหลด

ADR 0041: เครื่องมือที่วางแผนการสลับ (bench เฟส 10-03, เอกสาร, คนหน้างาน)
ต้องเชื่อค่าใน manifest ได้โดยไม่ต้องเดา — สามชั้นที่นี่:

1. ทุก plugin บนดิสก์ประกาศค่าที่ถูกต้อง (อ่านผ่าน registry จริง ไม่ใช่อ่านไฟล์เอง)
2. ค่าตรงกับ**กฎของ port** — type + `factor` ตัดสิน ไม่ใช่รายชื่อ plugin
   (เพิ่ม plugin ใหม่แล้วกฎตัดสินให้เอง · ตั้งใจต่างจากกฎต้องมาแก้ที่นี่พร้อมเหตุผล)
3. registry **ปฏิเสธตอนโหลด**เมื่อค่าขาดหรือสะกดผิด — พังตอน start ไม่ใช่วันสลับจริง
"""

import json
import pathlib

import pytest

from app import plugins


def _expected_class(plugin_type: str, manifest: dict) -> str:
    """กฎของ port ตาม ADR 0041 ข้อ 3 — หนึ่งเดียวกับตารางใน ADR"""
    if plugin_type in ("db", "secrets"):
        return "cold"
    if plugin_type == "themes":
        return "live"
    if plugin_type == "cache":
        # วัดจริง 10-03: rolling swap บน compose+nginx(DNS) หลุด 1 request ใน
        # 2/6 รอบ — การันตี 0-fail ไม่ได้บน stack นี้ แต่ session เดิมรอดครบ
        # ทุกรอบ → warm ไม่ใช่ live (ตัวเลขใน docs/PERFORMANCE.md)
        return "warm"
    if plugin_type == "auth":
        return "live" if manifest.get("factor") == "second" else "warm"
    raise AssertionError(f"type ใหม่ ({plugin_type}) — เพิ่มกฎของ port ใน ADR 0041 ก่อน")


def _all_plugins() -> list[plugins.Plugin]:
    found = [
        plugin
        for plugin_type in ("themes", "auth", "cache", "secrets", "db")
        for plugin in plugins._scan(plugin_type).values()
    ]
    assert len(found) >= 14, f"เจอ plugin แค่ {len(found)} — ตัวสแกนพังหรือเปล่า"
    return found


def test_every_plugin_declares_a_valid_class():
    bad = [
        f"{p.type}/{p.id}: {p.manifest.get('migration')!r}"
        for p in _all_plugins()
        if p.manifest.get("migration") not in plugins.MIGRATION_CLASSES
    ]
    assert not bad, f"plugin ที่ migration ไม่ถูกต้อง: {bad}"


def test_every_class_matches_the_port_rule():
    """ประกาศ `live` ทั้งที่ port มันเป็น `cold` คือคำสัญญาที่ bench จะพิสูจน์ว่าโกหก"""
    wrong = []
    for plugin in _all_plugins():
        expected = _expected_class(plugin.type, plugin.manifest)
        if plugin.migration != expected:
            wrong.append(
                f"{plugin.type}/{plugin.id}: ประกาศ {plugin.migration!r} แต่ port คาด {expected!r}"
            )
    assert not wrong, "\n  ".join(["class ที่ขัดกับกฎของ port (ADR 0041):", *wrong])


def test_enhancements_do_not_declare_migration():
    """ส่วนเสริมเสียบกับ plugin แม่ ไม่ได้ถูกสลับเดี่ยว ๆ — ประกาศไว้คือความเข้าใจผิด"""
    offenders = [
        enhancement.key
        for plugin in _all_plugins()
        for enhancement in plugins._scan_enhancements(plugin).values()
        if "migration" in enhancement.manifest
    ]
    assert not offenders, f"ส่วนเสริมที่ประกาศ migration: {offenders}"


@pytest.mark.parametrize("broken", [{}, {"migration": "hot"}, {"migration": "Live"}])
def test_the_registry_refuses_a_plugin_without_a_valid_class(tmp_path, monkeypatch, broken):
    """ค่าขาด/สะกดผิด/ผิดตัวพิมพ์ = ไม่ start — ไม่ใช่เงียบไว้จนวันสลับจริง"""
    plugin_dir = tmp_path / "themes" / "broken"
    plugin_dir.mkdir(parents=True)
    (plugin_dir / "plugin.json").write_text(
        json.dumps({"type": "themes", "name": "x", **broken}), encoding="utf-8"
    )
    monkeypatch.setattr(plugins, "PLUGIN_ROOT", tmp_path)

    with pytest.raises(plugins.PluginError, match="migration"):
        plugins._scan("themes")


# ---------------------------------------------------------------- 10-04: ผูกกับตัวเลขวัดจริง

PERFORMANCE = pathlib.Path(__file__).resolve().parent.parent / "docs" / "PERFORMANCE.md"
BENCH_START = "<!-- ตาราง bench เริ่ม — tests/test_migration_class.py อ่านตารางนี้ -->"
BENCH_END = "<!-- ตาราง bench จบ -->"

# port ที่ต้องมีแถววัด → class ที่คาด (มาจากกฎเดียวกับ _expected_class)
PORTS = {
    "themes": "live",
    "auth-second": "live",
    "auth-primary": "warm",
    "cache": "warm",
    "secrets": "cold",
    "db": "cold",
}


def _bench_rows() -> dict[str, tuple[str, str]]:
    """port → (class, ตัวเลข) จากตาราง bench ใน PERFORMANCE.md"""
    text = PERFORMANCE.read_text(encoding="utf-8")
    assert BENCH_START in text, "PERFORMANCE.md ไม่มีเครื่องหมายเปิดตาราง bench"
    assert BENCH_END in text, "PERFORMANCE.md ไม่มีเครื่องหมายปิดตาราง bench"
    block = text.split(BENCH_START, 1)[1].split(BENCH_END, 1)[0]
    rows = {}
    for line in block.splitlines():
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) == 4 and cells[0] in PORTS:
            rows[cells[0]] = (cells[1], cells[3])
    return rows


def test_every_port_has_measured_numbers():
    """class ที่ประกาศโดยไม่มีตัวเลขวัดรองรับ คือคำสัญญาเปล่า (ADR 0041 ข้อ 2)"""
    rows = _bench_rows()
    missing = sorted(PORTS.keys() - rows.keys())
    assert not missing, f"port ที่ยังไม่มีแถววัดในตาราง bench: {missing}"


def test_measured_class_matches_the_declared_class():
    """ตาราง bench กับ manifest ต้องเล่าเรื่องเดียวกัน — ขัดกันคือมีฝั่งหนึ่งโกหก"""
    wrong = [
        f"{port}: ตารางว่า {klass!r} แต่กฎ/manifest ว่า {PORTS[port]!r}"
        for port, (klass, _) in _bench_rows().items()
        if klass != PORTS[port]
    ]
    assert not wrong, "\n  ".join(["ตาราง bench ขัดกับ class ที่ประกาศ:", *wrong])


def test_live_ports_measured_zero_failures_in_every_round():
    """เกณฑ์ live เป็นตัวเลข: 0 request ล้ม **ทุกรอบ** — ไม่ใช่ค่าเฉลี่ย (วินัย Phase 6)

    cache เคยประกาศ live แล้ววัดได้หลุด 1 request ใน 2/6 รอบ → ถูกลดชั้นเป็น
    warm ด้วยการวัด ไม่ใช่ด้วยการแก้เกณฑ์ — ด่านนี้กันไม่ให้ประกาศเกินการวัดอีก
    """
    for port, (klass, numbers) in _bench_rows().items():
        if klass != "live":
            continue
        assert "fails=" in numbers, f"{port}: แถว live ต้องรายงาน fails ต่อรอบ"
        values = numbers.split("fails=", 1)[1].split()[0].split(",")
        assert values, f"{port}: ไม่มีตัวเลข fails ให้อ่าน"
        assert all(v == "0" for v in values), (
            f"{port}: ประกาศ live แต่วัดได้ fails={values} — ลดชั้นหรือแก้กลไกแล้ววัดใหม่"
        )


def test_warm_ports_measured_full_session_survival():
    for port, (klass, numbers) in _bench_rows().items():
        if klass != "warm":
            continue
        assert "session=รอด" in numbers, f"{port}: แถว warm ต้องรายงานการรอดของ session"
        survived = numbers.split("session=รอด", 1)[1].strip().split()[0]
        done, total = survived.split("/")
        assert done == total, f"{port}: session รอด {survived} — warm ต้องครบทุกรอบ"


def test_cold_ports_declare_a_measured_pause():
    """cold ไม่ใช่คำแก้ตัว — ต้องประกาศช่วงหยุดเป็นตัวเลขจากการวัด ≥3 รอบ"""
    for port, (klass, numbers) in _bench_rows().items():
        if klass != "cold":
            continue
        assert "pause_ms=" in numbers, f"{port}: แถว cold ต้องรายงาน pause_ms"
        values = numbers.split("pause_ms=", 1)[1].split()[0].split(",")
        assert len(values) >= 3, f"{port}: pause_ms ต้องวัด ≥3 รอบ (ได้ {values})"
        assert all(v.isdigit() and int(v) > 0 for v in values), (
            f"{port}: pause_ms ต้องเป็นเลขบวกทุกค่า (ได้ {values})"
        )
