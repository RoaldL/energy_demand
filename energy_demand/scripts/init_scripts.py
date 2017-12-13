"""Script functions which are executed after
model installation and after each scenario definition
"""
import os
import logging
import numpy as np
from pkg_resources import Requirement
from pkg_resources import resource_filename
from energy_demand.read_write import data_loader
from energy_demand.assumptions import non_param_assumptions
from energy_demand.assumptions import param_assumptions
from energy_demand.scripts import s_raw_weather_data
from energy_demand.scripts import s_rs_raw_shapes
from energy_demand.scripts import s_ss_raw_shapes
from energy_demand.scripts import s_fuel_to_service
from energy_demand.scripts import s_generate_sigmoid
from energy_demand.scripts import s_disaggregation
from energy_demand.basic import basic_functions
from energy_demand.basic import logger_setup
from energy_demand.basic import date_prop
from energy_demand.technologies import fuel_service_switch
from energy_demand.geography import spatial_diffusion
from energy_demand.read_write import read_data

def post_install_setup(args):
    """Run this function after installing the energy_demand
    model with smif and putting the data folder with all necessary
    data into a local drive. This scripts only needs to be
    executed once after the energy_demand model has been installed

    Arguments
    ----------
    args : object
        Arguments defined in ``./cli/__init__.py``
    """
    print("... start running initialisation scripts")

    # Paths
    path_main = resource_filename(Requirement.parse("energy_demand"), "")
    local_data_path = args.data_energy_demand

    # Initialise logger
    logger_setup.set_up_logger(os.path.join(local_data_path, "logging_post_install_setup.log"))
    logging.info("... start local energy demand calculations")

    # Load data
    data = {}
    data['paths'] = data_loader.load_paths(path_main)
    data['local_paths'] = data_loader.load_local_paths(local_data_path)
    data['lookups'] = data_loader.load_basic_lookups()
    data['enduses'], data['sectors'], data['fuels'] = data_loader.load_fuels(
        data['paths'], data['lookups'])

    data['sim_param'] = {}
    data['sim_param']['base_yr'] = 2015
    data['sim_param']['simulated_yrs'] = [2015, 2020, 2025]

    # Assumptions
    data['assumptions'] = non_param_assumptions.load_non_param_assump(
        data['sim_param']['base_yr'], data['paths'], data['enduses'], data['lookups'])

    param_assumptions.load_param_assump(data['paths'], data['assumptions'])

    data['assumptions']['seasons'] = date_prop.read_season(year_to_model=2015)
    data['assumptions']['model_yeardays_daytype'], data['assumptions']['yeardays_month'], data['assumptions']['yeardays_month_days'] = date_prop.get_model_yeardays_datype(year_to_model=2015)
    data['assumptions']['technologies'] = non_param_assumptions.update_assumptions(
        data['assumptions']['technologies'],
        data['assumptions']['strategy_variables']['eff_achiev_f'],
        data['assumptions']['strategy_variables']['split_hp_gshp_to_ashp_ey'])

    # Delete all previous data from previous model runs
    basic_functions.del_previous_setup(data['local_paths']['data_processed'])
    basic_functions.del_previous_setup(data['local_paths']['data_results'])

    # Create folders and subfolder for data_processed
    basic_functions.create_folder(data['local_paths']['data_processed'])
    basic_functions.create_folder(data['local_paths']['path_post_installation_data'])
    basic_functions.create_folder(data['local_paths']['dir_raw_weather_data'])
    basic_functions.create_folder(data['local_paths']['dir_changed_weather_station_data'])
    basic_functions.create_folder(data['local_paths']['load_profiles'])
    basic_functions.create_folder(data['local_paths']['rs_load_profiles'])
    basic_functions.create_folder(data['local_paths']['ss_load_profiles'])
    basic_functions.create_folder(data['local_paths']['dir_disattregated'])

    # Read in temperature data from raw files
    s_raw_weather_data.run(data)

    # Read in residential submodel shapes
    s_rs_raw_shapes.run(data)

    # Read in service submodel shapes
    s_ss_raw_shapes.run(data)

    logging.info("... finished post_install_setup")
    print("... finished post_install_setup")
    return

