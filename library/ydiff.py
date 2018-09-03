#!/usr/bin/python
# (c) 2017, cytopia <cytopia@everythingcli.org>
#
# This module is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This software is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this software.  If not, see <http://www.gnu.org/licenses/>.
#

ANSIBLE_METADATA = {'metadata_version': '2.0',
                    'supported_by': 'community',
                    'status': ['preview']}

DOCUMENTATION = '''
---
module: ydiff
author: cytopia (@cytopia)

short_description: ydiff compares strings, files or command outputs as normalized yaml.
description:
    - ydiff compares a string, file or command output against a string file or command output.
    - Check mode is only supported when diffing strings or files, commands will only be executed in actual run.
    - More examples at U(https://github.com/cytopia/ansible-module-ydiff)
version_added: '2.6'
options:
    source:
        description:
            - The source input to diff. Can be a string, contents of a file or output from a command, depending on I(source_type).
        required: true
        default: null
        aliases: []

    target:
        description:
            - The target input to diff. Can be a string, contents of a file or output from a command, depending on I(target_type).
        required: true
        default: null
        aliases: []

    source_type:
        description:
            - Specify the input type of I(source).
        required: false
        default: string
        choices: [string, file, command]
        aliases: []

    target_type:
        description:
            - Specify the input type of I(target).
        required: false
        default: string
        choices: [string, file, command]
        aliases: []

    diff_ignore_keys:
        description:
            - Dictionary of keys to be ignored
        required: false
        default: {}
        aliases: []

    diff_ignore_empty:
        description:
            - Ignore empty keys (dictionary, lists or strings)
        required: false
        default: False
        aliases: []
'''

EXAMPLES = '''
# Diff compare two strings
- ydiff:
    source: 'foo'
    target: 'bar'
    source_type: string
    target_type: string

# Diff compare variable against template file (as strings)
- ydiff:
    source: "{{ lookup('template', tpl.yml.j2) }}"
    target: "{{ my_var }}"
    source_type: string
    target_type: string

# Diff compare string against command output
- ydiff:
    source: '/bin/bash'
    target: 'which bash'
    source_type: string
    target_type: command

# Diff compare file against command output
- ydiff:
    source: '/etc/hostname'
    target: 'hostname'
    source_type: file
    target_type: command

# Diff compare two normalized yaml files (sorted keys and comments stripped),
# but additionally ignore the yaml keys: 'creationTimestamp' (below meta) and 'status'
- ydiff:
    source: /tmp/file-1.yml
    target: /tmp/file-2.yml
    source_type: file
    target_type: file
    diff_ignore_keys:
      meta:
        creationTimestamp:
      status:
'''

RETURN = '''
ydiff:
    description: diff output
    returned: success
    type: string
    sample: + this line was added
'''

# pylint: disable=wrong-import-position
# Python imports for module operation
import os
import sys
import time
import subprocess
import yaml

try:
    from collections import OrderedDict
except ImportError:
    OrderedDict = dict

# Python imports for Ansible
from ansible.module_utils.basic import AnsibleModule
from ansible.module_utils._text import to_bytes

# Are we using Python2?
PY2 = sys.version_info.major == 2


################################################################################
# Helper Classes
################################################################################

class SortedDict(OrderedDict):
    '''
    This class adds a custom recursive JSON sorter.
    JSON dicts are sorted recursively and alphabetically by key.
    '''
    def __init__(self, **kwargs):
        super(SortedDict, self).__init__()

        for key, value in sorted(kwargs.items()):
            if isinstance(value, dict):
                self[key] = SortedDict(**value)
            else:
                self[key] = value


