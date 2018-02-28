"""Script functions which are executed after
model installation and after each scenario definition
"""
import os
import sys
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
    logging.info("... Start initialisation scripts")

    init_cont = defaultdict(dict)
    fuel_disagg = {}

    # Create logger
    logger_setup.set_up_logger(
        os.path.join(path_data_ed, "scenario_init.log"))

    # --------------------------------------------
    # Delete results from previous model runs and initialise folders
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
    basic_functions.create_folder(data['local_paths']['data_results_model_runs'])

    # ---------------------------------------
    # Load local datasets for disaggregateion
    # ---------------------------------------
    data['scenario_data']['employment_stats'] = data_loader.read_employment_stats(
        data['paths']['path_employment_statistics'])

    # ---------------------------------------
    # Disaggregate fuel for all regions init_cont
    # ---------------------------------------
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

    # ---------------------------------------
    # Convert base year fuel input assumptions to
    # energy service on a national scale
    # ---------------------------------------
    # Residential
    init_cont['rs_s_tech_by_p'], init_cont['rs_s_fueltype_tech_by_p'], init_cont['rs_s_fueltype_by_p'] = s_fuel_to_service.get_s_fueltype_tech(
        data['enduses']['rs_enduses'],
        data['assumptions']['tech_list'],
        data['lookups']['fueltypes'],
        data['assumptions']['rs_fuel_tech_p_by'],
        data['fuels']['rs_fuel_raw'],
        data['assumptions']['technologies'])

    # Service
    init_cont['ss_s_tech_by_p'] = {}
    for sector in data['sectors']['ss_sectors']:
        init_cont['ss_s_tech_by_p'][sector], init_cont['ss_s_fueltype_tech_by_p'][sector], init_cont['ss_s_fueltype_by_p'][sector] = s_fuel_to_service.get_s_fueltype_tech(
            data['enduses']['ss_enduses'],
            data['assumptions']['tech_list'],
            data['lookups']['fueltypes'],
            data['assumptions']['ss_fuel_tech_p_by'],
            data['fuels']['ss_fuel_raw'],
            data['assumptions']['technologies'],
            sector)

    # Industry
    init_cont['is_s_tech_by_p'] = {}
    for sector in data['sectors']['is_sectors']:
        init_cont['is_s_tech_by_p'][sector], init_cont['is_s_fueltype_tech_by_p'][sector], init_cont['is_s_fueltype_by_p'][sector] = s_fuel_to_service.get_s_fueltype_tech(
            data['enduses']['is_enduses'],
            data['assumptions']['tech_list'],
            data['lookups']['fueltypes'],
            data['assumptions']['is_fuel_tech_p_by'],
            data['fuels']['is_fuel_raw'],
            data['assumptions']['technologies'],
            sector)

    # ------------------------------------
    # Autocomplement defined service switches with technologies not
    # explicitly specified in switch on a national scale
    # ------------------------------------
    logging.debug("... autocompleting switches")
    init_cont['rs_service_switches'] = data['assumptions']['rs_service_switches']
    init_cont['ss_service_switches'] = data['assumptions']['ss_service_switches']
    init_cont['is_service_switches'] = data['assumptions']['is_service_switches']

    rs_service_switches_completed = fuel_service_switch.autocomplete_switches(
        init_cont['rs_service_switches'],
        data['assumptions']['rs_specified_tech_enduse_by'],
        init_cont['rs_s_tech_by_p'])

    ss_service_switches_completed = {}
    for sector in data['sectors']['ss_sectors']:
        ss_service_switches_completed[sector] = fuel_service_switch.autocomplete_switches(
            init_cont['ss_service_switches'],
            data['assumptions']['ss_specified_tech_enduse_by'],
            init_cont['ss_s_tech_by_p'][sector])

    is_service_switches_completed = {}
    for sector in data['sectors']['is_sectors']:
        is_service_switches_completed[sector] = fuel_service_switch.autocomplete_switches(
            init_cont['is_service_switches'],
            data['assumptions']['is_specified_tech_enduse_by'],
            init_cont['is_s_tech_by_p'][sector])

    # ------------------------------------
    # Capacity switches (installations)
    # ======================
    # Calculate service shares considering potential capacity installations
    # on a national scale
    # ------------------------------------
    logging.debug("... processing capacity switches")
    # Residential
    init_cont['rs_service_switches'] = fuel_service_switch.capacity_switch(
        init_cont['rs_service_switches'],
        data['assumptions']['capacity_switches']['rs_capacity_switches'],
        data['assumptions']['technologies'],
        data['assumptions']['enduse_overall_change']['other_enduse_mode_info'],
        data['fuels']['rs_fuel_raw'],
        data['assumptions']['rs_fuel_tech_p_by'],
        data['sim_param']['base_yr'])

    # Service
    ss_aggr_sector_fuels = s_fuel_to_service.sum_fuel_enduse_sectors(
        data['fuels']['ss_fuel_raw'],
        data['enduses']['ss_enduses'],
        data['lookups']['fueltypes_nr'])

    init_cont['ss_service_switches'] = fuel_service_switch.capacity_switch(
        init_cont['ss_service_switches'],
        data['assumptions']['capacity_switches']['ss_capacity_switches'],
        data['assumptions']['technologies'],
        data['assumptions']['enduse_overall_change']['other_enduse_mode_info'],
        ss_aggr_sector_fuels,
        data['assumptions']['ss_fuel_tech_p_by'],
        data['sim_param']['base_yr'])

    # Industry
    is_aggr_sector_fuels = s_fuel_to_service.sum_fuel_enduse_sectors(
        data['fuels']['is_fuel_raw'],
        data['enduses']['is_enduses'],
        data['lookups']['fueltypes_nr'])

    init_cont['is_service_switches'] = fuel_service_switch.capacity_switch(
        init_cont['is_service_switches'],
        data['assumptions']['capacity_switches']['is_capacity_switches'],
        data['assumptions']['technologies'],
        data['assumptions']['enduse_overall_change']['other_enduse_mode_info'],
        is_aggr_sector_fuels,
        data['assumptions']['is_fuel_tech_p_by'],
        data['sim_param']['base_yr'])

    # ------------------------------------
    # Service switches
    # ================
    #
    # Get service shares of technologies for future year by considering
    # service switches (defined on a national scale)
    # ------------------------------------
    logging.debug("... processing service switches")
    rs_share_s_tech_ey_p = fuel_service_switch.get_share_s_tech_ey(
        rs_service_switches_completed,
        data['assumptions']['rs_specified_tech_enduse_by'])

    ss_share_s_tech_ey_p = {}
    for sector in data['sectors']['ss_sectors']:
        ss_share_s_tech_ey_p[sector] = fuel_service_switch.get_share_s_tech_ey(
            ss_service_switches_completed[sector],
            data['assumptions']['ss_specified_tech_enduse_by'])

    is_share_s_tech_ey_p = {}
    for sector in data['sectors']['is_sectors']:
        is_share_s_tech_ey_p[sector] = fuel_service_switch.get_share_s_tech_ey(
            is_service_switches_completed[sector],
            data['assumptions']['is_specified_tech_enduse_by'])

    # Spatial explicit modelling
    if data['criterias']['spatial_exliclit_diffusion']:
        rs_reg_share_s_tech_ey_p, ss_reg_share_s_tech_ey_p, is_reg_share_s_tech_ey_p, init_cont = spatial_diffusion.spatially_differentiated_modelling(
            data['lu_reg'],
            data['enduses']['all_enduses'],
            init_cont,
            fuel_disagg,
            rs_share_s_tech_ey_p,
            ss_share_s_tech_ey_p,
            is_share_s_tech_ey_p,
            techs_affected_spatial_f=['heat_pumps_electricity'])

        regions = data['lu_reg']
        regional_specific = True
        rs_share_s_tech_ey_p = rs_reg_share_s_tech_ey_p
        ss_share_s_tech_ey_p = ss_reg_share_s_tech_ey_p
        is_share_s_tech_ey_p = is_reg_share_s_tech_ey_p
    else:
        regions = False
        regional_specific = False

    # ---------------------------------------
    # Fuel switches
    # =============
    #
    # Calculate sigmoid diffusion considering fuel switches
    # and service switches
    #
    # Non spatiall differentiated modelling of
    # technology diffusion (same diffusion pattern for
    # the whole UK) or spatially differentiated (every region)
    # ---------------------------------------
    logging.debug("... processing fuel switches")
    for enduse in data['enduses']['rs_enduses']:
        init_cont['rs_sig_param_tech'][enduse], init_cont['rs_service_switch'][enduse] = sig_param_calc_incl_fuel_switch(
            data['sim_param']['base_yr'],
            data['assumptions']['technologies'],
            enduse=enduse,
            fuel_switches=data['assumptions']['rs_fuel_switches'],
            service_switches=init_cont['rs_service_switches'],
            s_tech_by_p=init_cont['rs_s_tech_by_p'][enduse],
            s_fueltype_by_p=init_cont['rs_s_fueltype_by_p'][enduse],
            share_s_tech_ey_p=rs_share_s_tech_ey_p[enduse],
            fuel_tech_p_by=data['assumptions']['rs_fuel_tech_p_by'][enduse],
            regions=regions,
            regional_specific=regional_specific)

    for enduse in data['enduses']['ss_enduses']:
        init_cont['ss_sig_param_tech'][enduse] = {}
        init_cont['ss_service_switch'][enduse] = {}

        for sector in data['sectors']['ss_sectors']:
            init_cont['ss_sig_param_tech'][enduse][sector], init_cont['ss_service_switch'][enduse][sector] = sig_param_calc_incl_fuel_switch(
                data['sim_param']['base_yr'],
                data['assumptions']['technologies'],
                enduse=enduse,
                fuel_switches=data['assumptions']['ss_fuel_switches'],
                service_switches=init_cont['ss_service_switches'],
                s_tech_by_p=init_cont['ss_s_tech_by_p'][sector][enduse],
                s_fueltype_by_p=init_cont['ss_s_fueltype_by_p'][sector][enduse],
                share_s_tech_ey_p=ss_share_s_tech_ey_p[sector][enduse],
                fuel_tech_p_by=data['assumptions']['ss_fuel_tech_p_by'][enduse][sector],
                regions=regions,
                regional_specific=regional_specific)

    for enduse in data['enduses']['is_enduses']:
        init_cont['is_sig_param_tech'][enduse] = {}
        init_cont['is_service_switch'][enduse] = {}

        for sector in data['sectors']['is_sectors']:
            init_cont['is_sig_param_tech'][enduse][sector], init_cont['is_service_switch'][enduse][sector] = sig_param_calc_incl_fuel_switch(
                data['sim_param']['base_yr'],
                data['assumptions']['technologies'],
                enduse=enduse,
                fuel_switches=data['assumptions']['is_fuel_switches'],
                service_switches=init_cont['is_service_switches'],
                s_tech_by_p=init_cont['is_s_tech_by_p'][sector][enduse],
                s_fueltype_by_p=init_cont['is_s_fueltype_by_p'][sector][enduse],
                share_s_tech_ey_p=is_share_s_tech_ey_p[sector][enduse],
                fuel_tech_p_by=data['assumptions']['is_fuel_tech_p_by'][enduse][sector],
                regions=regions,
                regional_specific=regional_specific)

    logging.debug("... finished scenario initialisation")
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