def scenario_initalisation(path_data_ed, data=False):
    """Scripts which need to be run for every different scenario.
    Only needs to be executed once for each scenario (not for every
    simulation year)

    Arguments
    ----------
    path_data_ed : str
        Path to the energy demand data folder
    data : dict
        Data container
    """
    logging.info("... start running sceario_initialisation scripts")

    sgs_cont = {}
    fts_cont = {}
    sd_cont = {}

    # Initialise logger
    logger_setup.set_up_logger(os.path.join(path_data_ed, "scenario_init.log"))

    # --------------------------------------------
    # Delete processed data from former model runs and create folders
    # --------------------------------------------
    logging.info("... delete previous model run results")
    basic_functions.del_previous_results(
        data['local_paths']['data_processed'],
        data['local_paths']['path_post_installation_data'])
    basic_functions.del_previous_setup(data['local_paths']['data_results'])

    basic_functions.create_folder(data['local_paths']['data_results'])
    basic_functions.create_folder(data['local_paths']['dir_services'])
    basic_functions.create_folder(data['local_paths']['path_sigmoid_data'])
    basic_functions.create_folder(data['local_paths']['data_results_PDF'])
    basic_functions.create_folder(data['local_paths']['data_results'], "model_run_pop")
    basic_functions.create_folder(data['local_paths']['data_results_validation'])

    # ---------------------------------------
    # Load local datasets for disaggregateion
    # ---------------------------------------
    data['scenario_data']['employment_statistics'] = data_loader.read_employment_statistics(
        data['local_paths']['path_employment_statistics'])

    # -------------------
    # Disaggregate fuel for all regions
    # -------------------
    sd_cont['rs_fuel_disagg'], sd_cont['ss_fuel_disagg'], sd_cont['is_fuel_disagg'] = s_disaggregation.disaggregate_base_demand(
        data['lu_reg'],
        data['sim_param']['base_yr'],
        data['sim_param']['curr_yr'],
        data['fuels'],
        data['scenario_data'],
        data['assumptions'],
        data['reg_coord'],
        data['weather_stations'],
        data['temp_data'],
        data['sectors'],
        data['sectors']['all_sectors'],
        data['enduses'])

    # -------------------
    # Convert fuel to service on a national scale (s_fuel_to_service)
    # Convert base year fuel input assumptions to energy service
    # -------------------

    # Residential
    fts_cont['rs_service_tech_by_p'], fts_cont['rs_service_fueltype_tech_by_p'], fts_cont['rs_service_fueltype_by_p'] = s_fuel_to_service.get_service_fueltype_tech(
        data['assumptions']['tech_list'],
        data['lookups']['fueltype'],
        data['assumptions']['rs_fuel_tech_p_by'],
        data['fuels']['rs_fuel_raw_data_enduses'],
        data['assumptions']['technologies'])

    # Service
    fuels_aggregated_across_sectors = s_fuel_to_service.ss_sum_fuel_enduse_sectors(
        data['fuels']['ss_fuel_raw_data_enduses'],
        data['enduses']['ss_all_enduses'],
        data['lookups']['fueltypes_nr'])
    fts_cont['ss_service_tech_by_p'], fts_cont['ss_service_fueltype_tech_by_p'], fts_cont['ss_service_fueltype_by_p'] = s_fuel_to_service.get_service_fueltype_tech(
        data['assumptions']['tech_list'],
        data['lookups']['fueltype'],
        data['assumptions']['ss_fuel_tech_p_by'],
        fuels_aggregated_across_sectors,
        data['assumptions']['technologies'])

    # Industry
    fuels_aggregated_across_sectors = s_fuel_to_service.ss_sum_fuel_enduse_sectors(
        data['fuels']['is_fuel_raw_data_enduses'],
        data['enduses']['is_all_enduses'],
        data['lookups']['fueltypes_nr'])
    fts_cont['is_service_tech_by_p'], fts_cont['is_service_fueltype_tech_by_p'], fts_cont['is_service_fueltype_by_p'] = s_fuel_to_service.get_service_fueltype_tech(
        data['assumptions']['tech_list'],
        data['lookups']['fueltype'],
        data['assumptions']['is_fuel_tech_p_by'],
        fuels_aggregated_across_sectors,
        data['assumptions']['technologies'])

    # ------------------------------------
    # Autocomplement service switches on a national scale
    # ------------------------------------
    switches_cont = {}
    switches_cont['rs_service_switches'] = fuel_service_switch.autocomplete_switches(
        data['assumptions']['rs_service_switches'],
        data['assumptions']['rs_specified_tech_enduse_by'],
        fts_cont['rs_service_tech_by_p'])

    switches_cont['ss_service_switches'] = fuel_service_switch.autocomplete_switches(
        data['assumptions']['ss_service_switches'],
        data['assumptions']['ss_specified_tech_enduse_by'],
        fts_cont['ss_service_tech_by_p'])

    switches_cont['is_service_switches'] = fuel_service_switch.autocomplete_switches(
        data['assumptions']['is_service_switches'],
        data['assumptions']['is_specified_tech_enduse_by'],
        fts_cont['is_service_tech_by_p'])

    # -------------------------------------
    # Get service shares of technologies for future year by considering service switch on a national scale
    # -------------------------------------
    switches_cont['rs_share_service_tech_ey_p'] = fuel_service_switch.get_share_service_tech_ey(
        switches_cont['rs_service_switches'],
        data['assumptions']['rs_specified_tech_enduse_by'])
    switches_cont['ss_share_service_tech_ey_p'] = fuel_service_switch.get_share_service_tech_ey(
        switches_cont['ss_service_switches'],
        data['assumptions']['ss_specified_tech_enduse_by'])
    switches_cont['is_share_service_tech_ey_p'] = fuel_service_switch.get_share_service_tech_ey(
        switches_cont['is_service_switches'],
        data['assumptions']['is_specified_tech_enduse_by'])

    # -------------------------------
    # Calculate sigmoid diffusion parameters (either for every region or aggregated for all regions)
    # -------------------------------
    if data['criterias']['spatial_exliclit_diffusion']:
        pass
        '''
        # -------------------------------
        # Spatially differentiated modelling
        # -------------------------------
        # Define technologies affected by regional diffusion TODO
        techs_affected_spatial_f = ['heat_pumps_electricity'] #'boiler_hydrogen',

        # Load diffusion values
        spatial_diff_values = spatial_diffusion.load_spatial_diff_values(
            data['lu_reg'],
            data['enduses']['all_enduses'])

        # Load diffusion factors
        spatial_diffusion_factor = spatial_diffusion.calc_diff_factor(
            data['lu_reg'],
            spatial_diff_values,
            [sd_cont['rs_fuel_disagg'], sd_cont['ss_fuel_disagg'], sd_cont['is_fuel_disagg']])

        # Residential spatial explicit modelling
        rs_reg_enduse_tech_p_ey = spatial_diffusion.calc_regional_services(
            switches_cont['rs_share_service_tech_ey_p'],
            data['lu_reg'],
            spatial_diffusion_factor,
            sd_cont['rs_fuel_disagg'],
            techs_affected_spatial_f)

        # Generate sigmoid curves (s_generate_sigmoid) for every region
        ss_reg_enduse_tech_p = spatial_diffusion.calc_regional_services(
            switches_cont['ss_share_service_tech_ey_p'],
            data['lu_reg'],
            spatial_diffusion_factor,
            sum_across_sectors_all_regs(sd_cont['ss_fuel_disagg']),
            techs_affected_spatial_f)

        is_reg_enduse_tech_p = spatial_diffusion.calc_regional_services(
            switches_cont['is_share_service_tech_ey_p'],
            data['lu_reg'],
            spatial_diffusion_factor,
            sum_across_sectors_all_regs(sd_cont['is_fuel_disagg']),
            techs_affected_spatial_f)

        # -------------------------------
        # Calculate regional service shares of technologies for every technology
        # -------------------------------
        sgs_cont['rs_tech_increased_service'], sgs_cont['rs_tech_decreased_share'], sgs_cont['rs_tech_constant_share'] = s_generate_sigmoid.get_tech_future_service(
            fts_cont['rs_service_tech_by_p'], rs_reg_enduse_tech_p_ey, data['lu_reg'], True)

        sgs_cont['ss_tech_increased_service'], sgs_cont['ss_tech_decreased_share'], sgs_cont['ss_tech_constant_share'] = s_generate_sigmoid.get_tech_future_service(
            fts_cont['ss_service_tech_by_p'], ss_reg_enduse_tech_p, data['lu_reg'], True)

        sgs_cont['is_tech_increased_service'], sgs_cont['is_tech_decreased_share'], sgs_cont['is_tech_constant_share'] = s_generate_sigmoid.get_tech_future_service(
            fts_cont['is_service_tech_by_p'], is_reg_enduse_tech_p, data['lu_reg'], True)

        # -------------------------------
        # Calculate diffusion parameters for technologies
        # -------------------------------
        # Regional specific sigmoid curves (Residential)
        sgs_cont['rs_installed_tech'], sgs_cont['rs_sig_param_tech'], rs_service_tech_switched_p = s_generate_sigmoid.get_sig_diffusion(
            data['sim_param']['base_yr'],
            data['assumptions']['technologies'],
            data['assumptions']['rs_service_switches'],
            data['assumptions']['rs_fuel_switches'],
            data['enduses']['rs_all_enduses'],
            sgs_cont['rs_tech_increased_service'],
            rs_reg_enduse_tech_p_ey,
            fts_cont['rs_service_fueltype_by_p'],
            fts_cont['rs_service_tech_by_p'],
            data['assumptions']['rs_fuel_tech_p_by'],
            data['lu_reg'],
            True)

        # Regional specific sigmoid curves (Service)
        sgs_cont['ss_installed_tech'], sgs_cont['ss_sig_param_tech'], ss_service_tech_switched_p = s_generate_sigmoid.get_sig_diffusion(
            data['sim_param']['base_yr'],
            data['assumptions']['technologies'],
            data['assumptions']['ss_service_switches'],
            data['assumptions']['ss_fuel_switches'],
            data['enduses']['ss_all_enduses'],
            sgs_cont['ss_tech_increased_service'],
            ss_reg_enduse_tech_p,
            fts_cont['ss_service_fueltype_by_p'],
            fts_cont['ss_service_tech_by_p'],
            data['assumptions']['ss_fuel_tech_p_by'],
            data['lu_reg'],
            True)

        # Regional specific sigmoid curves (Industry)
        sgs_cont['is_installed_tech'], sgs_cont['is_sig_param_tech'], is_service_tech_switched_p = s_generate_sigmoid.get_sig_diffusion(
            data['sim_param']['base_yr'],
            data['assumptions']['technologies'],
            data['assumptions']['is_service_switches'],
            data['assumptions']['is_fuel_switches'],
            data['enduses']['is_all_enduses'],
            sgs_cont['is_tech_increased_service'],
            is_reg_enduse_tech_p,
            fts_cont['is_service_fueltype_by_p'],
            fts_cont['is_service_tech_by_p'],
            data['assumptions']['is_fuel_tech_p_by'],
            data['lu_reg'],
            True)
        '''
    else:
        #No spatial explicit diffusion


        # -------------------------------
        # Calculate diffusion parameters for technologies
        # -------------------------------
        rs_crit_fuel_switch = False
        rs_crit_switch_service = False
        rs_crit_fuel_switch_enduses = {}

        rs_techs = s_generate_sigmoid.get_tech_installed(data['enduses']['rs_all_enduses'], data['assumptions']['rs_fuel_switches'])
        for enduse, rs_techs in rs_techs.items():
            
            if len(rs_techs) > 0:
                rs_crit_fuel_switch = True
                rs_crit_fuel_switch_enduses[enduse] = True
            else:
                rs_crit_fuel_switch_enduses[enduse] = False
    
        if len(switches_cont['rs_service_switches']) > 0:
            rs_crit_switch_service = True
        else:
            rs_crit_switch_service = False

        ss_crit_fuel_switch = False
        ss_crit_switch_service = False
        ss_techs = s_generate_sigmoid.get_tech_installed(data['enduses']['ss_all_enduses'], data['assumptions']['ss_fuel_switches'])
        for enduse, ss_techs in ss_techs.items():
            if len(ss_techs) > 0:
                ss_crit_fuel_switch = True
        if len(switches_cont['ss_service_switches']) > 0:
            ss_crit_switch_service = True
        else:
            ss_crit_switch_service = False

        is_crit_fuel_switch = False
        is_crit_switch_service = False
        is_techs = s_generate_sigmoid.get_tech_installed(data['enduses']['is_all_enduses'], data['assumptions']['is_fuel_switches'])
        for enduse, is_techs in is_techs.items():
            if len(is_techs) > 0:
                is_crit_fuel_switch = True
        if len(switches_cont['is_service_switches']) > 0:
            is_crit_switch_service = True
        else:
            is_crit_switch_service = False

        # ===================================
        '''
        sgs_cont['rs_installed_tech'], sgs_cont['rs_sig_param_tech'] = sig_param_calculation_including_fuel_switch(
            data['sim_param']['base_yr'],
            data['assumptions']['technologies'],
            enduses=data['enduses']['rs_all_enduses'],
            fuel_switches=data['assumptions']['rs_fuel_switches'],
            service_switches=data['assumptions']['rs_service_switches'],
            service_tech_by_p=fts_cont['rs_service_tech_by_p'],
            service_fueltype_by_p=fts_cont['rs_service_fueltype_by_p'],
            share_service_tech_ey_p=switches_cont['rs_share_service_tech_ey_p'],
            fuel_tech_p_by=data['assumptions']['rs_fuel_tech_p_by'])
        
        sgs_cont['ss_installed_tech'], sgs_cont['ss_sig_param_tech'] = sig_param_calculation_including_fuel_switch(
            data['sim_param']['base_yr'],
            data['assumptions']['technologies'],
            enduses=data['enduses']['ss_all_enduses'],
            fuel_switches=data['assumptions']['ss_fuel_switches'],
            service_switches=data['assumptions']['ss_service_switches'],
            service_tech_by_p=fts_cont['ss_service_tech_by_p'],
            service_fueltype_by_p=fts_cont['ss_service_fueltype_by_p'],
            share_service_tech_ey_p=switches_cont['ss_share_service_tech_ey_p'],
            fuel_tech_p_by=data['assumptions']['ss_fuel_tech_p_by'])
        
        sgs_cont['is_installed_tech'], sgs_cont['is_sig_param_tech'] = sig_param_calculation_including_fuel_switch(
            data['sim_param']['base_yr'],
            data['assumptions']['technologies'],
            enduses=data['enduses']['is_all_enduses'],
            fuel_switches=data['assumptions']['is_fuel_switches'],
            service_switches=data['assumptions']['is_service_switches'],
            service_tech_by_p=fts_cont['is_service_tech_by_p'],
            service_fueltype_by_p=fts_cont['is_service_fueltype_by_p'],
            share_service_tech_ey_p=switches_cont['is_share_service_tech_ey_p'],
            fuel_tech_p_by=data['assumptions']['is_fuel_tech_p_by'])
        
        '''
        # -------------------------------
        # ONLY SERVICE SWITCH SO FAR Calculate technologies with more, less and constant service based on service switch assumptions
        # -------------------------------
        sgs_cont['rs_sig_param_tech'] = {}
        sgs_cont['ss_sig_param_tech'] = {}
        sgs_cont['is_sig_param_tech'] = {}

        sgs_cont['rs_installed_tech'] = {}
        sgs_cont['ss_installed_tech'] = {}
        sgs_cont['is_installed_tech'] = {}

        sgs_cont['rs_tech_increased_service'], sgs_cont['rs_tech_decreased_share'], sgs_cont['rs_tech_constant_share'] = {}, {}, {}
        for enduse in data['enduses']['rs_all_enduses']:
            sgs_cont['rs_tech_increased_service'][enduse] = {}
            sgs_cont['rs_tech_decreased_share'][enduse]  = {}
            sgs_cont['rs_tech_constant_share'][enduse] = {}

            sgs_cont['rs_installed_tech'][enduse] = {}

        sgs_cont['ss_tech_increased_service'], sgs_cont['ss_tech_decreased_share'], sgs_cont['ss_tech_constant_share'] = {}, {}, {}
        for enduse in data['enduses']['ss_all_enduses']:
            sgs_cont['ss_tech_increased_service'][enduse] = {}
            sgs_cont['ss_tech_decreased_share'][enduse]  = {}
            sgs_cont['ss_tech_constant_share'][enduse] = {}
            
            sgs_cont['ss_installed_tech'][enduse] = {}

        sgs_cont['is_tech_increased_service'], sgs_cont['is_tech_decreased_share'], sgs_cont['is_tech_constant_share'] = {}, {}, {}
        for enduse in data['enduses']['is_all_enduses']:
            sgs_cont['is_tech_increased_service'][enduse] = {}
            sgs_cont['is_tech_decreased_share'][enduse]  = {}
            sgs_cont['is_tech_constant_share'][enduse] = {}
            
            sgs_cont['is_installed_tech'][enduse] = {}
   
    
        if rs_crit_switch_service: #MAKE ENDUSE SPECIFIC

            # Calculate only from service switch
            sgs_cont['rs_tech_increased_service'], sgs_cont['rs_tech_decreased_share'], sgs_cont['rs_tech_constant_share'] = s_generate_sigmoid.get_tech_future_service(
                fts_cont['rs_service_tech_by_p'], switches_cont['rs_share_service_tech_ey_p'])

            # Calculate sigmoid diffusion parameters (if no switches, no calculations)
            rs_service_tech_switched_p, rs_l_values_sig = s_generate_sigmoid.get_sig_diffusion_service(
                data['assumptions']['technologies'],
                data['assumptions']['rs_service_switches'],
                data['enduses']['rs_all_enduses'],
                sgs_cont['rs_tech_increased_service'],
                switches_cont['rs_share_service_tech_ey_p'])

        if rs_crit_fuel_switch:
            print("... calculate sigmoid based on fuel switches")

            rs_service_tech_switched_p, rs_l_values_sig = s_generate_sigmoid.calc_diff_fuel_switch(
                data['assumptions']['technologies'],
                data['assumptions']['rs_fuel_switches'],
                data['enduses']['rs_all_enduses'],
                fts_cont['rs_service_fueltype_by_p'],
                fts_cont['rs_service_tech_by_p'],
                data['assumptions']['rs_fuel_tech_p_by'])

            # Convert fuel switch to service switches
            switches_cont['rs_service_switches'] = convert_fuel_switches_to_service_switches(
                all_techs=[rs_service_tech_switched_p],
                fuel_switches=data['assumptions']['rs_fuel_switches'])

        if rs_crit_switch_service or rs_crit_fuel_switch:
            sgs_cont['rs_installed_tech'], sgs_cont['rs_sig_param_tech'] = s_generate_sigmoid.calc_sigm_parameters(
                data['sim_param']['base_yr'],
                data['assumptions']['technologies'],
                data['enduses']['rs_all_enduses'],
                rs_l_values_sig,
                sgs_cont['rs_tech_increased_service'], #TODO DOUBLE
                rs_service_tech_switched_p,
                switches_cont['rs_service_switches'],
                sgs_cont['rs_tech_increased_service'])

        # SERVICE
        if ss_crit_switch_service:
            print("..ss calculate service switch")
            # Calculate only from service switch
            sgs_cont['ss_tech_increased_service'], sgs_cont['ss_tech_decreased_share'], sgs_cont['ss_tech_constant_share'] = s_generate_sigmoid.get_tech_future_service(
                fts_cont['ss_service_tech_by_p'], switches_cont['ss_share_service_tech_ey_p'])

            # Calculate sigmoid diffusion parameters
            ss_service_tech_switched_p, ss_l_values_sig = s_generate_sigmoid.get_sig_diffusion_service(
                data['assumptions']['technologies'],
                data['assumptions']['ss_service_switches'],
                data['enduses']['ss_all_enduses'],
                sgs_cont['ss_tech_increased_service'],
                switches_cont['ss_share_service_tech_ey_p'])

        if ss_crit_fuel_switch:
            ss_service_tech_switched_p, ss_l_values_sig = s_generate_sigmoid.calc_diff_fuel_switch(
                data['assumptions']['technologies'],
                data['assumptions']['ss_fuel_switches'],
                data['enduses']['ss_all_enduses'],
                fts_cont['ss_service_fueltype_by_p'],
                fts_cont['ss_service_tech_by_p'],
                data['assumptions']['ss_fuel_tech_p_by'])

            print("... calculate sigmoid based on fuel switches" + str(ss_l_values_sig))
            switches_cont['ss_service_switches'] = convert_fuel_switches_to_service_switches(
                all_techs=[ss_service_tech_switched_p],
                fuel_switches=data['assumptions']['ss_fuel_switches'])

            sgs_cont['ss_tech_increased_service'], sgs_cont['ss_tech_decreased_share'], sgs_cont['ss_tech_constant_share'] = s_generate_sigmoid.get_tech_future_service(
                fts_cont['ss_service_tech_by_p'], ss_service_tech_switched_p)

        if ss_crit_switch_service or ss_crit_fuel_switch:
            #installed_technologies = 1somhoe wrong
    
            sgs_cont['ss_installed_tech'], sgs_cont['ss_sig_param_tech'] = s_generate_sigmoid.calc_sigm_parameters(
                data['sim_param']['base_yr'],
                data['assumptions']['technologies'],
                data['enduses']['ss_all_enduses'],
                ss_l_values_sig,
                sgs_cont['ss_tech_increased_service'],
                ss_service_tech_switched_p,
                switches_cont['ss_service_switches'],
                sgs_cont['ss_tech_increased_service'])

        # Industry
        if is_crit_switch_service:
            print("..ss calculate service switch")
            # Calculate only from service switch
            sgs_cont['is_tech_increased_service'], sgs_cont['is_tech_decreased_share'], sgs_cont['is_tech_constant_share'] = s_generate_sigmoid.get_tech_future_service(
                fts_cont['is_service_tech_by_p'], switches_cont['is_share_service_tech_ey_p'])

            # Calculate sigmoid diffusion parameters (if no switches, no calculations)
            is_service_tech_switched_p, l_values_sig = s_generate_sigmoid.get_sig_diffusion_service(
                data['assumptions']['technologies'],
                data['assumptions']['is_service_switches'],
                data['enduses']['is_all_enduses'],
                sgs_cont['is_tech_increased_service'],
                switches_cont['is_share_service_tech_ey_p'])

        if is_crit_fuel_switch:
            is_service_tech_switched_p, l_values_sig = s_generate_sigmoid.calc_diff_fuel_switch(
                data['assumptions']['technologies'],
                data['assumptions']['is_fuel_switches'],
                data['enduses']['is_all_enduses'],
                fts_cont['is_service_fueltype_by_p'],
                fts_cont['is_service_tech_by_p'],
                data['assumptions']['is_fuel_tech_p_by'])

            print("... calculate sigmoid based on fuel switches")
            switches_cont['is_service_switches'] = convert_fuel_switches_to_service_switches(
                all_techs=[is_service_tech_switched_p],
                fuel_switches=data['assumptions']['is_fuel_switches'])

            # CALCULATE TECH AGAINS
            sgs_cont['is_tech_increased_service'], sgs_cont['is_tech_decreased_share'], sgs_cont['is_tech_constant_share'] = s_generate_sigmoid.get_tech_future_service(
                fts_cont['is_service_tech_by_p'], is_service_tech_switched_p)

        if is_crit_switch_service or is_crit_fuel_switch:
            sgs_cont['is_installed_tech'], sgs_cont['is_sig_param_tech'] = s_generate_sigmoid.calc_sigm_parameters(
                data['sim_param']['base_yr'],
                data['assumptions']['technologies'],
                data['enduses']['is_all_enduses'],
                l_values_sig,
                sgs_cont['is_tech_increased_service'],
                is_service_tech_switched_p,
                switches_cont['is_service_switches'],
                sgs_cont['is_tech_increased_service'])

    return fts_cont, sgs_cont, sd_cont, switches_cont

