# Copyright (C) 2015-2017 by the RBniCS authors
#
# This file is part of RBniCS.
#
# RBniCS is free software: you can redistribute it and/or modify
# it under the terms of the GNU Lesser General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# RBniCS is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with RBniCS. If not, see <http://www.gnu.org/licenses/>.
#

import types

def sync_setters__internal(other_object__name, method__name, private_attribute__name, method__decorator=None):
    def sync_setters_decorator(__init__):
        
        def __synced__init__(self, *args, **kwargs):
            # Call the parent initialization
            __init__(self, *args, **kwargs)
            # Get other_object
            other_object = getattr(self, other_object__name)
            # Sync setters only if the other object is not None
            if other_object is not None:
                # Initialize private storage
                if method__name not in _synced_setters:
                    _synced_setters[method__name] = dict()
                # Detect if either self or other_object are already in sync with somebody else
                all_synced_setters_for_method_self = None
                if self in _synced_setters[method__name]:
                    all_synced_setters_for_method_self = _synced_setters[method__name][self]
                all_synced_setters_for_method_other_object = None
                if other_object in _synced_setters[method__name]:
                    all_synced_setters_for_method_other_object = _synced_setters[method__name][other_object]
                # Add current methods to the set of syncronized setters in storage
                if (
                    all_synced_setters_for_method_self is not None
                        and
                    all_synced_setters_for_method_other_object is not None
                ):
                    assert all_synced_setters_for_method_self is all_synced_setters_for_method_other_object
                elif (
                    all_synced_setters_for_method_self is None
                        and
                    all_synced_setters_for_method_other_object is not None
                ):
                    all_synced_setters_for_method = all_synced_setters_for_method_other_object
                    all_synced_setters_for_method.add((self, getattr(self, method__name)))
                    _synced_setters[method__name][self] = all_synced_setters_for_method
                elif (
                    all_synced_setters_for_method_self is not None
                        and
                    all_synced_setters_for_method_other_object is None
                ):
                    all_synced_setters_for_method = all_synced_setters_for_method_self
                    all_synced_setters_for_method.add((other_object, getattr(other_object, method__name)))
                    _synced_setters[method__name][other_object] = all_synced_setters_for_method
                else:
                    all_synced_setters_for_method = set()
                    all_synced_setters_for_method.add((self, getattr(self, method__name)))
                    all_synced_setters_for_method.add((other_object, getattr(other_object, method__name)))
                    _synced_setters[method__name][self] = all_synced_setters_for_method
                    _synced_setters[method__name][other_object] = all_synced_setters_for_method
                # Now both storage and local variable should be consistent between self and other_object, 
                # and pointing to the same memory location
                assert _synced_setters[method__name][self] is _synced_setters[method__name][other_object]
                # Override both self and other_object setters to propagate to all synced setters
                def overridden_method(self_, arg):
                    if method__name not in _synced_setters__disabled_methods:
                        all_synced_setters = _synced_setters[method__name][self_]
                        for (obj, setter) in all_synced_setters:
                            if getattr(obj, private_attribute__name) is not arg:
                                setter(arg)
                if method__decorator is not None:
                    overridden_method = method__decorator(overridden_method)
                if all_synced_setters_for_method_self is None:
                    setattr(self, method__name, types.MethodType(overridden_method, self))
                if all_synced_setters_for_method_other_object is None:
                    setattr(other_object, method__name, types.MethodType(overridden_method, other_object))
                # Make sure that the value of my attribute is in sync with the value that is currently 
                # stored in other_object, because it was set before overriding was carried out
                getattr(self, method__name)(getattr(other_object, private_attribute__name))
        
        return __synced__init__
    return sync_setters_decorator

def sync_setters(other_object__name, method__name, private_attribute__name):
    assert method__name in ("set_final_time", "set_initial_time", "set_mu", "set_mu_range", "set_time", "set_time_step_size") # other uses have not been considered yet
    if method__name in ("set_final_time", "set_initial_time", "set_mu", "set_time", "set_time_step_size"):
        return sync_setters__internal(other_object__name, method__name, private_attribute__name)
    elif method__name == "set_mu_range":
        def set_mu_range__decorator(set_mu_range__method):
            def set_mu_range__decorated(self_, mu_range):
                # set_mu_range by defaults calls set_mu. Since set_mu
                # (1) requires a properly initialized mu range, but
                # (2) it has been overridden to be kept in sync, also
                #     for object which have not been initialized yet, 
                # we first disable set_mu
                _synced_setters__disabled_methods.add("set_mu")
                # We set (and sync) the mu range
                set_mu_range__method(self_, mu_range)
                # Finally, we restore the original set_mu and set (and sync)
                # the value of mu so that it has the correct length,
                # as done in ParametrizedProblem
                _synced_setters__disabled_methods.remove("set_mu")
                self_.set_mu(tuple([r[0] for r in mu_range]))
            return set_mu_range__decorated
        return sync_setters__internal(other_object__name, method__name, private_attribute__name, set_mu_range__decorator)
    else:
        raise AssertionError("Invalid method in sync_setters.")
    
_synced_setters = dict()
_synced_setters__disabled_methods = set()
