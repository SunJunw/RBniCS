# Copyright (C) 2015- 2017 by the RBniCS authors
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

import os
from sympy import Float, MatrixSymbol, preorder_traversal, simplify, sympify
from rbnics.shape_parametrization.problems.affine_shape_parametrization_decorated_problem import affine_shape_parametrization_from_vertices_mapping
from rbnics.utils.io import PickleIO

data_dir = os.path.join(os.path.dirname(os.path.realpath(__file__)), "data", "test_affine_shape_parametrization_from_vertices_mapping")

# Global enums for clearer notation for asserts
X = 0
Y = 1

# Check equality between symbolic expressions
def symbolic_equal(expression1, expression2, x, mu):
    locals = {"x": x, "mu": mu}
    difference = sympify(expression1, locals=locals) - sympify(expression2, locals=locals)
    difference = simplify(difference)
    for node in preorder_traversal(difference):
        if isinstance(node, Float):
            difference = difference.subs(node, round(node, 10))
    return difference == 0

# Test affine shape parametrization for tutorial 3
def test_affine_shape_parametrization_from_vertices_mapping_hole():
    filename = "vertices_mapping_hole"
    assert PickleIO.exists_file(data_dir, filename)
    vertices_mappings = PickleIO.load_file(data_dir, filename)
    shape_parametrization_expression = [affine_shape_parametrization_from_vertices_mapping(2, vertices_mapping) for vertices_mapping in vertices_mappings]
    # Auxiliary symbolic quantities
    x = MatrixSymbol("x", 2, 1)
    mu = MatrixSymbol("mu", 2, 1)
    # Start checks
    assert len(shape_parametrization_expression) is 8
    # Check subdomain 1
    assert len(shape_parametrization_expression[0]) is 2
    assert symbolic_equal(shape_parametrization_expression[0][X], "2 - 2*mu[0] + mu[0]*x[0] + (2 - 2*mu[0])*x[1]", x, mu)
    assert symbolic_equal(shape_parametrization_expression[0][Y], "2 - 2*mu[1] + (2 - mu[1])*x[1]", x, mu)
    # Check subdomain 2
    assert len(shape_parametrization_expression[1]) is 2
    assert symbolic_equal(shape_parametrization_expression[1][X], "2*mu[0]- 2 +x[0] + (mu[0] - 1)*x[1]", x, mu)
    assert symbolic_equal(shape_parametrization_expression[1][Y], "2 - 2*mu[1] + (2 - mu[1])*x[1]", x, mu)
    # Check subdomain 3
    assert len(shape_parametrization_expression[2]) is 2
    assert symbolic_equal(shape_parametrization_expression[2][X], "2 - 2*mu[0] + (2 - mu[0])*x[0]", x, mu)
    assert symbolic_equal(shape_parametrization_expression[2][Y], "2 - 2*mu[1] + (2- 2*mu[1])*x[0] + mu[1]*x[1]", x, mu)
    # Check subdomain 4
    assert len(shape_parametrization_expression[3]) is 2
    assert symbolic_equal(shape_parametrization_expression[3][X], "2 - 2*mu[0] + (2 - mu[0])*x[0]", x, mu)
    assert symbolic_equal(shape_parametrization_expression[3][Y], "2*mu[1] - 2 + (mu[1] - 1)*x[0] + x[1]", x, mu)
    # Check subdomain 5
    assert len(shape_parametrization_expression[4]) is 2
    assert symbolic_equal(shape_parametrization_expression[4][X], "2*mu[0] - 2 + (2 - mu[0])*x[0]", x, mu)
    assert symbolic_equal(shape_parametrization_expression[4][Y], "2 - 2*mu[1] + (2*mu[1]- 2)*x[0] + mu[1]*x[1]", x, mu)
    # Check subdomain 6
    assert len(shape_parametrization_expression[5]) is 2
    assert symbolic_equal(shape_parametrization_expression[5][X], "2*mu[0] - 2 + (2 - mu[0])*x[0]", x, mu)
    assert symbolic_equal(shape_parametrization_expression[5][Y], "2*mu[1] - 2 + (1 - mu[1])*x[0] + x[1]", x, mu)
    # Check subdomain 7
    assert len(shape_parametrization_expression[6]) is 2
    assert symbolic_equal(shape_parametrization_expression[6][X], "2 - 2*mu[0] + mu[0]*x[0] + (2*mu[0] - 2)*x[1]", x, mu)
    assert symbolic_equal(shape_parametrization_expression[6][Y], "2*mu[1] - 2 + (2 - mu[1])*x[1]", x, mu)
    # Check subdomain 8
    assert len(shape_parametrization_expression[7]) is 2
    assert symbolic_equal(shape_parametrization_expression[7][X], "2*mu[0] - 2 + x[0] + (1 - mu[0])*x[1]", x, mu)
    assert symbolic_equal(shape_parametrization_expression[7][Y], "2*mu[1] - 2 + (2 - mu[1])*x[1]", x, mu)
    
