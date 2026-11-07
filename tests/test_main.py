"""Unit tests for the pure and file-reading half of `zram_advisor.main`.

Nothing here needs root, a loaded zRAM device, or a terminal: the live monitor
and the root-only `fix-zram` calls are exercised by the manual plan in
`TESTING.md`.  These tests keep the calculations and the packaged data files
honest, and they are what the coverage floor measures.
"""

from pathlib import Path

import pytest
from zram_advisor.main import (
    ZramAdvisor,
    compute_zram_effective,
    human,
)

PACKAGE = Path(__file__).resolve().parent.parent / 'zram_advisor'
GB = 1024 ** 3


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
