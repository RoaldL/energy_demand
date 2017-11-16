"""Provides an entry point from the command line to the energy demand model
"""
import os
import sys
from pkg_resources import Requirement
from pkg_resources import resource_filename
from argparse import ArgumentParser
import logging
from collections import defaultdict

import energy_demand
from energy_demand.main import energy_demand_model
from energy_demand.read_write import data_loader
from energy_demand.assumptions import non_param_assumptions
from energy_demand.assumptions import param_assumptions
from energy_demand.scripts.init_scripts import post_install_setup
from energy_demand.scripts.init_scripts import scenario_initalisation
from energy_demand.read_write import read_data
from energy_demand.dwelling_stock import dw_stock
from energy_demand.plotting import plotting_results
from energy_demand.basic import basic_functions
from energy_demand.basic import date_prop

def init_scenario(args):
    """
    """
    data_energy_demand = args.data_energy_demand
    scenario_initalisation(data_energy_demand)

def run_model(args):
    """
    Main function to run the energy demand model from the command line

    Notes
    -----
    - path_main is the path to the local data e.g. that stored in the package
    - local_data_path is the path to the restricted data which must be provided
    to the model

    #NOTE: TO RUN FROM COMMAND LINE
    """
    #Subfolder where module is installed
    path_main_data = resource_filename(Requirement.parse("energy_demand"), "data")
    path_main = os.path.join(path_main_data, '../')
    local_data_path = args.data_folder

    # Load data
    data = {}
    data['paths'] = data_loader.load_paths(path_main)
    data['local_paths'] = data_loader.load_local_paths(local_data_path)
    data['lookups'] = data_loader.load_basic_lookups()
    data['enduses'], data['sectors'], data['fuels'], data['all_sectors'] = data_loader.load_fuels(data['paths'], data['lookups'])

    data['sim_param'] = {}
    data['sim_param']['base_yr'] = 2015
    data['sim_param']['simulated_yrs'] = [2015, 2018, 2025, 2050]

    # Assumptions
    data['assumptions'] = non_param_assumptions.load_non_param_assump(data['sim_param']['base_yr'], data['paths'], data['enduses'], data['lookups'], data['fuels'])
    param_assumptions.load_param_assump(data['paths'], data['assumptions'])

    data['assumptions']['seasons'] = date_prop.read_season(year_to_model=2015)
    data['assumptions']['model_yeardays_daytype'], data['assumptions']['yeardays_month'], data['assumptions']['yeardays_month_days'] = date_prop.get_model_yeardays_datype(year_to_model=2015)
    data['assumptions']['technologies'] = non_param_assumptions.update_assumptions(data['assumptions']['technologies'], data['assumptions']['eff_achiev_f']['factor_achieved'])

    data['tech_lp'] = data_loader.load_data_profiles(
        data['paths'],
        data['local_paths'],
        data['assumptions']['model_yeardays'],
        data['assumptions']['model_yeardays_daytype'])

    data['weather_stations'], data['temp_data'] = data_loader.load_temp_data(data['local_paths'])
    
    data['rs_floorarea_2015_virtual_bs'], data['ss_floorarea_sector_2015_virtual_bs'] = data_loader.virtual_building_datasets(data['lu_reg'], data['all_sectors'])

    # Floor areas TODO LOAD FROM NEWCASTLE
    rs_floorarea = defaultdict(dict)
    for year in range(2015, 2101):
        rs_floorarea[year] = {}
        for region_geocode in data['lu_reg']:
            rs_floorarea[year][region_geocode] = 10000

    data['scenario_data'] = {
        'gva': data['gva'],
        'population': data['population'],
        'floor_area': {
            'rs_floorarea_newcastle': rs_floorarea
        }
    }

    # In order to load these data, the initialisation scripts need to be run
    logging.info("... Load data from script calculations")
    data = read_data.load_script_data(data)

    #--------------------
    # Folder cleaning
    #--------------------
    logging.info("... delete previous model run results")
    basic_functions.del_previous_setup(data['local_paths']['data_results'])
    basic_functions.create_folder(data['local_paths']['data_results'])
    basic_functions.create_folder(data['local_paths']['data_results_PDF'])
    basic_functions.create_folder(data['local_paths']['data_results'], "model_run_pop")

    results = energy_demand_model(data)

    logging.debug("... Result section")

    results_every_year = [results]

    logging.debug("Finished energy demand model from command line execution")
    print("Finished energy demand model from command line execution")

def parse_arguments():
    """Parse command line arguments

    Returns
    =======
    :class:`argparse.ArgumentParser`

    """
    parser = ArgumentParser(description='Command line tools for energy_demand')
    parser.add_argument('-V', '--version',
                        action='version',
                        version="energy_demand " + energy_demand.__version__,
                        help='show the current version of energy_demand')

    subparsers = parser.add_subparsers()

    # Run main model
    parser_run = subparsers.add_parser(
        'run',
        help='Run the model'
        )
    parser_run.add_argument(
        '-d',
        '--data_folder',
        default='./processed_data',
        help='Path to the input data folder'
        )
    parser_run.set_defaults(func=run_model)

    # Initialisation of energy demand model (processing raw files)
    parser_init = subparsers.add_parser(
        'post_install_setup',
        help='Executes the raw reading functions'
        )
    parser_init.add_argument(
        '-d',
        '--data_energy_demand',
        default='./data_energy_demand',
        help='Path to the input data folder'
        )

    parser_init.set_defaults(func=post_install_setup)

    # Scenario initialisation
    scenario_init = subparsers.add_parser(
        'scenario_initialisation',
        help='Needs to be initialised')

    scenario_init.add_argument(
        '-d',
        '--data_energy_demand',
        default='./data_energy_demand',
        help='Path to main data folder'
        )

    scenario_init.set_defaults(func=init_scenario)

    return parser

def main(arguments=None):
    """Parse args and run
    """
    parser = parse_arguments()
    args = parser.parse_args(arguments)

    if 'func' in args:
        args.func(args)
    else:
        parser.print_help()

if __name__ == '__main__':
    main(sys.argv[1:])