# Test affine shape parametrization for tutorial 4
def test_affine_shape_parametrization_from_vertices_mapping_graetz():
    vertices_mappings = [
        {
            ("0", "0"): ("0", "0"),
            ("0", "1"): ("0", "1"),
            ("1", "1"): ("1", "1")
        }, # subdomain 1 top
        {
            ("0", "0"): ("0", "0"),
            ("1", "0"): ("1", "0"),
            ("1", "1"): ("1", "1")
        }, # subdomain 1 bottom
        {
            ("1", "0"): ("1", "0"),
            ("1", "1"): ("1", "1"),
            ("2", "1"): ("1 + mu[0]", "1")
        }, # subdomain 2 top
        {
            ("1", "0"): ("1", "0"),
            ("2", "0"): ("1 + mu[0]", "0"),
            ("2", "1"): ("1 + mu[0]", "1")
        } # subdomain 2 bottom
    ]
    shape_parametrization_expression = [affine_shape_parametrization_from_vertices_mapping(2, vertices_mapping) for vertices_mapping in vertices_mappings]
    # Auxiliary symbolic quantities
    x = MatrixSymbol("x", 2, 1)
    mu = MatrixSymbol("mu", 1, 1)
    # Start checks
    assert len(shape_parametrization_expression) is 4
    # Check subdomain 1 top
    assert len(shape_parametrization_expression[0]) is 2
    assert symbolic_equal(shape_parametrization_expression[0][X], "x[0]", x, mu)
    assert symbolic_equal(shape_parametrization_expression[0][Y], "x[1]", x, mu)
    # Check subdomain 1 bottom
    assert len(shape_parametrization_expression[1]) is 2
    assert symbolic_equal(shape_parametrization_expression[1][X], "x[0]", x, mu)
    assert symbolic_equal(shape_parametrization_expression[1][Y], "x[1]", x, mu)
    # Check subdomain 2 top
    assert len(shape_parametrization_expression[2]) is 2
    assert symbolic_equal(shape_parametrization_expression[2][X], "mu[0]*(x[0] - 1) + 1", x, mu)
    assert symbolic_equal(shape_parametrization_expression[2][Y], "x[1]", x, mu)
    # Check subdomain 2 bottom
    assert len(shape_parametrization_expression[3]) is 2
    assert symbolic_equal(shape_parametrization_expression[3][X], "mu[0]*(x[0] - 1) + 1", x, mu)
    assert symbolic_equal(shape_parametrization_expression[3][Y], "x[1]", x, mu)
    
