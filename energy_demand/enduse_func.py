"""
Enduse
======

Contains the `Enduse` Class. This is the most important class
where the change in enduse specific energy demand is simulated
depending on scenaric assumptions.
"""
import logging
import numpy as np
from energy_demand.initalisations import helpers
from energy_demand.profiles import load_profile as lp
from energy_demand.profiles import load_factors as lf
from energy_demand.technologies import diffusion_technologies
from energy_demand.technologies import fuel_service_switch

class Enduse(object):
    """Enduse Class for all endueses in each SubModel

    For every region and sector, a different instance
    is generated. In this class, first the change in
    energy demand is calculated on a annual temporal scale.
    Calculations are performed in a cascade (e.g. first
    reducing climate change induced savings, then substracting
    further behavioral savings etc.). After annual calculations,
    the demand is converted to hourly demand.

    Also within this function, the fuel inputs are converted
    to energy service (short: service) and converted back to
    fuels (e.g. electricit).

    Arguments
    ----------
    region_name : str
        Region name
    scenario_data : dict
        Scenario data
    assumptions : dict
        Assumptions
    non_regional_lp_stock : dict
        Load profile stock
    sim_param : dict
        Simulation parameter
    enduse : str
        Enduse name
    sector : str
        Sector name
    fuel : array
        Yearly fuel data for different fueltypes
    tech_stock : object
        Technology stock of region
    heating_factor_y : array
        Distribution of fuel within year to days (yd) (directly correlates with HDD)
    cooling_factor_y : array
        Distribution of fuel within year to days (yd) (directly correlates with CDD)
    service_switches : list
        Service switches
    fuel_tech_p_by : dict
        Fuel tech assumtions in base year
    tech_increased_service : dict
        Technologies per enduse with increased service due to scenarios
    tech_decreased_service : dict
        Technologies per enduse with decreased service due to scenarios
    tech_constant_service : dict
        Technologies per enduse with constat service
    sig_param_tech : dict
        Sigmoid parameters
    enduse_overall_change : dict
        Assumptions related to overal change in endyear
    regional_lp_stock : object
        Load profile stock
    dw_stock : object,default=False
        Dwelling stock
    reg_scen_drivers : bool,default=None
        Scenario drivers per enduse
    flat_profile_crit : bool,default=False
        Criteria of enduse has a flat shape or not

    Note
    ----
    - Load profiles are assigned independently of the fueltype, i.e.
      the same profiles are assumed to hold true across different fueltypes

    - ``self.fuel_new_y`` is always overwritten
      in the cascade of calculations

    Warning
    -------
    Not all enduses have technologies assigned. Load peaks are derived
    from techstock in case technologies are defined. Otherwise enduse load
    profiles are used.
    """
    def __init__(
            self,
            region_name,
            scenario_data,
            assumptions,
            non_regional_lp_stock,
            sim_param,
            enduse,
            sector,
            fuel,
            tech_stock,
            heating_factor_y,
            cooling_factor_y,
            service_switches,
            fuel_tech_p_by,
            tech_increased_service,
            tech_decreased_service,
            tech_constant_service,
            sig_param_tech,
            enduse_overall_change,
            regional_lp_stock,
            criterias,
            fueltypes_nr,
            fueltypes,
            dw_stock=False,
            reg_scen_drivers=None,
            flat_profile_crit=False,
        ):
        """Enduse class constructor
        """
        #print("--- Enduse: " + str(enduse))
        self.region_name = region_name
        self.enduse = enduse
        self.fuel_new_y = fuel
        self.flat_profile_crit = flat_profile_crit

        if self.enduse == 'rs_space_heating':
            print("rs_space_heatingEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEE : " + str(np.sum(fuel)))
        if self.enduse == 'ss_space_heating':
            print("ss_space_heatingEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEE : " + str(np.sum(fuel)))
        if self.enduse == 'is_space_heating':
            print("is_space_heatingEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEE : " + str(np.sum(fuel)))

        if np.sum(fuel) == 0: #If enduse has no fuel return empty shapes
            self.flat_profile_crit = True
            self.fuel_y = np.zeros((fueltypes_nr), dtype=float)
            self.fuel_yh = 0
            self.fuel_peak_dh = np.zeros((fueltypes_nr, 24), dtype=float)
            self.fuel_peak_h = 0

            #  ------NEW
            self.techs_fuel_yh = {}
            self.techs_fuel_peak_h = {}
            self.techs_fuel_peak_dh = {}
            for tech in assumptions['heating_technologies']:
                model_yeardays_nrs = 365 #TODO GLOBAL
                self.techs_fuel_yh[tech] = np.zeros((fueltypes_nr, model_yeardays_nrs, 24), dtype=float)
                self.techs_fuel_peak_h[tech] = np.zeros((fueltypes_nr, model_yeardays_nrs, 24), dtype=float)
                self.techs_fuel_peak_dh[tech] = np.zeros((fueltypes_nr, model_yeardays_nrs, 24), dtype=float)
        else:
            # Get correct parameters depending on model configuration
            load_profiles = get_lp_stock(
                enduse, non_regional_lp_stock, regional_lp_stock)

            self.enduse_techs = get_enduse_tech(fuel_tech_p_by)

            # -------------------------------
            # Cascade of calculations on a yearly scale
            # --------------------------------
            # --Change fuel consumption based on climate change induced temperature differences
            self.fuel_new_y = apply_climate_change(
                enduse,
                self.fuel_new_y,
                cooling_factor_y,
                heating_factor_y,
                assumptions)
            #logging.info("... Fuel train B: " + str(np.sum(self.fuel_new_y)))
            #print("... Fuel train B: " + str(np.sum(self.fuel_new_y)))

            # --Change fuel consumption based on smart meter induced general savings
            self.fuel_new_y = apply_smart_metering(
                enduse,
                self.fuel_new_y,
                assumptions['smart_meter_assump'],
                assumptions['strategy_variables'],
                sim_param['base_yr'],
                sim_param['curr_yr'])
            #logging.info("... Fuel train C: " + str(np.sum(self.fuel_new_y)))
            #print("... Fuel train C: " + str(np.sum(self.fuel_new_y)))

            # --Enduse specific fuel consumption change in %
            self.fuel_new_y = apply_specific_change(
                enduse,
                self.fuel_new_y,
                enduse_overall_change,
                assumptions['strategy_variables'],
                sim_param)
            #logging.info("... Fuel train D: " + str(np.sum(self.fuel_new_y)))
            #print("... Fuel train D: " + str(np.sum(self.fuel_new_y)))

            # Calculate new fuel demands after scenario drivers
            self.fuel_new_y = apply_scenario_drivers(
                enduse,
                self.fuel_new_y,
                dw_stock,
                region_name,
                scenario_data['gva'],
                scenario_data['population'],
                reg_scen_drivers,
                sim_param)
            #logging.info("... Fuel train E: " + str(np.sum(self.fuel_new_y)))
            #print("... Fuel train E: " + str(np.sum(self.fuel_new_y)))

            # ----------------------------------
            # Hourly Disaggregation
            # ----------------------------------
            #print("ENDUSE:  {}  TECHS {}".format(enduse, self.enduse_techs))
            if self.enduse_techs == []:
                """If no technologies are defined for an enduse, the load profiles
                are read from dummy shape, which show the load profiles of the whole enduse.
                No switches can be implemented and only overall change of enduse.

                Note: for heating, technologies need to be assigned. Otherwise,
                here there will be problems
                """
                if flat_profile_crit:
                    self.fuel_y = self.fuel_new_y * assumptions['model_yeardays_nrs'] / 365.0
                else:
                    self.fuel_yh, self.fuel_peak_dh, self.fuel_peak_h = assign_lp_no_techs(
                        enduse,
                        sector,
                        load_profiles,
                        self.fuel_new_y)
            else:
                """If technologies are defined for an enduse
                """
                # ----
                # Get enduse specific configurations
                # ----
                mode_constrained, crit_switch_service = get_enduse_configuration(
                    criterias['mode_constrained'],
                    enduse,
                    assumptions['enduse_space_heating'],
                    sim_param['base_yr'],
                    sim_param['curr_yr'],
                    service_switches)
                print("--MODE--  {}   {} ".format(enduse, mode_constrained))
                # ------------------------------------
                # Calculate regional energy service
                # ------------------------------------
                tot_service_y_cy, service_tech_y_cy, service_tech_cy_p = fuel_to_service(
                    enduse,
                    self.fuel_new_y,
                    self.enduse_techs,
                    fuel_tech_p_by,
                    tech_stock,
                    fueltypes,
                    mode_constrained)

                # ------------------------------------
                # Reduction of service because of heat recovery
                # (standard sigmoid diffusion)
                # ------------------------------------
                tot_service_y_cy = apply_heat_recovery(
                    enduse,
                    assumptions['strategy_variables'],
                    assumptions['enduse_overall_change'],
                    tot_service_y_cy,
                    'tot_service_y_cy',
                    sim_param['base_yr'],
                    sim_param['curr_yr'])

                service_tech_y_cy = apply_heat_recovery(
                    enduse,
                    assumptions['strategy_variables'],
                    assumptions['enduse_overall_change'],
                    service_tech_y_cy,
                    'service_tech',
                    sim_param['base_yr'],
                    sim_param['curr_yr'])

                # --------------------------------
                # Switches (service or fuel)
                # --------------------------------
                if crit_switch_service:
                    service_tech_y_cy = calc_service_switch(
                        tot_service_y_cy,
                        service_tech_cy_p,
                        tech_increased_service,
                        tech_decreased_service,
                        tech_constant_service,
                        sig_param_tech,
                        sim_param['curr_yr'])

                # -------------------------------------------
                # Convert annual service to fuel per fueltype
                # -------------------------------------------
                self.fuel_new_y, fuel_tech_y = service_to_fuel(
                    enduse,
                    service_tech_y_cy,
                    tech_stock,
                    fueltypes_nr,
                    fueltypes,
                    mode_constrained)

                self.fuel_y = self.fuel_new_y

                # ------------------------------------------
                # Assign load profiles
                # ------------------------------------------
                if self.flat_profile_crit: # NEW INSERTED AGAIN
                    self.fuel_y = calc_fuel_tech_y(
                        enduse,
                        tech_stock,
                        fuel_tech_y,
                        fueltypes_nr,
                        fueltypes,
                        mode_constrained)
                else:
                    # ---------------------------------------
                    # Demand Management (peak shaving)
                    # ---------------------------------------
                    if mode_constrained:
                        print("mode_constrained: {}  {}".format(mode_constrained, enduse))
                        self.techs_fuel_yh = {}
                        self.techs_fuel_peak_h = {}
                        self.techs_fuel_peak_dh = {}
                        # ---
                        # Contrainsed (i.e. with technologies) fuel calculation
                        # ---
                        constrained_fuel_yh = calc_fuel_tech_yh(
                            enduse,
                            sector,
                            self.enduse_techs,
                            fuel_tech_y,
                            tech_stock,
                            load_profiles,
                            fueltypes_nr,
                            fueltypes,
                            assumptions['model_yeardays_nrs'],
                            mode_constrained=True)

                        # --PEAK
                        # Iterate technologies in enduse and assign technology specific profiles
                        fuel_peak_dh = calc_peak_tech_dh(
                            enduse,
                            sector,
                            self.enduse_techs,
                            fuel_tech_y,
                            constrained_fuel_yh,
                            tech_stock,
                            load_profiles,
                            fueltypes_nr,
                            fueltypes,
                            mode_constrained=True)

                        for tech in constrained_fuel_yh:
                            #print("TECH  {}  {}".format(tech, np.sum(constrained_fuel_yh[tech])))
                            tech_fuel_yh, tech_fuel_peak_h, tech_fuel_peak_dh = demand_management(
                                enduse,
                                sim_param,
                                assumptions,
                                constrained_fuel_yh[tech],
                                fuel_peak_dh[tech],
                                self.enduse_techs,
                                sector,
                                fuel_tech_y,
                                tech_stock,
                                load_profiles,
                                fueltypes_nr,
                                mode_constrained=True)

                            self.techs_fuel_yh[tech] = tech_fuel_yh
                            self.techs_fuel_peak_h[tech] = tech_fuel_peak_h
                            self.techs_fuel_peak_dh[tech] = tech_fuel_peak_dh

                        # ------------
                        # New: Calculate heat related factors for all technologies
                        # -----------
                        self.fuel_yh = np.zeros((tech_fuel_yh.shape), dtype=float)
                        self.fuel_peak_h = np.zeros((tech_fuel_peak_h.shape), dtype=float)
                        self.fuel_peak_dh = np.zeros((tech_fuel_peak_dh.shape), dtype=float)

                        for tech in self.techs_fuel_yh:
                            self.fuel_yh += self.techs_fuel_yh[tech]
                            self.fuel_peak_h += self.techs_fuel_peak_h[tech]
                            self.fuel_peak_dh += self.techs_fuel_peak_dh[tech]
                    else:
                        # ONLY FOR HEATING ENDUSES
                        #---NON-PEAK
                        unconstrained_fuel_yh = calc_fuel_tech_yh(
                            enduse,
                            sector,
                            self.enduse_techs,
                            fuel_tech_y,
                            tech_stock,
                            load_profiles,
                            fueltypes_nr,
                            fueltypes,
                            assumptions['model_yeardays_nrs'],
                            mode_constrained=False)

                        # --PEAK
                        # Iterate technologies in enduse and assign technology specific profiles
                        fuel_peak_dh = calc_peak_tech_dh(
                            enduse,
                            sector,
                            self.enduse_techs,
                            fuel_tech_y,
                            unconstrained_fuel_yh,
                            tech_stock,
                            load_profiles,
                            fueltypes_nr,
                            fueltypes,
                            mode_constrained=False)

                        self.fuel_yh, self.fuel_peak_h, self.fuel_peak_dh = demand_management(
                            enduse,
                            sim_param,
                            assumptions,
                            unconstrained_fuel_yh,
                            fuel_peak_dh,
                            self.enduse_techs,
                            sector,
                            fuel_tech_y,
                            tech_stock,
                            load_profiles,
                            fueltypes_nr,
                            mode_constrained=False)

