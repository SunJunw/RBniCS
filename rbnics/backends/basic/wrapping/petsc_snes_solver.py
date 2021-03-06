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

from petsc4py import PETSc

def BasicPETScSNESSolver(backend, wrapping):
    class _BasicPETScSNESSolver(object):
        def __init__(self, problem, solution):
            self.problem = problem
            self.solution = solution
            # Create SNES object
            self.snes = PETSc.SNES().create(wrapping.get_mpi_comm(solution))
            # ... and associate residual and jacobian
            self.snes.setFunction(self.problem.residual_vector_eval, wrapping.to_petsc4py(self.problem.residual_vector))
            self.snes.setJacobian(self.problem.jacobian_matrix_eval, wrapping.to_petsc4py(self.problem.jacobian_matrix))
            # Set sensible default values to parameters
            self._report = None
            self.set_parameters({
                "report": True
            })
             
        def set_parameters(self, parameters):
            snes_tolerances = [1.e-10, 1.e-9, 1.e-16, 50]
            for (key, value) in parameters.items():
                if key == "absolute_tolerance":
                    snes_tolerances[0] = value
                elif key == "linear_solver":
                    ksp = self.snes.getKSP()
                    ksp.setType("preonly")
                    ksp.getPC().setType("lu")
                    if value == "default":
                        value = wrapping.get_default_linear_solver()
                    if hasattr(ksp.getPC(), "setFactorSolverType"): # PETSc >= 3.9
                        ksp.getPC().setFactorSolverType(value)
                    else:
                        ksp.getPC().setFactorSolverPackage(value)
                elif key == "line_search":
                    raise ValueError("Line search is not wrapped yet by petsc4py")
                elif key == "maximum_iterations":
                    snes_tolerances[3] = value
                elif key == "method":
                    self.snes.setType(value)
                elif key == "relative_tolerance":
                    snes_tolerances[1] = value
                elif key == "report":
                    self._report = value
                    self.snes.cancelMonitor()
                    def monitor(snes, it, fgnorm):
                        print("  " + str(it) + " SNES Function norm " + "{:e}".format(fgnorm))
                    self.snes.setMonitor(monitor)
                elif key == "solution_tolerance":
                    snes_tolerances[2] = value
                else:
                    raise ValueError("Invalid paramater passed to PETSc SNES object.")
            self.snes.setTolerances(*snes_tolerances)
            # Finally, read in additional options from the command line
            self.snes.setFromOptions()
            
        def solve(self):
            self.snes.solve(None, wrapping.to_petsc4py(self.solution))
            if self._report:
                reason = self.snes.getConvergedReason()
                its = self.snes.getIterationNumber()
                if reason > 0:
                    print("PETSc SNES solver converged in " + str(its) + " iterations with convergence reason " + str(reason) + ".")
                else:
                    print("PETSc SNES solver diverged in " + str(its) + " iterations with divergence reason " + str(reason) + ".")
            return self.solution
    
    return _BasicPETScSNESSolver
