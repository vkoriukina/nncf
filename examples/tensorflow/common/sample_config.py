"""
 Copyright (c) 2020 Intel Corporation
 Licensed under the Apache License, Version 2.0 (the "License");
 you may not use this file except in compliance with the License.
 You may obtain a copy of the License at
      http://www.apache.org/licenses/LICENSE-2.0
 Unless required by applicable law or agreed to in writing, software
 distributed under the License is distributed on an "AS IS" BASIS,
 WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 See the License for the specific language governing permissions and
 limitations under the License.
"""

from addict import Dict

import argparse
import os

from nncf import NNCFConfig

try:
    import jstyleson as json
except ImportError:
    import json


_DEFAULT_KEY_TO_ENV = {
    "world_size": "WORLD_SIZE",
}


class ActionWrapper(argparse.Action):
    def __init__(self, action):
        self._action = action
        super().__init__(action.option_strings, action.dest, nargs=action.nargs, const=action.const,
                         default=action.default, type=action.type, choices=action.choices, required=action.required,
                         help=action.help, metavar=action.metavar)
        self._action = action

    def __getattr__(self, item):
        return getattr(self._action, item)

    def __call__(self, parser, namespace, values, option_string=None):
        parser.seen_actions.add(self._action.dest)
        return self._action(parser, namespace, values, option_string)


# pylint: disable=protected-access
class CustomArgumentGroup(argparse._ArgumentGroup):
    def _add_action(self, action):
        super()._add_action(ActionWrapper(action))


# pylint: disable=protected-access
class CustomActionContainer(argparse._ActionsContainer):
    def add_argument_group(self, *args, **kwargs):
        group = CustomArgumentGroup(self, *args, **kwargs)
        self._action_groups.append(group)
        return group


class CustomArgumentParser(CustomActionContainer, argparse.ArgumentParser):
    """ArgumentParser that saves which arguments are provided"""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, *kwargs)
        self.seen_actions = set()

    def parse_known_args(self, args=None, namespace=None):
        self.seen_actions.clear()
        return super().parse_known_args(args, namespace)


class SampleConfig(Dict):
    @classmethod
    def from_json(cls, path) -> 'SampleConfig':
        with open(path, encoding='utf8') as f:
            loaded_json = json.load(f)
        return cls(loaded_json)

    def update_from_args(self, args, argparser=None):
        if argparser is not None:
            if isinstance(argparser, CustomArgumentParser):
                default_args = {arg for arg in vars(args) if arg not in argparser.seen_actions}
            else:
                # this will fail if we explicitly provide default argument in CLI
                known_args = argparser.parse_known_args()
                default_args = {k for k, v in vars(args).items() if known_args[k] == v}
        else:
            default_args = {k for k, v in vars(args).items() if v is None}

        for key, value in vars(args).items():
            if key not in default_args or key not in self:
                self[key] = value

    def update_from_env(self, key_to_env_dict=None):
        if key_to_env_dict is None:
            key_to_env_dict = _DEFAULT_KEY_TO_ENV
        for k, v in key_to_env_dict:
            if v in os.environ:
                self[k] = int(os.environ[v])


def create_sample_config(args, parser) -> SampleConfig:
    nncf_config = NNCFConfig.from_json(args.config)

    sample_config = SampleConfig.from_json(args.config)
    sample_config.update_from_args(args, parser)
    sample_config.nncf_config = nncf_config

    return sample_config
