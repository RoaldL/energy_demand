"""The sector model wrapper for smif to run the energy demand model
"""
import os
import numpy as np
from datetime import date
from smif.model.sector_model import SectorModel
from energy_demand.scripts.init_scripts import scenario_initalisation
from energy_demand.cli import run_model
from energy_demand.dwelling_stock import dw_stock
from energy_demand.read_write import read_data
from energy_demand.main import energy_demand_model
from energy_demand.read_write import data_loader
from energy_demand.assumptions import assumptions
from energy_demand.basic import date_handling
from pkg_resources import Requirement
from pkg_resources import resource_filename

class EDWrapper(SectorModel):
    """Energy Demand Wrapper"""

    def simulate(self, timestep, data=None):
        """

        1. Get scenario data

        Population data is required as a nested dict::

            data[year][region_geocode]

        GVA is the same::

            data[year][region_geocode]

        Floor area::

            data[year][region_geoode][sector]

        2. Run initialise scenarios
        3. For each timestep, run the model

        """
        energy_demand_data_path = '/vagrant/energy_demand_data'
        energy_demand_data_out_path = '/vagrant/energy_demand_data/_result_data'

        # Scenario data
        population = data['population']
        gva = data['gva']
        floor_area = data['floor_area']


        # Load data and initialise scenario

        path_main = resource_filename(Requirement.parse("energy_demand"), "")
        ed_data = {}
        ed_data['paths'] = data_loader.load_paths(path_main)
        ed_data['local_paths'] = data_loader.load_local_paths(energy_demand_data_path)
        ed_data = data_loader.load_fuels(data)
        ed_data['sim_param'], ed_data['assumptions'] = assumptions.load_assumptions(ed_data)
        ed_data['weather_stations'], data['temperature_data'] = data_loader.load_data_temperatures(data['local_paths'])
        ed_data = data_loader.dummy_data_generation(data)

        # Initialise SCNEARIO == NEEDS TO BE IN INIT
        scenario_initalisation(energy_demand_data_out_path, ed_data)

        # Write data from smif to data container from energy demand model

        ed_data['sim_param']['current_year'] = timestep
        #ed_data['sim_param']['end_year'] = timestep
        #ed_data['sim_param']['sim_years_intervall'] = 

        ed_data['assumptions']['assump_diff_floorarea_pp'] = data['assump_diff_floorarea_pp']
        ed_data['assumptions']['climate_change_temp_diff_month'] = data['climate_change_temp_diff_month']
        ed_data['assumptions']['rs_t_base_heating']['end_yr'] = data['rs_t_base_heating_ey']
        ed_data['assumptions']['efficiency_achieving_factor'] = data['efficiency_achieving_factor']

        # Update: Necessary updates after external data definition
        ed_data['sim_param']['sim_period'] = range(ed_data['sim_param']['base_yr'], ed_data['sim_param']['end_yr'] + 1, ed_data['sim_param']['sim_years_intervall'])
        ed_data['sim_param']['sim_period_yrs'] = int(ed_data['sim_param']['end_yr'] + 1 - ed_data['sim_param']['base_yr'])
        ed_data['sim_param']['list_dates'] = date_handling.fullyear_dates(
            start=date(ed_data['sim_param']['base_yr'], 1, 1),
            end=date(ed_data['sim_param']['base_yr'], 12, 31))

        ed_data['assumptions'] = assumptions.update_assumptions(ed_data['assumptions']) #Maybe write s_script

        # Run model
        data = read_data.load_script_data(data)

        # Generate dwelling stocks over whole simulation period
        ed_data['rs_dw_stock'] = dw_stock.rs_dw_stock(data['lu_reg'], ed_data)
        ed_data['ss_dw_stock'] = dw_stock.ss_dw_stock(data['lu_reg'], ed_data)

        _, results = energy_demand_model(ed_data)

        print("FINISHED WRAPPER CALCULATIONS")
        return results

    def extract_obj(self, results):
        """Implement this method to return a scalar value objective function

        This method should take the results from the output of the `simulate`
        method, process the results, and return a scalar value which can be
        used as the objective function

        Arguments
        =========
        results : :class:`dict`
            The results from the `simulate` method

        Returns
        =======
        float
            A scalar component generated from the simulation model results
        """
        pass
