"""The sector model wrapper for smif to run the energy demand model
"""
import os
import logging
import configparser
import numpy as np
from datetime import date
from collections import defaultdict
from smif.model.sector_model import SectorModel
from pkg_resources import Requirement, resource_filename
from pyproj import Proj, transform
from pyinstrument import Profiler

from energy_demand.scripts.init_scripts import scenario_initalisation
from energy_demand.technologies import tech_related
from energy_demand.cli import run_model
from energy_demand.dwelling_stock import dw_stock
from energy_demand.read_write import read_data
from energy_demand.read_write import write_data
from energy_demand.read_write import data_loader
from energy_demand.main import energy_demand_model
from energy_demand.assumptions import param_assumptions
from energy_demand.assumptions import non_param_assumptions
from energy_demand.basic import date_prop
from energy_demand.basic import logger_setup
from energy_demand.validation import lad_validation
from energy_demand.technologies import fuel_service_switch

# must match smif project name for Local Authority Districts
REGION_SET_NAME = 'lad_uk_2016'
NR_OF_MODELLEd_REGIONS = 2 #391 #391 # uk: 391, england.: 380
PROFILER = False

class EDWrapper(SectorModel):
    """Energy Demand Wrapper
    """
    def before_model_run(self, data=None):
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
        data = defaultdict(dict, data)

        # Criteria
        data['criterias']['mode_constrained'] = True                    # True: Technologies are defined in ED model and fuel is provided, False: Heat is delievered not per technologies
        data['criterias']['virtual_building_stock_criteria'] = True     # True: Run virtual building stock model
        data['criterias']['plot_HDD_chart'] = False                     # True: Plotting of HDD vs gas chart
        data['criterias']['validation_criteria'] = True                 # True: Plot validation plots
        data['criterias']['spatial_exliclit_diffusion'] = False         # True: Spatial explicit calculations
        data['criterias']['writeYAML'] = False
        data['criterias']['write_to_txt'] = True
        data['criterias']['beyond_supply_outputs'] = True
        data['criterias']['plot_crit'] = True

        data['sim_param']['base_yr'] = 2015                             # Base year
        data['sim_param']['curr_yr'] = data['sim_param']['base_yr']
        self.user_data['base_yr'] = data['sim_param']['base_yr']

        # -----------------------------
        # Paths
        # -----------------------------
        path_main = resource_filename(Requirement.parse("energy_demand"), "")

        config = configparser.ConfigParser()
        config.read(os.path.join(path_main, 'wrapperconfig.ini'))
        self.user_data['data_path'] = config['PATHS']['path_local_data']
        self.processed_path = config['PATHS']['path_processed_data']
        self.result_path = config['PATHS']['path_result_data']

        data['paths'] = data_loader.load_paths(path_main)
        data['local_paths'] = data_loader.load_local_paths(self.user_data['data_path'])

        # -----------------------------
        # Region related info
        # -----------------------------
        data['lu_reg'] = self.get_region_names(REGION_SET_NAME)

        reg_centroids = self.get_region_centroids(REGION_SET_NAME)
        data['reg_coord'] = self.get_long_lat_decimal_degrees(reg_centroids)

        # SCRAP REMOVE: ONLY SELECT NR OF MODELLED REGIONS
        data['lu_reg'] = data['lu_reg'][:NR_OF_MODELLEd_REGIONS]
        logging.info("Modelled for a number of regions: " + str(len(data['lu_reg'])))
        data['reg_nrs'] = len(data['lu_reg'])

        # ---------------------
        # Energy demand specific input which need to generated or read in
        # ---------------------
        data['lookups'] = data_loader.load_basic_lookups()
        data['weather_stations'], data['temp_data'] = data_loader.load_temp_data(data['local_paths'])
        data['enduses'], data['sectors'], data['fuels'] = data_loader.load_fuels(
            data['paths'], data['lookups'])

        # -----------------------------
        # Obtain external scenario data
        # -----------------------------
        pop_array = self.get_scenario_data('population')
        pop_dict = self.array_to_dict(pop_array)
        data['population'][data['sim_param']['base_yr']] = pop_dict[2015] # Get only population of base year

        gva_array = self.get_scenario_data('gva')
        data['gva'] = self.array_to_dict(gva_array)

        # Get building related data
        if data['criterias']['virtual_building_stock_criteria']:
            rs_floorarea, ss_floorarea = data_loader.virtual_building_datasets(
                data['lu_reg'], data['sectors']['all_sectors'], data['local_paths'])
        else:
            pass
            # Load floor area from newcastle
            #rs_floorarea = defaultdict(dict)
            #ss_floorarea = defaultdict(dict)

        # --------------
        # Scenario data
        # --------------
        data['scenario_data'] = {
            'gva': data['gva'],
            'population': data['population'],
            'floor_area': {
                'rs_floorarea': rs_floorarea,
                'ss_floorarea': ss_floorarea
                }
        }

        # ------------
        # Load assumptions
        # ------------
        data['assumptions'] = non_param_assumptions.load_non_param_assump(
            data['sim_param']['base_yr'],
            data['paths'],
            data['enduses'],
            data['lookups']['fueltypes'],
            data['lookups']['fueltypes_nr'])
        data['assumptions']['seasons'] = date_prop.read_season(year_to_model=2015)
        data['assumptions']['model_yeardays_daytype'], data['assumptions']['yeardays_month'], data['assumptions']['yeardays_month_days'] = date_prop.get_model_yeardays_datype(
            year_to_model=2015)

        # ------------
        # Load load profiles of technologies
        # ------------
        data['tech_lp'] = data_loader.load_data_profiles(
            data['paths'],
            data['local_paths'],
            data['assumptions']['model_yeardays'],
            data['assumptions']['model_yeardays_daytype'])

        # ---------------------
        # Convert capacity switches to service switches for every submodel
        # ---------------------
        data['assumptions'] = fuel_service_switch.capacity_to_service_switches(
            data['assumptions'], data['fuels'], data['sim_param']['base_yr'])

        # ------------------------
        # Load all SMIF parameters and replace data dict
        # ------------------------
        data['assumptions'] = self.load_smif_parameters(
            data,
            data['assumptions'])

        # TODO TEST THAT NARRATIVE IS IMPORTED
        #print(data['assumptions']['strategy_variables']['climate_change_temp_d__Jan'])
        #prnt(":")

        # Update technologies after strategy definition
        data['assumptions']['technologies'] = non_param_assumptions.update_assumptions(
            data['assumptions']['technologies'],
            data['assumptions']['strategy_variables']['eff_achiev_f'],
            data['assumptions']['strategy_variables']['split_hp_gshp_to_ashp_ey'])

        # ------------------------
        # Pass along to simulate()
        # ------------------------
        self.user_data['gva'] = self.array_to_dict(gva_array)
        self.user_data['population'] = self.array_to_dict(pop_array)
        self.user_data['rs_floorarea'] = rs_floorarea
        self.user_data['ss_floorarea'] = ss_floorarea
        self.user_data['data_pass_along'] = {}
        self.user_data['data_pass_along']['criterias'] = data['criterias']
        self.user_data['data_pass_along']['temp_data'] = data['temp_data']
        self.user_data['data_pass_along']['weather_stations'] = data['weather_stations']
        self.user_data['data_pass_along']['tech_lp'] = data['tech_lp']
        self.user_data['data_pass_along']['lookups'] = data['lookups']
        self.user_data['data_pass_along']['assumptions'] = data['assumptions']
        self.user_data['data_pass_along']['enduses'] = data['enduses']
        self.user_data['data_pass_along']['sectors'] = data['sectors']
        self.user_data['data_pass_along']['fuels'] = data['fuels']
        self.user_data['data_pass_along']['reg_coord'] = data['reg_coord']
        self.user_data['data_pass_along']['lu_reg'] = data['lu_reg']
        self.user_data['data_pass_along']['reg_nrs'] = data['reg_nrs']

        # --------------------
        # Initialise scenario
        # --------------------
        self.user_data['init_cont'], self.user_data['fuel_disagg'] = scenario_initalisation(
            self.user_data['data_path'], data)

        # ------
        # Write population scenario data to txt files for this scenario run
        # ------
        for t_idx, timestep in enumerate(self.timesteps):
            write_data.write_pop(
                timestep,
                data['local_paths']['data_results'],
                pop_array[t_idx])

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

        Returns
        =======
        supply_results : dict
            key: name defined in sector models
                value: np.zeros((len(reg), len(intervals)) )
        """
        # Convert data to default dict
        data = defaultdict(dict, data)

        # Paths
        path_main = resource_filename(Requirement.parse("energy_demand"), "")

        # Ini info
        config = configparser.ConfigParser()
        config.read(os.path.join(path_main, 'wrapperconfig.ini'))

        # ---------------------------------------------
        # Paths
        # ---------------------------------------------
        # Go two levels down
        path, folder = os.path.split(path_main)
        path_nismod, folder = os.path.split(path)
        self.user_data['data_path'] = os.path.join(path_nismod, 'data_energy_demand')

        data['paths'] = data_loader.load_paths(path_main)
        data['local_paths'] = data_loader.load_local_paths(self.user_data['data_path'])

        # ---------------------------------------------
        # Logger
        # ---------------------------------------------
        logger_setup.set_up_logger(os.path.join(data['local_paths']['data_results'], "logger_smif_run.log"))

        data['sim_param']['base_yr'] = self.user_data['base_yr'] # Base year definition
        data['sim_param']['curr_yr'] = timestep                  # Read in current year from smif
        data['sim_param']['simulated_yrs'] = self.timesteps      # Read in all simulated years from smif

        # ---------------------------------------------
        # Load data from scripts (Get simulation parameters from before_model_run()
        # ---------------------------------------------
        data = self.pass_to_simulate(data, self.user_data['data_pass_along'])
        data = self.pass_to_simulate(data, self.user_data['fuel_disagg'])
        data['assumptions'] = self.pass_to_simulate(data['assumptions'], self.user_data['init_cont'])


        # Update: Necessary updates after external data definition
        data['assumptions']['technologies'] = non_param_assumptions.update_assumptions(
            data['assumptions']['technologies'],
            data['assumptions']['strategy_variables']['eff_achiev_f'],
            data['assumptions']['strategy_variables']['split_hp_gshp_to_ashp_ey'])

        # ---------------------------------------------
        # Scenario data
        # ---------------------------------------------
        pop_array = self.get_scenario_data('population') #for simulation year
        pop_dict = self.array_to_dict(pop_array)

        pop_by_cy = {}
        pop_by_cy[data['sim_param']['base_yr']] = pop_dict[2015]                         # Get population of by
        pop_by_cy[data['sim_param']['curr_yr']] = pop_dict[data['sim_param']['curr_yr']] # Get population of cy

        data['scenario_data'] = {
            'gva': self.user_data['gva'],
            'population': pop_by_cy,

            # Only add newcastle floorarea here
            'floor_area': {
                'rs_floorarea': self.user_data['rs_floorarea'],
                'ss_floorarea': self.user_data['ss_floorarea']}}

        # ---------------------------------------------
        # Create .ini file with simulation info
        # ---------------------------------------------
        write_data.write_simulation_inifile(
            data['local_paths']['data_results'],
            data['sim_param'],
            data['enduses'],
            data['assumptions'],
            data['reg_nrs'],
            data['lu_reg'])

        # ---------------------------------------------
        # Run energy demand model
        # ---------------------------------------------
        if PROFILER:
            profiler = Profiler(use_signal=False)
            profiler.start()

        sim_obj = energy_demand_model(data)

        if PROFILER:
            profiler.stop()
            logging.info("Profiler Results")
            logging.info(profiler.output_text(unicode=True, color=True))

        # ------------------------------------------------
        # Validation base year: Hourly temporal validation
        # ------------------------------------------------
        if data['criterias']['validation_criteria'] == True and timestep == data['sim_param']['base_yr']:
            lad_validation.tempo_spatial_validation(
                data['sim_param']['base_yr'],
                data['assumptions']['model_yearhours_nrs'],
                data['assumptions']['model_yeardays_nrs'],
                data['scenario_data'],
                sim_obj.ed_fueltype_national_yh,
                sim_obj.ed_fueltype_regs_yh,
                sim_obj.tot_peak_enduses_fueltype,
                data['lookups']['fueltypes'],
                data['lookups']['fueltypes_nr'],
                data['local_paths'],
                data['lu_reg'],
                data['reg_coord'],
                data['assumptions']['seasons'],
                data['assumptions']['model_yeardays_daytype'],
                data['criterias']['plot_crit'])

        # -------------------------------------------
        # Write annual results to txt files
        # -------------------------------------------
        if data['criterias']['write_to_txt']:
            #tot_fuel_y_max_enduses = sim_obj.tot_fuel_y_max_enduses
            logging.info("... Start writing results to file")
            path_run = data['local_paths']['data_results_model_runs']
            write_data.write_supply_results(
                timestep, "result_tot_yh", path_run, sim_obj.ed_fueltype_regs_yh, "result_tot_submodels_fueltypes")
            write_data.write_enduse_specific(
                timestep, path_run, sim_obj.tot_fuel_y_enduse_specific_h, "out_enduse_specific")
            write_data.write_max_results(
                timestep, path_run, "result_tot_peak_enduses_fueltype", sim_obj.tot_peak_enduses_fueltype, "tot_peak_enduses_fueltype")
            write_data.write_lf(
                path_run, "result_reg_load_factor_y", [timestep], sim_obj.reg_load_factor_y, 'reg_load_factor_y')
            write_data.write_lf(
                path_run, "result_reg_load_factor_yd", [timestep], sim_obj.reg_load_factor_yd, 'reg_load_factor_yd')
            write_data.write_lf(
                path_run, "result_reg_load_factor_winter", [timestep], sim_obj.reg_seasons_lf['winter'], 'reg_load_factor_winter')
            write_data.write_lf(
                path_run, "result_reg_load_factor_spring", [timestep], sim_obj.reg_seasons_lf['spring'], 'reg_load_factor_spring')
            write_data.write_lf(
                path_run, "result_reg_load_factor_summer", [timestep], sim_obj.reg_seasons_lf['summer'], 'reg_load_factor_summer')
            write_data.write_lf(
                path_run, "result_reg_load_factor_autumn", [timestep], sim_obj.reg_seasons_lf['autumn'], 'reg_load_factor_autumn')
            logging.info("... finished writing results to file")

        # ------------------------------------
        # Write results output for supply
        # ------------------------------------
        # Form of np.array(fueltype, sectors, region, periods)
        results_unconstrained = sim_obj.ed_fueltype_submodel_regs_yh
        #write_data.write_supply_results(['rs_submodel', 'ss_submodel', 'is_submodel'],timestep, path_run, results_unconstrained, "results_unconstrained")

        # Form of {constrained_techs: np.array(fueltype, sectors, region, periods)}
        results_constrained = sim_obj.ed_techs_fueltype_submodel_regs_yh
        #write_data.write_supply_results(['rs_submodel', 'ss_submodel', 'is_submodel'], timestep, path_run, results_unconstrained, "results_constrained")

        supply_sectors = ['residential', 'service', 'industry']

        if data['criterias']['mode_constrained']:
            supply_results = constrained_results(
                results_constrained,
                results_unconstrained,
                supply_sectors,
                data['lookups']['fueltypes'],
                data['assumptions']['technologies'])

            # Generate YAML file with keynames for `sector_model`
            if data['criterias']['writeYAML']:
                write_data.write_yaml_output_keynames(
                    data['paths']['yaml_parameters_keynames_constrained'], supply_results.keys())
        else:
            supply_results = unconstrained_results(
                results_unconstrained,
                supply_sectors,
                data['lookups']['fueltypes'])

            # Generate YAML file with keynames for `sector_model`
            if data['criterias']['writeYAML']:
                write_data.write_yaml_output_keynames(
                    data['paths']['yaml_parameters_keynames_unconstrained'], supply_results.keys())

        _total_scrap = 0
        for key in supply_results:
            _total_scrap += np.sum(supply_results[key])
        print("FINALSUM: " + str(_total_scrap))
        logging.info("... finished wrapper calculations")
        return supply_results

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

    def pass_to_simulate(self, dict_to_copy_into, dict_to_pass_along):
        """Pass dict defined in before_model_run() to simlate() function
        by copying key and values

        Arguments
        ---------
        dict_to_copy_into : dict
            Dict to copy values into
        dict_to_pass_along : dict
            Dictionary which needs to be copied and passed along
        """
        for key, value in dict_to_pass_along.items():
            dict_to_copy_into[key] = value

        return dict(dict_to_copy_into)

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

        return dict(output_dict)

    def load_smif_parameters(self, data, assumptions):
        """Get all model parameters from smif (`data`) depending
        on narrative and replace in assumption dict

        Arguments
        ---------
        data : dict
            Dict with all data
        assumptions : dict
            Assumptions

        Returns
        -------
        assumptions : dict
            Assumptions with added strategy variables
        """
        strategy_variables = {}

        # Get all parameter names
        all_strategy_variables = self.parameters.keys()

        # Get variable from dict and reassign and delete from data
        for var_name in all_strategy_variables:
            logging.info("Load strategy parameter: {}  {}".format(var_name, data[var_name]))

            # Get narrative variable from input data dict
            strategy_variables[var_name] = data[var_name]
            del data[var_name]

        # Add to assumptions
        assumptions['strategy_variables'] = strategy_variables

        return assumptions

    def get_long_lat_decimal_degrees(self, reg_centroids):
        """Project coordinates from shapefile to get
        decimal degrees (from OSGB_1936_British_National_Grid to
        WGS 84 projection). Info: #http://spatialreference.org/ref/epsg/wgs-84/

        Arguments
        ---------
        reg_centroids : dict
            Centroid information read in from shapefile via smif

        Return
        -------
        reg_coord : dict
            Contains long and latidue for every region in decimal degrees
        """
        reg_coord = {}
        for centroid in reg_centroids:

            inProj = Proj(init='epsg:27700') # OSGB_1936_British_National_Grid
            outProj = Proj(init='epsg:4326') #WGS 84 projection

            # Convert to decimal degrees
            long_dd, lat_dd = transform(
                inProj,
                outProj,
                centroid['geometry']['coordinates'][0], #longitude
                centroid['geometry']['coordinates'][1]) #latitude

            reg_coord[centroid['properties']['name']] = {}
            reg_coord[centroid['properties']['name']]['longitude'] = long_dd
            reg_coord[centroid['properties']['name']]['latitude'] = lat_dd

        return reg_coord

def constrained_results(
        results_constrained,
        results_unconstrained,
        supply_sectors,
        fueltypes,
        technologies
    ):
    """Prepare results for energy supply model for
    constrained model running mode (no heat is provided but
    technology specific fuel use).
    The results for the supply model are provided aggregated
    for every submodel, fueltype, technology, region, timestep

    Note
    -----
    Because SMIF only takes results in the
    form of {key: np.aray(regions, timesteps)}, the key
    needs to contain information about submodel, fueltype,
    and technology

    Also these key must be defined in the `submodel_model`
    configuration file

    Arguments
    ----------
    results_constrained : dict
        Aggregated results in form
        {technology: np.array((fueltype, sector, region, timestep))}
    results_unconstrained : array
        Restuls of unconstrained mode
        np.array((fueltype, sector, region, timestep))
    supply_sectors : list
        Names of sectors fur supply model
    fueltypes : dict
        Fueltype lookup
    technologies : dict
        Technologies

    Returns
    -------
    supply_results : dict
        No technology specific delivery (heat is provided in form of a fueltype)
        {submodel_fueltype: np.array((region, intervals))}
    """
    supply_results = {}

    # ----------------------------------------
    # Add all constrained technologies
    # Aggregate according to submodel, fueltype, technology, region, timestep
    # ----------------------------------------
    for submodel_nr, submodel in enumerate(supply_sectors):
        for tech, fuel_tech in results_constrained.items():
            fueltype_str = technologies[tech].fueltype_str
            fueltype_int = technologies[tech].fueltype_int

            # ----
            # Simplifications because of different technology definition
            # ----
            tech_simplified = model_tech_simplification(tech)

            # Generate key name (must be defined in `sector_models`)
            key_name = "{}_{}_{}".format(submodel, fueltype_str, tech_simplified)

            if key_name in supply_results.keys():
                # Do not replace by +=
                supply_results[key_name] = supply_results[key_name] + fuel_tech[fueltype_int][submodel_nr]
            else:
                supply_results[key_name] = fuel_tech[fueltype_int][submodel_nr]

    # --------------------------------
    # Add all technologies of restricted enduse (heating)
    # --------------------------------
    # Create empty with shape (fueltypes, sector, region, timestep)
    non_heating_ed = np.zeros((results_unconstrained.shape))

    for fueltype_str, fueltype_int in fueltypes.items():

        # Calculate tech fueltype specific to fuel of constrained technologies
        constrained_ed = np.zeros((results_unconstrained.shape))

        for tech, fuel_tech in results_constrained.items():
            if technologies[tech].fueltype_str == fueltype_str:
                constrained_ed += fuel_tech

        # Substract constrained fuel from nonconstrained (total) fuel
        non_heating_ed[fueltype_int] = results_unconstrained[fueltype_int] - constrained_ed[fueltype_int]

    # Add non_heating for all fueltypes
    for submodel_nr, submodel in enumerate(supply_sectors):
        for fueltype_str, fueltype_int in fueltypes.items():

            if fueltype_str == 'heat':
                pass #Do not add non_heating demand for fueltype heat
            else:
                # Generate key name (must be defined in `sector_models`)
                key_name = "{}_{}_{}".format(submodel, fueltype_str, "non_heating")

                supply_results[key_name] = non_heating_ed[fueltype_int][submodel_nr]

    logging.info("Prepared results for energy supply model in constrained mode")
    return dict(supply_results)

def unconstrained_results(results_unconstrained, supply_sectors, fueltypes):
    """Prepare results for energy supply model for
    unconstrained model running mode (heat is provided).
    The results for the supply model are provided aggregated
    for every submodel, fueltype, region, timestep

    Note
    -----
    Because SMIF only takes results in the
    form of {key: np.aray(regions, timesteps)}, the key
    needs to contain information about submodel and fueltype

    Also these key must be defined in the `submodel_model`
    configuration file

    Arguments
    ----------
    results_unconstrained : array
        Aggregated results in form of np.array((fueltype, sector, region, timestep))
    supply_sectors : list
        Names of sectors fur supply model
    fueltypes : dict
        Fueltype lookup

    Returns
    -------
    supply_results : dict
        No technology specific delivery (heat is provided in form of a fueltype)
        {submodel_fueltype: np.array((region, intervals))}
    """
    supply_results = {}

    # Iterate submodel and fueltypes
    for submodel_nr, submodel in enumerate(supply_sectors):
        for fueltype_str, fueltype_int in fueltypes.items():

            # Generate key name (must be defined in `sector_models`)
            key_name = "{}_{}".format(submodel, fueltype_str)

            supply_results[key_name] = results_unconstrained[fueltype_int][submodel_nr]

    logging.info("Prepared results for energy supply model in unconstrained mode")
    return supply_results

def model_tech_simplification(tech):
    """This function aggregated different technologies
    which are not defined in supply model

    Arguments
    ---------
    tech : str
        Technology

    Returns
    -------
    tech_newly_assigned : str
        Technology newly assigned
    """
    # Assign condensing boiler to regular boilers
    if tech == 'boiler_condensing_gas':
        tech_newly_assigned = 'boiler_gas'
    elif tech == 'boiler_condensing_oil':
        tech_newly_assigned = 'boiler_oil'
    elif tech == 'storage_heater_electricity':
        tech_newly_assigned = 'boiler_electricity'
    elif tech == 'secondary_heater_electricity':
        tech_newly_assigned = 'boiler_electricity'
    else:
        # return idential tech
        tech_newly_assigned = tech

    return tech_newly_assigned