class YdiffDict(object):
    '''
    Ydiff dictionary class that handles the conversion and normalization of
    yaml strings and dictionaries.
    '''
    ############################################################
    # Privates
    ############################################################

    # Error function
    __err_func = None
    __err_parm = None

    # Values for keys to be considered to be empty inside a dictionary
    __empty_dict_vals = ['', '[]', '{}', None, [], {}]

    # Values for keys to be considered to be empty inside a list
    # Note that [''] is omitted as it is a valid list element
    __empty_list_vals = ['[]', '{}', None, [], {}]


    def __error(self, message):
        '''
        Error handler of this class
        '''
        if self.__err_parm is not None:
            params = {self.__err_parm: message}
            self.__err_func(**params)
        else:
            self.__err_func(message)

    def __normalize(self, obj):
        '''
        Convert all possible null values to an empty string
        to be safe when converting to JSON or Yaml.
        Additionally convert all non string values (integer, floats, etc) to string.
        '''
        # Ensure JSON null values are converted to Python None values
        if obj in ('None', 'null', 'Null', 'NULL'):
            return None
        # Recurse for lists and tuples
        if isinstance(obj, (list, tuple)):
            return [self.__normalize(item) for item in obj]
        # Recurse for dictionaries
        if isinstance(obj, dict):
            return dict((self.__normalize(key), self.__normalize(val)) for key, val in obj.items())
        # Stringify everything else
        return str(obj)

    def __dict_to_yaml_str(self, obj):
        '''
        Convert a dictionary to a human readable yaml string.
        '''
        obj = self.__normalize(obj)
        try:
            obj = yaml.dump(obj, default_flow_style=False, allow_unicode=True)
        except yaml.YAMLError as err:
            self.__error(err)
        return obj

    def __yaml_str_to_dict(self, string):
        '''
        Convert a yaml string to a Python dictionary
        '''
        try:
            # Load string into object
            obj = yaml.load(string)
            obj = self.__normalize(obj)
            # Handle empty dict
            if obj is None:
                return {}
            return obj
        except yaml.YAMLError as err:
            self.__error(err)

    ############################################################
    # Constructor
    ############################################################

    def __init__(self, err_func, err_parm=None):
        '''
        The constructur sets the Ansible error handler

        Args:
          err_func (func):     The error function to call
          del_dict (str|None): If set, specifies the parameter name of the error msg for err_func.
                               err_func(err_parm='error msg')
        '''
        self.__err_func = err_func
        self.__err_parm = err_parm

    ############################################################
    # Publics
    ############################################################

    def dict2yaml(self, obj):
        '''
        Convert a dictionary to a human readable yaml string.
        '''
        return self.__dict_to_yaml_str(obj)

    def yaml2dict(self, string):
        '''
        Convert a yaml string to a Python dictionary.
        '''
        # Make all dicts a string first
        if isinstance(string, dict):
            string = self.__dict_to_yaml_str(string)

        return self.__yaml_str_to_dict(string)

    def del_ignore_keys(self, src_dict, del_dict):
        '''
        Removes any keys from the src_dict that are present and empty within the
        del_dict or have the same value in src_dict and del_dict.

        Args:
          src_dict (dict): The dictionary to delete keys on
          del_dict (dict): The dictionary that specifies the keys to delete
        Returns:
          dict             Cleaned dictionary
        '''
        result_dict = dict()

        # Handle dictionaries
        if isinstance(src_dict, dict) and isinstance(del_dict, dict):
            for key, src_val in src_dict.items():
                # Check if the key can be removed
                try:
                    del_val = del_dict[key]
                    # If dict/list recurse
                    if isinstance(src_val, (dict, list)) and isinstance(del_val, (dict, list)):
                        result_dict[key] = self.del_ignore_keys(src_val, del_val)
                    # If the del value is empty, do not add to the resulting dict (delete operation)
                    elif del_val in self.__empty_dict_vals:
                        continue
                    # If we have a match, do not add to the resulting dict (delete operation)
                    elif del_val == src_val:
                        continue
                    # No match so far, add it to the result dict (keep operation)
                    else:
                        result_dict[key] = src_val
                # Key is not specified in del_dict, so keep it
                except KeyError:
                    result_dict[key] = src_val

        # Handle lists
        elif isinstance(src_dict, list) and isinstance(del_dict, list) and len(del_dict) == 1:
            del_val = del_dict[0]
            for idx in reversed(range(len(src_dict))):
                src_val = src_dict[idx]

                # If dict/list recurse
                if isinstance(src_val, (dict, list)) and isinstance(del_val, (dict, list)):
                    result_dict[idx] = self.del_ignore_keys(src_val, del_val)
                # If the del value is empty, do not add to the resulting dict (delete operation)
                elif del_val in self.__empty_list_vals:
                    continue
                # If we have a match, do not add to the resulting dict (delete operation)
                elif del_val == src_val:
                    continue
                # No match so far, add it to the result dict (keep operation)
                else:
                    result_dict[key] = src_val

        # Neither dict nor list, its an absolute value that can be returned
        return result_dict

    def del_empty_keys(self, obj):
        '''
        Recursively remove all empty fields from a nested
        dict structure. Note, a non-empty field could turn
        into an empty one after its children deleted.
        https://stackoverflow.com/a/27974067

        Args:
          obj (dict): The dictionary to delete keys on
        Returns:
          dict        Cleaned dictionary
        '''
        if isinstance(obj, dict):
            for key, val in obj.items():

                # Dive into a deeper level
                if isinstance(val, (dict, list)):
                    val = self.del_empty_keys(val)

                # Delete the field if it's empty
                if val in self.__empty_dict_vals:
                    del obj[key]

        elif isinstance(obj, list):
            for idx in reversed(range(len(obj))):
                val = obj[idx]

                # Dive into a deeper level
                if isinstance(val, (dict, list)):
                    val = self.del_empty_keys(val)

                # Delete the field if it's empty
                if val in self.__empty_list_vals:
                    obj.pop(idx)

        return obj


