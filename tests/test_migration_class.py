"""migration class เป็นสัญญาของ plugin — ประกาศครบ ตรงกับ port และถูกบังคับตอนโหลด

ADR 0041: เครื่องมือที่วางแผนการสลับ (bench เฟส 10-03, เอกสาร, คนหน้างาน)
ต้องเชื่อค่าใน manifest ได้โดยไม่ต้องเดา — สามชั้นที่นี่:

1. ทุก plugin บนดิสก์ประกาศค่าที่ถูกต้อง (อ่านผ่าน registry จริง ไม่ใช่อ่านไฟล์เอง)
2. ค่าตรงกับ**กฎของ port** — type + `factor` ตัดสิน ไม่ใช่รายชื่อ plugin
   (เพิ่ม plugin ใหม่แล้วกฎตัดสินให้เอง · ตั้งใจต่างจากกฎต้องมาแก้ที่นี่พร้อมเหตุผล)
3. registry **ปฏิเสธตอนโหลด**เมื่อค่าขาดหรือสะกดผิด — พังตอน start ไม่ใช่วันสลับจริง
"""

import json

import pytest

from app import plugins


def _expected_class(plugin_type: str, manifest: dict) -> str:
    """กฎของ port ตาม ADR 0041 ข้อ 3 — หนึ่งเดียวกับตารางใน ADR"""
    if plugin_type in ("db", "secrets"):
        return "cold"
    if plugin_type in ("themes", "cache"):
        return "live"
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
