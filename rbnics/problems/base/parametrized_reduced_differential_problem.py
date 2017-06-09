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

from __future__ import print_function
from abc import ABCMeta, abstractmethod
import types
from math import sqrt
from numpy import isclose
from rbnics.problems.base.parametrized_problem import ParametrizedProblem
from rbnics.backends import AffineExpansionStorage, assign, BasisFunctionsMatrix, copy, product, sum, transpose
from rbnics.backends.online import OnlineAffineExpansionStorage, OnlineFunction, OnlineLinearSolver
from rbnics.utils.io import OnlineSizeDict
from rbnics.utils.decorators import Extends, override, StoreMapFromProblemToReducedProblem, sync_setters
from rbnics.utils.mpi import log, print, PROGRESS

@Extends(ParametrizedProblem) # needs to be first in order to override for last the methods.
@StoreMapFromProblemToReducedProblem
class ParametrizedReducedDifferentialProblem(ParametrizedProblem):
    __metaclass__ = ABCMeta
    
    """
    Base class containing the interface of a projection based ROM for elliptic coercive problems.
    Initialization of dimension of reduced problem N, boundary conditions, terms and their order, number of terms in the affine expansion Q, reduced operators and inner products, reduced solution, reduced basis functions matrix.
    
    :param truth_problem: class of the truth problem to be solved. 
    """
    
    @override
    @sync_setters("truth_problem", "set_mu", "mu")
    @sync_setters("truth_problem", "set_mu_range", "mu_range")
    def __init__(self, truth_problem, **kwargs):
    
        # Call to parent
        ParametrizedProblem.__init__(self, type(truth_problem).__name__)
        
        # $$ ONLINE DATA STRUCTURES $$ #
        # Online reduced space dimension
        self.N = None # integer (for problems with one component) or dict of integers (for problem with several components)
        self.N_bc = None # integer (for problems with one component) or dict of integers (for problem with several components)
        self.dirichlet_bc = None # bool (for problems with one component) or dict of bools (for problem with several components)
        self.dirichlet_bc_are_homogeneous = None # bool (for problems with one component) or dict of bools (for problem with several components)
        # Form names and order
        self.terms = truth_problem.terms
        self.terms_order = truth_problem.terms_order
        self.components = truth_problem.components
        # Number of terms in the affine expansion
        self.Q = dict() # from string to integer
        # Reduced order operators
        self.operator = dict() # from string to OnlineAffineExpansionStorage
        self.inner_product = None # AffineExpansionStorage (for problems with one component) or dict of AffineExpansionStorage (for problem with several components), even though it will contain only one matrix
        self._combined_inner_product = None
        self.projection_inner_product = None # AffineExpansionStorage (for problems with one component) or dict of AffineExpansionStorage (for problem with several components), even though it will contain only one matrix
        self._combined_projection_inner_product = None
        # Solution
        self._solution = OnlineFunction()
        self._solution_cache = dict() # of Functions
        self._output = 0
        self._compute_error__previous_mu = None
        self._compute_error_output__previous_mu = None
        
        # $$ OFFLINE DATA STRUCTURES $$ #
        # High fidelity problem
        self.truth_problem = truth_problem
        # Basis functions matrix
        self.Z = BasisFunctionsMatrix(truth_problem.V)
        # I/O
        self.folder["basis"] = self.folder_prefix + "/" + "basis"
        self.folder["reduced_operators"] = self.folder_prefix + "/" + "reduced_operators"
    
    def init(self, current_stage="online"):
        """
        Calls _init_operators() and _init_basis_functions().
        """
        self._init_operators(current_stage)
        self._init_basis_functions(current_stage)
            
    def _init_operators(self, current_stage="online"):
        """
        Initialize data structures required for the online phase. Internal method.
        """
        assert current_stage in ("online", "offline")
        if current_stage == "online":
            n_components = len(self.components)
            # Inner products
            if n_components > 1:
                inner_product_string = "inner_product_{c}"
                self.inner_product = dict()
                for component in self.components:
                    self.inner_product[component] = self.assemble_operator(inner_product_string.format(c=component), "online")
            else:
                self.inner_product = self.assemble_operator("inner_product", "online")
            self._combined_inner_product = self._combine_all_inner_products()
            # Projection inner product
            if n_components > 1:
                projection_inner_product_string = "projection_inner_product_{c}"
                self.projection_inner_product = dict()
                for component in self.components:
                    self.projection_inner_product[component] = self.assemble_operator(projection_inner_product_string.format(c=component), "online")
            else:
                self.projection_inner_product = self.assemble_operator("projection_inner_product", "online")
            self._combined_projection_inner_product = self._combine_all_projection_inner_products()
            # Terms
            for term in self.terms:
                self.operator[term] = self.assemble_operator(term, "online")
                self.Q[term] = len(self.operator[term])
        elif current_stage == "offline":
            n_components = len(self.components)
            # Inner products
            if n_components > 1:
                self.inner_product = dict()
                for component in self.components:
                    self.inner_product[component] = OnlineAffineExpansionStorage(1)
            else:
                self.inner_product = OnlineAffineExpansionStorage(1)
            # Projection inner product
            if n_components > 1:
                self.projection_inner_product = dict()
                for component in self.components:
                    self.projection_inner_product[component] = OnlineAffineExpansionStorage(1)
            else:
                self.projection_inner_product = OnlineAffineExpansionStorage(1)
            # Terms
            for term in self.terms:
                self.Q[term] = self.truth_problem.Q[term]
                self.operator[term] = OnlineAffineExpansionStorage(self.Q[term])
        else:
            raise AssertionError("Invalid stage in _init_operators().")
            
    def _combine_all_inner_products(self):
        if len(self.components) > 1:
            all_inner_products = list()
            for component in self.components:
                assert len(self.inner_product[component]) == 1 # the affine expansion storage contains only the inner product matrix
                all_inner_products.append(self.inner_product[component][0])
            all_inner_products = tuple(all_inner_products)
        else:
            assert len(self.inner_product) == 1 # the affine expansion storage contains only the inner product matrix
            all_inner_products = (self.inner_product[0], )
        all_inner_products = OnlineAffineExpansionStorage(all_inner_products)
        all_inner_products_thetas = (1.,)*len(all_inner_products)
        return sum(product(all_inner_products_thetas, all_inner_products))
        
    def _combine_all_projection_inner_products(self):
        if len(self.components) > 1:
            all_projection_inner_products = list()
            for component in self.components:
                assert len(self.projection_inner_product[component]) == 1 # the affine expansion storage contains only the inner product matrix
                all_projection_inner_products.append(self.projection_inner_product[component][0])
            all_projection_inner_products = tuple(all_projection_inner_products)
        else:
            assert len(self.projection_inner_product) == 1 # the affine expansion storage contains only the inner product matrix
            all_projection_inner_products = (self.projection_inner_product[0], )
        all_projection_inner_products = OnlineAffineExpansionStorage(all_projection_inner_products)
        all_projection_inner_products_thetas = (1.,)*len(all_projection_inner_products)
        return sum(product(all_projection_inner_products_thetas, all_projection_inner_products))
        
    def _init_basis_functions(self, current_stage="online"):
        """
        Basis functions are initialized. Internal method.
        """
        assert current_stage in ("online", "offline")
        # Initialize basis functions mappings
        self.Z.init(self.components)
        # Get number of components
        n_components = len(self.components)
        # Get helper strings depending on the number of basis components
        if n_components > 1:
            dirichlet_bc_string = "dirichlet_bc_{c}"
            def has_non_homogeneous_dirichlet_bc(component):
                return self.dirichlet_bc[component] and not self.dirichlet_bc_are_homogeneous[component]
            def get_Z(component):
                return self.Z[component]
        else:
            dirichlet_bc_string = "dirichlet_bc"
            def has_non_homogeneous_dirichlet_bc(component):
                return self.dirichlet_bc and not self.dirichlet_bc_are_homogeneous
            def get_Z(component):
                return self.Z
        # Detect how many theta terms are related to boundary conditions
        assert (self.dirichlet_bc is None) == (self.dirichlet_bc_are_homogeneous is None)
        if self.dirichlet_bc is None: # init was not called already
            dirichlet_bc = dict()
            for component in self.components:
                try:
                    theta_bc = self.compute_theta(dirichlet_bc_string.format(c=component))
                except ValueError: # there were no Dirichlet BCs to be imposed by lifting
                    dirichlet_bc[component] = False
                else:
                    dirichlet_bc[component] = True
            if n_components == 1:
                self.dirichlet_bc = dirichlet_bc.values()[0]
            else:
                self.dirichlet_bc = dirichlet_bc
            self.dirichlet_bc_are_homogeneous = self.truth_problem.dirichlet_bc_are_homogeneous
        # Load basis functions
        if current_stage == "online":
            Z_loaded = self.Z.load(self.folder["basis"], "basis")
            # To properly initialize N and N_bc, detect how many theta terms
            # are related to boundary conditions
            if Z_loaded:
                N = dict()
                N_bc = dict()
                for component in self.components:
                    if has_non_homogeneous_dirichlet_bc(component):
                        theta_bc = self.compute_theta(dirichlet_bc_string.format(c=component))
                        N[component] = len(get_Z(component)) - len(theta_bc)
                        N_bc[component] = len(theta_bc)
                    else:
                        N[component] = len(get_Z(component))
                        N_bc[component] = 0
                assert len(N) == len(N_bc)
                assert len(N) > 0
                if len(N) == 1:
                    self.N = N.values()[0]
                    self.N_bc = N_bc.values()[0]
                else:
                    self.N = OnlineSizeDict(N)
                    self.N_bc = OnlineSizeDict(N_bc)
        elif current_stage == "offline":
            # Store the lifting functions in self.Z
            for component in self.components:
                self.assemble_operator(dirichlet_bc_string.format(c=component), "offline") # no return value from assemble_operator in this case
            # Save basis functions matrix, that contains up to now only lifting functions
            self.Z.save(self.folder["basis"], "basis")
            # Properly fill in self.N_bc
            total_N_bc = 0
            if n_components == 1:
                self.N = 0
                self.N_bc = len(self.Z)
                total_N_bc = self.N_bc
            else:
                N = dict()
                N_bc = dict()
                for component in self.components:
                    N[component] = 0
                    N_bc[component] = len(self.Z[component])
                self.N = OnlineSizeDict(N)
                self.N_bc = OnlineSizeDict(N_bc)
                total_N_bc = sum(N_bc.values())
            # Note that, however, self.N is not increased, so it will actually contain the number
            # of basis functions without the lifting ones.
        else:
            raise AssertionError("Invalid stage in _init_basis_functions().")
            
    @override
    def solve(self, N=None, **kwargs):
        """
        Perform an online solve. self.N will be used as matrix dimension if the default value is provided for N.
        
        :param N : Dimension of the reduced problem
        :type N : integer
        :return: reduced solution 
        """
        N, kwargs = self._online_size_from_kwargs(N, **kwargs)
        N += self.N_bc
        cache_key = self._cache_key_from_N_and_kwargs(N, **kwargs)
        self._solution = OnlineFunction(N)
        if cache_key in self._solution_cache:
            log(PROGRESS, "Loading reduced solution from cache")
            assign(self._solution, self._solution_cache[cache_key])
        else:
            log(PROGRESS, "Solving reduced problem")
            assert not hasattr(self, "_is_solving")
            self._is_solving = True
            self._solve(N, **kwargs)
            delattr(self, "_is_solving")
            self._solution_cache[cache_key] = copy(self._solution)
        return self._solution
        
    class ProblemSolver(object):
        __metaclass__ = ABCMeta
        
        def __init__(self, problem, N):
            self.problem = problem
            self.N = N
        
        def bc_eval(self):
            problem = self.problem
            if len(problem.components) > 1:
                all_dirichlet_bcs_thetas = dict()
                for component in problem.components:
                    if problem.dirichlet_bc[component] and not problem.dirichlet_bc_are_homogeneous[component]:
                        all_dirichlet_bcs_thetas[component] = problem.compute_theta("dirichlet_bc_" + component)
                if len(all_dirichlet_bcs_thetas) == 0:
                    all_dirichlet_bcs_thetas = None
            else:
                if problem.dirichlet_bc and not problem.dirichlet_bc_are_homogeneous:
                    all_dirichlet_bcs_thetas = problem.compute_theta("dirichlet_bc")
                else:
                    all_dirichlet_bcs_thetas = None
            return all_dirichlet_bcs_thetas
            
        @abstractmethod
        def solve(self):
            pass
        
    # Perform an online solve (internal)
    @override
    def _solve(self, N, **kwargs):
        problem_solver = self.ProblemSolver(self, N)
        problem_solver.solve()
        
    def project(self, snapshot, N=None, **kwargs):
        N, kwargs = self._online_size_from_kwargs(N, **kwargs)
        N += self.N_bc
        
        # Get truth and reduced inner product matrices for projection
        X = self.truth_problem._combined_projection_inner_product
        X_N = self._combined_projection_inner_product[:N, :N]
                
        # Get basis
        Z = self.Z[:N]
        
        # Define storage for projected solution
        projected_snapshot_N = OnlineFunction(N)
        
        # Project on reduced basis
        solver = OnlineLinearSolver(X_N, projected_snapshot_N, transpose(Z)*X*snapshot)
        solver.solve()
        return projected_snapshot_N
    
    def compute_output(self):
        """
        Calls _compute_output().
        
        :return: reduced output
        """
        N = self._solution.N
        self._compute_output(N)
        return self._output
        
    def _compute_output(self, N):
        """
        Perform an online evaluation of the output.
        """
        self._output = NotImplemented
        
    def _online_size_from_kwargs(self, N, **kwargs):
        """
        
        """
        if len(self.components) > 1:
            if N is None:
                all_components_in_kwargs = self.components[0] in kwargs
                for component in self.components:
                    if all_components_in_kwargs:
                        assert component in kwargs, "You need to specify the online size of all components in kwargs" 
                    else:
                        assert component not in kwargs, "You need to specify the online size of all components in kwargs"
                if all_components_in_kwargs:
                    N = OnlineSizeDict()
                    for component in self.components:
                        N[component] = kwargs[component]
                        del kwargs[component]
                else:
                    N = OnlineSizeDict(self.N) # copy the default dict
            else:
                assert isinstance(N, int)
                N_int = N
                N = OnlineSizeDict()
                for component in self.components:
                    N[component] = N_int
                    assert component not in kwargs, "You cannot provide both an int and kwargs for components"
        else:
            if N is None:
                assert len(self.components) == 1
                component_0 = self.components[0]
                if component_0 in kwargs:
                    N = kwargs[component_0]
                else:
                    N = self.N
            else:
                assert isinstance(N, int)
                
        return N, kwargs
        
    def _cache_key_from_N_and_kwargs(self, N, **kwargs):
        """
        Internal method.
        
        :param N: dimension of reduced problem.
        """
        for blacklist in ("components", "inner_product"):
            if blacklist in kwargs:
                del kwargs[blacklist]
        if isinstance(N, dict):
            return (self.mu, tuple(sorted(N.items())), tuple(sorted(kwargs.items())))
        else:
            assert isinstance(N, int)
            return (self.mu, N, tuple(sorted(kwargs.items())))
        
    def build_reduced_operators(self):
        """
        It asssembles the reduced order affine expansion.
        """
        n_components = len(self.components)
        # Inner products
        if n_components > 1:
            inner_product_string = "inner_product_{c}"
            for component in self.components:
                self.inner_product[component] = self.assemble_operator(inner_product_string.format(c=component), "offline")
        else:
            self.inner_product = self.assemble_operator("inner_product", "offline")
        self._combined_inner_product = self._combine_all_inner_products()
        # Projection inner product
        if n_components > 1:
            projection_inner_product_string = "projection_inner_product_{c}"
            for component in self.components:
                self.projection_inner_product[component] = self.assemble_operator(projection_inner_product_string.format(c=component), "offline")
        else:
            self.projection_inner_product = self.assemble_operator("projection_inner_product", "offline")
        self._combined_projection_inner_product = self._combine_all_projection_inner_products()
        # Terms
        for term in self.terms:
            self.operator[term] = self.assemble_operator(term, "offline")
        
    def compute_error(self, N=None, **kwargs):
        """
        Returns the function _compute_error() evaluated for the desired parameter.
        
        :param N: dimension of reduced problem
        :return: error between online and offline solutions.
        """
        if self._compute_error__previous_mu != self.mu:
            self.truth_problem.solve(**kwargs)
            self.truth_problem.compute_output()
            # Do not carry out truth solves anymore for the same parameter
            self._compute_error__previous_mu = self.mu
        # Compute the error on the solution
        self.solve(N, **kwargs)
        return self._compute_error(**kwargs)
        
    def _compute_error(self, **kwargs):
        """
        It computes the error of the reduced order approximation with respect to the full order one for the current value of mu.
        """
        (components, inner_product) = self._preprocess_compute_error_and_relative_error_kwargs(**kwargs)
        # Storage
        error = dict()
        # Compute the error on the solution
        if len(components) > 0:
            N = self._solution.N
            reduced_solution = self.Z[:N]*self._solution
            truth_solution = self.truth_problem._solution
            error_function = truth_solution - reduced_solution
            for component in components:
                error_norm_squared_component = transpose(error_function)*inner_product[component]*error_function
                assert error_norm_squared_component >= 0. or isclose(error_norm_squared_component, 0.)
                error[component] = sqrt(error_norm_squared_component)
        # Simplify trivial case
        if len(components) == 1:
            error = error[components[0]]
        #
        return error
        
    def compute_relative_error(self, N=None, **kwargs):
        """
        It returns the function _compute_relative_error() evaluated for the desired parameter.
        
        :param N: dimension of reduced problem
        :return: relative error.
        """
        absolute_error = self.compute_error(N, **kwargs)
        return self._compute_relative_error(absolute_error, **kwargs)
        
    def _compute_relative_error(self, absolute_error, **kwargs):
        """
        It computes the relative error of the reduced order approximation with respect to the full order one for the current value of mu.
        """
        (components, inner_product) = self._preprocess_compute_error_and_relative_error_kwargs(**kwargs)
        # Handle trivial case from compute_error
        if len(components) == 1:
            absolute_error_ = dict()
            absolute_error_[components[0]] = absolute_error
            absolute_error = absolute_error_
        # Storage
        relative_error = dict()
        # Compute the relative error on the solution
        if len(components) > 0:
            truth_solution = self.truth_problem._solution
            for component in components:
                exact_norm_squared_component = transpose(truth_solution)*inner_product[component]*truth_solution
                assert exact_norm_squared_component >= 0. or isclose(exact_norm_squared_component, 0.)
                relative_error[component] = absolute_error[component]/sqrt(exact_norm_squared_component)
        # Simplify trivial case
        if len(components) == 1:
            relative_error = relative_error[components[0]]
        #
        return relative_error
                
    def _preprocess_compute_error_and_relative_error_kwargs(self, **kwargs):
        """
        This function returns the components and the inner products, picking them up from the kwargs or choosing default ones in case they are not defined yet. Internal method.
        
        :return: components and inner_product.
        """
        # Set default components, if needed
        if "components" not in kwargs:
            kwargs["components"] = self.components
        # Set inner product for components, if needed
        if "inner_product" not in kwargs:
            inner_product = dict()
            if len(kwargs["components"]) > 1:
                for component in kwargs["components"]:
                    assert len(self.truth_problem.inner_product[component]) == 1
                    inner_product[component] = self.truth_problem.inner_product[component][0]
            else:
                assert len(self.truth_problem.inner_product) == 1
                inner_product[kwargs["components"][0]] = self.truth_problem.inner_product[0]
            kwargs["inner_product"] = inner_product
        else:
            assert isinstance(kwargs["inner_product"], dict)
            assert set(kwargs["inner_product"].keys()) == set(kwargs["components"])
        #
        return (kwargs["components"], kwargs["inner_product"])
                
    # Compute the error of the reduced order output with respect to the full order one
    # for the current value of mu
    def compute_error_output(self, N=None, **kwargs):
        """
        It returns the function _compute_error_output() evaluated for the desired parameter.
        
        :param N: dimension of reduced problem.
        :return: output error.
        """
        if self._compute_error__previous_mu != self.mu:
            self.truth_problem.solve(**kwargs)
            # Do not carry out truth solves anymore for the same parameter
            self._compute_error__previous_mu = self.mu
        if self._compute_error_output__previous_mu != self.mu:
            self.truth_problem.compute_output()
            # Do not carry out truth solves anymore for the same parameter
            self._compute_error_output__previous_mu = self.mu
        # Compute the error on the output
        self.solve(N, **kwargs)
        self.compute_output()
        return self._compute_error_output(**kwargs)
                
    # Internal method for output error computation
    def _compute_error_output(self, **kwargs):
        """
        It computes the output error of the reduced order approximation with respect to the full order one for the current value of mu.
        """
        # Skip if no output defined
        if self._output is NotImplemented:
            assert self.truth_problem._output is NotImplemented
            return NotImplemented
        else: # Compute the error on the output
            reduced_output = self._output
            truth_output = self.truth_problem._output
            error_output = abs(truth_output - reduced_output)
            return error_output
        
    # Compute the relative error of the reduced order approximation with respect to the full order one
    # for the current value of mu
    def compute_relative_error_output(self, N=None, **kwargs):
        """
        It returns the function _compute_relative_error_output() evaluated for the desired parameter.
        
        :param N: dimension of reduced problem
        :return: relative output error.
        """
        absolute_error_output = self.compute_error_output(N, **kwargs)
        return self._compute_relative_error_output(absolute_error_output, **kwargs)
        
    # Internal method for output error computation
    def _compute_relative_error_output(self, absolute_error_output, **kwargs):
        """
        It computes the realtive output error of the reduced order approximation with respect to the full order one for the current value of mu.
        """
        # Skip if no output defined
        if self._output is NotImplemented:
            assert self.truth_problem._output is NotImplemented
            assert absolute_error_output is NotImplemented
            return NotImplemented
        else: # Compute the relative error on the output
            truth_output = self.truth_problem._output
            if truth_output == 0.:
                return float('NaN')
            else:
                return absolute_error_output/truth_output
        
    @override
    def export_solution(self, folder, filename, solution=None, component=None, suffix=None):
        """
        It exports reduced solution to file.
        
        :param folder: the folder into which we want to save the solution.
        :param filename: the name of the file to be saved.
        :param solution: the solution to be saved.
        :param component: the component of the of the solution to be saved.
        :param suffix: suffix to add to the name.
        """
        if solution is None:
            solution = self._solution
        N = solution.N
        self.truth_problem.export_solution(folder, filename, self.Z[:N]*solution, component, suffix)

    def compute_theta(self, term):
        """
        Return theta multiplicative terms of the affine expansion of the problem.
        
        :param term: the forms of the class of the problem.
        :return: computed thetas.
        """
        return self.truth_problem.compute_theta(term)
        
    ## Assemble the reduced order affine expansion
    def assemble_operator(self, term, current_stage="online"):
        """
        Terms and respective thetas are assembled.
        
        :param term: the forms of the class of the problem.
        :param current_stage: online or offline stage.
        """
        assert current_stage in ("online", "offline")
        if current_stage == "online": # load from file
            # Note that it would not be needed to return the loaded operator in 
            # init(), since it has been already modified in-place. We do this, however,
            # because we want this interface to be compatible with the one in 
            # EllipticCoerciveProblem, i.e. we would like to be able to use a reduced 
            # problem also as a truth problem for a nested reduction
            if term in self.terms:
                if term not in self.operator:
                    self.operator[term] = OnlineAffineExpansionStorage(0) # it will be resized by load
                assert "reduced_operators" in self.folder
                self.operator[term].load(self.folder["reduced_operators"], "operator_" + term)
                return self.operator[term]
            elif term.startswith("inner_product"):
                component = term.replace("inner_product", "").replace("_", "")
                if component != "":
                    assert component in self.components
                    if component not in self.inner_product:
                        self.inner_product[component] = OnlineAffineExpansionStorage(0) # it will be resized by load
                    assert "reduced_operators" in self.folder
                    self.inner_product[component].load(self.folder["reduced_operators"], term)
                    return self.inner_product[component]
                else:
                    assert len(self.components) == 1
                    if self.inner_product is None:
                        self.inner_product = OnlineAffineExpansionStorage(0) # it will be resized by load
                    assert "reduced_operators" in self.folder
                    self.inner_product.load(self.folder["reduced_operators"], term)
                    return self.inner_product
            elif term.startswith("projection_inner_product"):
                component = term.replace("projection_inner_product", "").replace("_", "")
                if component != "":
                    assert component in self.components
                    if component not in self.projection_inner_product:
                        self.projection_inner_product[component] = OnlineAffineExpansionStorage(0) # it will be resized by load
                    assert "reduced_operators" in self.folder
                    self.projection_inner_product[component].load(self.folder["reduced_operators"], term)
                    return self.projection_inner_product[component]
                else:
                    assert len(self.components) == 1
                    if self.projection_inner_product is None:
                        self.projection_inner_product = OnlineAffineExpansionStorage(0) # it will be resized by load
                    assert "reduced_operators" in self.folder
                    self.projection_inner_product.load(self.folder["reduced_operators"], term)
                    return self.projection_inner_product
            elif term.startswith("dirichlet_bc"):
                raise ValueError("There should be no need to assemble Dirichlet BCs when querying online reduced problems.")
            else:
                raise ValueError("Invalid term for assemble_operator().")
        elif current_stage == "offline":
            # As in the previous case, there is no need to return anything because 
            # we are still training the reduced order model, so the previous remark 
            # (on the usage of a reduced problem as a truth one) cannot hold here.
            # However, in order to have a consistent interface we return the assembled
            # operator
            if term in self.terms:
                for q in range(self.Q[term]):
                    assert self.terms_order[term] in (0, 1, 2)
                    if self.terms_order[term] == 2:
                        self.operator[term][q] = transpose(self.Z)*self.truth_problem.operator[term][q]*self.Z
                    elif self.terms_order[term] == 1:
                        self.operator[term][q] = transpose(self.Z)*self.truth_problem.operator[term][q]
                    elif self.terms_order[term] == 0:
                        self.operator[term][q] = self.truth_problem.operator[term][q]
                    else:
                        raise AssertionError("Invalid value for order of term " + term)
                if "reduced_operators" in self.folder:
                    self.operator[term].save(self.folder["reduced_operators"], "operator_" + term)
                return self.operator[term]
            elif term.startswith("inner_product"):
                component = term.replace("inner_product", "").replace("_", "")
                if component != "":
                    assert component in self.components
                    assert len(self.inner_product[component]) == 1 # the affine expansion storage contains only the inner product matrix
                    assert len(self.truth_problem.inner_product[component]) == 1 # the affine expansion storage contains only the inner product matrix
                    self.inner_product[component][0] = transpose(self.Z)*self.truth_problem.inner_product[component][0]*self.Z
                    if "reduced_operators" in self.folder:
                        self.inner_product[component].save(self.folder["reduced_operators"], term)
                    return self.inner_product[component]
                else:
                    assert len(self.components) == 1 # single component case
                    assert len(self.inner_product) == 1 # the affine expansion storage contains only the inner product matrix
                    assert len(self.truth_problem.inner_product) == 1 # the affine expansion storage contains only the inner product matrix
                    self.inner_product[0] = transpose(self.Z)*self.truth_problem.inner_product[0]*self.Z
                    if "reduced_operators" in self.folder:
                        self.inner_product.save(self.folder["reduced_operators"], term)
                    return self.inner_product
            elif term == "projection_inner_product":
                component = term.replace("projection_inner_product", "").replace("_", "")
                if component != "":
                    assert component in self.components
                    assert len(self.projection_inner_product[component]) == 1 # the affine expansion storage contains only the inner product matrix
                    assert len(self.truth_problem.projection_inner_product[component]) == 1 # the affine expansion storage contains only the inner product matrix
                    self.projection_inner_product[component][0] = transpose(self.Z)*self.truth_problem.projection_inner_product[component][0]*self.Z
                    if "reduced_operators" in self.folder:
                        self.projection_inner_product[component].save(self.folder["reduced_operators"], term)
                    return self.projection_inner_product[component]
                else:
                    assert len(self.components) == 1 # single component case
                    assert len(self.projection_inner_product) == 1 # the affine expansion storage contains only the inner product matrix
                    assert len(self.truth_problem.projection_inner_product) == 1 # the affine expansion storage contains only the inner product matrix
                    self.projection_inner_product[0] = transpose(self.Z)*self.truth_problem.projection_inner_product[0]*self.Z
                    if "reduced_operators" in self.folder:
                        self.projection_inner_product.save(self.folder["reduced_operators"], term)
                    return self.projection_inner_product
            elif term.startswith("dirichlet_bc"):
                component = term.replace("dirichlet_bc", "").replace("_", "")
                if component != "":
                    assert component in self.components
                    has_non_homogeneous_dirichlet_bc = self.dirichlet_bc[component] and not self.dirichlet_bc_are_homogeneous[component]
                else:
                    assert len(self.components) == 1
                    component = None
                    has_non_homogeneous_dirichlet_bc = self.dirichlet_bc and not self.dirichlet_bc_are_homogeneous
                if has_non_homogeneous_dirichlet_bc:
                    # Compute lifting functions for the value of mu possibly provided by the user
                    Q_dirichlet_bcs = len(self.compute_theta(term))
                    # Temporarily override compute_theta method to return only one nonzero 
                    # theta term related to boundary conditions
                    standard_compute_theta = self.truth_problem.compute_theta
                    for i in range(Q_dirichlet_bcs):
                        def modified_compute_theta(self, term_):
                            if term_ == term:
                                theta_bc = standard_compute_theta(term_)
                                modified_theta_bc = list()
                                for j in range(Q_dirichlet_bcs):
                                    if j != i:
                                        modified_theta_bc.append(0.)
                                    else:
                                        modified_theta_bc.append(theta_bc[i])
                                return tuple(modified_theta_bc)
                            else:
                                return standard_compute_theta(term_)
                        self.truth_problem.compute_theta = types.MethodType(modified_compute_theta, self.truth_problem)
                        # ... and store the solution of the truth problem corresponding to that boundary condition
                        # as lifting function
                        solve_message = "Computing and storing lifting function n. " + str(i)
                        if component is not None:
                            solve_message += " for component " + component
                        solve_message += " (obtained for mu = " + str(self.mu) + ") in the basis matrix"
                        print(solve_message)
                        lifting = self._lifting_truth_solve(term, i)
                        self.Z.enrich(lifting, component=component)
                    # Restore the standard compute_theta method
                    self.truth_problem.compute_theta = standard_compute_theta
            else:
                raise ValueError("Invalid term for assemble_operator().")
        else:
            raise AssertionError("Invalid stage in assemble_operator().")
    
    def _lifting_truth_solve(self, term, i):
        # Since lifting solves for different values of i are associated to the same parameter 
        # but with a patched call to compute_theta(), which returns the i-th component, we set
        # a custom cache_key so that they are properly differentiated when reading from cache.
        lifting = self.truth_problem.solve(cache_key="lifting_" + str(i))
        lifting /= self.compute_theta(term)[i]
        return lifting
    
    def get_stability_factor(self):
        """
        Return a lower bound for the coercivity constant.
        """
        return self.truth_problem.get_stability_factor()
    
