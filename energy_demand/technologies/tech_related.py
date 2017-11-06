"""Functions related to technologies
"""
import logging
import numpy as np
from energy_demand.technologies import diffusion_technologies as diffusion

def insert_dummy_tech(technologies, tech_p_by, all_specified_tech_enduse_by):
    """Define dummy technologies. Where no specific technologies are
    assigned for an enduse and a fueltype, dummy technologies
    are generated. This is necessary because the model needs
    a technology for every fueltype in an enduse.

    Arguments
    ----------
    technologies : dict
        Technologies
    tech_p_by : dict
        Fuel assignement of technologies in base year
    all_specified_tech_enduse_by : dict
        Technologies per enduse

    Returns
    -------
    tech_p_by : dict
        Fuel assignement of technologies in base year
    all_specified_tech_enduse_by : dict
        Technologies per enduse
    technologies : dict
        Technologies
    """
    for end_use in tech_p_by:
        for fuel_type in tech_p_by[end_use]:

            # TODO write explicit in assumptions: Test if any fueltype
            # is specified with a technology.
            # If yes, do not insert dummy technologies
            # because in the fuel definition all technologies of all endueses need to be defined
            crit_tech_defined_in_enduse = False
            all_defined_tech_in_fueltype = tech_p_by[end_use].values()
            for definition in all_defined_tech_in_fueltype:
                if definition == {}:
                    pass
                else:
                    crit_tech_defined_in_enduse = True
                    continue

            # If an enduse has no defined technologies across all fueltypes
            if crit_tech_defined_in_enduse is False:
                if tech_p_by[end_use][fuel_type] == {}:
                    all_specified_tech_enduse_by[end_use].append("dummy_tech")

                    # Assign total fuel demand to dummy technology
                    tech_p_by[end_use][fuel_type] = {"dummy_tech": 1.0}

                    # Insert dummy tech
                    technologies['dummy_tech'] = {}

    return tech_p_by, all_specified_tech_enduse_by, technologies

def get_enduses_with_dummy_tech(enduse_tech_p_by):
    """Find all enduses with defined dummy technologies

    Arguments
    ----------
    enduse_tech_p_by : dict
        Fuel share definition of technologies

    Return
    ------
    dummy_enduses : list
        List with all endueses with dummy technologies
    """
    dummy_enduses = []
    for enduse, fueltype_techs in enduse_tech_p_by.items():
        for techs in fueltype_techs.values():
            for tech in techs:
                if tech == 'dummy_tech':
                    dummy_enduses.append(enduse)
                    continue

    return list(set(dummy_enduses))

def calc_hp_eff(temp_yr, efficiency_intersect, t_base_heating):
    """Calculate efficiency according to temperature difference of base year

    Arguments
    ----------
    temp_yr : array
        Temperatures for every hour in a year
    efficiency_intersect : float
        Y-value (Efficiency) at 10 degree difference
    t_base_heating : float
        Base temperature for heating

    Return
    ------
    eff_hp_yh : array
        Efficiency for every hour in a year

    Note
    -----
    - For every hour the temperature difference is calculated  and the efficiency
      of the heat pump calculated based on efficiency assumptions
    - The efficiency assumptions of the heat pump are taken from Staffell et al. (2012).

      Staffell, I., Brett, D., Brandon, N., & Hawkes, A. (2012). A review of domestic heat pumps.
      Energy & Environmental Science, 5(11), 9291. https://doi.org/10.1039/c2ee22653g
    """
    # Calculate temperature difference to t_base_heating
    temp_difference_temp_yr = t_base_heating - temp_yr
    temp_difference_temp_yr[temp_difference_temp_yr < 0] = 0 #Ignore all hours where no heating is necessary

    # Calculate average efficiency of heat pumps over full year
    eff_hp_yh = eff_heat_pump(temp_difference_temp_yr, efficiency_intersect)

    return float(eff_hp_yh)

def eff_heat_pump(temp_diff, efficiency_intersect, m_slope=-.08, h_diff=10):
    """Calculate efficiency of heat pump

    Arguments
    ----------
    temp_diff: array
        Temperature difference between base temperature and temperature
    efficiency_intersect : float,default=-0.08
        Extrapolated intersect at temp diff of 10 degree (which is treated as efficiency)
    m_slope : float, default=10
        Temperature dependency of heat pumps (slope) derived from Staffell et al. (2012)
    h_diff : float
        Temperature difference

    Return
    ------
    efficiency_hp : array
        Efficiency of heat pump

    Note
    ----
    Because the efficieny of heat pumps is temperature dependent, the efficiency needs to
    be calculated based on slope and intersect which is provided as input for temp difference 10
    and treated as efficiency

    The intersect at temp differenc 10 is for ASHP about 6, for GSHP about 9
    """
    #efficiency_hp = m_slope * h_diff + (intersect + (-1 * m_slope * 10))
    #var_c = efficiency_intersect - (m_slope * h_diff)
    #var_c = efficiency_intersect - (m_slope * h_diff)
    #efficiency_hp = m_slope * temp_diff + var_c

    #SLOW
    efficiency_hp = m_slope * temp_diff + (efficiency_intersect - (m_slope * h_diff))

    #FAST
    #efficiency_hp = -.08 * temp_diff + (efficiency_intersect - (-0.8))
    # Calculate average efficiency over whole year
    efficiency_hp_mean = np.mean(efficiency_hp)

    return efficiency_hp_mean

