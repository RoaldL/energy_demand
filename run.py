"""The sector model wrapper for smif to run the energy demand model
"""
import os
import logging
import configparser
from datetime import date
from collections import defaultdict
from smif.model.sector_model import SectorModel
from energy_demand.scripts.init_scripts import scenario_initalisation
from energy_demand.cli import run_model
from energy_demand.dwelling_stock import dw_stock
from energy_demand.read_write import read_data, write_data
from energy_demand.main import energy_demand_model
from energy_demand.read_write import data_loader
from energy_demand.assumptions import non_param_assumptions
from energy_demand.assumptions import param_assumptions
from energy_demand.basic import date_prop
from pkg_resources import Requirement, resource_filename

# must match smif project name for Local Authority Districts
REGION_SET_NAME = 'lad_2016' #TODO
NR_OF_MODELLEd_REGIONS = 10

class EDWrapper(SectorModel):
    """Energy Demand Wrapper
    """

    def array_to_dict(self, input_array):
        """Convert array to dict

        Arguments
        ---------
        input_array : numpy.ndarray
            timesteps, regions, interval

        Returns
        -------
        output_dict : dict
            timesteps, region, interval

        """
        output_dict = defaultdict(dict)
        for t_idx, timestep in enumerate(self.timesteps):
            for r_idx, region in enumerate(self.get_region_names(REGION_SET_NAME)):
                output_dict[timestep][region] = input_array[t_idx, r_idx, 0]

        return output_dict

    def before_model_run(self):
        """Runs prior to any ``simulate()`` step

        Writes scenario data out into the scenario files

        Saves useful data into the ``self.user_data`` dictionary for access
        in the ``simulate()`` method

        Data is accessed using the `get_scenario_data()` method is provided
        as a numpy array with the dimensions timesteps-by-regions-by-intervals.

        Info
        -----
        `self.user_data` allows to pass data from before_model_run to main model
        """
        data = {}
        # -----------------------------
        # Paths
        # -----------------------------
        path_main = resource_filename(Requirement.parse("energy_demand"), "")

        config = configparser.ConfigParser()
        config.read(os.path.join(path_main, 'wrapperconfig.ini'))

        self.user_data['data_path'] = config['PATHS']['path_local_data']
        self.processed_path = config['PATHS']['path_processed_data']
        self.result_path = config['PATHS']['path_result_data']

        # Add to data container for scenario initialisation
        data['paths'] = data_loader.load_paths(path_main)
        data['local_paths'] = data_loader.load_local_paths(self.user_data['data_path'])

        # ---------------------
        # Simulation parameters
        # ---------------------
        data['print_criteria'] = False

        data['sim_param'] = {}
        data['sim_param']['base_yr'] = 2015 #REPLACE
        data['sim_param']['curr_yr'] = data['sim_param']['base_yr']
        self.user_data['base_yr'] = data['sim_param']['base_yr']

        # -----------------------------
        # Region related informatiom
        # -----------------------------
        data['lu_reg'] = self.get_region_names(REGION_SET_NAME)
        #data['reg_coord'] = regions.get_region_centroids(REGION_SET_NAME) #TO BE IMPLEMENTED BY THE SMIF GUYS
        data['reg_coord'] = data_loader.get_dummy_coord_region(data['lu_reg'], data['local_paths']) #REMOVE IF CORRECT DATA IN

        # SCRAP REMOVE: ONLY SELECT NR OF MODELLED REGIONS
        data['lu_reg'] = data['lu_reg'][:NR_OF_MODELLEd_REGIONS]
        print("Modelled for a nuamer of regions: " + str(len(data['lu_reg'])))



        data = data_loader.dummy_data_generation(data, data['lu_reg']) #TODO REMOVE

        # -----------------------------
        # Obtain external scenario data
        # -----------------------------
        # Population
        pop_array = self.get_scenario_data('population') #maybe only cy and by data
        data['population'] = self.array_to_dict(pop_array['population'])

        # GVA
        gva_array = self.get_scenario_data('gva')
        data['gva'] = self.array_to_dict(gva_array['gva'])

        # Floor areas
        
        #Scenario data
        data['scenario_data'] = {
            'gva': data['gva'],
            'population': data['population'],
            'floor_area': {
                'rs_floorarea': data['rs_floorarea'],
                'ss_sector_floor_area_by': data['ss_sector_floor_area_by']
                }
        }

        '''# Building stock related data

        # --Residential Floor Area
        floor_array = self.get_scenario_data('floor_area_rs_detached_pre1930')
        '''

        # ---------------------
        # Energy demand specific input which needs to be read in
        # ---------------------
        data['lookups'] = data_loader.load_basic_lookups()
        data['weather_stations'], data['temp_data'] = data_loader.load_temp_data(data['local_paths'])
        data['enduses'], data['sectors'], data['fuels'] = data_loader.load_fuels(data['paths'], data['lookups'])
        
        # Assumptions
        data['assumptions'] = non_param_assumptions.load_non_param_assump(data['sim_param']['base_yr'], data['paths'], data['enduses'], data['lookups'], data['fuels'])

        # ------------------------
        # Load all SMIF parameters and replace data dict
        # ------------------------
        data['assumptions'], data = self.load_all_smif_parameters(data['assumptions'], data)

        data['assumptions']['seasons'] = date_prop.read_season(year_to_model=2015)
        data['assumptions']['model_yeardays_daytype'], data['assumptions']['yeardays_month'], data['assumptions']['yeardays_month_days'] = date_prop.get_model_yeardays_datype(year_to_model=2015)

        data['tech_lp'] = data_loader.load_data_profiles(data['paths'], data['local_paths'], data['assumptions'])
        
        # ------------------------
        # Pass along to simulate()
        # ------------------------
        self.user_data['temp_data'] = data['temp_data']
        self.user_data['weather_stations'] = data['weather_stations']
        self.user_data['gva'] = self.array_to_dict(gva_array['gva'])
        self.user_data['population'] = self.array_to_dict(pop_array['population'])

        # --------------------
        # Initialise scenario
        # --------------------
        self.user_data['fts_cont'], self.user_data['sgs_cont'], self.user_data['sd_cont'] = scenario_initalisation(
            self.user_data['data_path'], data)

    def initialise(self, initial_conditions):
        """
        """
        pass

    def simulate(self, timestep, data=None):
        """Runs the Energy Demand model for one `timestep`

        Arguments
        ---------
        timestep : int
            The name of the current timestep
        data : dict
            A dictionary containing all parameters and model inputs defined in
            the smif configuration by name

        Notes
        -----
        1. Get scenario data

        Population data is required as a nested dict::

            data[year][region_geocode]

        GVA is the same::

            data[year][region_geocode]

        Floor area::

            data[year][region_geoode][sector]

        2. Run initialise scenarios
        3. For each timestep, run the model

        Data is provided to these methods in the format::

            {'parameter_name': value_array}

        where ``value_array`` is a regions-by-intervals numpy array.

        """
        data = {}

        # ------
        # Paths
        # ------
        path_main = resource_filename(Requirement.parse("energy_demand"), "")

        config = configparser.ConfigParser()
        config.read(os.path.join(path_main, 'wrapperconfig.ini'))

        # Go two levels down
        path, folder = os.path.split(path_main)
        path_nismod, folder = os.path.split(path)
        self.user_data['data_path'] = os.path.join(path_nismod, 'data_energy_demand')

        data['paths'] = data_loader.load_paths(path_main)
        data['local_paths'] = data_loader.load_local_paths(self.user_data['data_path'])

        # --------------------
        # Simulation parameters
        # --------------------
        data['sim_param'] = {}
        data['sim_param']['base_yr'] = self.user_data['base_yr'] # Base year definition
        data['sim_param']['curr_yr'] = timestep                  # Read in current year from smif
        data['sim_param']['simulated_yrs'] = self.timesteps      # Read in all simulated years from smif

        # Copy from before_model_run()
        data['lu_reg'] = self.get_region_names(REGION_SET_NAME)
        data['lu_reg'] = data['lu_reg'][:NR_OF_MODELLEd_REGIONS] #TODO REMOVE

        # =========DUMMY DATA
        data = data_loader.dummy_data_generation(data, data['lu_reg']) #TODO REMOVE
        # =========DUMMY DATA

        # ---------
        # Scenario data
        # ---------
        data['print_criteria'] = False

        data['scenario_data'] = {
            'gva': self.user_data['gva'],
            'population':  self.user_data['population'],
                'floor_area': {
                'rs_floorarea': data['rs_floorarea'],
                'ss_sector_floor_area_by': data['ss_sector_floor_area_by']}
            }

        # ---------
        # Replace data in data with data provided from wrapper or before_model_run
        # Write data from smif to data container from energy demand model
        # ---------
        data['lu_reg'] = self.get_region_names(REGION_SET_NAME)
        #data['reg_coord'] = regions.get_region_centroids(REGION_SET_NAME) #TO BE IMPLEMENTED BY THE SMIF GUYS
        data['lu_reg'] = data['lu_reg'][:NR_OF_MODELLEd_REGIONS]
        print("Modelled for a nuamer of regions: " + str(len(data['lu_reg'])))

        #REPLACE BY SMIF INPUT
        data['reg_coord'] = data_loader.get_dummy_coord_region(data['lu_reg'], data['local_paths'])

        # ED related stuff
        data['lookups'] = data_loader.load_basic_lookups()
        data['enduses'], data['sectors'], data['fuels'] = data_loader.load_fuels(data['paths'], data['lookups'])
        data['assumptions'] = non_param_assumptions.load_non_param_assump(
            data['sim_param']['base_yr'], data['paths'], data['enduses'], data['lookups'], data['fuels'])
        
        # ------------------------
        # Load all SMIF parameters and replace data dict
        # ------------------------
        data['assumptions'], data = self.load_all_smif_parameters(data['assumptions'], data) #TODO: REMOVE DATA

        data['assumptions']['seasons'] = date_prop.read_season(year_to_model=2015)
        data['assumptions']['model_yeardays_daytype'], data['assumptions']['yeardays_month'], data['assumptions']['yeardays_month_days'] = date_prop.get_model_yeardays_datype(year_to_model=2015)
        data['tech_lp'] = data_loader.load_data_profiles(data['paths'], data['local_paths'], data['assumptions'])

        # Update: Necessary updates after external data definition
        data['assumptions']['technologies'] = non_param_assumptions.update_assumptions(
            data['assumptions']['technologies'], data['assumptions']['eff_achiev_f']['factor_achieved'])

        # -----------------------
        # Load data from scripts
        # -----------------------
        # Insert from script calculations which are stored in memory
        data['temp_data'] = self.user_data['temp_data']
        data['weather_stations'] = self.user_data['weather_stations']
        data['assumptions']['rs_service_tech_by_p'] = self.user_data['fts_cont']['rs_service_tech_by_p']
        data['assumptions']['ss_service_tech_by_p'] = self.user_data['fts_cont']['ss_service_tech_by_p']
        data['assumptions']['is_service_tech_by_p'] = self.user_data['fts_cont']['is_service_tech_by_p']
        data['assumptions']['rs_service_fueltype_by_p'] = self.user_data['fts_cont']['rs_service_fueltype_by_p']
        data['assumptions']['ss_service_fueltype_by_p'] = self.user_data['fts_cont']['ss_service_fueltype_by_p']
        data['assumptions']['is_service_fueltype_by_p'] = self.user_data['fts_cont']['is_service_fueltype_by_p']
        data['assumptions']['rs_service_fueltype_tech_by_p'] = self.user_data['fts_cont']['rs_service_fueltype_tech_by_p']
        data['assumptions']['ss_service_fueltype_tech_by_p'] = self.user_data['fts_cont']['ss_service_fueltype_tech_by_p']
        data['assumptions']['is_service_fueltype_tech_by_p'] = self.user_data['fts_cont']['is_service_fueltype_tech_by_p']
        data['assumptions']['rs_tech_increased_service'] = self.user_data['sgs_cont']['rs_tech_increased_service']
        data['assumptions']['ss_tech_increased_service'] = self.user_data['sgs_cont']['ss_tech_increased_service']
        data['assumptions']['is_tech_increased_service'] = self.user_data['sgs_cont']['is_tech_increased_service']
        data['assumptions']['rs_tech_decreased_share'] = self.user_data['sgs_cont']['rs_tech_decreased_share']
        data['assumptions']['ss_tech_decreased_share'] = self.user_data['sgs_cont']['ss_tech_decreased_share']
        data['assumptions']['is_tech_decreased_share'] = self.user_data['sgs_cont']['is_tech_decreased_share']
        data['assumptions']['rs_tech_constant_share'] = self.user_data['sgs_cont']['rs_tech_constant_share']
        data['assumptions']['ss_tech_constant_share'] = self.user_data['sgs_cont']['ss_tech_constant_share']
        data['assumptions']['is_tech_constant_share'] = self.user_data['sgs_cont']['is_tech_constant_share']
        data['assumptions']['rs_sig_param_tech'] = self.user_data['sgs_cont']['rs_sig_param_tech']
        data['assumptions']['ss_sig_param_tech'] = self.user_data['sgs_cont']['ss_sig_param_tech']
        data['assumptions']['is_sig_param_tech'] = self.user_data['sgs_cont']['is_sig_param_tech']
        data['assumptions']['rs_installed_tech'] = self.user_data['sgs_cont']['rs_installed_tech']
        data['assumptions']['ss_installed_tech'] = self.user_data['sgs_cont']['ss_installed_tech']
        data['assumptions']['is_installed_tech'] = self.user_data['sgs_cont']['is_installed_tech']
        data['rs_fuel_disagg'] = self.user_data['sd_cont']['rs_fuel_disagg']
        data['ss_fuel_disagg'] = self.user_data['sd_cont']['ss_fuel_disagg']
        data['is_fuel_disagg'] = self.user_data['sd_cont']['is_fuel_disagg']

        # ---------------------------------------------
        # Create .ini file with simulation information
        # ---------------------------------------------
        write_data.write_simulation_inifile(
            data['local_paths']['data_results'],
            data['sim_param'],
            data['enduses'],
            data['assumptions'],
            data['reg_nrs'])

        # ---------
        # Run model
        # ---------
        results = energy_demand_model(data)

        # ------------------------------------
        # Write results output for supply
        # ------------------------------------
        supply_results = results.ed_fueltype_regs_yh

        logging.info("... finished wrapper calculations")
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

    def load_all_smif_parameters(self, assumptions, data):
        """Get all model parameters from smif and replace in data dict

        Arguments
        =========
        assumptions : dict
            Data container

        Returns
        =========
        assumptions : dict
            Assumptions container with added parameters
        """
        '''
        assumptions['demand_management'] = {}
        assumptions['demand_management']['demand_management_yr_until_changed'] = self.get_SMIF_param('demand_management_yr_until_changed')

        assumptions['demand_management']['enduses_demand_managent'] = {}
        #demand_management_improvement__ Residential submodule
        assumptions['demand_management']['demand_management_improvement__rs_space_heating' = self.get_SMIF_param('demand_management_yr_until_changed')
        assumptions['demand_management']['demand_management_improvement__rs_water_heating' = self.get_SMIF_param('demand_management_improvement__rs_water_heating')
        assumptions['demand_management']['demand_management_improvement__rs_lighting' = self.get_SMIF_param('demand_management_improvement__rs_lighting')
        assumptions['demand_management']['demand_management_improvement__rs_cooking' = self.get_SMIF_param('demand_management_improvement__rs_cooking')
        assumptions['demand_management']['demand_management_improvement__rs_cold' = self.get_SMIF_param('demand_management_improvement__rs_cold')
        assumptions['demand_management']['demand_management_improvement__rs_wet' = self.get_SMIF_param('demand_management_improvement__rs_wet')
        assumptions['demand_management']['demand_management_improvement__rs_consumer_electronics' = self.get_SMIF_param('demand_management_improvement__rs_consumer_electronics')
        assumptions['demand_management']['demand_management_improvement__rs_home_computing' = self.get_SMIF_param('demand_management_improvement__rs_home_computing')

        # Service submodule
        assumptions['demand_management']['demand_management_improvement__ss_space_heating' = self.get_SMIF_param('demand_management_improvement__ss_space_heating')
        assumptions['demand_management']['demand_management_improvement__ss_water_heating' = self.get_SMIF_param('demand_management_improvement__ss_water_heating')
        assumptions['demand_management']['demand_management_improvement__ss_lighting' = self.get_SMIF_param('demand_management_improvement__ss_lighting')
        assumptions['demand_management']['demand_management_improvement__ss_catering' = self.get_SMIF_param('demand_management_improvement__ss_catering')
        assumptions['demand_management']['demand_management_improvement__ss_computing' = self.get_SMIF_param('demand_management_improvement__ss_computing')
        assumptions['demand_management']['demand_management_improvement__ss_space_cooling' = self.get_SMIF_param('demand_management_improvement__ss_space_cooling')
        assumptions['demand_management']['demand_management_improvement__ss_other_gas' = self.get_SMIF_param('demand_management_improvement__ss_other_gas')
        assumptions['demand_management']['demand_management_improvement__ss_other_electricity' = self.get_SMIF_param('demand_management_improvement__ss_other_electricity')

        # Industry submodule
        assumptions['demand_management']['demand_management_improvement__is_high_temp_process' = self.get_SMIF_param('demand_management_improvement__is_high_temp_process')
        assumptions['demand_management']['demand_management_improvement__is_low_temp_process' = self.get_SMIF_param('demand_management_improvement__is_low_temp_process')
        assumptions['demand_management']['demand_management_improvement__is_drying_separation' = self.get_SMIF_param('demand_management_improvement__is_drying_separation')
        assumptions['demand_management']['demand_management_improvement__is_motors' = self.get_SMIF_param('demand_management_improvement__is_motors')
        assumptions['demand_management']['demand_management_improvement__is_compressed_air' = self.get_SMIF_param('demand_management_improvement__is_compressed_air')
        assumptions['demand_management']['demand_management_improvement__is_lighting' = self.get_SMIF_param('demand_management_improvement__is_lighting')
        assumptions['demand_management']['demand_management_improvement__is_space_heating' = self.get_SMIF_param('demand_management_improvement__is_space_heating')
        assumptions['demand_management']['demand_management_improvement__is_other' = self.get_SMIF_param('demand_management_improvement__is_other')
        assumptions['demand_management']['demand_management_improvement__is_refrigeration' = self.get_SMIF_param('demand_management_improvement__is_refrigeration')
        '''
        # TODO: REMOVE param_assumptions.load_param_assump IF FULLY IMPLEMENTED
        param_assumptions.load_param_assump(
            data['paths'], data['assumptions'], data['enduses'], data['lookups'], data['fuels'], data['sim_param'])

        return assumptions, data