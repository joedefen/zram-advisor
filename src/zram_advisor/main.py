#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Program to analyze the zRAM configuration (if any) and suggest
some improvements.

===== References =====
www.kernel.org/doc/Documentation/blockdev/zram.txt
fedoraproject.org/wiki/Changes/Scale_ZRAM_to_full_memory_size
kernelnewbies.org/Linux_5.8 - when swappiness rose to 2020-08-02

Tested on:
 - Linux Mint (Mate) 21.3 - 6.5 kernel (upgraded)
 - Debian (KDE) 12.4.0
 - Linux Lite 6.6 - 5.x kernel
 - elementary OS 7.1 Horus
"""
# pylint: disable=invalid-name,multiple-statements,global-statement
# pylint: disable=too-many-instance-attributes,broad-exception-caught
# pylint: disable=too-many-locals

import re
from types import SimpleNamespace
import shutil
import os
import sys
import traceback
import configparser
import time
import argparse
import subprocess

##############################################################################

####################################################################################

class Term:
    """ Escape sequences; e.g., see:
     - https://en.wikipedia.org/wiki/ANSI_escape_code
     - https://gist.github.com/fnky/458719343aabd01cfb17a3a4f7296797#file-ansi-md
    """
    esc = '\x1B'
    # pylint: disable=missing-function-docstring,multiple-statements
    @staticmethod
    def erase_line(): return f'{Term.esc}[2K'
    @staticmethod
    def bold(): return f'{Term.esc}[1m'
    @staticmethod
    def reverse_video(): return f'{Term.esc}[7m'
    @staticmethod
    def normal_video(): return f'{Term.esc}[m'
    @staticmethod
    def pos_up(cnt): return f'{Term.esc}[{cnt}F' if cnt > 0 else ''
    @staticmethod
    def pos_down(cnt): return f'{Term.esc}[{cnt}E' if cnt > 0 else ''
    @staticmethod
    def col(pos): return f'{Term.esc}[{pos}G'
    @staticmethod
    def clear_screen(): return f'{Term.esc}[H{Term.esc}[2J{Term.esc}[3J'


##############################################################################
def human(number):
    """ Return a concise number description."""
    if number <= 0:
        return '0'
    suffixes = ['', 'K', 'M', 'G', 'T', 'Q']
    while suffixes:
        suffix = suffixes.pop(0)
        if number < 999.95 or not suffixes:
            num = f'{number:.1f}'
            num = num[0:-2] if num.endswith('.0') else num
            return f'{num}{suffix}'
        number /= 1024
    return 'TooHuge'

##############################################################################
class ZramAdvisor:
    """ Workhorse class for zram-advisor """
    def __init__(self):
        self.meminfo = None #selected info from meminfo
        self.effective = None # effective system params
        self.probe = None  # info about runnable programs
        self.devs = None # info about zram devices
        self.params = None # related kernel parameters
        self.release = None
        self.ram_total = 0
        self.tab_count = 0  # number of tabs created so far
        self.download_dir = os.path.expanduser('~/Downloads')
        self.script_dir = os.path.dirname(os.path.realpath(__file__))
        # options:
        self.DB = False
        self.limit_pct = 80 # arbitrary limit on amount of RAM used by zRAM

    def human_pct(self, number):
        """ Return the number in human form and as pct total memory. """
        rv = human(number)
        if number > 0 and self.ram_total > 0:
            fraction = number/self.ram_total
            pct = int(round(100*fraction))
            rv += f'/{pct}%'
        return rv

    def get_meminfo(self):
        """Get most vital stats from /proc/meminfo'"""
        meminfofile = '/proc/meminfo'
        meminfo = {'MemTotal': 0, 'MemAvailable': 0, 'Dirty':0, 'Shmem':0}
        keys = list(meminfo.keys())

        with open(meminfofile, encoding='utf-8') as fileh:
            for line in fileh:
                match = re.match(r'^([^:]+):\s+(\d+)\s*kB', line)
                if not match:
                    continue
                key, value = match.group(1), int(match.group(2))
                if key not in keys:
                    continue
                meminfo[key] = value * 1024
                keys.remove(key)
                if not keys:
                    break
        assert not keys, f'ALERT: cannot get vitals ({keys}) from {meminfofile}'
        ns = SimpleNamespace(**meminfo)
        ns.MemUsed = ns.MemTotal - ns.MemAvailable # synthetic
        if self.DB: print(f'DB: meminfo: {ns}')
        if self.DB: print(f'DB: RAM={human(ns.MemTotal)}')
        self.ram_total = ns.MemTotal
        return ns

    @staticmethod
    def keyword_in_manpage(manpage, keyword):
        """ Is a given keyword in the man page?"""
        try:
            # Use subprocess to run the man command and grep for the keyword
            command = f"man {manpage} | grep -q '{keyword}'"
            subprocess.run(command, shell=True, check=True)
            return True
        except subprocess.CalledProcessError:
            return False

    def prober(self):
        """ Probe for distro specific attributes """
        def has(program): # is program on path?
            return shutil.which(program) is not None


        ns = SimpleNamespace(installer=None)
        ns.fraction_str = ''

        others = ('zramctl', )
        for other in others:
            setattr(ns, other, has(other))
        if self.DB: print(f'DB: probe: {ns}')
        return ns

    def load_script(self):
        """ Give the user the onboot script"""
        pathname = os.path.join(self.script_dir, 'fix-zram.sh')
        with open(pathname, "r", encoding='utf8') as fh:
            script = fh.read()
        return script

    def run_script(self, keyword, arguments=None):
        """ Dump 'fix-zram' into /tmp and run it."""
        script = self.load_script()
        pathname = os.path.join('/tmp', 'fix-zram.sh')
        with open(pathname, "w", encoding='utf-8') as fh:
            fh.write(script)
        os.chmod(pathname, 0o755)
        arguments = [] if arguments is None else arguments
        os.system(f'set -x; sudo bash {pathname} --{keyword} {" ".join(arguments)}')

    def create_site_import(self):
        """ Get a randomly chosen site """
        random_site_file = os.path.join(self.script_dir, 'random-sites.txt')
        with open(random_site_file, "r", encoding='utf8') as fh:
            sites = [line.rstrip('\n') for line in fh]
        rv = """<!DOCTYPE NETSCAPE-Bookmark-file-1>
<META HTTP-EQUIV="Content-Type" CONTENT="text/html; charset=UTF-8">
<TITLE>Bookmarks</TITLE>
<H1>Bookmarks</H1><DL><p>
"""
        rv += '<DT><H3>Rand0</H3><DL><p>\n'
        for idx, site in enumerate(sites):
            if idx and idx % 10 == 0:
                rv += f'</DL><p>\n<DT><H3>Rand{idx//10}</H3><DL><p>\n'
            href = f'https://{site}/'
            site = site[4:] if site.startswith('www.') else site
            rv += f'     <DT><A HREF="{href}">{site}</A>\n'
        rv += '</DL><p>\n</DL><p>\n'
        return rv

    def get_zram_stats(self):
        """ Get only what we want
         orig_data_size   uncompressed size of data stored in this disk.
         compr_data_size  compressed size of data stored in this disk
         mem_used_total   the amount of memory allocated for this disk.
         mem_limit        max RAM ZRAM can use to store (0 means unlimited)
         mem_used_max     max RAM zram has consumed to store the data
        """
        fields = ('orig_data_size compr_data_size mem_used_total'
                 + ' mem_limit mem_used_max').split()
        infos = {}
        zram_devices = sorted([device for device in os.listdir('/sys/class/block/')
                    if device.startswith('zram')])
        for device in zram_devices:
            statfile = f'/sys/class/block/{device}/mm_stat'
            if not os.path.exists(statfile):
                continue # not active
            with open(statfile, encoding='utf-8') as fileh:
                ns = SimpleNamespace()
                for line in fileh: # all the goodies are on 1st line
                    nums = line.split()
                    for idx, field in enumerate(fields):
                        setattr(ns, field, int(nums[idx]))
                    break
                infos[device] = ns
            for param in ('disksize', ):
                statfile = f'/sys/class/block/{device}/{param}'
                with open(statfile, encoding='utf-8') as fileh:
                    for line in fileh: # one value, one line
                        setattr(ns, param, int(line.strip()))
                        break
            if self.DB: print(f'DB: {device}: {ns}')

        return infos

    def get_vm_params(self):
        """ Looking for (and good values):
            vm.swappiness = 180
            vm.watermark_boost_factor = 0
            vm.watermark_scale_factor = 125
            vm.page-cluster = 0
        """
        def add_param(coll, name, least, most):
            key = name.replace('-', '_')
            coll[key] = SimpleNamespace(
                name=name, value=None, least=least, most=most, key=key)
        params = {}
        add_param(params, 'swappiness', 150, 200)
        add_param(params, 'watermark_boost_factor', 0, 0)
        add_param(params, 'watermark_scale_factor', 125, 125)
        add_param(params, 'page-cluster', 0, 0)

        vm_dirname = '/proc/sys/vm'
        for param in params.values():
            param_file = os.path.join(vm_dirname, param.name)
            with open(param_file, encoding='utf-8') as fileh:
                param.value = int(fileh.readline().strip())
        if self.DB: print(f'DB: vm.params: {params}')
        return params

    def get_name_value_info(self, pathname):
        """ Parse a name=value file; e.g., pathname
            - keys are made lower case for uniformity because it varies
            - values are left intact
        """
        ns = SimpleNamespace()
        parser = configparser.ConfigParser()
        with open(pathname, encoding='utf-8') as stream:
            parser.read_string('[top]\n' + stream.read())

        for section in parser.sections():
            for key, value in parser.items(section):
                setattr(ns, key.lower(), value.replace('"', ''))
        if self.DB: print(f'DB: {os.path.basename(pathname)}: {ns}')
        return ns

    def compute_effective(self):
        """ Compute the effective values """
        def dump_effective(ns, annotation=''):
            nonlocal self
            for key, value in vars(ns).items():
                print(f'DB: {annotation} {key}: {self.human_pct(value)}')

        if not self.devs:
            return None
        meminfo = self.meminfo
        stats = None
        for stat in self.devs.values():
            # NOTE: generalization for more than one weak unless all
            #        are identically configured
            if not stats:
                stats = vars(stat).copy()
                continue
            for key, value in vars(stat).items():
                stats[key] += value
        stats = SimpleNamespace(**stats)

        ns = SimpleNamespace(e_used=meminfo.MemUsed,
            e_avail=meminfo.MemAvailable, e_total=meminfo.MemTotal,
            e_max_used=meminfo.MemTotal, stats=stats)
        e_used = meminfo.MemUsed - stats.mem_used_total + stats.orig_data_size
        ratio = None
        if e_used <= ns.e_used: # zram hurts. assume not enuf data to project
            e_used = ns.e_used
            ratio = 3.5 # wild guess for projection
            # if self.DB: dump_effective(ns, '(unchg)')
            # return ns
        ns.e_used = e_used
        limit_pct = self.limit_pct
        if stats.mem_limit > 0:
            stats_limit_pct = (stats.limit / meminfo.MemTotal)*100
            limit_pct = min(1.0, limit_pct, stats_limit_pct)
            # projected amount of orig used memory that fits in limit
        if ratio is None: # hopefully about 4 ;-)
            ratio = stats.orig_data_size / stats.mem_used_total
        e_max_used = ratio * meminfo.MemTotal * limit_pct/100
            # now limit by disksize
        e_max_used = min(e_max_used, stats.disksize)
            # now add uncompressed memory
        e_max_used += meminfo.MemTotal - e_max_used/ratio
        ns.e_max_used = e_max_used
        ns.e_avail = e_max_used - e_used
        if self.DB: dump_effective(ns)
        return ns


    def show_system_summary(self, once=False):
        """ Just the facts, ma'am """
        if not once:
            print(f'{"":>18} [[ type CTL-C to terminate]]')
        print(f'{"Distro":>16} : {self.release.marquee}')
        for param in self.params.values():
            ok = '....' if param.least <= param.value <= param.most else ' NOT'
            print(f'{param.value:>16} : vm.{param.name.ljust(24, ".")}'
                  f'{ok} in [{param.least}, {param.most}]')
        if not self.devs:
            print('   NO zRAM: zRAM is either not installed or not enabled')
            sys.exit(1)
        GB = 1024*1024*1024
        ram = self.meminfo.MemTotal
        min_disksize = (1.5*ram if ram <= 8*GB else 4*GB)
        actual_disksize = self.effective.stats.disksize
        ok = '....' if min_disksize <= actual_disksize else ' NOT'
        print(f'{human(actual_disksize):>16} : {"zRAM.disksize".ljust(27, ".")}'
              f'{ok} >= {human(min_disksize)}')

        start = time.time()
        time.sleep(2)
        for _ in range(1000*1000):
            meminfo = self.meminfo
            eff = self.effective
            delta = int(round(time.time() - start))
            print('='*16, f'{delta}s', '='*16)
            print(f'{human(self.meminfo.MemTotal):>16} : {"Total Memory":<16}',
                        f'eTotal={self.human_pct(eff.e_max_used)}')
            print(f'{self.human_pct(meminfo.MemUsed):>16} : {"Used":<16}',
                        f' eUsed={self.human_pct(eff.e_used)}')
            print(f'{self.human_pct(meminfo.MemAvailable):>16} : {"Available":<16}',
                        f'eAvail={self.human_pct(eff.e_avail)}')
            for dev, stats in self.devs.items():
                print(f'{dev}:')
                print(f'   uncmpr: {human(stats.orig_data_size)} limit={human(stats.disksize)}')
                factor = (stats.orig_data_size/stats.compr_data_size
                            if stats.compr_data_size > 0 else 0)
                print(f'     cmpr: {self.human_pct(stats.compr_data_size)}',
                        f'factor={factor:.2f}')
                print(f'     RAM: {self.human_pct(stats.mem_used_total)}'
                                    if stats.mem_used_total > 0 else 'n/a',
                        f'most={self.human_pct(stats.mem_used_max)}',
                        f'limit={self.human_pct(stats.mem_limit)}')
            if self.DB:
                break
            time.sleep(1)
            self.meminfo = self.get_meminfo()
            self.devs = self.get_zram_stats()
            self.effective = self.compute_effective()

            emit = Term.pos_up(1) + Term.erase_line() + '\r'
            print((4 + len(self.devs) * 4) * emit, end='')
            if once:
                break

    def main(self):
        """ Do something useful. """
        parser = argparse.ArgumentParser()
        parser.add_argument('-s', '--setup-fix-zram', action="store_true",
                help='install/run "fix-zram --setup [args ...]" for persistent install')
        parser.add_argument('-d', '--dump-fix-zram', action="store_true",
                help='print "fix-zram.sh" for manual install')
        parser.add_argument('-t', '--gen-test-sites', action="store_true",
                help='print "bookmarks.html" to import to a web-browser for load test')
        parser.add_argument('--DB', action="store_true",
                help='debug creation of low-level objects/data')
        parser.add_argument('-L', '--reload', action="store_true",
                help='run "fix-zram --reload [args ...]" to test zRAM w/o any footprint')
        parser.add_argument('-U', '--unload', action="store_true",
                help='run "fix-zram --unload"')
        parser.add_argument('args', nargs='*', type=str,
                help='arguments for --reload')
        opts = parser.parse_args()

        try:
            self.release = self.get_name_value_info('/etc/os-release')
            self.release.marquee = self.release.pretty_name
        except Exception:
            try:
                self.release = self.get_name_value_info('/etc/lsb-release')
                self.release.marquee = self.release.distrib_description
            except Exception:
                print("cannot get os-release or lsb-release")

        def loop(once=False):
            nonlocal self
            self.meminfo = self.get_meminfo()
            self.probe = self.prober()
            self.devs = self.get_zram_stats()
            self.params = self.get_vm_params()
            self.effective = self.compute_effective()
            self.show_system_summary(once)

        if opts.reload:
            self.run_script('reload', opts.args)
            loop()
        elif opts.unload:
            self.run_script('unload')
            loop(once=True)
        elif opts.dump_fix_zram:
            script = self.load_script()
            print(script, end='')
        elif opts.setup_fix_zram:
            self.run_script('setup', opts.args)
        elif opts.gen_test_sites:
            import_html = self.create_site_import()
            print(import_html, end='')
        else:
            loop()
def run():
    """ Entry point"""
    try:
        ZramAdvisor().main()
    except KeyboardInterrupt:
        print('\n   OK, QUITTING NOW\n')
        sys.exit(0)
    except Exception as exce:
        print("exception:", str(exce))
        print(traceback.format_exc())
        sys.exit(15)

if __name__ == "__main__":
    run()