def get_fueltype_str(fueltype_lu, fueltype_nr):
    """Read from dict the fueltype string based on fueltype KeyError

    Inputs
    ------
    fueltype : dict
        Fueltype lookup dictionary
    fueltype_nr : int
        Key which is to be found in lookup dict

    Returns
    -------
    fueltype_in_string : str
        Fueltype string
    """
    for fueltype_str in fueltype_lu:
        if fueltype_lu[fueltype_str] == fueltype_nr:
            return fueltype_str

def get_fueltype_int(fueltypes, fueltype_string):
    """Read from dict the fueltype string based on fueltype KeyError

    Inputs
    ------
    fueltype : dict
        Fueltype lookup dictionary
    fueltype_string : int
        Key which is to be found in lookup dict

    Returns
    -------
    fueltype_in_string : str
        Fueltype string
    """
    return fueltypes[fueltype_string]

def get_tech_type(tech_name, tech_list):
    """Get technology type of technology

    Arguments
    ----------
    tech_name : string
        Technology name

    tech_list : dict
        All technology lists are defined in assumptions

    Returns
    ------
    tech_type : string
        Technology type
    """
    if tech_name in tech_list['tech_heating_temp_dep']:
        tech_type = 'heat_pump'
    elif tech_name in tech_list['tech_heating_const']:
        tech_type = 'boiler_heating_tech'
    elif tech_name in tech_list['primary_heating_electricity']:
        tech_type = 'storage_heating_electricity'
    elif tech_name in tech_list['secondary_heating_electricity']:
        tech_type = 'secondary_heating_electricity'
    elif tech_name == 'dummy_tech':
        tech_type = 'dummy_tech'
    else:
        tech_type = 'regular_tech'

    return tech_type

def generate_heat_pump_from_split(temp_dependent_tech_list, technologies, heat_pump_assump):
    """Delete all heat_pump from tech dict, define average new heat pump
    technologies 'av_heat_pump_fueltype' with efficiency depending on installed ratio

    Arguments
    ----------
    temp_dependent_tech_list : list
        List to store temperature dependent technologies (e.g. heat-pumps)
    technologies : dict
        Technologies
    heat_pump_assump : dict
        The split of the ASHP and GSHP

    Returns
    -------
    technologies : dict
        Technologies with added averaged heat pump technologies for every fueltype
    temp_dependent_tech_list : list
        List with added temperature dependent technologies

    Note
    ----
    - Market Entry of different technologies must be the same year!
      (the lowest is selected if different years)
    - Diff method is linear
    """
    heat_pumps = []

    # Calculate average efficiency of heat pump depending on installed ratio
    for fueltype in heat_pump_assump:
        av_eff_hps_by, av_eff_hps_ey, eff_achieved_av, market_entry_lowest = 0, 0, 0, 2200

        for heat_pump_type in heat_pump_assump[fueltype]:
            share_heat_pump = heat_pump_assump[fueltype][heat_pump_type]
            eff_heat_pump_by = technologies[heat_pump_type]['eff_by']
            eff_heat_pump_ey = technologies[heat_pump_type]['eff_ey']
            eff_achieved = technologies[heat_pump_type]['eff_achieved']
            market_entry = technologies[heat_pump_type]['market_entry']
            tech_assum_max_share = technologies[heat_pump_type]['tech_assum_max_share']

            # Calc average values
            av_eff_hps_by += share_heat_pump * eff_heat_pump_by
            av_eff_hps_ey += share_heat_pump * eff_heat_pump_ey
            eff_achieved_av += share_heat_pump * eff_achieved

            if market_entry < market_entry_lowest:
                market_entry_lowest = market_entry

        # Add average 'av_heat_pumps' to technology dict
        name_av_hp = "heat_pumps_{}".format(fueltype)

        logging.debug("... create new averaged heat pump technology: %s", name_av_hp)

        # Add technology to temperature dependent technology list
        temp_dependent_tech_list.append(name_av_hp)

        # Add new averaged technology
        technologies[name_av_hp] = {}
        technologies[name_av_hp]['fuel_type'] = fueltype
        technologies[name_av_hp]['eff_by'] = av_eff_hps_by
        technologies[name_av_hp]['eff_ey'] = av_eff_hps_ey
        technologies[name_av_hp]['eff_achieved'] = eff_achieved_av
        technologies[name_av_hp]['diff_method'] = 'linear'
        technologies[name_av_hp]['market_entry'] = market_entry_lowest
        technologies[name_av_hp]['tech_assum_max_share'] = tech_assum_max_share

        heat_pumps.append(name_av_hp)

    # Remove all heat pumps from tech dict
    for fueltype in heat_pump_assump:
        for heat_pump_type in heat_pump_assump[fueltype]:
            del technologies[heat_pump_type]

    return technologies, temp_dependent_tech_list, heat_pumps