def demand_management(
        enduse,
        sim_param,
        assumptions,
        fuel_yh,
        fuel_peak_dh,
        enduse_techs,
        sector,
        fuel_tech_y,
        tech_stock,
        load_profiles,
        fueltypes_nr,
        mode_constrained
    ):
    """Demand management

    Arguments
    ----------
    enduse : str
        Enduse
    sim_param : dict

    assumptions : dict

    fuel_yh : array

    fuel_peak_dh : 

    enduse_techs : 

    sector : 

    fuel_tech_y : 

    tech_stock : 

    load_profiles : 

    fueltypes_nr : 

    mode_constrained : 

    Returns
    -------

    TODO DESCRIBE
    """
    # Calculate average for every day
    average_fuel_yd = np.mean(fuel_yh, axis=2)

    # Calculate laod factors (only inter_day load shifting as for now)
    loadfactor_yd_cy = lf.calc_lf_d(fuel_yh, average_fuel_yd)

    # Calculate current year load factors
    lf_cy_improved_d, peak_shift_crit = calc_lf_improvement(
        enduse,
        sim_param['base_yr'],
        sim_param['curr_yr'],
        loadfactor_yd_cy,
        assumptions['strategy_variables'],
        assumptions['strategy_variables']['demand_management_yr_until_changed'])

    if not peak_shift_crit:
        fuel_yh = fuel_yh
        fuel_peak_dh = fuel_peak_dh
        # Get maximum hour demand of peak day
        fuel_peak_h = lp.calk_peak_h_dh(fuel_peak_dh)
    else:
        fuel_yh = lf.peak_shaving_max_min(
            lf_cy_improved_d,
            average_fuel_yd,
            fuel_yh)

        fuel_peak_dh = calc_peak_tech_dh(
            enduse,
            sector,
            enduse_techs,
            fuel_tech_y,
            fuel_yh,
            tech_stock,
            load_profiles,
            fueltypes_nr,
            mode_constrained)

        fuel_peak_h = lp.calk_peak_h_dh(fuel_peak_dh)

    return fuel_yh, fuel_peak_h, fuel_peak_dh

