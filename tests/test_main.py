"""Unit tests for the pure and file-reading half of `zram_advisor.main`.

Nothing here needs root, a loaded zRAM device, or a terminal: the live monitor
and the root-only `fix-zram` calls are exercised by the manual plan in
`TESTING.md`.  These tests keep the calculations and the packaged data files
honest, and they are what the coverage floor measures.
"""

from pathlib import Path
from types import SimpleNamespace

import pytest
from console_window import (
    ConsoleWindow,
    ConsoleWindowOpts,
    Glyphs,
    Theme,
)
from console_window import window as window_mod
from console_window.backend import HeadlessBackend
from zram_advisor.main import (
    SummaryScreen,
    ZramAdvisor,
    compute_zram_effective,
    human,
)

PACKAGE = Path(__file__).resolve().parent.parent / 'zram_advisor'
GB = 1024 ** 3

# curses binds the alternate character set only after initscr(); a headless
# render still paints the separator row, so the ACS_* names must exist.
_ACS = {'ACS_HLINE': '-', 'ACS_VLINE': '|', 'ACS_ULCORNER': '+',
        'ACS_URCORNER': '+', 'ACS_LLCORNER': '+', 'ACS_LRCORNER': '+'}


@pytest.fixture(autouse=True)
def _headless_curses(monkeypatch):
    for name, value in _ACS.items():
        if not hasattr(window_mod.curses, name):
            monkeypatch.setattr(window_mod.curses, name, value, raising=False)


# --- formatting ----------------------------------------------------------

@pytest.mark.parametrize('number, expected', [
    (0, '0'),
    (-1, '0'),
    (1024, '1K'),
    (1536, '1.5K'),
    (1024 ** 2, '1M'),
    (1024 ** 3, '1G'),
])
def test_human(number, expected):
    assert human(number) == expected


def test_human_pct_adds_the_fraction_of_total_ram():
    advisor = ZramAdvisor()
    advisor.ram_total = 1000

    assert advisor.human_pct(500) == '500/50%'
    assert advisor.human_pct(0) == '0'

    advisor.ram_total = 0
    assert advisor.human_pct(500) == '500'


# --- the portable projection ---------------------------------------------

def test_no_zram_data_uses_the_conservative_guess():
    result = compute_zram_effective(
        meminfo_total=8 * GB, meminfo_used=4 * GB,
        zram_orig_data_size=0, zram_mem_used_total=0,
        zram_disksize=16 * GB)

    assert result.e_used == 4 * GB
    assert result.ratio_current == 2.75
    assert result.usage_fraction == 0
    assert result.projection_confidence == 'uncertain'


def test_mid_fill_is_confident_and_projects_a_degraded_ratio():
    result = compute_zram_effective(
        meminfo_total=8 * GB, meminfo_used=4 * GB,
        zram_orig_data_size=1 * GB, zram_mem_used_total=GB // 2,
        zram_disksize=4 * GB)

    assert result.usage_fraction == pytest.approx(0.25)
    assert result.ratio_current == pytest.approx(2.0)
    assert result.ratio_projected == pytest.approx(1.7)
    assert result.projection_confidence == 'confident'
    # zRAM data is uncompressed for the effective-used figure.
    assert result.e_used == pytest.approx(4.5 * GB)


def test_a_well_filled_device_is_certain():
    result = compute_zram_effective(
        meminfo_total=8 * GB, meminfo_used=4 * GB,
        zram_orig_data_size=3 * GB, zram_mem_used_total=GB,
        zram_disksize=4 * GB)

    assert result.usage_fraction == pytest.approx(0.75)
    assert result.ratio_current == pytest.approx(3.0)
    assert result.ratio_projected == pytest.approx(2.85)
    assert result.projection_confidence == 'certain'


def test_a_mem_limit_caps_the_projection():
    result = compute_zram_effective(
        meminfo_total=10 * GB, meminfo_used=4 * GB,
        zram_orig_data_size=2 * GB, zram_mem_used_total=GB,
        zram_disksize=20 * GB, zram_mem_limit=5 * GB)

    # A 5G cap on a 10G machine is 50%, tighter than the 80% default.
    assert result.e_max_used == pytest.approx(13.5 * GB)
    assert result.e_avail == pytest.approx(8.5 * GB)


def test_an_empty_device_cannot_divide_by_zero():
    result = compute_zram_effective(
        meminfo_total=8 * GB, meminfo_used=4 * GB,
        zram_orig_data_size=0, zram_mem_used_total=0,
        zram_disksize=0)

    assert result.usage_fraction == 0
    assert result.projection_confidence == 'uncertain'


# --- the packaged files --------------------------------------------------

def test_load_script_reads_the_packaged_fix_zram():
    script = ZramAdvisor().load_script()

    assert script.startswith('#!/bin/bash')
    assert 'zram' in script


def test_create_site_import_emits_one_bookmark_per_site():
    advisor = ZramAdvisor()
    sites = (PACKAGE / 'random-sites.txt').read_text(encoding='utf-8').splitlines()

    html = advisor.create_site_import()

    assert html.count('<DT><A HREF="https://') == len(sites)
    assert '<!DOCTYPE NETSCAPE-Bookmark-file-1>' in html
    assert f'https://{sites[0]}/' in html


def test_name_value_files_are_lower_cased_and_unquoted(tmp_path):
    release = tmp_path / 'os-release'
    release.write_text('NAME="Test Linux"\nVERSION_ID="1"\n', encoding='utf-8')

    info = ZramAdvisor().get_name_value_info(release)

    assert info.name == 'Test Linux'
    assert info.version_id == '1'


