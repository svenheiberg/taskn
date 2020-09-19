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

import sys
import subprocess
import argparse
import os
import logging
import json

from .utils import expand_tree, create_notes_dir, dump_yaml, init_logging
from .utils import worker_pool

logger = logging.getLogger('taskn')

try:
    from taskw import TaskWarriorExperimental, TaskWarrior
    wo = TaskWarrior()
    w = TaskWarriorExperimental()
except ImportError:
    logger.critical('ERROR - taskw module required.')
    exit(1)


# ############ setup function #############


def get_or_make_task(task=None):
    if task is None or not task:
        logger.critical('cannot add a note to an unspecified task')
        exit(1)
    else:
        if len(task) == 1:
            try:
                return w.get_task(id=int(task[0]))
            except ValueError:
                logger.critical(f'no task with id {task[0]}')
                exit(1)
        else:
            task_desc = ' '.join(task)
            logger.info(f'adding new task with description: "{task_desc}"')
            new_task = wo.task_add(description=task_desc, project='note')['id']
            return w.get_task(id=new_task)


# ############ core functions #############


def edit_note(task, dir, editor, ext='txt', asyncr=False):
    id = task[0]
    task = task[1]

    fn = '.'.join([os.path.join(dir, task['uuid']), ext])
    logger.info('editing {0} for id {1}'.format(fn, id))

    logger.info('current asyncr mode is {0}'.format(asyncr))

    open_editor(editor.split(), id, fn, asyncr=asyncr)

    if not asyncr:
        logger.info('in sync-mode: adding/updating task annotation.')
        update_annotation(task, fn)


def open_editor(cmd, id, fn, asyncr=False):
    if not os.path.exists(fn):
        open(fn, 'w').close()
        logger.debug(f'file: {fn} did not exist, created.')

    if asyncr:
        logger.debug('using asyncr-mode: tasknote ends before editor.')
        with open(os.devnull, 'w') as fnull:
            cmd.append('-n')
            cmd.append(fn)
            cmd_str = ' '.join(cmd)
            logger.debug(f'editing task {id} with command: {cmd_str}')
            subprocess.Popen(cmd, stderr=fnull, stdout=fnull)
    else:
        logger.debug('using sync-mode: tasknote waits for editor.')
        cmd.append(fn)
        cmd_str = ' '.join(cmd)
        logger.debug(f'editing task {id} with command: {cmd_str}')
        try:
            subprocess.check_call(
                cmd, stderr=subprocess.PIPE, stdout=subprocess.PIPE)
            logger.debug(f'successfully edited task {id}.')
        except subprocess.CalledProcessError:
            logger.critical(f'editor error while annotating task: {id}')
            exit(1)


def update_annotation(task, fn):
    w.task_denotate(task, '[tasknote]')
    logger.info('removed previous tasknote annotation.')

    with open(os.path.join(fn), 'r') as f:
        title = f.readline()

    w.task_annotate(task, f'[tasknote] {title}')
    logger.info(f'added new tasknote invitation with text {title}')


def view_task(task_id, fmt, dir, ext):
    task_id = int(task_id)
    data = w.get_task(id=task_id)[1]
    uuid = data['uuid']

    with open('.'.join([os.path.join(dir, uuid), ext])) as f:
        notation = f.read()

    if fmt == 'note':
        logger.info(f'returning note text for {task_id}')
        print(notation)
    else:
        logger.info(
            f'returning full task information for {task_id} in {fmt} format.')
        if fmt == 'yaml':
            data['notation'] = '\n' + notation
            output = dump_yaml(data)

        elif fmt == 'json':
            data['notation'] = notation
            output = json.dumps(data, indent=3)

        print(output)


def render_list_item(note, query, tasks):
    uuid = os.path.splitext(os.path.split(note)[-1])[0]
    task_id, task = w.get_task(uuid=uuid)

    o = dict(task=task['description'], note=note, status=task['status'])

    if task_id is not None:
        o['id'] = task_id

    if query is None or o['status'] == query:
        tasks.append(o)


def list_tasks(query, dir, ext):
    notes = expand_tree(dir, ext)
    tasks = []

    worker_pool(notes, render_list_item, query, tasks)

    return tasks


def render_task_list(query, dir, ext, fmt):
    if fmt in ['note', 'yaml']:
        print(dump_yaml(list_tasks(query, dir, ext)))
    elif fmt == 'json':
        for doc in list_tasks(query, dir, ext):
            print(json.dumps(doc, indent=2))


# ######### User Interaction and Setup ##########


def user_input():
    try:
        editor = os.environ['VISUAL']
    except KeyError:
        editor = 'emacs'
        logger.info('falling back to set the default editor to "emacs".')

    parser = argparse.ArgumentParser('tasknote python implementation')
    parser.add_argument('--editor', '-e', default=editor)
    parser.add_argument('--taskw', '-t', default='/usr/bin/task')
    parser.add_argument('--notesdir', '-n',
                        default=os.path.join(os.environ['HOME'], '.tasknote'))
    parser.add_argument('--logfile', default=None)
    parser.add_argument('--ext', default='txt')
    parser.add_argument('--strict', '-s', default=False, action="store_true")
    parser.add_argument('--view', '-v', default=False, action="store_true")
    parser.add_argument('--asyncr', '-a', default=False, action="store_true")
    parser.add_argument('--list', '-l', default=False, action="store_true")
    parser.add_argument('--filter', default=None, action="store",
                        choices=["pending",
                                 "deleted",
                                 "completed",
                                 "waiting",
                                 "recurring"])
    parser.add_argument('--format', '-f', default='note',
                        choices=['note', 'yaml', 'json'])
    parser.add_argument('--debug', '-d', default=False, action="store_true")
    parser.add_argument('task', nargs='*', default=None)

    return parser.parse_args()


def main():
    # Setup: logging, notesdir
    ui = user_input()

    init_logging(ui.logfile, ui.debug)
    create_notes_dir(ui.notesdir, ui.strict)

    # user interface wiring
    if len(sys.argv) == 1 or (len(sys.argv) == 2 and sys.argv[1] == '--debug'):
        render_task_list(query='pending',
                         dir=ui.notesdir,
                         ext=ui.ext,
                         fmt=ui.format)
    elif ui.list:
        render_task_list(query=ui.filter,
                         dir=ui.notesdir,
                         ext=ui.ext,
                         fmt=ui.format)
    elif ui.view:
        view_task(task_id=ui.task[0],
                  fmt=ui.format,
                  dir=ui.notesdir,
                  ext=ui.ext)
    else:
        edit_note(task=get_or_make_task(ui.task),
                  dir=ui.notesdir,
                  editor=ui.editor,
                  ext=ui.ext,
                  asyncr=ui.asyncr)


if __name__ == '__main__':
    main()