def calc_lf_improvement(enduse, base_yr, curr_yr, loadfactor_yd_cy, lf_improvement_ey, yr_until_changed):
    """Calculate lf improvement depending on linear diffusion

    Test if lager than zero --> replace by one

    """
    try:
        # Get assumed load shift
        param_name = 'demand_management_improvement__{}'.format(enduse)

        if lf_improvement_ey[param_name] == 0:
            return False, False
        else:
            # Calculate linear diffusion of improvement of load management
            lin_diff_factor = diffusion_technologies.linear_diff(
                base_yr,
                curr_yr,
                0,
                1,
                yr_until_changed)

            # Current year load factor improvement
            lf_improvement_cy = lf_improvement_ey[param_name] * lin_diff_factor

            # Improve load factor
            lf_cy_improved_d = loadfactor_yd_cy + lf_improvement_cy

            # If lager than zero, set to 1
            lf_cy_improved_d[lf_cy_improved_d > 1] = 1

            peak_shift_crit = True

            return lf_cy_improved_d, peak_shift_crit
    except KeyError:
        logging.debug("... no load management was defined for enduse")
        return False, False

def assign_lp_no_techs(enduse, sector, load_profiles, fuel_new_y):
    """Assign load profiles for an enduse which has not
    technologies defined.

    Arguments
    ---------
    enduse : str
        Enduse
    sector : str
        Enduse
    load_profiles : obj
        Load profiles
    fuel_new_y : array
        Fuels

    Returns
    -------
    fuel_yh
    fuel_peak_dh
    fuel_peak_h
    """
    _fuel = fuel_new_y[:, np.newaxis, np.newaxis]

    fuel_yh = load_profiles.get_lp(
        enduse, sector, 'dummy_tech', 'shape_yh') * _fuel

    # Read dh profile from peak day
    peak_day = get_peak_day(fuel_yh)

    shape_peak_dh = lp.abs_to_rel(fuel_yh[:, peak_day, :])

    enduse_peak_yd_factor = load_profiles.get_lp(
        enduse, sector, 'dummy_tech', 'enduse_peak_yd_factor')

    fuel_peak_dh = fuel_new_y[:, np.newaxis] * enduse_peak_yd_factor * shape_peak_dh

    fuel_peak_h = lp.calk_peak_h_dh(fuel_peak_dh)

    return fuel_yh, fuel_peak_dh, fuel_peak_h