def sum_across_sectors_all_regs(fuel_disagg_reg):
    """Sum fuel across all sectors for every region

    Arguments
    ---------
    fuel_disagg_reg : dict
        Fuel per region, sector and enduse

    Returns
    -------
    fuel_aggregated : dict
        Aggregated fuel per region and enduse
    """
    fuel_aggregated = {}
    for reg, entries in fuel_disagg_reg.items():
        enduses = []
        fuel_aggregated[reg] = {}
        for sector in entries:
            for enduse in entries[sector]:
                fuel_aggregated[reg][enduse] = 0
                enduses.append(enduse)
            break

        for sector in entries:
            for enduse in entries[sector]:
                fuel_aggregated[reg][enduse] += np.sum(entries[sector][enduse])

    return fuel_aggregated

def convert_fuel_switches_to_service_switches(all_techs, fuel_switches):
    """TODO
    """

    service_switches_after_fuel_switch = []
    for tech_types in all_techs:
        for enduse in tech_types:
            for tech in tech_types[enduse]:
                if tech =='dummy_tech':
                    pass
                else:
                    # GET YEAR OF AN SWITCH (all the same) TODO
                    for fuelswitch in fuel_switches:
                        if fuelswitch.enduse == enduse: # and fuelswitch.technology_install == tech:
                            switch_yr = fuelswitch.switch_yr
                            break

                    switch_new = read_data.ServiceSwitch(
                        enduse=enduse,
                        technology_install=tech,
                        service_share_ey=tech_types[enduse][tech],
                        switch_yr=switch_yr)
                        
                    service_switches_after_fuel_switch.append(switch_new)

    return service_switches_after_fuel_switch



