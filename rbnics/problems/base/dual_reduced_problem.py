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

from rbnics.utils.decorators import PreserveClassName

def DualReducedProblem(ParametrizedDifferentialReducedProblem_DerivedClass):
            
    @PreserveClassName
    class DualReducedProblem_Class(ParametrizedDifferentialReducedProblem_DerivedClass):
        # Default initialization of members.
        def __init__(self, dual_problem, **kwargs):
            # Call to parent
            ParametrizedDifferentialReducedProblem_DerivedClass.__init__(self, dual_problem, **kwargs)
            
            # Primal truth problem
            self.primal_truth_problem = dual_problem.primal_problem
            # Primal reduced problem, which will be attached by reduction method at the end of the offline stage
            self.primal_reduced_problem = None
            
            # Change the folder names in Parent
            new_folder_prefix = dual_problem.folder_prefix
            for (key, name) in self.folder.items():
                self.folder[key] = name.replace(self.folder_prefix, new_folder_prefix)
            self.folder_prefix = new_folder_prefix
            
    # return value (a class) for the decorator
    return DualReducedProblem_Class