def get_lp_stock(enduse, non_regional_lp_stock, regional_lp_stock):
    """Defines the load profile stock depending on `enduse`.
    (Get regional or non-regional load profile data)

    Arguments
    ----------
    enduse : str
        Enduse
    non_regional_lp_stock : object
        Non regional dependent load profiles
    regional_lp_stock : object
        Regional dependent load profiles

    Returns
    -------
    load_profiles : object
        Load profile

    Note
    -----
    Because for some enduses the load profiles depend on the region
    they are stored in the `WeatherRegion` Class. One such example is
    heating. If the enduse is not dependent on the region, the same
    load profile can be used for all regions

    If the enduse depends on regional factors, `regional_lp_stock`
    is returned. Otherwise, non-regional load profiles which can
    be applied for all regions is used (`non_regional_lp_stock`)
    """
    if enduse in non_regional_lp_stock.enduses_in_stock:
        return non_regional_lp_stock
    else:
        return regional_lp_stock

def get_running_mode(enduse, mode_constrained, enduse_space_heating):
    """Check which mode needs to be run for an enduse

    Arguments
    -----------
    mode_constrained : bool
        Criteria of running mode
    enduse_space_heating : dict
        All heating enduses across all models

    Returns
    -------
    bool : bool
        The return value

    Note
    ----
    If 'crit_mode' == True, then overall heat is provided to
    the supply model not specified for technologies. Otherwise,
    heat demand is supplied per technology
    """
    if mode_constrained:
        return True
    elif not mode_constrained and enduse in enduse_space_heating:
        return False
    elif not mode_constrained and enduse not in enduse_space_heating:
        return True # All other enduses wher technologies (non_heat)

def get_enduse_configuration(
        mode_constrained,
        enduse,
        enduse_space_heating,
        base_yr,
        curr_yr,
        service_switches
    ):
    """Get enduse specific configuration

    Arguments
    ---------
    mode_constrained : bool
        Constrained mode criteria
    enduse : str
        Enduse
    enduse_space_heating : 
        
    base_yr, curr_yr : int
        Base, current, year
    service_switches :     
    """
    mode_constrained = get_running_mode(
        enduse,
        mode_constrained,
        enduse_space_heating)

    crit_switch_service = get_crit_switch(
        enduse,
        service_switches,
        base_yr,
        curr_yr,
        mode_constrained)

    return mode_constrained, crit_switch_service

def get_crit_switch(enduse, switches, base_yr, curr_yr, mode_constrained):
    """Test whether there is a switch (service or fuel)

    Arguments
    ----------
    switches : dict
        All switches
    sim_param : float
        Base Arguments
    mode_constrained : bool
        Mode criteria

    Note
    ----
    If base year, no switches are implemented
    """
    if base_yr == curr_yr or mode_constrained is False:
        return False
    else:
        for switch in switches:
            if switch.enduse == enduse:
                return True

        return False

def get_peak_day(fuel_yh):
    """Iterate yh and get day with highes fuel (across all fueltypes)

    Return
    ------
    peak_day_nr : int
        Day with most fuel or service across all fueltypes

    Note
    -----
    - The day with most fuel across all fueltypes is
    considered to be the peak day
    - The Peak day may change date in a year
    """
    # Sum all fuel across all fueltypes for every hour in a year
    all_fueltypes_tot_h = np.sum(fuel_yh, axis=0)
    #all_fueltypes_tot_h = np.sum(fuel_yh, axis=1)

    if np.sum(all_fueltypes_tot_h) == 0:
        print("TODO: FIX ERROR: NP PEAK FOUND")
        return 0
    else:
        # Sum fuel within every hour for every day and get day with maximum fuel
        peak_day_nr = np.argmax(np.sum(all_fueltypes_tot_h, axis=1))
        return peak_day_nr

def calc_peak_tech_dh(
        enduse,
        sector,
        enduse_techs,
        enduse_fuel_tech,
        fuel_yh,
        tech_stock,
        load_profile,
        fueltypes_nr,
        fueltypes,
        mode_constrained
    ):
    """Calculate peak demand for every fueltype

    Arguments
    ----------
    assumptions : array
        Assumptions
    enduse_fuel_tech : array
        Fuel per enduse and technology
    tech_stock : data
        Technology stock
    load_profile : object
        Load profile
    fueltypes_nr : int
        Number of fueltypes
    mode_constrained : bool
        Constrained mode criteria

    Returns
    -------
    fuels_peak_dh : array
        Peak values for peak day for every fueltype

    Note
    ----
    - This function gets the hourly values of the peak day for every fueltype.
        The daily fuel is converted to dh for each technology.

    - For some technology types (heat_pump a)
        the dh peak day profile is not read in from technology
        stock but from shape_yh of peak day.
    """
    if mode_constrained:
        fuels_peak_dh = {}
    else:
        fuels_peak_dh = np.zeros((fueltypes_nr, 24), dtype=float)

    for tech in enduse_techs:
        tech_type = tech_stock.get_tech_attr(enduse, tech, 'tech_type')

        tech_fuel_type_int = tech_stock.get_tech_attr(
            enduse, tech, 'tech_fueltype_int')

        if tech not in enduse_fuel_tech.keys():
            pass #"no fuel assigned"
        else:
            if tech_type == 'heat_pump':
                """Read fuel from peak day
                """
                # Get day with most fuel across all fueltypes
                if mode_constrained:
                    peak_day_nr = get_peak_day(fuel_yh[tech])
                else:
                    peak_day_nr = get_peak_day(fuel_yh)

                # Calculate absolute fuel values for yd (multiply fuel with yd_shape)
                fuel_tech_yd = enduse_fuel_tech[tech] * load_profile.get_lp(
                    enduse, sector, tech, 'shape_yd')

                # Calculate fuel for peak day
                fuel_tech_peak_d = fuel_tech_yd[peak_day_nr]

                # The 'shape_peak_dh'is not defined in technology stock because
                # in the 'Region' the peak day is not yet known
                # Therfore, the shape_yh is read in and with help of
                # information on peak da
                tech_peak_dh = load_profile.get_lp(
                    enduse, sector, tech, 'shape_y_dh')[peak_day_nr]
            else:
                """Calculate fuel with peak factor
                """
                enduse_peak_yd_factor = load_profile.get_lp(
                    enduse, sector, tech, 'enduse_peak_yd_factor')

                # Calculate fuel for peak day
                fuel_tech_peak_d = enduse_fuel_tech[tech] * enduse_peak_yd_factor

                # Assign Peak shape of a peak day of a technology
                tech_peak_dh = load_profile.get_shape_peak_dh(
                    enduse, sector, tech)

            # Multiply absolute d fuels with dh peak fuel shape
            fuel_tech_peak_dh = tech_peak_dh * fuel_tech_peak_d

            if mode_constrained:
                tech_fuels_peak_dh = np.zeros((fueltypes_nr, 24), dtype=float)
                tech_fuels_peak_dh[tech_fuel_type_int] = fuel_tech_peak_dh
                fuels_peak_dh[tech] = tech_fuels_peak_dh
            else:
                # Peak day fuel shape * fueltype distribution for peak day
                # select from (7, nr_of_days, 24) only peak day for all fueltypes
                fuels_peak_dh[fueltypes['heat']] += fuel_tech_peak_dh
                
    return fuels_peak_dh

