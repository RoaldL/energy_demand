"""Script functions which are executed after model installation and 
after each scenario definition
"""
from pkg_resources import Requirement
from pkg_resources import resource_filename
from energy_demand.read_write import data_loader
from energy_demand.assumptions import assumptions

def post_install_setup(args):
    """Run initialisation scripts

    Parameters
    ----------
    args : object
        Arguments defined in ``./cli/__init__.py``

    Note
    ----
    Only needs to be executed once after the energy_demand
    model has been installed
    """
    print("... start running initialisation scripts")

    #Subfolder where module is installed
    path_main = resource_filename(Requirement.parse("energy_demand"), "")
    local_data_path = args.data_energy_demand #Energy demand data folder

    # Read in temperature data from raw files
    from energy_demand.scripts import s_raw_weather_data
    s_raw_weather_data.run(local_data_path)

    # Read in residenital submodel shapes
    from energy_demand.scripts import s_rs_raw_shapes
    s_rs_raw_shapes.run(path_main, local_data_path)

    # Read in service submodel shapes
    from energy_demand.scripts import s_ss_raw_shapes
    s_ss_raw_shapes.run(path_main, local_data_path)

def scenario_initalisation(path_data_energy_demand, data=False):
    """Scripts which need to be run for every different scenario

    Parameters
    ----------
    path_data_energy_demand : str
        Path to the energy demand data folder

    Note
    ----
    Only needs to be executed once for each scenario (not for every
    simulation year)

    The ``path_data_processed`` must be in the local path provided to
    post_install_setup
    """
    path_main = resource_filename(Requirement.parse("energy_demand"), "")

    if data == False:
        data = {}
        data['paths'] = data_loader.load_paths(path_main)
        data['local_paths'] = data_loader.load_local_paths(path_data_energy_demand)
        data = data_loader.load_fuels(data)
        data['sim_param'], data['assumptions'] = assumptions.load_assumptions(data)
        data['assumptions'] = assumptions.update_assumptions(data['assumptions'])
        data['weather_stations'], data['temperature_data'] = data_loader.load_data_temperatures(
            data['local_paths'])
        # IMPROVE TODO: LOAD FLOOR AREA DATA
        data = data_loader.dummy_data_generation(data)
    else:
        pass

    from energy_demand.scripts import s_change_temp
    s_change_temp.run(data)

    from energy_demand.scripts import s_fuel_to_service
    s_fuel_to_service.run(data)

    from energy_demand.scripts import s_generate_sigmoid
    s_generate_sigmoid.run(data)

    from energy_demand.scripts import s_disaggregation
    s_disaggregation.run(data)

    print("...  finished running scripts for the specified scenario")
    return
