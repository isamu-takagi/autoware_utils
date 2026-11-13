# Copyright 2026 The Autoware Contributors
# SPDX-License-Identifier: Apache-2.0

# https://github.com/ros2/launch/blob/rolling/launch/launch/actions/include_launch_description.py
# https://github.com/ros2/launch/blob/rolling/launch/launch/actions/group_action.py
# https://github.com/ros2/launch/blob/rolling/launch/launch/launch_description.py
#
# Copyright 2018 Open Source Robotics Foundation, Inc.
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

"""Module for the IncludeLaunchDescription action."""

from typing import Any
from typing import Dict
from typing import Iterable
from typing import List
from typing import Optional
from typing import Tuple
from typing import Type
from typing import Union

from launch import Action
from launch import LaunchContext
from launch import LaunchDescriptionEntity
from launch import LaunchDescriptionSource
from launch.actions import DeclareLaunchArgument
from launch.actions import IncludeLaunchDescription
from launch.actions import PopEnvironment
from launch.actions import PopLaunchConfigurations
from launch.actions import PushEnvironment
from launch.actions import PushLaunchConfigurations
from launch.actions import ResetEnvironment
from launch.actions import ResetLaunchConfigurations
from launch.actions import SetLaunchConfiguration
from launch.frontend import Entity
from launch.frontend import Parser
from launch.frontend import expose_action
from launch.some_substitutions_type import SomeSubstitutionsType
from launch.utilities import normalize_to_list_of_substitutions
from launch.utilities import perform_substitutions


@expose_action("autoware_strict_include")
class StrictInclude(IncludeLaunchDescription):
    """
    Action that includes a launch description source and yields its entities when visited.

    Unlike IncludeLaunchDescription, this enforces forwarding and isolates the scope.
    This is similar to using an include action in combination with the keep setting of a group action.
    """

    def __init__(
        self,
        launch_description_source: Union[LaunchDescriptionSource, SomeSubstitutionsType],
        *,
        launch_arguments: Optional[
            Iterable[Tuple[SomeSubstitutionsType, SomeSubstitutionsType]]
        ] = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(launch_description_source, launch_arguments=launch_arguments, **kwargs)

    @classmethod
    def parse(cls, entity: Entity, parser: Parser) -> Tuple[Type["StrictInclude"], Dict[str, Any]]:
        _, kwargs = super().parse(entity, parser)
        return cls, kwargs

    def execute(
        self, context: LaunchContext
    ) -> List[Union[SetLaunchConfiguration, LaunchDescriptionEntity]]:
        launch_description = self.launch_description_source.get_launch_description(context)
        launch_configurations = {tuple(key): value for key, value in self.launch_arguments}
        launch_file_location = {
            "current_launch_file_path": self._get_launch_file(),
            "current_launch_file_directory": self._get_launch_file_directory(),
        }

        self._validate_arguments(context, launch_description)
        return [
            PushLaunchConfigurations(),
            PushLocals(),
            PushEnvironment(),
            ResetEnvironment(),
            ResetLaunchConfigurations(launch_configurations),
            ExtendLocals(launch_file_location),
            launch_description,
            PopEnvironment(),
            PopLocals(),
            PopLaunchConfigurations(),
        ]

    def _validate_arguments(
        self, context: LaunchContext, launch_description: LaunchDescriptionEntity
    ) -> None:
        argument_names = []
        for name, value in self.launch_arguments:
            resolved_name = perform_substitutions(context, normalize_to_list_of_substitutions(name))
            argument_names.append(resolved_name)

        provided_arguments = set(argument_names)
        required_arguments = self._get_toplevel_launch_arguments(launch_description)
        for argument in required_arguments:
            if argument.default_value is not None:
                continue
            if argument.name not in provided_arguments:
                raise RuntimeError(
                    f"Missing argument '{argument.name}' ({self._get_launch_file()})"
                )

    @staticmethod
    def _get_toplevel_launch_arguments(
        description: LaunchDescriptionEntity,
    ) -> Iterable[DeclareLaunchArgument]:
        """
        Return a list of launch arguments with its associated include launch descriptions actions.

        This is a non-recursive version of LaunchDescription.get_launch_arguments_with_include_launch_description_actions.
        """
        declared_launch_arguments: Dict[str, DeclareLaunchArgument] = {}

        def process_entities(entities):
            for entity in entities:
                if isinstance(entity, ResetLaunchConfigurations):
                    return
                if isinstance(entity, IncludeLaunchDescription):
                    return
                if isinstance(entity, DeclareLaunchArgument):
                    if entity.name in declared_launch_arguments:
                        ValueError(f"Duplicate launch argument declaration: {entity.name}")
                    declared_launch_arguments[entity.name] = entity
                process_entities(entity.describe_sub_entities())

        process_entities(description.entities)
        return declared_launch_arguments.values()


class PushLocals(Action):
    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)

    def execute(self, context: LaunchContext) -> None:
        context._push_locals()


class PopLocals(Action):
    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)

    def execute(self, context: LaunchContext) -> None:
        context._pop_locals()


class ExtendLocals(Action):
    def __init__(self, values: Dict[str, Any], **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.__values = values

    def execute(self, context: LaunchContext) -> None:
        context.extend_locals(self.__values)