def sig_param_calculation_including_fuel_switch(
        base_yr,
        technologies,
        enduses, #data['enduses']['rs_all_enduses']
        fuel_switches, #data['assumptions']['rs_fuel_switches']
        service_switches, #data['assumptions']['rs_service_switches']
        service_tech_by_p, #fts_cont['rs_service_tech_by_p'],
        service_fueltype_by_p,  # fts_cont['rs_service_fueltype_by_p'],
        share_service_tech_ey_p, #switches_cont['rs_share_service_tech_ey_p']
        fuel_tech_p_by #data['assumptions']['rs_fuel_tech_p_by']
    ):
    """

    Returns
    sgs_cont['rs_installed_tech'],
    sgs_cont['rs_sig_param_tech'],

    sgs_cont['rs_tech_increased_service'],
    sgs_cont['rs_tech_decreased_share'],
    sgs_cont['rs_tech_constant_share']

    sgs_cont['rs_installed_tech']


    """
    crit_fuel_switch = False
    rs_crit_switch_service = False
    crit_fuel_switch_enduses = {}

    techs = s_generate_sigmoid.get_tech_installed(enduses, fuel_switches)

    for enduse, techs in techs.items():

        if len(techs) > 0:
            crit_fuel_switch = True
            crit_fuel_switch_enduses[enduse] = True #TODO USE FOR ENDUS SPECIFIC
        else:
            crit_fuel_switch_enduses[enduse] = False

    if len(service_switches) > 0:
        rs_crit_switch_service = True
    else:
        rs_crit_switch_service = False

    # -------------------------------
    # ONLY SERVICE SWITCH SO FAR Calculate technologies with more, less and constant service based on service switch assumptions
    # -------------------------------

    tech_increased_service, tech_decrased_share, tech_constant_share = {}, {}, {}
    for enduse in enduses:
        tech_increased_service[enduse] = {}
        tech_decrased_share[enduse]  = {}
        tech_constant_share[enduse] = {}

    if rs_crit_switch_service:

        # Calculate only from service switch #ENDUSE OK
        tech_increased_service, tech_decrased_share, tech_constant_share = s_generate_sigmoid.get_tech_future_service(
            service_tech_by_p, share_service_tech_ey_p)

        # Calculate sigmoid diffusion parameters (if no switches, no calculations) #ENDUSE OK
        rs_service_tech_switched_p, rs_l_values_sig = s_generate_sigmoid.get_sig_diffusion_service(
            technologies,
            service_switches,
            enduses,
            tech_increased_service,
            share_service_tech_ey_p)

    if crit_fuel_switch:
        print("... calculate sigmoid based on fuel switches")
        # TROUBELING
        rs_service_tech_switched_p, rs_l_values_sig = s_generate_sigmoid.calc_diff_fuel_switch(
            technologies,
            fuel_switches,
            enduses,
            service_fueltype_by_p,
            service_tech_by_p,
            fuel_tech_p_by)
        #OK
        # Convert fuel switch to service switches
        service_switches_fuelswitch = convert_fuel_switches_to_service_switches(
            all_techs=[rs_service_tech_switched_p],
            fuel_switches=fuel_switches)

        service_switches = service_switches_fuelswitch

    # ok
    if rs_crit_switch_service or crit_fuel_switch:
        installed_tech, sig_param_tech = s_generate_sigmoid.calc_sigm_parameters(
            base_yr,
            technologies,
            enduses,
            rs_l_values_sig,
            tech_increased_service, #TODO DOUBLE
            rs_service_tech_switched_p,
            service_switches,
            tech_increased_service)

    return installed_tech, sig_param_tech, tech_increased_service, tech_decrased_share, tech_constant_share