def test_affine_shape_parametrization_from_vertices_mapping_stokes_optimal_dirichlet_boundary_control():
    vertices_mappings = [
        "identity", # subdomain 1
        {
            ("0.9", "0.0"): ("0.9", "0.0"),
            ("1.0", "0.0"): ("0.9+mu[0]", "0.0"),
            ("0.9", "0.4"): ("0.9", "0.4")
        }, # subdomain 2
        {
            ("1.0", "0.0"): ("0.9+mu[0]", "0.0"),
            ("1.0", "0.4"): ("0.9+mu[0]", "0.4"),
            ("0.9", "0.4"): ("0.9", "0.4")
        }, # subdomain 3
        {
            ("0.9", "0.6"): ("0.9", "0.6"),
            ("1.0", "0.6"): ("0.9+mu[0]", "0.6"),
            ("0.9", "1.0"): ("0.9", "1.0")
        }, # subdomain 4
        {
            ("1.0", "0.6"): ("0.9+mu[0]", "0.6"),
            ("1.0", "1.0"): ("0.9+mu[0]", "1.0"),
            ("0.9", "1.0"): ("0.9", "1.0")
        }, # subdomain 5
        {
            ("1.0", "0.0"): ("0.9+mu[0]", "0.0"),
            ("1.8", "0.2"): ("1.8", "0.2"),
            ("1.0", "0.4"): ("0.9+mu[0]", "0.4")
        }, # subdomain 6
        {
            ("1.0", "0.0"): ("0.9+mu[0]", "0.0"),
            ("2.0", "0.0"): ("2.0", "0.0"),
            ("1.8", "0.2"): ("1.8", "0.2")
        }, # subdomain 7
        {
            ("1.0", "0.6"): ("0.9+mu[0]", "0.6"),
            ("1.8", "0.8"): ("1.8", "0.8"),
            ("1.0", "1.0"): ("0.9+mu[0]", "1.0")
        }, # subdomain 8
        {
            ("1.0", "1.0"): ("0.9+mu[0]", "1.0"),
            ("1.8", "0.8"): ("1.8", "0.8"),
            ("2.0", "1.0"): ("2.0", "1.0")
        }, # subdomain 9
        {
            ("1.8", "0.8"): ("1.8", "0.8"),
            ("2.0", "0.0"): ("2.0", "0.0"),
            ("2.0", "1.0"): ("2.0", "1.0")
        }, # subdomain 10
        {
            ("1.8", "0.8"): ("1.8", "0.8"),
            ("1.8", "0.2"): ("1.8", "0.2"),
            ("2.0", "0.0"): ("2.0", "0.0")
        }, # subdomain 11
        {
            ("1.0", "0.4"): ("0.9+mu[0]", "0.4"),
            ("1.8", "0.2"): ("1.8", "0.2"),
            ("1.0", "0.6"): ("0.9+mu[0]", "0.6")
        }, # subdomain 12
        {
            ("1.0", "0.6"): ("0.9+mu[0]", "0.6"),
            ("1.8", "0.2"): ("1.8", "0.2"),
            ("1.8", "0.8"): ("1.8", "0.8")
        }  # subdomain 13
    ]
    shape_parametrization_expression = [affine_shape_parametrization_from_vertices_mapping(2, vertices_mapping) for vertices_mapping in vertices_mappings]
    # Auxiliary symbolic quantities
    x = MatrixSymbol("x", 2, 1)
    mu = MatrixSymbol("mu", 1, 1)
    # Start checks
    assert len(shape_parametrization_expression) is 13
    # Check subdomain 1
    assert len(shape_parametrization_expression[0]) is 2
    assert symbolic_equal(shape_parametrization_expression[0][X], "x[0]", x, mu)
    assert symbolic_equal(shape_parametrization_expression[0][Y], "x[1]", x, mu)
    # Check subdomain 2
    assert len(shape_parametrization_expression[1]) is 2
    assert symbolic_equal(shape_parametrization_expression[1][X], "0.9 - 9.0*mu[0] + 10.0*mu[0]*x[0] ", x, mu)
    assert symbolic_equal(shape_parametrization_expression[1][Y], "x[1]", x, mu)
    # Check subdomain 3
    assert len(shape_parametrization_expression[2]) is 2
    assert symbolic_equal(shape_parametrization_expression[2][X], "0.9 - 9.0*mu[0] + 10.0*mu[0]*x[0] ", x, mu)
    assert symbolic_equal(shape_parametrization_expression[2][Y], "x[1]", x, mu)
    # Check subdomain 4
    assert len(shape_parametrization_expression[3]) is 2
    assert symbolic_equal(shape_parametrization_expression[3][X], "0.9 - 9.0*mu[0] + 10.0*mu[0]*x[0] ", x, mu)
    assert symbolic_equal(shape_parametrization_expression[3][Y], "x[1]", x, mu)
    # Check subdomain 5
    assert len(shape_parametrization_expression[4]) is 2
    assert symbolic_equal(shape_parametrization_expression[4][X], "0.9 - 9.0*mu[0] + 10.0*mu[0]*x[0] ", x, mu)
    assert symbolic_equal(shape_parametrization_expression[4][Y], "x[1]", x, mu)
    # Check subdomain 6
    assert len(shape_parametrization_expression[5]) is 2
    assert symbolic_equal(shape_parametrization_expression[5][X], "2.25*mu[0] + x[0]*(-1.25*mu[0] + 1.125) - 0.225 ", x, mu)
    assert symbolic_equal(shape_parametrization_expression[5][Y], "x[1]", x, mu)
    # Check subdomain 7
    assert len(shape_parametrization_expression[6]) is 2
    assert symbolic_equal(shape_parametrization_expression[6][X], "2.0*mu[0] + x[0]*(-mu[0] + 1.1) + x[1]*(-mu[0] + 0.1) - 0.2 ", x, mu)
    assert symbolic_equal(shape_parametrization_expression[6][Y], "x[1]", x, mu)
    # Check subdomain 8
    assert len(shape_parametrization_expression[7]) is 2
    assert symbolic_equal(shape_parametrization_expression[7][X], "2.25*mu[0] + x[0]*(-1.25*mu[0] + 1.125) - 0.225 ", x, mu)
    assert symbolic_equal(shape_parametrization_expression[7][Y], "x[1]", x, mu)
    # Check subdomain 9
    assert len(shape_parametrization_expression[8]) is 2
    assert symbolic_equal(shape_parametrization_expression[8][X], "mu[0] + x[0]*(-mu[0] + 1.1) + x[1]*(mu[0] - 0.1) - 0.1", x, mu)
    assert symbolic_equal(shape_parametrization_expression[8][Y], "x[1]", x, mu)
    # Check subdomain 10
    assert len(shape_parametrization_expression[9]) is 2
    assert symbolic_equal(shape_parametrization_expression[9][X], "x[0]", x, mu)
    assert symbolic_equal(shape_parametrization_expression[9][Y], "x[1]", x, mu)
    # Check subdomain 11
    assert len(shape_parametrization_expression[10]) is 2
    assert symbolic_equal(shape_parametrization_expression[10][X], "x[0]", x, mu)
    assert symbolic_equal(shape_parametrization_expression[10][Y], "x[1]", x, mu)
    # Check subdomain 12
    assert len(shape_parametrization_expression[11]) is 2
    assert symbolic_equal(shape_parametrization_expression[11][X], "x[0]*(-1.25*mu[0] + 1.125) + 2.25*mu[0] - 0.225", x, mu)
    assert symbolic_equal(shape_parametrization_expression[11][Y], "x[1]", x, mu)
    # Check subdomain 13
    assert len(shape_parametrization_expression[12]) is 2
    assert symbolic_equal(shape_parametrization_expression[12][X], "2.25*mu[0] + x[0]*(-1.25*mu[0] + 1.125) - 0.225", x, mu)
    assert symbolic_equal(shape_parametrization_expression[12][Y], "x[1]", x, mu)