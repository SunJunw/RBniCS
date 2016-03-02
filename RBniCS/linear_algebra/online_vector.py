# Copyright (C) 2015-2016 by the RBniCS authors
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
## @file online_vector.py
#  @brief Type of online vector
#
#  @author Francesco Ballarin <francesco.ballarin@sissa.it>
#  @author Gianluigi Rozza    <gianluigi.rozza@sissa.it>
#  @author Alberto   Sartori  <alberto.sartori@sissa.it>

###########################     ONLINE STAGE     ########################### 
## @defgroup OnlineStage Methods related to the online stage
#  @{

# Declare reduced vector type
from numpy import matrix as OnlineVector_Base
class OnlineVector_Type(OnlineVector_Base): # make sure that online matrices and vectors correspond to two different types
    pass

# We prefer not to subclass numpy ndarray because it is not so trivial,
# see http://docs.scipy.org/doc/numpy-1.10.1/user/basics.subclassing.html
from numpy import zeros as OnlineVectorContent_Base
def OnlineVector(N=None):
    if N is not None:
        return OnlineVector_Type(OnlineVectorContent_Base((N))).transpose() # as column vector
    else:
        return None

#  @}
########################### end - ONLINE STAGE - end ########################### 

