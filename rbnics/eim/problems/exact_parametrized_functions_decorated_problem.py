# Copyright (C) 2015-2018 by the RBniCS authors
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

import hashlib
import inspect
from rbnics.backends import SymbolicParameters
from rbnics.eim.backends import OfflineOnlineBackend
from rbnics.eim.utils.decorators import StoreMapFromParametrizedOperatorsToProblem, StoreMapFromParametrizedOperatorsToTermAndIndex
from rbnics.utils.decorators import overload, PreserveClassName, ProblemDecoratorFor, tuple_of
from rbnics.utils.test import PatchInstanceMethod

def ExactParametrizedFunctions_OfflineAndOnline(**kwargs):
    assert kwargs["stages"] in ("offline", ("offline", ), ("offline", "online"))
    if kwargs["stages"] == ("offline", "online"):
        # Keep exact parametrized functions evaluation both offline and online
        from rbnics.eim.problems.exact_parametrized_functions import ExactParametrizedFunctions
        return ExactParametrizedFunctions(**kwargs)
    else:
        # This exact decorator should do nothing. Indeed EIM/DEIM exact decorator will take
        # care of adding the ExactParametrizedFunctions decorator, and we should not add it again here
        def DoNothing(ParametrizedDifferentialProblem_DerivedClass):
            return ParametrizedDifferentialProblem_DerivedClass
        return DoNothing


