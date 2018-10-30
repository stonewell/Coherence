# Licensed under the MIT license
# http://opensource.org/licenses/mit-license.php

# Copyright (C) 2006 Fluendo, S.A. (www.fluendo.com).
# Copyright 2006,2007,2008,2009 Frank Scholz <coherence@beebits.net>

from twisted.python import failure
from twisted.python.util import OrderedDict

from coherence import log


class Argument:

    def __init__(self, name, direction, state_variable):
        self.name = name
        self.direction = direction
        self.state_variable = state_variable

    def get_name(self):
        return self.name

    def get_direction(self):
        return self.direction

    def get_state_variable(self):
        return self.state_variable

    def __repr__(self):
        return ("Argument(%(name)r, %(direction)r, %(state_variable)r"
                % vars(self))

    def as_tuples(self):
        r = [
            ('Name', self.name),
            ('Direction', self.direction),
            ('Related State Variable', self.state_variable)
            ]
        return r

    def as_dict(self):
        return {
            'name': self.name,
            'direction': self.direction,
            'related_state_variable': self.state_variable
            }


class Action(log.Loggable):
    logCategory = 'action'

    def __init__(self, service, name, implementation, arguments_list):
        log.Loggable.__init__(self)
        self.service = service
        self.name = name
        self.implementation = implementation
        self.arguments_list = arguments_list
        self.callback = None

    def _get_client(self):
        client = self.service._get_client(self.name)
        return client

    def get_name(self):
        return self.name

    def get_implementation(self):
        return self.implementation

    def get_arguments_list(self):
        return self.arguments_list

    def get_in_arguments(self):
        return [arg for arg in self.arguments_list
                if arg.direction == 'in']

    def get_out_arguments(self):
        return [arg for arg in self.arguments_list
                if arg.direction == 'out']

    def get_service(self):
        return self.service

    def set_callback(self, callback):
        self.callback = callback

    def get_callback(self):
        return self.callback

    def call(self, *args, **kwargs):
        self.info("calling %s", self.name)
        in_arguments = self.get_in_arguments()
        self.info("in arguments %s", [a.get_name() for a in in_arguments])
        instance_id = kwargs.get('InstanceID', 0)

        # check for missing or extraneous arguments
        passed_args = set(kwargs)
        expected_args = set(a.get_name() for a in in_arguments)
        if passed_args - expected_args:
            self.error("arguments %s not valid for action %s",
                       list(passed_args - expected_args), self.name)
            return
        elif expected_args - passed_args:
            self.error("argument %s missing for action %s",
                       list(expected_args - passed_args), self.name)
            return

        action_name = self.name

        device_client = self.service.device.client
        if self.name in getattr(device_client, 'overlay_actions', {}):
            self.info("we have an overlay method %r for action %r",
                      device_client.overlay_actions[self.name], self.name)
            action_name, kwargs = device_client.overlay_actions[self.name](**kwargs)
            self.info("changing action to %r %r", action_name, kwargs)

        if hasattr(device_client, 'overlay_headers'):
            self.info("action call has headers %r", 'headers' in kwargs)
            if 'headers' in kwargs:
                kwargs['headers'].update(device_client.overlay_headers)
            else:
                kwargs['headers'] = device_client.overlay_headers
            self.info("action call with new/updated headers %r", kwargs['headers'])

        ordered_arguments = OrderedDict()
        for argument in self.get_in_arguments():
            ordered_arguments[argument.name] = kwargs[argument.name]
        if 'headers' in kwargs:
            ordered_arguments['headers'] = kwargs['headers']

        client = self._get_client()
        d = client.callRemote(action_name, ordered_arguments)
        d.addCallback(self._got_results, instance_id=instance_id,
                      name=action_name)
        d.addErrback(self._got_error)
        return d

    def _got_error(self, failure):
        self.warning("error on %s request with %s %s",
                     self.name, self.service.service_type,
                     self.service.control_url)
        self.info(failure)
        return failure

    def _got_results(self, results, instance_id, name):
        instance_id = int(instance_id)
        out_arguments = self.get_out_arguments()
        self.info("call %s (instance %d) returns %d arguments: %r",
                  name, instance_id, len(out_arguments), results)
        # Update state-variables from the result. NB: This silently
        # ignores missing and extraneous result values. I'm not sure
        # if this is according to the DLNA specs. :todo: check the DLNS-specs
        for outarg in out_arguments:
            if outarg.get_name() in results:
                var = self.service.get_state_variable(
                    outarg.get_state_variable(), instance_id)
                var.update(results[outarg.get_name()])

        return results

    def __repr__(self):
        return ("Action(%(name)r, %(implementation)r, (%arguments_list)r"
                % vars(self))

    def as_tuples(self):
        r = [
            ('Name', self.name),
            ("Number of 'in' arguments", len(self.get_in_arguments())),
            ("Number of 'out' arguments", len(self.get_out_arguments())),
            ]
        return r

    def as_dict(self):
        return {
            'name': self.name,
            'arguments': [a.as_dict() for a in self.arguments_list]
            }