def get_enduse_tech(fuel_tech_p_by):
    """Get all defined technologies of an enduse

    Arguments
    ----------
    fuel_tech_p_by : dict
        Percentage of fuel per enduse per technology

    Return
    ------
    enduse_techs : list
        All technologies

    Note
    ----
    All technologies are read out, including those which
    are potentiall defined in fuel or service switches.

    If for an enduse a dummy technology is defined,
    the technologies of an enduse are set to an empty
    list.

    Warning
    -------
    For every enduse technologes must either be defined
    for no fueltype or for all fueltypes
    """
    enduse_techs = []
    for tech_fueltype in fuel_tech_p_by.values():
        if 'dummy_tech' in tech_fueltype.keys():
            return []
        else:
            enduse_techs += tech_fueltype.keys()

    return list(set(enduse_techs))

def calc_fuel_tech_yh(
        enduse,
        sector,
        enduse_techs,
        enduse_fuel_tech,
        tech_stock,
        load_profiles,
        fueltypes_nr,
        fueltypes,
        model_yeardays_nrs,
        mode_constrained
    ):
    """Iterate fuels for each technology and assign shape yd and yh shape

    Arguments
    ----------
    enduse_fuel_tech : dict
        Fuel per technology in enduse
    tech_stock : object
        Technologies
    load_profiles : object
        Load profiles
    fueltypes_nr : dict
        Nr of fueltypes
    fueltypes : dict
        Fueltypes lookup
    mode_constrained : bool
        Mode criteria
    model_yeardays_nrs : int
        Number of modelled yeardays

    Return
    ------
    fuels_yh : array
        Fueltype storing hourly fuel for every fueltype (fueltype, model_yeardays_nrs, 24)

    TODO: CLEAN
    """
    if mode_constrained:
        fuels_yh = {}
        for tech in enduse_techs:
            load_profile = load_profiles.get_lp(enduse, sector, tech, 'shape_yh')
            tech_fueltype_int = tech_stock.get_tech_attr(enduse, tech, 'tech_fueltype_int')

            if model_yeardays_nrs != 365:
                load_profile = lp.abs_to_rel(load_profile)

            tech_fuels_yh = np.zeros((fueltypes_nr, model_yeardays_nrs, 24), dtype=float)

            if tech not in enduse_fuel_tech.keys():
                # Technology has not fuel assigned
                #fuels_yh[fueltypes['heat']] += 0
                fuels_yh[tech] = tech_fuels_yh
            else:
                fuel_tech_yh = enduse_fuel_tech[tech] * load_profile

                tech_fuels_yh[tech_fueltype_int] += fuel_tech_yh
                fuels_yh[tech] = tech_fuels_yh
    else:
        fuels_yh = np.zeros((fueltypes_nr, model_yeardays_nrs, 24), dtype=float)
        for tech in enduse_techs:

            load_profile = load_profiles.get_lp(enduse, sector, tech, 'shape_yh')

            # Fuel distribution
            # Only needed if modelled days is not 365 because the
            # service in fuel_to_service() was already reduced
            # to selected modelled days
            if model_yeardays_nrs != 365:
                load_profile = lp.abs_to_rel(load_profile)

            if tech not in enduse_fuel_tech.keys():
                # Technology has not fuel assigned
                #fuels_yh[tech_fueltype_int] += 0
                pass
            else:
                fuel_tech_yh = enduse_fuel_tech[tech] * load_profile

                # Get distribution per fueltype
                fuels_yh[fueltypes['heat']] += fuel_tech_yh

    return fuels_yh

def calc_fuel_tech_y(
        enduse,
        tech_stock,
        fuel_tech_y,
        fueltypes_nr,
        fueltypes,
        mode_constrained
    ):
    """Calculate yearly fuel per technology (no load profile assigned).

    Arguments
    -----------
    enduse : str
        Enduse
    tech_stock : object
        Technology stock
    fuel_tech_y : dict
        Fuel per technology per year
    lookups : dict
        look-up
    fueltype : dict
        Integer of fueltypes
    mode_constrained : bool
        Running mode

    Returns
    -------
    fuel_y : array
        Fuel per year per fueltype

    Note
    ----
    This function can be run in two different modes
    """
    fuel_y = np.zeros((fueltypes_nr), dtype=float)

    for tech, fuel_tech_y in fuel_tech_y.items():
        if mode_constrained:
            tech_fuel_type_int = tech_stock.get_tech_attr(
                enduse,
                tech,
                'tech_fueltype_int')

            fuel_y[tech_fuel_type_int] += np.sum(fuel_tech_y)
        else:
            # Assign all to heat fueltype
            fuel_y[fueltypes['heat']] += np.sum(fuel_tech_y)

    return fuel_y