################################################################################
# Helper Functions
################################################################################

def is_str(var):
    '''Test if a variable is a string'''
    # Check if string (lenient for byte-strings on Py2):
    if isinstance(var, basestring if PY2 else str):
        return True
    # Check if strictly a string (unicode-string):
    if isinstance(var, unicode if PY2 else str):
        return True
    # Check if either string (unicode-string) or byte-string:
    if isinstance(var, basestring if PY2 else (str, bytes)):
        return True
    # Check for byte-string (Py3 and Py2.7):
    if isinstance(var, bytes):
        return True

    return False


def shell_exec(command):
    '''
    Execute raw shell command and return exit code and output
    '''
    # Get absolute path of bash
    bash = os.popen('command -v bash').read().rstrip('\r\n')
    cpt = subprocess.Popen(
        command,
        executable=bash,
        shell=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    )

    # Wait until process terminates (without using p.wait())
    while cpt.poll() is None:
        # Process hasn't exited yet, let's wait some more time
        time.sleep(0.1)

    # Get stdout, stderr and return code
    stdout, stderr = cpt.communicate()
    return_code = cpt.returncode

    return return_code, stdout, stderr


################################################################################
# Ansible: Module functions
################################################################################

def eval_input(direction, module):
    '''
    Retrieve source or target input from file, command or string.
    Args:
      direction (str):   'source' or 'target'.
      module (dict):     Ansible module dictionary
                         the provided keys and sends them to a recursive delete function.
    Returns:
      str:               'source' or 'taget' input
    '''
    # Get 'source' or 'target' and 'source_type' or 'target_type'
    input_data_name = direction
    input_type_name = direction + '_type'
    # Get input from Ansible module call
    input_data = module.params.get(input_data_name)
    input_type = module.params.get(input_type_name)

    # Input is a file
    if input_type == 'file':
        with open(input_data, 'rt') as fpt:
            input_data = fpt.read().decode('UTF-8')
    # Input is a command
    elif input_type == 'command':
        command = input_data
        ret, input_data, stderr = shell_exec(command)
        if ret != 0:
            module.fail_json(msg='%s command failed: %s' % (input_data_name, stderr))
    # Input is string
    else:
        pass

    # Return input
    return input_data


def assert_type_command(module):
    '''
    Assert conditions if (source|target)_type is 'command'
    '''
    # Validate source
    if module.params.get('source_type') == 'command':
        if module.check_mode:
            result = dict(
                changed=False,
                msg='This module does not support check mode when source_type is \'command\'.',
                skipped=True
            )
            module.exit_json(**result)

    # Validate target
    if module.params.get('target_type') == 'command':
        if module.check_mode:
            result = dict(
                changed=False,
                msg='This module does not support check mode when target_type is \'command\'.',
                skipped=True
            )
            module.exit_json(**result)


