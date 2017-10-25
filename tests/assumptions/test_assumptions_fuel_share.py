"""
"""
from energy_demand.assumptions import assumptions_fuel_shares
from energy_demand.assumptions import base_assumptions
from energy_demand.read_write import data_loader
import os

def test_assign_by_fuel_tech_p():
    """DUMMY OS FAR
    """
    path_main_data = r"C://Users//cenv0553//nismod//models//energy_demand//energy_demand"
    path_main = os.path.join(path_main_data, '../')
    local_data_path = "C://DATA_NISMODII//data_energy_demand"

    # Load data
    data = {}
    data['paths'] = data_loader.load_paths(path_main)
    data['local_paths'] = data_loader.load_local_paths(local_data_path)
    data['lookups'] = data_loader.load_basic_lookups()
    data['enduses'], data['sectors'], data['fuels'] = data_loader.load_fuels(data['paths'], data['lookups'])

    #Load assumptions
    _, data['assumptions'] = base_assumptions.load_assumptions(data['paths'], data['enduses'], data['lookups'], write_sim_param=True)

    result = assumptions_fuel_shares.assign_by_fuel_tech_p(data['assumptions'], data['enduses'], data['lookups'])

    # Dummy test
    assert result['test'] == 'test'