def service_to_fuel(
        enduse,
        service_tech,
        tech_stock,
        fueltypes_nr,
        fueltypes,
        mode_constrained
    ):
    """Convert yearly energy service to yearly fuel demand.
    For every technology the service is taken and converted
    to fuel based on efficiency of current year

    Inputs
    ------
    enduse : str
        Enduse
    service_tech : dict
        Service per fueltype and technology
    tech_stock : object
        Technological stock
    lookups : dict
        look-up
    mode_constrained : bool
        Mode running criteria

    Return
    ------
    fuel_new_y : array
        Fuel per fueltype
    fuel_per_tech : dict
        Fuel per technology

    Note
    -----
    - The attribute 'fuel_new_y' is updated
    - Fuel = Energy service / efficiency
    """
    fuel_per_tech = {}
    fuel_new_y = np.zeros((fueltypes_nr), dtype=float)

    if mode_constrained:
        for tech, service in service_tech.items():
            tech_eff = tech_stock.get_tech_attr(
                enduse, tech, 'eff_cy')

            tech_fuel_type_int = tech_stock.get_tech_attr(
                enduse, tech, 'tech_fueltype_int')

            # Convert to fuel
            fuel = service / tech_eff

            fuel_per_tech[tech] = fuel

            # Multiply fuel of technology per fueltype with shape of annual distrbution
            fuel_new_y[tech_fuel_type_int] += fuel
            #fuel_new_y[fueltypes['heat']] += fuel
    else:
        for tech, fuel_tech in service_tech.items():
            fuel = fuel_tech

            #tech_fuel_type_int = tech_stock.get_tech_attr(
            #    enduse, tech, 'tech_fueltype_int')

            fuel_new_y[fueltypes['heat']] += fuel
            #fuel_new_y[tech_fuel_type_int] += fuel
            fuel_per_tech[tech] = fuel #which is heat

    return fuel_new_y, fuel_per_tech

def fuel_to_service(
        enduse,
        fuel_new_y,
        enduse_techs,
        fuel_tech_p_by,
        tech_stock,
        fueltypes,
        mode_constrained,
    ):
    """Converts fuel to energy service (1),
    calcualates contribution service fraction (2)

    Arguments
    ----------
    enduse : str
        Enduse
    fuel_new_y : array
        Fuel per fueltype
    enduse_techs : dict
        Technologies of enduse
    fuel_tech_p_by : dict
        Fuel composition of base year for every fueltype for each
        enduse (assumtions for national scale)
    tech_stock : object
        Technology stock of region
    fueltypes : dict
        Fueltype look-up
    mode_constrained : bool
        Criteria about mode

    Return
    ------
    tot_service_yh : array
        Absolute total yh energy service per technology and fueltype
    service_tech : dict
        Absolute energy service for every technology
    service_tech_p : dict
        Fraction of energy service for every technology
        (sums up to one in total (not specified by fueltype))
    service_fueltype_tech_p : dict
        Fraction of energy service per fueltype and technology
        (within every fueltype sums up to one)
    service_fueltype_p : dict
        Fraction of service per fueltype
        (within every fueltype sums up to one)

    Note
    -----
    **(1)** Calculate energy service of each technology based on assumptions
    about base year fuel shares of an enduse (`fuel_tech_p_by`).

    **(2)** The fraction of an invidual technology to which it
    contributes to total energy service (e.g. how much of
    total heat service is provided by boiler technology).

    -   Efficiency changes of technologis are considered.
    -   Energy service = fuel * efficiency
    -   This function can be run in two modes, depending on `mode_constrained` criteria
    -   The base year efficiency is taken because the actual service can
        only be calculated with base year. Otherwise, the service would
        increase e.g. if technologies would become more efficient.
        Efficiencies are only considered if converting back to fuel
        However, the self.fuel_new_y is taken because the actual
        service was reduced e.g. due to smart meters or temperatur changes
    """
    service_tech = dict.fromkeys(enduse_techs, 0)
    tot_service_y = 0

    if mode_constrained:
        """Constrained version
        """
        service_fueltype_tech = helpers.service_type_tech_by_p(fueltypes, fuel_tech_p_by)

        # Calulate share of energy service per tech depending on fuel and efficiencies
        for fueltype, tech_list in fuel_tech_p_by.items():
            for tech, fuel_share in tech_list.items():
                tech_eff = tech_stock.get_tech_attr(enduse, tech, 'eff_by')

                # Calculate fuel share and convert fuel to service
                service_tech_y = fuel_new_y[fueltype] * fuel_share * tech_eff

                service_tech[tech] += service_tech_y

                # Add fuel for each technology (float() is necessary to avoid inf error)
                service_fueltype_tech[fueltype][tech] += service_tech_y

                # Sum total yearly service
                tot_service_y += service_tech_y #(y)
    else:
        """
        Unconstrained version
        no efficiencies are considered, because not technology specific service calculation
        """
        service_fueltype_tech = helpers.service_type_tech_by_p(fueltypes, fuel_tech_p_by)
        # Calculate share of service
        for fueltype, tech_list in fuel_tech_p_by.items():
            for tech, fuel_share in tech_list.items():
                fuel_tech = fuel_new_y[fueltype] * fuel_share
                tot_service_y += fuel_tech
                service_tech[tech] += fuel_tech

                # Assign all service to fueltype 'heat_fueltype'
                try:
                    service_fueltype_tech[fueltypes['heat']][tech] += float(np.sum(fuel_tech))
                except KeyError:
                    service_fueltype_tech[fueltypes['heat']][tech] = 0
                    service_fueltype_tech[fueltypes['heat']][tech] += float(np.sum(fuel_tech))

    # Convert service of every technology to fraction of total service
    service_tech_p = convert_service_to_p(tot_service_y, service_fueltype_tech)

    return tot_service_y, service_tech, service_tech_p

def apply_heat_recovery(enduse, strategy_variables, enduse_overall_change, service, crit_dict, base_yr, curr_yr):
    """Reduce heating demand according to assumption on heat reuse

    Arguments
    ----------
    assumptions : dict
        Assumptions
    service : dict or array
        Service of current year
    crit_dict : str
        Criteria to run function differently
    base_sim_param : dict
        Base simulation parameters

    Returns
    -------
    service_reduced : dict or array
        Reduced service after assumption on reuse

    Note
    ----
    A standard sigmoid diffusion is assumed from base year to end year
    """
    try:

        # Fraction of heat recovered until end_year
        heat_recovered_p_by = strategy_variables["heat_recoved__{}".format(enduse)]

        if heat_recovered_p_by == 0:
            return service
        else:
            # Fraction of heat recovered in current year
            sig_diff_factor = diffusion_technologies.sigmoid_diffusion(
                base_yr,
                curr_yr,
                strategy_variables['heat_recovered_yr_until_changed'],
                enduse_overall_change['other_enduse_mode_info']['sigmoid']['sig_midpoint'],
                enduse_overall_change['other_enduse_mode_info']['sigmoid']['sig_steeppness'])

            heat_recovered_p_cy = sig_diff_factor * heat_recovered_p_by

            # Apply to technologies each stored in dictionary
            if crit_dict == 'service_tech':
                service_reduced = {}
                for tech, service_tech in service.items():
                    service_reduced[tech] = service_tech * (1.0 - heat_recovered_p_cy)

            # Apply to array
            elif crit_dict == 'tot_service_y_cy':
                service_reduced = service * (1.0 - heat_recovered_p_cy)

            return service_reduced
    except:
        # no recycling defined
        return service

