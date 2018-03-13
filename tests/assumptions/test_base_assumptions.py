"""Testing
"""
import os
from energy_demand.basic import lookup_tables
from energy_demand.assumptions import non_param_assumptions
from energy_demand.read_write import data_loader

def test_load_non_param_assump():

    path_main = os.path.abspath("C://Users//cenv0553//nismod//models//energy_demand")
    path_main = os.path.join("")

    # Load data
    data = {}
    paths = data_loader.load_paths(path_main)
    lu = lookup_tables.basic_lookups()
    enduses, sectors, _ = data_loader.load_fuels(paths, lu)

    non_param_assumptions.load_non_param_assump(
        2015,
        paths,
        enduses,
        sectors,
        lu['fueltypes'],
        lu['fueltypes_nr'])

    # Test if yaml file is created
    #assert 

def test_load_param_assump():
    """
    """
    path_main = os.path.abspath("C://Users//cenv0553//nismod//models//energy_demand")
    path_main = os.path.join("")

    # Load data
    data = {}
    data['paths'] = data_loader.load_paths(path_main)
    data['lookups'] = lookup_tables.basic_lookups()
    data['enduses'], data['sectors'], data['fuels'] = data_loader.load_fuels(data['paths'], data['lookups'])

    sim_param_expected = {}
    sim_param_expected['base_yr'] = 2015

    #assumptions_expected = param_assumptions.load_param_assump(data['paths'], data['enduses'])

    # Dummy test
    assert sim_param_expected['base_yr'] == 2015
    return
