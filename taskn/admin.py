#!/usr/bin/python3
#
# Copyright 2013 Sam Kleinman (tychoish)
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import re
import os
import logging
import argparse
import shutil

from .note import list_tasks
from .utils import mkdir_if_needed, symlink, worker_pool, init_logging

logger = logging.getLogger('taskn.admin')


# ######### Heavy Lifting ##########


def move_if_needed(src, dst, cond=None, value=None):
    if cond == value:
        if not os.path.exists(src):
            logger.debug(
                f'not moving {src} to {dst}: source file doesn\'t exist')
        elif os.path.exists(os.path.join(dst, os.path.basename(src))):
            logger.warning(
                f'not moving {src} to {dst}: destination file exists')
        else:
            shutil.move(src, dst)
            logger.debug(f'moved {src} to {dst}')
    else:
        logger.debug(f'not moving {src} to {dst}: {cond} != {value}')


def note_symlink(name, source, alias_dir):
    alias_path = os.path.join(alias_dir, name)

    if os.path.exists(alias_path):
        if os.readlink(alias_path) == source:
            logger.debug(
                f'not creating symlink "{alias_path}" because it exists')
        elif not os.path.islink(alias_path):
            logger.warning(
                f'{alias_path} is not a symbolic link. doing nothing')
        else:
            os.remove(alias_path)
            logger.debug('removed stale symlink to {alias_path}')
            symlink(alias_path, source)
            logger.debug('created link from {source} to {name}')
    else:
        symlink(alias_path, source)
        logger.debug('created link from {source} to {name}')


# ######### Worker Wrapper Function ##########


def _move_note_if_needed(task, archive_dir, query):
    move_if_needed(task['note'], archive_dir, task['status'], query)


def _create_note_symlink(task, alias_dir):
    bugw_re = re.compile(r'\(bw\).*\#.* - (.*) \.\. .*')
    delim_re = re.compile(r'[\:\;\-\.\,\_]')

    name = bugw_re.sub(r'\1', task['task'])
    name = delim_re.sub(r' ', name)
    name = '-'.join(name.split())
    name = '.'.join([name, 'txt'])

    logger.debug('processed note name into: {0}'.format(name))
    note_symlink(name, task['note'], alias_dir)


# ######### Major Functionality Wrappers ##########


def archive_stale(tasks, dir):
    archive_dir = mkdir_if_needed('archive', dir)

    logger.info('creating thread pool to archive stale notes')
    worker_pool(tasks, _move_note_if_needed, archive_dir, 'completed')


def generate_aliases(tasks, dir):
    alias_dir = mkdir_if_needed('aliases', dir)

    logger.info('creating thread pool to generate more user friendly links')
    worker_pool(tasks, _create_note_symlink, alias_dir)


# ######### User Interface ##########


def user_input():
    parser = argparse.ArgumentParser(
        'administrative operations for tasknote management')

    parser.add_argument('--logfile', default=None)
    parser.add_argument('--debug', '-d', default=False, action="store_true")
    parser.add_argument('--notesdir', '-n',
                        default=os.path.join(os.environ['HOME'], '.tasknote'))
    parser.add_argument('--ext', default='txt')
    parser.add_argument('cmd', nargs=1, default='list')

    return parser.parse_args()


def main():
    ui = user_input()
    init_logging(ui.logfile, ui.debug)

    tasks = list_tasks(None, ui.notesdir, ui.ext)

    if ui.cmd[0] == 'archive':
        archive_stale(tasks, ui.notesdir)
    elif ui.cmd[0] == 'alias':
        generate_aliases(tasks, ui.notesdir)


if __name__ == '__main__':
    main()