def apply_scenario_drivers(
        enduse,
        fuel_y,
        dw_stock,
        region_name,
        gva,
        population,
        reg_scen_drivers,
        base_sim_param
    ):
    """The fuel data for every end use are multiplied with respective
    scenario drivers. If no dwelling specific scenario driver is found,
    the identical fuel is returned.

    Arguments
    ----------
    enduse: str
        Enduse
    fuel_y : array
        Yearly fuel per fueltype
    dw_stock : object
        Dwelling stock
    region_name : str
        Region name
    data : dict
        Data container
    reg_scen_drivers : dict
        Scenario drivers per enduse
    base_sim_param : dict
        Base simulation parameters

    Returns
    -------
    fuel_y : array
        Changed yearly fuel per fueltype
    """
    if reg_scen_drivers is None:
        reg_scen_drivers = {}

    base_yr = base_sim_param['base_yr']
    curr_yr = base_sim_param['curr_yr']

    if not dw_stock:
        """Calculate non-dwelling related scenario drivers, if no dwelling stock
        Info: No dwelling stock is defined for this submodel
        """
        scenario_drivers = reg_scen_drivers[enduse]

        by_driver, cy_driver = 1, 1 #not 0

        for scenario_driver in scenario_drivers:

            # Get correct data depending on driver
            if scenario_driver == 'gva':
                by_driver_data = gva[base_yr][region_name]
                cy_driver_data = gva[curr_yr][region_name]
            elif scenario_driver == 'population':
                by_driver_data = population[base_yr][region_name]
                cy_driver_data = population[curr_yr][region_name]
            #TODO :ADD OTHER ENDSES

            # Multiply drivers
            by_driver *= by_driver_data
            cy_driver *= cy_driver_data
        try:
            factor_driver = cy_driver / by_driver # FROZEN (as in chapter 3.1.2 EQ E-2)
        except ZeroDivisionError:
            factor_driver = 1

        fuel_y = fuel_y * factor_driver
    else:
        """Scenario driver calculation based on dwelling stock
        """
        # Test if enduse has a dwelling related scenario driver
        if hasattr(dw_stock[region_name][base_yr], enduse) and curr_yr != base_yr:

            # Scenariodriver of dwelling stock base year and new stock
            by_driver = getattr(dw_stock[region_name][base_yr], enduse)
            cy_driver = getattr(dw_stock[region_name][curr_yr], enduse)

            # base year / current (checked) (as in chapter 3.1.2 EQ E-2)
            try:
                factor_driver = cy_driver / by_driver # FROZEN
            except ZeroDivisionError:
                factor_driver = 1

            fuel_y = fuel_y * factor_driver
        else:
            pass #enduse not define with scenario drivers

    return fuel_y

def apply_specific_change(
        enduse,
        fuel_y,
        enduse_overall_change,
        enduse_overall_change_strategy,
        sim_param
    ):
    """Calculates fuel based on assumed overall enduse
    specific fuel consumption changes

    Arguments
    ----------
    enduse : str
        Enduse
    fuel_y : array
        Yearly fuel per fueltype
    enduse_overall_change : dict
        Info about how the enduse is overall changed (e.g. diff method)
    enduse_overall_change_strategy : dict
        Change in overall enduse for every enduse (percent ey)
    sim_param : dict
        Simulation parameters

    Returns
    -------
    fuel_y : array
        Yearly new fuels

    Note
    -----
    -   Because for enduses where no technology stock is defined (and may
        consist of many different) technologies, a linear diffusion is
        suggested to best represent multiple sigmoid efficiency improvements
        of individual technologies.

    -   The changes are assumed across all fueltypes.

    -   Either a sigmoid standard diffusion or linear diffusion can be implemented.
        inear is suggested.
    """
    # Fuel consumption shares in base and end year
    percent_by = 1.0
    percent_ey = enduse_overall_change_strategy['enduse_change__{}'.format(enduse)]

    # Share of fuel consumption difference
    diff_fuel_consump = percent_ey - percent_by
    diffusion_choice = enduse_overall_change['other_enduse_mode_info']['diff_method']

    if diff_fuel_consump != 0: # If change in fuel consumption

        # Lineare diffusion up to cy
        if diffusion_choice == 'linear':
            lin_diff_factor = diffusion_technologies.linear_diff(
                sim_param['base_yr'],
                sim_param['curr_yr'],
                percent_by,
                percent_ey,
                enduse_overall_change_strategy['enduse_specific_change_yr_until_changed'])
            change_cy = lin_diff_factor

        # Sigmoid diffusion up to cy
        elif diffusion_choice == 'sigmoid':
            sig_diff_factor = diffusion_technologies.sigmoid_diffusion(
                sim_param['base_yr'],
                sim_param['curr_yr'],
                enduse_overall_change_strategy['enduse_specific_change_yr_until_changed'],
                enduse_overall_change['other_enduse_mode_info']['sigmoid']['sig_midpoint'],
                enduse_overall_change['other_enduse_mode_info']['sigmoid']['sig_steeppness'])
            change_cy = diff_fuel_consump * sig_diff_factor

        return fuel_y * change_cy
    else:
        return fuel_y

def apply_climate_change(
        enduse,
        fuel_new_y,
        cooling_factor_y,
        heating_factor_y,
        assumptions
    ):
    """Change fuel demand for heat and cooling service
    depending on changes in HDD and CDD within a region
    (e.g. climate change induced)

    Paramters
    ---------
    enduse : str
        Enduse
    fuel_new_y : array
        Yearly fuel per fueltype
    cooling_factor_y : array
        Distribution of fuel within year to days (yd)
    heating_factor_y : array
        Distribution of fuel within year to days (yd)
    assumptions : dict
        Assumptions

    Return
    ------
    fuel_new_y : array
        Changed yearly fuel per fueltype

    Note
    ----
    - `cooling_factor_y` and `heating_factor_y` are based on the sum
        over the year. Therefore it is assumed that fuel correlates
        directly with HDD or CDD.
    """
    if enduse in assumptions['enduse_space_heating']:
        fuel_new_y = fuel_new_y * heating_factor_y
    elif enduse in assumptions['enduse_space_cooling']:
        fuel_new_y = fuel_new_y * cooling_factor_y

    return fuel_new_y