# --- the 3.x page and its attention row -----------------------------------

def make_advisor(swappiness=180, disksize=12 * GB):
    """A ZramAdvisor with one healthy (or deliberately off-spec) device."""
    advisor = ZramAdvisor()
    advisor.release = SimpleNamespace(marquee='Test Linux')
    advisor.ram_total = 8 * GB
    advisor.meminfo = SimpleNamespace(MemTotal=8 * GB, MemUsed=4 * GB,
                                      MemAvailable=4 * GB)
    params = (('swappiness', swappiness, 150, 200),
              ('watermark_boost_factor', 0, 0, 0),
              ('watermark_scale_factor', 125, 125, 125),
              ('page-cluster', 0, 0, 0))
    advisor.params = {
        name.replace('-', '_'): SimpleNamespace(
            name=name, value=value, least=least, most=most,
            key=name.replace('-', '_'))
        for name, value, least, most in params}
    stats = SimpleNamespace(orig_data_size=2 * GB, compr_data_size=GB // 2,
                            mem_used_total=GB, mem_limit=0,
                            mem_used_max=GB, disksize=disksize)
    advisor.devs = {'zram0': stats}
    advisor.effective = advisor.compute_effective()
    return advisor


def test_the_snapshot_is_the_header_band_plus_the_body():
    advisor = make_advisor()

    header = advisor.header_lines()
    body = advisor.body_lines()

    assert header[0].endswith('Test Linux')
    assert any('vm.swappiness' in line for line in header)
    assert advisor.display_lines() == header + body
    # The projection arrow comes from the registry, so the window and the
    # print path agree on the active spelling instead of transliterating a
    # pasted '→' only in the window.
    assert any(Glyphs.get('nav_next') in line for line in body)


def test_the_effective_memory_values_carry_the_hotswap_role():
    rows = make_advisor().body_rows()

    hot = [text for row in rows for text, role in row if role == Theme.HOTSWAP]
    assert len(hot) == 3
    assert hot[0].startswith('eTotal=')
    assert hot[1].startswith('eUsed=')
    assert hot[2].startswith('eAvail=')


def test_the_confidence_note_carries_its_semantic_role():
    def note_role(disksize):
        rows = make_advisor(disksize=disksize).body_rows()
        cmpr = next(row for row in rows
                    if row[0][0].lstrip().startswith('cmpr'))
        return next((text, role) for text, role in cmpr
                    if text.startswith('('))

    # Fill fraction picks the confidence: <10% uncertain, 10-50% confident,
    # >50% certain (plain text).
    assert note_role(40 * GB) == ('(uncertain)', Theme.DANGER)
    assert note_role(12 * GB) == ('(confident)', Theme.SUCCESS)
    assert note_role(3 * GB) == ('(certain)', None)


def test_attention_notes_stay_quiet_when_the_settings_are_in_range():
    assert make_advisor().attention_notes() == []


def test_attention_notes_name_what_is_out_of_range():
    notes = make_advisor(swappiness=99, disksize=GB).attention_notes()

    assert 'vm.swappiness=99' in notes
    assert any(note.startswith('disksize=') for note in notes)


def test_summary_screen_draws_the_whole_live_page(monkeypatch):
    """The 3.x shape: the Screen owns the page and the window paints it."""
    monkeypatch.setenv('TERM', 'xterm-256color')
    Glyphs.reset()
    advisor = make_advisor(swappiness=99)
    win = ConsoleWindow(
        opts=ConsoleWindowOpts(head_line=True, ctrl_c_terminates=False),
        backend=HeadlessBackend(rows=30, cols=120),
        singleton=False)
    advisor.win = win
    screen = SummaryScreen(advisor)

    screen.clear()
    screen.draw_screen()

    head = '\n'.join(screen.head.texts)
    body = '\n'.join(screen.body.texts)
    assert 'zram-advisor' in head
    assert 'vm.swappiness' in head
    assert 'Total Memory' in body
    # The attention badge lives on the window's status row, in the registry's
    # active spelling (two cells in Unicode, 'S ' in ASCII).
    assert win.current_status[0].startswith(Glyphs.get('star_glow'))


def test_the_live_loop_renders_and_prints_the_final_snapshot(monkeypatch, capsys):
    """Drive the real five-line loop: clear, draw, render, prompt, then quit."""
    monkeypatch.setenv('TERM', 'xterm-256color')
    Glyphs.reset()
    advisor = make_advisor()
    advisor.window_backend = HeadlessBackend(rows=30, cols=120)
    advisor.window_singleton = False
    advisor.window_backend.queue_keys(ord('q'))
    monkeypatch.setattr('zram_advisor.main.time.sleep', lambda _seconds: None)

    advisor.show_system_summary()

    out = capsys.readouterr().out
    assert 'Final snapshot:' in out
    assert 'vm.swappiness' in out


def test_no_color_selects_the_mono_theme(monkeypatch):
    """NO_COLOR is resolved by the app before the window is built."""
    monkeypatch.setenv('TERM', 'xterm-256color')
    monkeypatch.setenv('NO_COLOR', '1')
    Glyphs.reset()
    advisor = make_advisor()
    advisor.window_backend = HeadlessBackend(rows=30, cols=120)
    advisor.window_singleton = False
    advisor.window_backend.queue_keys(ord('q'))
    monkeypatch.setattr('zram_advisor.main.time.sleep', lambda _seconds: None)

    try:
        advisor.show_system_summary()

        assert advisor.win.theme == 'mono'
        assert Theme.get_current() == 'mono'
    finally:
        # Themes are process state; leave the suite on the library default.
        Theme.set_active('default')