def convert_sharesdict_to_service_switches(
        yr_until_switched,
        enduse,
        s_tech_switched_p,
        regions=False,
        regional_specific=False
    ):
    """Convert service of technologies to service switches.

    Arguments
    ---------
    yr_until_switched : int
        Year until switch happens
    enduse : str
        Enduse
    s_tech_switched_p : dict
        Fraction of total service of technologies after switch
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

            for tech, s_tech_p in s_tech_switched_p[reg].items():

                if tech == 'dummy_tech':
                    pass
                else:
                    switch_new = read_data.ServiceSwitch(
                        enduse=enduse,
                        technology_install=tech,
                        service_share_ey=s_tech_p,
                        switch_yr=yr_until_switched)

                    new_service_switches[reg].append(switch_new)
    else:
        new_service_switches = []

        for tech, s_tech_p in s_tech_switched_p.items():

            if tech == 'dummy_tech':
                pass
            else:
                switch_new = read_data.ServiceSwitch(
                    enduse=enduse,
                    technology_install=tech,
                    service_share_ey=s_tech_p,
                    switch_yr=yr_until_switched)

                new_service_switches.append(switch_new)

    return new_service_switches

def sig_param_calc_incl_fuel_switch(
        base_yr,
        technologies,
        enduse,
        fuel_switches,
        service_switches,
        s_tech_by_p,
        s_fueltype_by_p,
        share_s_tech_ey_p,
        fuel_tech_p_by,
        regions=False,
        regional_specific=False
    ):
    """Calculate sigmoid diffusion paramaters considering
    fuel or service switches. Test if service switch and
    fuel switch are defined simultaneously (raise error if true).

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
    s_tech_by_p : dict
        Service share per technology in base year
    s_fueltype_by_p : dict
        Service share per fueltype for base year
    share_s_tech_ey_p : dict
        Service share per technology for end year
    fuel_tech_p_by : dict
        Fuel share per technology in base year
    regions : dict
        Regions
    regional_specific : bool, default=False
        criteria

    Returns
    -------
    sig_param_tech : dict
        Sigmoid parameters for all affected technologies
    service_switches_out : list
        Service switches
    """
    # ----------------------------------------
    # Test if fuel switch is defined for enduse
    # Get affected technologies in fuel switch
    # ----------------------------------------
    tech_switch_affected = s_generate_sigmoid.get_tech_installed(
        enduse, fuel_switches)

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

    # ------------------------------------------
    # Test if a service and fuel switch are defined simultaneously
    # ------------------------------------------
    if crit_switch_service and crit_fuel_switch:
        logging.warning(
            "Error: Not possible to define fuel plus service switch for %s",
            enduse)
        sys.exit()

    # ------------------------------------------
    # Initialisations
    # ------------------------------------------
    sig_param_tech = {}
    if regional_specific:
        service_switches_out = {}
        for region in regions:
            sig_param_tech[region] = []
            service_switches_out[region] = service_switches_enduse
    else:
        service_switches_out = service_switches_enduse

    # ------------------------------------------
    # SERVICE switch
    #
    # Calculate service shares considering service
    # switches and the diffusion parameters
    # ------------------------------------------
    if crit_switch_service:

        # Calculate only from service switch
        s_tech_switched_p = share_s_tech_ey_p

        all_techs = s_tech_by_p.keys()

        # Calculate sigmoid diffusion parameters
        l_values_sig = s_generate_sigmoid.get_l_values(
            technologies,
            all_techs,
            regions=regions,
            regional_specific=regional_specific)

    # ------------------------------------------
    # FUEL switch
    # ------------------------------------------
    if crit_fuel_switch:
        """
        Calculate future service share after fuel switches
        and calculte sigmoid diffusion paramters.
        """
        # Get fuel switches of enduse
        enduse_fuel_switches = fuel_service_switch.get_fuel_switches_enduse(
            fuel_switches, enduse)
        
        # Get year of switches
        for fuelswitch in enduse_fuel_switches:
            yr_until_switched = fuelswitch.switch_yr
            break

        if regional_specific:
            l_values_sig = {}
            s_tech_switched_p = {}

            for reg in regions:

                # Calculate service demand after fuel switches for each technology
                s_tech_switched_p[reg] = s_generate_sigmoid.calc_service_fuel_switched(
                    enduse_fuel_switches,
                    technologies,
                    s_fueltype_by_p,
                    s_tech_by_p,
                    fuel_tech_p_by,
                    'actual_switch')

                # Calculate L for every technology for sigmod diffusion
                l_values_sig[reg] = s_generate_sigmoid.tech_l_sigmoid(
                    s_tech_switched_p[reg],
                    enduse_fuel_switches,
                    technologies,
                    s_tech_by_p.keys(),
                    s_fueltype_by_p,
                    s_tech_by_p,
                    fuel_tech_p_by)
        else:
            # Calculate future service demand after fuel switches for each technology
            s_tech_switched_p = s_generate_sigmoid.calc_service_fuel_switched(
                enduse_fuel_switches,
                technologies,
                s_fueltype_by_p,
                s_tech_by_p,
                fuel_tech_p_by,
                'actual_switch')

            # Calculate L for every technology for sigmod diffusion
            l_values_sig = s_generate_sigmoid.tech_l_sigmoid(
                s_tech_switched_p,
                enduse_fuel_switches,
                technologies,
                s_tech_by_p.keys(),
                s_fueltype_by_p,
                s_tech_by_p,
                fuel_tech_p_by)

        # Convert serivce shares to service switches
        service_switches_out = convert_sharesdict_to_service_switches(
            yr_until_switched=yr_until_switched,
            enduse=enduse,
            s_tech_switched_p=s_tech_switched_p,
            regions=regions,
            regional_specific=regional_specific)

        # Calculate only from fuel switch
        share_s_tech_ey_p = fuel_service_switch.switches_to_dict(
            service_switches_out, regional_specific)

        assert round(sum(share_s_tech_ey_p.values()), 3) == 1

    if crit_switch_service or crit_fuel_switch:
        logging.info("---------- switches {} {}  {}".format(enduse, crit_switch_service, crit_fuel_switch))

        # Calculates parameters for sigmoid diffusion of
        # technologies which are switched to/installed. With
        # `regional_specific` the assumption can be changed that
        # the technology diffusion is the same over all the uk
        # (if `regional_specific`== False, no regionally different diffusion)
        sig_param_tech = {}

        if regional_specific:

            # Get year of switches
            for region in regions:
                for switch in service_switches_out[region]:
                    yr_until_switched = switch.switch_yr
                    break
                break

            for reg in regions:
                sig_param_tech[reg] = s_generate_sigmoid.tech_sigmoid_parameters(
                    yr_until_switched,
                    base_yr,
                    technologies,
                    l_values_sig[reg],
                    s_tech_by_p,
                    s_tech_switched_p[reg])
        else:

            # Get year of switches
            for switch in service_switches_out:
                yr_until_switched = switch.switch_yr
                break

            # Calclulate sigmoid parameters for every installed technology
            sig_param_tech = s_generate_sigmoid.tech_sigmoid_parameters(
                yr_until_switched,
                base_yr,
                technologies,
                l_values_sig,
                s_tech_by_p,
                s_tech_switched_p)
    else:
        pass #no switches are defined

    return sig_param_tech, service_switches_out