def calc_eff_cy(
        technology,
        sim_param,
        technologies,
        other_enduse_mode_info,
        eff_achieved_factor,
        diff_method
    ):
    """Calculate efficiency of current year based on efficiency
    assumptions and achieved efficiency

    Arguments
    ----------
    technology : str
        Name of technology
    sim_param : dict
        Base simulation parameters
    technologies : dict
        Technologies
    other_enduse_mode_info : Dict
        diffusion information
    eff_achieved_factor : dict
        Efficiency achievement factor (how much of the efficiency is achieved)
    diff_method : str
        Diffusion method

    Returns
    -------
    eff_cy : array
        Array with hourly efficiency of current year

    Notes
    -----
    The development of efficiency improvements over time is assumed to be linear
    This can however be changed with the `diff_method` attribute

    TODO: Generate two types of sigmoid (convex & concav)
    """
    # Theoretical maximum efficiency potential if theoretical maximum is linearly calculated
    if diff_method == 'linear':
        theor_max_eff = diffusion.linear_diff(
            sim_param['base_yr'],
            sim_param['curr_yr'],
            technologies[technology]['eff_by'],
            technologies[technology]['eff_ey'],
            sim_param['sim_period_yrs'])

        # Consider actual achieved efficiency
        eff_cy = theor_max_eff * eff_achieved_factor

        return eff_cy

    elif diff_method == 'sigmoid':
        theor_max_eff = diffusion.sigmoid_diffusion(
            sim_param['base_yr'],
            sim_param['curr_yr'],
            sim_param['end_yr'],
            other_enduse_mode_info['sig_midpoint'],
            other_enduse_mode_info['sig_steeppness'])

        # Differencey in efficiency change
        efficiency_change = theor_max_eff * (
            technologies[technology]['eff_ey'] - technologies[technology]['eff_by'])

        # Actual efficiency potential
        eff_cy = technologies[technology]['eff_by'] + efficiency_change

        return eff_cy

def generate_ashp_gshp_split(split_factor):
    """Assing split for each fueltype of heat pump technologies

    Arguments
    ----------
    split_factor : float
        Fraction of ASHP to GSHP
    data : dict
        Data

    Returns
    --------
    installed_heat_pump : dict
        Ditionary with split of heat pumps for every fueltype
    """
    ashp_fraction = split_factor
    gshp_fraction = 1 - split_factor

    installed_heat_pump = {
        'hydrogen': {
            'heat_pump_ASHP_hydro': ashp_fraction,
            'heat_pump_GSHP_hydro': gshp_fraction
            },
        'electricity': {
            'heat_pump_ASHP_electricity': ashp_fraction,
            'heat_pump_GSHP_electricity': gshp_fraction
            },
        'gas': {
            'heat_pump_ASHP_gas': ashp_fraction,
            'heat_pump_GSHP_gas': gshp_fraction
            },
    }

    return installed_heat_pump

'''def get_average_eff_by(tech_low_temp, tech_high_temp, assump_service_share_low_tech, assumptions):
    """Calculate average efficiency for base year of hybrid technologies for
    overall national energy service calculation

    Arguments
    ----------
    tech_low_temp : str
        Technology for lower temperatures
    tech_high_temp : str
        Technology for higher temperatures
    assump_service_share_low_tech : float
        Assumption about the overall share of the service provided
        by the technology used for lower temperatures
        (needs to be between 1.0 and 0)
    assumptions : dict
        Assumptions

    Returns
    -------
    av_eff : float
        Average efficiency of hybrid tech

    Note
    -----
    It is necssary to define an average efficiency of hybrid technologies to calcualte
    the share of total energy service in base year for the whole country. Because
    the input is fuel for the whole country, it is not possible to calculate the
    share for individual regions
    """
    # The average is calculated for the 10 temp difference intercept
    # because input for heat pumps is provided for 10 degree differences
    average_h_diff_by = 10

    # Service shares
    service_low_temp_tech_p = assump_service_share_low_tech
    service_high_temp_tech_p = 1 - assump_service_share_low_tech

    # Efficiencies of technologies of hybrid tech
    if tech_low_temp in assumptions['tech_list']['tech_heating_temp_dep']:
        eff_tech_low_temp = eff_heat_pump(
            temp_diff=average_h_diff_by,
            efficiency_intersect=assumptions['technologies'][tech_low_temp]['eff_by'])
    else:
        eff_tech_low_temp = assumptions['technologies'][tech_low_temp]['eff_by']

    if tech_high_temp in assumptions['tech_list']['tech_heating_temp_dep']:
        eff_tech_high_temp = eff_heat_pump(
            temp_diff=average_h_diff_by,
            efficiency_intersect=assumptions['technologies'][tech_high_temp]['eff_by'])
    else:
        eff_tech_high_temp = assumptions['technologies'][tech_high_temp]['eff_by']

    # Weighted average efficiency
    av_eff = service_low_temp_tech_p * eff_tech_low_temp + service_high_temp_tech_p * eff_tech_high_temp

    return av_eff
'''