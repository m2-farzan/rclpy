# Copyright 2022 Open Source Robotics Foundation, Inc.
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

import time
from typing import Callable, List, Optional, Sequence, Union

from rcl_interfaces.msg import Parameter as ParameterMsg
from rcl_interfaces.srv import DescribeParameters
from rcl_interfaces.srv import GetParameters
from rcl_interfaces.srv import GetParameterTypes
from rcl_interfaces.srv import ListParameters
from rcl_interfaces.srv import SetParameters
from rcl_interfaces.srv import SetParametersAtomically

from rclpy.callback_groups import CallbackGroup
from rclpy.node import Node
from rclpy.parameter import Parameter as Parameter
from rclpy.parameter import parameter_dict_from_yaml_file
from rclpy.qos import qos_profile_services_default
from rclpy.qos import QoSProfile
from rclpy.task import Future


class AsyncParameterClient:
    def __init__(
            self,
            node: Node,
            remote_node_name: str,
            qos_profile: QoSProfile = qos_profile_services_default,
            callback_group: Optional[CallbackGroup] = None):
        """
        Create an AsyncParameterClient.

        An AsyncParameterClient that uses services offered by a remote node
        to query and modify parameters in a streamlined way.
        
        Usage example:

        .. code-block:: python

            import rclpy
            from rclpy.parameter import Parameter
            node = rclpy.create_node('my_node')

            client = AsyncParameterClient(node, 'example_node')

            # set parameters
            future = client.set_parameters([
                Parameter('int_param', Parameter.Type.INTEGER, 88).to_parameter_msg(),
                Parameter('string/param', Parameter.Type.STRING, 'hello world').to_parameter_msg(),
            ])
            self.executor.spin_until_future_complete(future)
            results = future.result()  # rcl_interfaces.srv.SetParameters.Response

        For more on service names, see: `ROS 2 docs`_.

        .. _ROS 2 docs: https://docs.ros.org/en/rolling/Concepts/About-ROS-2-Parameters.html#interacting-with-parameters # noqa E501

        :param node: Node used to create clients that will interact with the remote node
        :param remote_node_name: Name of remote node for which the parameters will be managed
        """
        self.remote_node_name = remote_node_name
        self.node = node
        self._get_parameter_client = self.node.create_client(
            GetParameters, f'{remote_node_name}/get_parameters',
            qos_profile=qos_profile, callback_group=callback_group
        )
        self._list_parameter_client = self.node.create_client(
            ListParameters, f'{remote_node_name}/list_parameters',
            qos_profile=qos_profile, callback_group=callback_group
        )
        self._set_parameter_client = self.node.create_client(
            SetParameters, f'{remote_node_name}/set_parameters',
            qos_profile=qos_profile, callback_group=callback_group
        )
        self._get_parameter_types_client = self.node.create_client(
            GetParameterTypes, f'{remote_node_name}/get_parameter_types',
            qos_profile=qos_profile, callback_group=callback_group
        )
        self._describe_parameters_client = self.node.create_client(
            DescribeParameters, f'{remote_node_name}/describe_parameters',
            qos_profile=qos_profile, callback_group=callback_group
        )
        self._set_parameters_atomically_client = self.node.create_client(
            SetParametersAtomically, f'{remote_node_name}/set_parameters_atomically',
            qos_profile=qos_profile, callback_group=callback_group
        )

    def service_is_ready(self) -> bool:
        """
        Check if all services are ready.

        :return: ``True`` if all services are available, False otherwise.
        """
        return all([
            self._list_parameter_client.service_is_ready(),
            self._set_parameter_client.service_is_ready(),
            self._get_parameter_client.service_is_ready(),
            self._get_parameter_types_client.service_is_ready(),
            self._describe_parameters_client.service_is_ready(),
            self._set_parameters_atomically_client.service_is_ready(),
        ])

    def wait_for_service(self, timeout_sec: Optional[float] = None) -> bool:
        """
        Wait for all parameter services to be available.

        :param timeout_sec: Seconds to wait. If ``None``, then wait forever.
        :return: ``True`` if all services were waite , ``False`` otherwise.
        """
        client_wait_fns = [
                self._list_parameter_client.wait_for_service,
                self._set_parameter_client.wait_for_service,
                self._get_parameter_client.wait_for_service,
                self._get_parameter_types_client.wait_for_service,
                self._describe_parameters_client.wait_for_service,
                self._set_parameters_atomically_client.wait_for_service,
        ]

        if timeout_sec is None:
            return all([fn() for fn in client_wait_fns])

        prev = time.time()
        for wait_for_service in client_wait_fns:
            if timeout_sec < 0 or not wait_for_service(timeout_sec):
                return False
            timeout_sec -= time.time() - prev
            prev = time.time()
        return True

    def list_parameters(
        self,
        prefixes: Optional[List[str]] = None,
        depth: int = 1,
        callback: Optional[Callable] = None
    ) -> Future:
        """
        List all parameters with given prefixs.

        :param prefixes: List of prefixes to filter by.
        :param depth: Depth of the parameter tree to list.
        :param callback: Callback function to call when the request is complete.
        :return: ``Future`` with the result of the request.
        """
        request = ListParameters.Request()
        if prefixes:
            request.prefixes = prefixes
        request.depth = depth
        future = self._list_parameter_client.call_async(request)
        if callback:
            future.add_done_callback(callback)
        return future

    def get_parameters(self, names: List[str], callback: Optional[Callable] = None) -> Future:
        """
        Get parameters given names.

        :param names: List of parameter names to get.
        :param callback: Callback function to call when the request is complete.
        :return: ``Future`` with the result of the request.
        """
        request = GetParameters.Request()
        request.names = names
        future = self._get_parameter_client.call_async(request)
        if callback:
            future.add_done_callback(callback)
        return future

    def set_parameters(
        self,
        parameters: Sequence[Union[Parameter, ParameterMsg]],
        callback: Optional[Callable] = None
    ) -> Future:
        """
        Set parameters given a list of parameters.

        The result after the returned future is complete
        will be of type ``rcl_interfaces.srv.SetParameters.Response``.

        :param parameters: Sequence of parameters to set.
        :param callback: Callback function to call when the request is complete.
        :return: ``Future`` with the result of the request.
        """
        request = SetParameters.Request()
        request.parameters = [
            i.to_parameter_msg() if isinstance(i, Parameter) else i for i in parameters
        ]
        future = self._set_parameter_client.call_async(request)
        if callback:
            future.add_done_callback(callback)
        return future

    def describe_parameters(
        self,
        names: List[str],
        callback: Optional[Callable] = None
    ) -> Future:
        """
        Describe parameters given names.

        The result after the returned future is complete
        will be of type ``rcl_interfaces.srv.DescribeParameters.Response``.

        :param names: List of parameter names to describe
        :param callback: Callback function to call when the request is complete.
        :return: ``Future`` with the result of the request.
        """
        request = DescribeParameters.Request()
        request.names = names
        future = self._describe_parameters_client.call_async(request)
        if callback:
            future.add_done_callback(callback)
        return future

    def get_parameter_types(
        self,
        names: List[str],
        callback: Optional[Callable] = None
    ) -> Future:
        """
        Get parameter types given names.

        The result after the returned future is complete
        will be of type ``rcl_interfaces.srv.GetParameterTypes.Response``.

        Parameter type definitions are given in rcl_interfaces.msg.ParameterType

        :param names: List of parameter names to get types for.
        :param callback: Callback function to call when the request is complete.
        :return: ``Future`` with the result of the request.
        """
        request = GetParameterTypes.Request()
        request.names = names
        future = self._get_parameter_types_client.call_async(request)
        if callback:
            future.add_done_callback(callback)
        return future

    def set_parameters_atomically(
        self,
        parameters: Sequence[Union[Parameter, ParameterMsg]],
        callback: Optional[Callable] = None
    ) -> Future:
        """
        Set parameters atomically.

        The result after the returned future is complete
        will be of type ``rcl_interfaces.srv.SetParametersAtomically.Response``.

        :param parameters: Sequence of parameters to set.
        :param callback: Callback function to call when the request is complete.
        :return: ``Future`` with the result of the request.
        """
        request = SetParametersAtomically.Request()
        request.parameters = [
            i.to_parameter_msg() if isinstance(i, Parameter) else i for i in parameters
        ]
        future = self._set_parameters_atomically_client.call_async(request)
        if callback:
            future.add_done_callback(callback)
        return future

    def delete_parameters(
        self, names: List[str], callback: Optional[Callable] = None
    ) -> Future:
        """
        Unset parameters with given names.

        The result after the returned future is complete
        will be of type ``rcl_interfaces.srv.SetParameters.Response``.

        :param names: List of parameter names to unset.
        :param callback: Callback function to call when the request is complete.
        :return: ``Future`` with the result of the request.
        """
        request = SetParameters.Request()
        request.parameters = [Parameter(name=i).to_parameter_msg() for i in names]
        future = self._set_parameter_client.call_async(request)
        if callback:
            future.add_done_callback(callback)
        return future

    def load_parameter_file(
        self,
        parameter_file: str,
        use_wildcard: bool = False,
    ) -> Future:
        """
        Load parameters from a yaml file.

        Wrapper around `rclpy.parameter.parameter_dict_from_yaml_file`.

        The result after the returned future is complete
        will be of type ``rcl_interfaces.srv.SetParameters.Response``.

        :param parameter_file: Path to the parameter file.
        :param use_wildcard: Whether to use wildcard expansion.
        :return: Future with the result from the set_parameter call.
        """
        param_dict = parameter_dict_from_yaml_file(parameter_file, use_wildcard)
        future = self.set_parameters(list(param_dict.values()))
        return future
