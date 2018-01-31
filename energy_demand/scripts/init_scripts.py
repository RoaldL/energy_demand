"""Script functions which are executed after
model installation and after each scenario definition
"""
import os
import logging
from collections import defaultdict
import numpy as np

from energy_demand.read_write import data_loader
from energy_demand.scripts import s_fuel_to_service
from energy_demand.scripts import s_generate_sigmoid
from energy_demand.scripts import s_disaggregation
from energy_demand.basic import basic_functions
from energy_demand.basic import logger_setup
from energy_demand.technologies import fuel_service_switch
from energy_demand.geography import spatial_diffusion
from energy_demand.read_write import read_data

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

    init_cont = defaultdict(dict)
    fuel_disagg = {}

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
    basic_functions.create_folder(data['local_paths']['data_results_model_run_pop'])
    basic_functions.create_folder(data['local_paths']['data_results_validation'])

    # ---------------------------------------
    # Load local datasets for disaggregateion
    # ---------------------------------------
    data['scenario_data']['employment_stats'] = data_loader.read_employment_stats(
        data['local_paths']['path_employment_statistics'])

    # -------------------
    # Disaggregate fuel for all regions
    # -------------------
    fuel_disagg['rs_fuel_disagg'], fuel_disagg['ss_fuel_disagg'], fuel_disagg['is_fuel_disagg'] = s_disaggregation.disaggregate_base_demand(
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
    # Convert base year fuel input assumptions to energy service
    # on a national scale
    # -------------------

    # Residential
    init_cont['rs_service_tech_by_p'], init_cont['rs_service_fueltype_tech_by_p'], init_cont['rs_service_fueltype_by_p'] = s_fuel_to_service.get_service_fueltype_tech(
        data['assumptions']['tech_list'],
        data['lookups']['fueltypes'],
        data['assumptions']['rs_fuel_tech_p_by'],
        data['fuels']['rs_fuel_raw_data_enduses'],
        data['assumptions']['technologies'])

    # Service
    ss_aggr_sector_fuels = s_fuel_to_service.sum_fuel_enduse_sectors(
        data['fuels']['ss_fuel_raw_data_enduses'],
        data['enduses']['ss_all_enduses'],
        data['lookups']['fueltypes_nr'])
    init_cont['ss_service_tech_by_p'], init_cont['ss_service_fueltype_tech_by_p'], init_cont['ss_service_fueltype_by_p'] = s_fuel_to_service.get_service_fueltype_tech(
        data['assumptions']['tech_list'],
        data['lookups']['fueltypes'],
        data['assumptions']['ss_fuel_tech_p_by'],
        ss_aggr_sector_fuels,
        data['assumptions']['technologies'])

    # Industry
    is_aggr_sector_fuels = s_fuel_to_service.sum_fuel_enduse_sectors(
        data['fuels']['is_fuel_raw_data_enduses'],
        data['enduses']['is_all_enduses'],
        data['lookups']['fueltypes_nr'])
    init_cont['is_service_tech_by_p'], init_cont['is_service_fueltype_tech_by_p'], init_cont['is_service_fueltype_by_p'] = s_fuel_to_service.get_service_fueltype_tech(
        data['assumptions']['tech_list'],
        data['lookups']['fueltypes'],
        data['assumptions']['is_fuel_tech_p_by'],
        is_aggr_sector_fuels,
        data['assumptions']['technologies'])

    # ------------------------------------
    # Autocomplement defined service switches
    # with technologies not explicitly specified in switch
    # on a national scale
    # ------------------------------------
    init_cont['rs_service_switches'] = fuel_service_switch.autocomplete_switches(
        data['assumptions']['rs_service_switches'],
        data['assumptions']['rs_specified_tech_enduse_by'],
        init_cont['rs_service_tech_by_p'])

    init_cont['ss_service_switches'] = fuel_service_switch.autocomplete_switches(
        data['assumptions']['ss_service_switches'],
        data['assumptions']['ss_specified_tech_enduse_by'],
        init_cont['ss_service_tech_by_p'])

    init_cont['is_service_switches'] = fuel_service_switch.autocomplete_switches(
        data['assumptions']['is_service_switches'],
        data['assumptions']['is_specified_tech_enduse_by'],
        init_cont['is_service_tech_by_p'])

    # ------------
    # Capacity installations (on a national scale)
    # ------------
    init_cont['rs_service_switches'] = fuel_service_switch.capacity_installations(
        init_cont['rs_service_switches'],
        data['assumptions']['capacity_switches']['rs_capacity_switches'],
        data['assumptions']['technologies'],
        data['assumptions']['enduse_overall_change']['other_enduse_mode_info'],
        data['fuels']['rs_fuel_raw_data_enduses'],
        data['assumptions']['rs_fuel_tech_p_by'],
        data['sim_param']['base_yr'])

    init_cont['ss_service_switches'] = fuel_service_switch.capacity_installations(
        init_cont['ss_service_switches'],
        data['assumptions']['capacity_switches']['ss_capacity_switches'],
        data['assumptions']['technologies'],
        data['assumptions']['enduse_overall_change']['other_enduse_mode_info'],
        ss_aggr_sector_fuels,
        data['assumptions']['ss_fuel_tech_p_by'],
        data['sim_param']['base_yr'])

    init_cont['is_service_switches'] = fuel_service_switch.capacity_installations(
        init_cont['is_service_switches'],
        data['assumptions']['capacity_switches']['is_capacity_switches'],
        data['assumptions']['technologies'],
        data['assumptions']['enduse_overall_change']['other_enduse_mode_info'],
        is_aggr_sector_fuels,
        data['assumptions']['is_fuel_tech_p_by'],
        data['sim_param']['base_yr'])

    # -------------------------------------
    # Get service shares of technologies for future year by considering
    # SERVICE switch on a national scale
    # -------------------------------------
    rs_share_service_tech_ey_p = fuel_service_switch.get_share_service_tech_ey(
        init_cont['rs_service_switches'],
        data['assumptions']['rs_specified_tech_enduse_by'])
    ss_share_service_tech_ey_p = fuel_service_switch.get_share_service_tech_ey(
        init_cont['ss_service_switches'],
        data['assumptions']['ss_specified_tech_enduse_by'])
    is_share_service_tech_ey_p = fuel_service_switch.get_share_service_tech_ey(
        init_cont['is_service_switches'],
        data['assumptions']['is_specified_tech_enduse_by'])

    # -------------------------------
    # Calculate sigmoid diffusion parameters
    # (either for every region or aggregated for all regions)
    # -------------------------------

    # -------------------------------
    # Spatially differentiated modelling
    # -------------------------------
    if data['criterias']['spatial_exliclit_diffusion']:
        rs_reg_share_service_tech_ey_p, ss_reg_share_service_tech_ey_p, is_reg_share_service_tech_ey_p, init_cont = spatial_diffusion.spatially_differentiated_modelling(
            data['lu_reg'],
            data['enduses']['all_enduses'],
            init_cont,
            sum_across_sectors_all_regs,
            rs_share_service_tech_ey_p,
            ss_share_service_tech_ey_p,
            is_share_service_tech_ey_p)

        regions = data['lu_reg']
        regional_specific = True
        rs_share_service_tech_ey_p = rs_reg_share_service_tech_ey_p
        ss_share_service_tech_ey_p = ss_reg_share_service_tech_ey_p
        is_share_service_tech_ey_p = is_reg_share_service_tech_ey_p
    else:
        regions = False
        regional_specific = False

    # ---------------------------------------
    # Calculate sigmoid diffusion
    #
    # Non spatiall differentiated modelling of
    # technology diffusion (same diffusion pattern for
    # the whole UK) or spatiall differentiated (every region)
    # ---------------------------------------
    for enduse in data['enduses']['rs_all_enduses']:
        init_cont['rs_sig_param_tech'][enduse], init_cont['rs_tech_increased_service'][enduse], init_cont['rs_tech_decreased_service'][enduse], init_cont['rs_tech_constant_service'][enduse], init_cont['rs_service_switch'][enduse] = sig_param_calculation_including_fuel_switch(
            data['sim_param']['base_yr'],
            data['assumptions']['technologies'],
            enduse=enduse,
            fuel_switches=data['assumptions']['rs_fuel_switches'],
            service_switches=init_cont['rs_service_switches'],
            service_tech_by_p=init_cont['rs_service_tech_by_p'][enduse],
            service_fueltype_by_p=init_cont['rs_service_fueltype_by_p'][enduse],
            share_service_tech_ey_p=rs_share_service_tech_ey_p[enduse],
            fuel_tech_p_by=data['assumptions']['rs_fuel_tech_p_by'][enduse],
            regions=regions,
            regional_specific=regional_specific)

    for enduse in data['enduses']['ss_all_enduses']:
        init_cont['ss_sig_param_tech'][enduse], init_cont['ss_tech_increased_service'][enduse], init_cont['ss_tech_decreased_service'][enduse], init_cont['ss_tech_constant_service'][enduse], init_cont['ss_service_switch'][enduse] = sig_param_calculation_including_fuel_switch(
            data['sim_param']['base_yr'],
            data['assumptions']['technologies'],
            enduse=enduse,
            fuel_switches=data['assumptions']['ss_fuel_switches'],
            service_switches=init_cont['ss_service_switches'],
            service_tech_by_p=init_cont['ss_service_tech_by_p'][enduse],
            service_fueltype_by_p=init_cont['ss_service_fueltype_by_p'][enduse],
            share_service_tech_ey_p=ss_share_service_tech_ey_p[enduse],
            fuel_tech_p_by=data['assumptions']['ss_fuel_tech_p_by'][enduse],
            regions=regions,
            regional_specific=regional_specific)

    for enduse in data['enduses']['is_all_enduses']:
        init_cont['is_sig_param_tech'][enduse], init_cont['is_tech_increased_service'][enduse], init_cont['is_tech_decreased_service'][enduse], init_cont['is_tech_constant_service'][enduse], init_cont['is_service_switch'][enduse] = sig_param_calculation_including_fuel_switch(
            data['sim_param']['base_yr'],
            data['assumptions']['technologies'],
            enduse=enduse,
            fuel_switches=data['assumptions']['is_fuel_switches'],
            service_switches=init_cont['is_service_switches'],
            service_tech_by_p=init_cont['is_service_tech_by_p'][enduse],
            service_fueltype_by_p=init_cont['is_service_fueltype_by_p'][enduse],
            share_service_tech_ey_p=is_share_service_tech_ey_p[enduse],
            fuel_tech_p_by=data['assumptions']['is_fuel_tech_p_by'][enduse],
            regions=regions,
            regional_specific=regional_specific)
    
    print("... finished scenario initialisation")
    return dict(init_cont), fuel_disagg

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
        fuel_aggregated[reg] = {}
        for enduse in entries:
            for sector in entries[enduse]:
                fuel_aggregated[reg][enduse] = 0

        for enduse in entries:
            for sector in entries[enduse]:
                fuel_aggregated[reg][enduse] += np.sum(entries[enduse][sector])

    return fuel_aggregated

def convert_fuel_switches_to_service_switches(
        enduse,
        service_tech_switched_p,
        enduse_fuel_switches,
        regions=False,
        regional_specific=False
    ):
    """Convert fuel switches to service switches.
    TODO IMPROVe
    Arguments
    ---------
    enduse : str
        Enduse
    service_tech_switched_p : dict
        Fraction of total service of technologies after switch
    enduse_fuel_switches : list
        Fuel switches of an enduse
    regions : dict, default=False
        All regions
    regional_specific : bool, default=False
        Criteria wheter region specific calculations

    Returns
    -------
    service_switches_after_fuel_switch : dict
        Changed services witches including fuel switches
    """
    if regional_specific:
        new_service_switches = {}

        for reg in regions:
            new_service_switches[reg] = []

            for tech in service_tech_switched_p[reg]:
                if tech == 'dummy_tech':
                    pass
                else:
                    # GET YEAR OF AN SWITCH (all the same) TODO
                    for fuelswitch in enduse_fuel_switches:
                        switch_yr = fuelswitch.switch_yr
                        break

                    switch_new = read_data.ServiceSwitch(
                        enduse=enduse,
                        technology_install=tech,
                        service_share_ey=service_tech_switched_p[reg][tech],
                        switch_yr=switch_yr)

                    new_service_switches[reg].append(switch_new)
    else:
        new_service_switches = []

        for tech in service_tech_switched_p:
            if tech == 'dummy_tech':
                pass
            else:
                # GET YEAR OF AN SWITCH (all the same) TODO
                for fuelswitch in enduse_fuel_switches:
                    switch_yr = fuelswitch.switch_yr
                    break

                switch_new = read_data.ServiceSwitch(
                    enduse=enduse,
                    technology_install=tech,
                    service_share_ey=service_tech_switched_p[tech],
                    switch_yr=switch_yr)

                new_service_switches.append(switch_new)

    return new_service_switches

def sig_param_calculation_including_fuel_switch(
        base_yr,
        technologies,
        enduse,
        fuel_switches,
        service_switches,
        service_tech_by_p,
        service_fueltype_by_p,
        share_service_tech_ey_p,
        fuel_tech_p_by,
        regions=False,
        regional_specific=False
    ):
    """Calculate sigmoid paramaters and consider fuel switches

    Arguments
    ---------
    base_yr : int
        Base year
    technologies : dict
        technologies
    enduse : str
        enduse
    fuel_switches : dict
        fuel switches
    service_switches : dict
        service switches
    service_tech_by_p : dict

    service_fueltype_by_p : dict

    share_service_tech_ey_p : dict

    fuel_tech_p_by : dict

    regions : dict
        Regions
    regional_specific : bool, default=False
        criteria
    """
    # ----------------------------------------
    # Test if fuel switch is defined for enduse
    # Get affected technologies in fuel switch
    # ----------------------------------------
    tech_switch_affected = s_generate_sigmoid.get_tech_installed(
        enduse, fuel_switches)

    # Test if any switch is implemented for enduse
    if len(tech_switch_affected) > 0:
        crit_fuel_switch = True
    else:
        crit_fuel_switch = False

    # ------------------------------------------
    # Test if service swich is defined for enduse
    # ------------------------------------------
    service_switches_enduse = fuel_service_switch.get_fuel_switches_enduse(
        service_switches, enduse)

    if len(service_switches_enduse) > 0:
        crit_switch_service = True
    else:
        crit_switch_service = False

    # --------
    # Test if a service and fuel switch are defined simultaneously
    # ---------
    if crit_switch_service and crit_fuel_switch:
        print("Error: Can't define fuel and service switch for {}".format(enduse))

    # -------------------------------
    # Initialisations
    # -------------------------------
    tech_increased_service = {}
    tech_decrased_share = {}
    tech_constant_service = {}
    sig_param_tech = {}

    if regional_specific:
        service_switches_out = {}
        for region in regions:
            sig_param_tech[region] = []
            tech_increased_service[region] = []
            tech_decrased_share[region] = []
            tech_constant_service[region] = []
            service_switches_out[region] = service_switches_enduse
    else:
        service_switches_out = service_switches_enduse

    # -------------------------------
    # SERVICE switch
    # Calculate technologies with more, less and constant service based on service switch assumptions
    # Calculate l_values
    # -------------------------------
    if crit_switch_service:
        print("... calculate sigmoid based on SERVICE switches " )
        print(share_service_tech_ey_p)
        print(sum(share_service_tech_ey_p.values()))
        print("... calculate sigmoid based on SERVICE switches ")
        print(service_tech_by_p)
        print(sum(service_tech_by_p.values()))
        # Calculate only from service switch
        tech_increased_service, tech_decrased_share, tech_constant_service = s_generate_sigmoid.get_tech_future_service(
            service_tech_by_p,
            share_service_tech_ey_p,
            regions=regions,
            regional_specific=regional_specific)

        service_tech_switched_p = share_service_tech_ey_p

        # Calculate sigmoid diffusion parameters (if no switches, no calculations)
        l_values_sig = s_generate_sigmoid.get_l_values(
            technologies,
            tech_increased_service,
            regions=regions,
            regional_specific=regional_specific)

    # -------------
    # FUEL SWITCH
    # -------------
    if crit_fuel_switch:
        print("... calculate sigmoid based on FUEL switches")

        # Get fuel switches of enduse
        enduse_fuel_switches = fuel_service_switch.get_fuel_switches_enduse(fuel_switches, enduse)

        # Tech with lager service shares in end year (installed in fuel switch)
        installed_tech = s_generate_sigmoid.get_tech_installed(enduse, enduse_fuel_switches)

        # ??
        service_tech_switched_p, l_values_sig = s_generate_sigmoid.calc_diff_fuel_switch(
            technologies,
            enduse_fuel_switches,
            installed_tech,
            service_fueltype_by_p,
            service_tech_by_p,
            fuel_tech_p_by,
            regions=regions,
            regional_specific=regional_specific)

        # Convert fuel switch to service switches
        service_switches_out = convert_fuel_switches_to_service_switches(
            enduse=enduse,
            service_tech_switched_p=service_tech_switched_p,
            enduse_fuel_switches=enduse_fuel_switches,
            regions=regions,
            regional_specific=regional_specific)

        # Calculate only from fuel switch
        share_service_tech_ey_p = fuel_service_switch.switches_to_dict(service_switches_out, regional_specific)

        tech_increased_service, tech_decrased_share, tech_constant_service = s_generate_sigmoid.get_tech_future_service(
            service_tech_by_p=service_tech_by_p,
            service_tech_ey_p=share_service_tech_ey_p,
            regions=regions,
            regional_specific=regional_specific)

    if crit_switch_service or crit_fuel_switch:
        print("... calculate sigmoid for techs defined in switch")
        #Calculate sigmoid for technologies defined in switch
        sig_param_tech = s_generate_sigmoid.calc_sigm_parameters(
            base_yr,
            technologies,
            l_values_sig,
            service_tech_by_p,
            service_tech_switched_p,
            service_switches_out,
            tech_increased_service,
            regions=regions,
            regional_specific=regional_specific)
    else:
        pass #no switches are defined

    return sig_param_tech, tech_increased_service, tech_decrased_share, tech_constant_service, service_switches_out