def ExactParametrizedFunctionsDecoratedProblem(
    stages=("offline", "online"),
    **decorator_kwargs
):

    from rbnics.eim.problems.exact_parametrized_functions import ExactParametrizedFunctions
    
    @ProblemDecoratorFor(ExactParametrizedFunctions, ExactAlgorithm=ExactParametrizedFunctions_OfflineAndOnline, stages=stages)
    def ExactParametrizedFunctionsDecoratedProblem_Decorator(ParametrizedDifferentialProblem_DerivedClass):
        
        @StoreMapFromParametrizedOperatorsToProblem
        @StoreMapFromParametrizedOperatorsToTermAndIndex
        @PreserveClassName
        class ExactParametrizedFunctionsDecoratedProblem_Class(ParametrizedDifferentialProblem_DerivedClass):
            
            # Default initialization of members
            def __init__(self, V, **kwargs):
                # Call the parent initialization
                ParametrizedDifferentialProblem_DerivedClass.__init__(self, V, **kwargs)
                # Storage for symbolic parameters
                self.mu_symbolic = None
                
                # Store values passed to decorator
                self._store_exact_evaluation_stages(stages)
                
                # Generate offline online backend for current problem
                self.offline_online_backend = OfflineOnlineBackend(self.name())
            
            @overload(str)
            def _store_exact_evaluation_stages(self, stage):
                assert stages != "online", "This choice does not make any sense because it requires an EIM/DEIM offline stage which then is not used online"
                assert stages == "offline"
                self._apply_exact_evaluation_at_stages = (stages, )
                
            @overload(tuple_of(str))
            def _store_exact_evaluation_stages(self, stage):
                assert len(stages) in (1, 2)
                assert stages[0] in ("offline", "online")
                if len(stages) > 1:
                    assert stages[1] in ("offline", "online")
                    assert stages[0] != stages[1]
                self._apply_exact_evaluation_at_stages = stages
            
            def init(self):
                has_disable_init_operators = hasattr(self, "disable_init_operators") # may be shared between EIM/DEIM and exact evaluation
                # Call parent's method (enforcing an empty parent call to _init_operators)
                if not has_disable_init_operators:
                    self.disable_init_operators = PatchInstanceMethod(self, "_init_operators", lambda self_: None)
                self.disable_init_operators.patch()
                ParametrizedDifferentialProblem_DerivedClass.init(self)
                self.disable_init_operators.unpatch()
                if not has_disable_init_operators:
                    del self.disable_init_operators
                # Then, initialize exact operators
                self._init_operators_exact()
            
            def _init_operators_exact(self):
                # Initialize symbolic parameters only once
                if self.mu_symbolic is None:
                    self.mu_symbolic = SymbolicParameters(self, self.V, self.mu)
                # Initialize offline/online switch storage only once (may be shared between EIM/DEIM and exact evaluation)
                OfflineOnlineClassMethod = self.offline_online_backend.OfflineOnlineClassMethod
                OfflineOnlineExpansionStorage = self.offline_online_backend.OfflineOnlineExpansionStorage
                OfflineOnlineExpansionStorageSize = self.offline_online_backend.OfflineOnlineExpansionStorageSize
                OfflineOnlineSwitch = self.offline_online_backend.OfflineOnlineSwitch
                if not isinstance(self.Q, OfflineOnlineSwitch):
                    assert isinstance(self.Q, dict)
                    assert len(self.Q) is 0
                    self.Q = OfflineOnlineExpansionStorageSize()
                if not isinstance(self.operator, OfflineOnlineSwitch):
                    assert isinstance(self.operator, dict)
                    assert len(self.operator) is 0
                    self.operator = OfflineOnlineExpansionStorage(self, "OperatorExpansionStorage")
                if not isinstance(self.assemble_operator, OfflineOnlineSwitch):
                    assert inspect.ismethod(self.assemble_operator)
                    self._assemble_operator_exact = self.assemble_operator
                    self.assemble_operator = OfflineOnlineClassMethod(self, "assemble_operator")
                if not isinstance(self.compute_theta, OfflineOnlineSwitch):
                    assert inspect.ismethod(self.compute_theta)
                    self._compute_theta_exact = self.compute_theta
                    self.compute_theta = OfflineOnlineClassMethod(self, "compute_theta")
                # Temporarily replace float parameters with symbols, so that the forms do not hardcode
                # the current value of the parameter while assemblying.
                mu_float = self.mu
                self.mu = self.mu_symbolic
                # Setup offline/online switches
                former_stage = OfflineOnlineSwitch.get_current_stage()
                for stage_exact in self._apply_exact_evaluation_at_stages:
                    OfflineOnlineSwitch.set_current_stage(stage_exact)
                    # Enforce exact evaluation of assemble_operator and compute_theta
                    self.assemble_operator.attach(self._assemble_operator_exact, lambda term: True)
                    self.compute_theta.attach(self._compute_theta_exact, lambda term: True)
                    # Setup offline/online operators storage with exact operators
                    self.operator.set_is_affine(False)
                    self._init_operators()
                    self.operator.unset_is_affine()
                # Restore former stage in offline/online switch storage
                OfflineOnlineSwitch.set_current_stage(former_stage)
                # Restore float parameters
                self.mu = mu_float
                
            def solve(self, **kwargs):
                # Exact operators should be used regardless of the current stage
                OfflineOnlineSwitch = self.offline_online_backend.OfflineOnlineSwitch
                former_stage = OfflineOnlineSwitch.get_current_stage()
                OfflineOnlineSwitch.set_current_stage("offline")
                # Call Parent method
                solution = ParametrizedDifferentialProblem_DerivedClass.solve(self, **kwargs)
                # Restore former stage in offline/online switch storage
                OfflineOnlineSwitch.set_current_stage(former_stage)
                # Return
                return solution
                
            def compute_output(self):
                # Exact operators should be used regardless of the current stage
                OfflineOnlineSwitch = self.offline_online_backend.OfflineOnlineSwitch
                former_stage = OfflineOnlineSwitch.get_current_stage()
                OfflineOnlineSwitch.set_current_stage("offline")
                # Call Parent method
                output = ParametrizedDifferentialProblem_DerivedClass.compute_output(self)
                # Restore former stage in offline/online switch storage
                OfflineOnlineSwitch.set_current_stage(former_stage)
                # Return
                return output
                
            def _cache_key_and_file_from_kwargs(self, **kwargs):
                (cache_key, cache_file) = ParametrizedDifferentialProblem_DerivedClass._cache_key_and_file_from_kwargs(self, **kwargs)
                # Change cache key depending on current stage
                OfflineOnlineSwitch = self.offline_online_backend.OfflineOnlineSwitch
                if OfflineOnlineSwitch.get_current_stage() in self._apply_exact_evaluation_at_stages:
                    # Append current stage to cache key
                    cache_key = cache_key + ("exact_evaluation", )
                    cache_file = hashlib.sha1(str(cache_key).encode("utf-8")).hexdigest()
                    # Update current cache_key to be used when computing output
                    self._output_cache__current_cache_key = cache_key
                # Return
                return (cache_key, cache_file)
                
        # return value (a class) for the decorator
        return ExactParametrizedFunctionsDecoratedProblem_Class
        
    # return the decorator itself
    return ExactParametrizedFunctionsDecoratedProblem_Decorator
