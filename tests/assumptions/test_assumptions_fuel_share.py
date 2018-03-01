"""
"""
from energy_demand.assumptions import assumptions_fuel_shares
from energy_demand.assumptions import non_param_assumptions
from energy_demand.assumptions import param_assumptions
from energy_demand.read_write import data_loader, read_data
import os

def test_assign_by_fuel_tech_p():
    """
    """
    path_main = os.path.join("")

    # Load data
    data = {}
    data['paths'] = data_loader.load_paths(path_main)
    data['lookups'] = data_loader.load_basic_lookups()
    data['enduses'], data['sectors'], data['fuels'] = data_loader.load_fuels(data['paths'], data['lookups'])

    #Load assumptions
    data['sim_param'] = {}
    data['sim_param']['base_yr'] = 2015
    data['sim_param']['simulated_yrs'] = [2015, 2020, 2025]
    data['sim_param']['curr_yr'] = 2015

    data['assumptions'] = non_param_assumptions.load_non_param_assump(
        data['sim_param']['base_yr'],
        data['paths'],
        data['enduses'],
        data['sectors'],
        data['lookups']['fueltypes'],
        data['lookups']['fueltypes_nr'])

    param_assumptions.load_param_assump(data['paths'], data['assumptions'])

    result = assumptions_fuel_shares.assign_by_fuel_tech_p(
        data['assumptions'],
        data['enduses'],
        data['sectors'],
        data['lookups']['fueltypes'],
        data['lookups']['fueltypes_nr'])