def apply_smart_metering(
        enduse,
        fuel_y,
        sm_assump,
        sm_assump_strategy,
        base_yr,
        curr_yr
    ):
    """Calculate fuel savings depending on smart meter penetration

    Arguments
    ----------
    enduse : str
        Enduse
    fuel_y : array
        Yearly fuel per fueltype
    sm_assump : dict
        smart meter assumptions
    sm_assump_strategy : dict
        Base simulation parameters
    base_yr, curr_yr : int
        years

    Returns
    -------
    fuel_y : array
        New fuel per year

    Note
    -----
    - The smart meter penetration is assumed with a sigmoid diffusion.

    - In the assumptions the maximum penetration and also the
        generally fuel savings for each enduse can be defined.
    """
    try:

        # Sigmoid diffusion up to current year
        sigm_factor = diffusion_technologies.sigmoid_diffusion(
            base_yr,
            curr_yr,
            sm_assump_strategy['smart_meter_yr_until_changed'],
            sm_assump['smart_meter_diff_params']['sig_midpoint'],
            sm_assump['smart_meter_diff_params']['sig_steeppness'])

        # Smart Meter penetration (percentage of people having smart meters)
        penetration_by = sm_assump['smart_meter_p_by']
        penetration_cy = sm_assump['smart_meter_p_by'] + (
            sigm_factor * (sm_assump_strategy['smart_meter_p_future'] - sm_assump['smart_meter_p_by']))

        savings = sm_assump_strategy['smart_meter_improvement_{}'.format(enduse)]

        saved_fuel = fuel_y * (penetration_cy -penetration_by) * savings
        fuel_y = fuel_y - saved_fuel

        return fuel_y

    except:
        # not defined for this enduse
        return fuel_y

def calc_service_switch(
        tot_service_yh_cy,
        service_tech_by_p,
        tech_increase_service,
        tech_decrease_service,
        tech_constant_service,
        sig_param_tech,
        curr_yr
    ):
    """Apply change in service depending on
    defined service switches.

    Paramters
    ---------
    tot_service_yh_cy : array
        Hourly service of all technologies
    service_tech_by_p : dict
        Fraction of service per technology
    tech_increase_service : dict
        Technologies with increased service
    tech_decrease_service : dict
        Technologies with decreased service
    tech_constant_service : dict
        Technologies with constant service
    sig_param_tech : dict
        Sigmoid diffusion parameters
    curr_yr : int
        Current year

    Returns
    -------
    service_tech_yh_cy : dict
        Service per technology in current year after switch
        for every hour in a year

    Note
    ----
    The service which is fulfilled by new technologies is
    substracted of the replaced technologies proportionally
    to the base year distribution of these technologies
    """
    # Result dict with cy service for every technology
    service_tech_cy_p = {}

    # ------------
    # Update all technologies with constant service
    # ------------
    service_tech_cy_p.update(tech_constant_service)

    # ------------
    # Calculate service for technology with increased service
    # ------------
    service_tech_incr_cy_p = get_service_diffusion(
        tech_increase_service,
        sig_param_tech,
        curr_yr)

    service_tech_cy_p.update(service_tech_incr_cy_p)

    # ------------
    # Calculate service for technologies with decreasing service
    # ------------
    # Add base year of decreasing technologies to substract from that later on
    for tech in tech_decrease_service:
        service_tech_cy_p[tech] = service_tech_by_p[tech]

    # Calculate service share to assing for substracted fuel
    service_tech_decrease_by_rel = fuel_service_switch.get_service_rel_tech_decr_by(
        tech_decrease_service,
        service_tech_by_p)

    # Calculated gained service and substract this proportionally along all decreasing technologies
    for tech_incr, service_tech_incr_cy in service_tech_incr_cy_p.items():

        # Difference in service up to current year per technology
        diff_service_incr = service_tech_incr_cy - service_tech_by_p[tech_incr]

        # Substract service gain proportionaly to all technologies which are
        # lowered and substract from other technologies
        for tech_decr, service_tech_decr_by in service_tech_decrease_by_rel.items():
            service_to_substract_p_cy = service_tech_decr_by * diff_service_incr

            ##assert (service_tech_cy_p[tech_decr] - service_to_substract_p_cy) >= 0 #Leave away for speed uproses
            service_tech_cy_p[tech_decr] -= service_to_substract_p_cy

    # Assign total service share to service share of technologies
    service_tech_yh_cy = {}
    for tech, enduse_share in service_tech_cy_p.items():
        service_tech_yh_cy[tech] = tot_service_yh_cy * enduse_share

    return service_tech_yh_cy

def convert_service_to_p(tot_service_y, service_fueltype_tech):
    """Calculate fraction of service for every technology
    of total service

    Arguments
    ----------
    tot_service_y : float
        Total yearly service
    service_fueltype_tech : dict
        Service per technology and fueltype

    Returns
    -------
    service_tech_p : dict
        All tecnology services are
        provided as a fraction of total service

    Note
    ----
    Iterate over values in dict and apply calculations
    """
    if tot_service_y == 0:
        _total_service = 0
    else:
        _total_service = 1 / tot_service_y

    # Iterate all technologies and calculate fraction of total service
    service_tech_p = {}
    for tech_services in service_fueltype_tech.values():
        for tech, service_tech in tech_services.items():
            service_tech_p[tech] = _total_service * service_tech

    return service_tech_p

def get_service_diffusion(tech_increase_service, sig_param_tech, curr_yr):
    """Calculate energy service fraction of technologies with increased service
    for current year based on sigmoid diffusion

    Arguments
    ----------
    enduse : str
        Enduse
    tech_increase_service : dict
        All technologies per enduse with increased future service share
    sig_param_tech : dict
        Sigmoid diffusion parameters per technology
    curr_yr : dict
        Current year
    spatial_exliclit_diffusion : crit

    Returns
    -------
    service_tech : dict
        Share of service per technology of current year
    """
    service_tech = {}

    for tech in tech_increase_service:
        service_tech[tech] = diffusion_technologies.sigmoid_function(
            curr_yr,
            sig_param_tech[tech]['l_parameter'],
            sig_param_tech[tech]['midpoint'],
            sig_param_tech[tech]['steepness'])

    return service_tech