def assert_type_file(module):
    '''
    Assert conditions if (source|target)_type is 'file'
    '''
    source = module.params.get('source')
    target = module.params.get('target')

    # Validate source
    if module.params.get('source_type') == 'file':
        b_source = to_bytes(source, errors='surrogate_or_strict')
        if not os.path.exists(b_source):
            module.fail_json(msg='source %s not found' % (source))
        if not os.access(b_source, os.R_OK):
            module.fail_json(msg='source %s not readable' % (source))
        if os.path.isdir(b_source):
            module.fail_json(
                msg='ydiff does not support recursive diff of directory: %s' % (source)
            )

    # Validate target
    if module.params.get('target_type') == 'file':
        b_target = to_bytes(target, errors='surrogate_or_strict')
        if not os.path.exists(b_target):
            module.fail_json(msg='target %s not found' % (target))
        if not os.access(b_target, os.R_OK):
            module.fail_json(msg='target %s not readable' % (target))
        if os.path.isdir(b_target):
            module.fail_json(
                msg='ydiff does not support recursive diff of directory: %s' % (target)
            )

def assert_ignore_keys(module):
    '''
    Assert that diff_ignore_keys is correct yaml.
    If not, its contents will be of type string, otherwise a correct dictionary is returned.
    '''
    ignore_keys = module.params.get('diff_ignore_keys')

    if is_str(ignore_keys):
        module.fail_json(msg='Invalid yaml for diff_ignore_keys')

    if not isinstance(ignore_keys, dict):
        module.fail_json(msg=str(type(ignore_keys)))
        module.fail_json(msg='Invalid yaml for diff_ignore_keys')



################################################################################
# Ansible: Initialize module
################################################################################

def init_ansible_module():
    '''
    Initialize Ansible Module.
    '''
    return AnsibleModule(
        argument_spec=dict(
            source=dict(type='str', required=True, default=None),
            target=dict(type='str', required=True, default=None),
            source_type=dict(
                type='str',
                required=False,
                default='string',
                choices=['string', 'file', 'command']
            ),
            target_type=dict(
                type='str',
                required=False,
                default='string',
                choices=['string', 'file', 'command']
            ),
            diff_ignore_keys=dict(
                type='dict',
                required=False,
                default={},
            ),
            diff_ignore_empty=dict(
                type='bool',
                required=False,
                default=False,
            )
        ),
        supports_check_mode=True
    )


################################################################################
# Main entry point
################################################################################

def main():
    '''
    Main entry point
    '''
    # Initialize module
    module = init_ansible_module()
    ydiff = YdiffDict(module.fail_json, 'msg')

    # Assert module input
    assert_type_command(module)
    assert_type_file(module)
    assert_ignore_keys(module)

    # Retrieve module inputs
    source = eval_input('source', module) # local template to deploy
    target = eval_input('target', module) # Currently deployed
    ignore_keys = module.params.get('diff_ignore_keys')
    ignore_empty = module.params.get('diff_ignore_empty')

    # Convert to normalized dicts
    ignore_keys = ydiff.yaml2dict(ignore_keys)
    source = ydiff.yaml2dict(source)
    target = ydiff.yaml2dict(target)

    # Remove ignored keys
    # TODO: Only remove keys from target, if they are not set in source
    # This will allow for complete diffs, when no target exists yet.
    source = ydiff.del_ignore_keys(source, ignore_keys)
    target = ydiff.del_ignore_keys(target, ignore_keys)

    # Remove empty yaml keys
    if ignore_empty:
        #source = ydiff.del_empty_keys(source)
        target = ydiff.del_empty_keys(target)

    # Convert back to string
    source = ydiff.dict2yaml(source)
    target = ydiff.dict2yaml(target)

    # Ansible diff output
    diff = {
        'before': target,
        'after': source,
    }
    # Did we have any changes?
    changed = (source != target)

    # Ansible module returned variables
    result = dict(
        diff=diff,
        changed=changed
    )

    # Exit ansible module call
    module.exit_json(**result)


if __name__ == '__main__':
    main()
