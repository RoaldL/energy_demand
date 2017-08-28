"""Virtual Building Generator

"""
import sys
import numpy as np
from energy_demand.technologies import diffusion_technologies as diffusion

class Dwelling(object):
    """Dwelling or aggregated group of dwellings

    Parameters
    ----------
    curr_yr : int
        Current year of simulation
    coordinates : float
        coordinates
    dwtype : int
        Dwelling type id. Description can be found in `daytype_lu`
    house_id : int
        Unique ID of dwelling or dwelling group
    age : int
        Age of dwelling in years (year the building was built)
    pop : float
        Dwelling population
    floorarea : float
        Floor area of dwelling
    hlc : float
        Heat loss coefficient
    hdd : float
        Heating degree days

    Note
    -----
    - Depending on service or residential model, not all attributes
      are filled (then they are inistialised as None or zero)
    - For every dwelling, the scenario drivers are calculated for each enduse

    """
    def __init__(self, curr_yr, region_name, coordinates, floorarea, enduses, driver_assumptions, population=0, age=None, dwtype=None, sector_type=None):
        """Constructor of Dwelling Class
        """
        self.dw_region_name = region_name
        self.curr_yr = curr_yr
        self.enduses = enduses
        self.longitude = coordinates['longitude']
        self.latitude = coordinates['longitude']
        self.dwtype = dwtype
        self.age = age
        self.population = population
        self.floorarea = floorarea
        self.sector_type = sector_type

        self.gva = 999 #TODO:

        # Testing
        assert floorarea != 0
    
        #: Calculate heat loss coefficient with age and dwelling type if possible
        self.hlc = self.get_hlc(dwtype, age)

        # Generate attribute for each enduse containing calculated scenario driver value
        self.calc_scenario_driver(driver_assumptions)


    def calc_scenario_driver(self, driver_assumptions):
        """Sum scenario drivers per enduse and add as attribute

        Parameters
        ---------
        driver_assumptions : dict
            Scenario drivers for every enduse
        """
        for enduse in self.enduses:
            scenario_driver_value = 1 #used to sum (not zero!)

            # If there is no scenario drivers for enduse, set to standard value 1
            if enduse not in driver_assumptions:
                Dwelling.__setattr__(self, enduse, scenario_driver_value)
            else:
                scenario_drivers = driver_assumptions[enduse]

                # Iterate scenario driver and get attriute to multiply values
                for scenario_driver in scenario_drivers:
                    print("enduse:  {} {}  {}".format(enduse, scenario_driver, getattr(self, scenario_driver)))
                    scenario_driver_value *= getattr(self, scenario_driver) #: sum drivers

                # Set attribute
                Dwelling.__setattr__(
                    self,
                    enduse,
                    scenario_driver_value
                    )

            if scenario_driver_value == 0:
                print("ddd")
            # Testing
            assert scenario_driver_value != 0

        return

    @classmethod
    def get_hlc(cls, dw_type, age):
        """Calculates the linearly derived heat loss coeeficients depending on age and dwelling type

        Parameters
        ----------
        dw_type : int
            Dwelling type
        age : int
            Age of dwelling

        Returns
        -------
        hls : Heat loss coefficient [W/m2 * K]

        Notes
        -----
        Source: Linear trends derived from Table 3.17 ECUK Tables
        https://www.gov.uk/government/collections/energy-consumption-in-the-uk
        """

        if dw_type is None or age is None:
            print("The HLC could not be calculated of a dwelling")
            return None

        # Dict with linear fits for all different dwelling types {dw_type: [slope, constant]}
        linear_fits_hlc = {
            0: [-0.0223, 48.292], # Detached
            1: [-0.0223, 48.251], # Semi-Detached
            2: [-0.0223, 48.063], # Terraced Average
            3: [-0.0223, 47.02], # Flats
            4: [-0.0223, 48.261], # Bungalow
            }

        # Get linearly fitted value
        hlc = linear_fits_hlc[dw_type][0] * age + linear_fits_hlc[dw_type][1]

        return hlc

class DwellingStock(object):
    """Class of the building stock in a region_name
    """
    def __init__(self, region_name, dwellings, enduses):
        """Returns a new building stock region_name object.

        Parameters
        ----------
        region_name : float
            Region of the dwelling
        dwellings : list
            List containing all dwelling objects
        enduses : list
            Enduses
        """
        self.region_name = region_name
        self.dwellings = dwellings

        self.population = self.get_tot_pop()

        # SUM: (but same name as in dwelling)Summed scenario drivers across all dwellings for every enduse
        # Set for the dwelling stock attributes for every enduse
        for enduse in enduses:
            DwellingStock.__setattr__(
                self,
                enduse,
                self.get_scenario_driver_enduse(enduse)
                )

    def get_scenario_driver_enduse(self, enduse):
        """Sum all scenario driver for space heating

        Parameters
        ----------
        enduse: string
            Enduse
        """
        sum_driver = 0
        for dwelling in self.dwellings:
            sum_driver += getattr(dwelling, enduse)

        return sum_driver

    def get_tot_pop(self):
        """Get total population of all dwellings
        """
        tot_pop = 0
        for dwelling in self.dwellings:
            tot_pop += dwelling.population

        return tot_pop

def get_floorare_pp(floorarea, reg_pop_by, sim_param, assump_final_diff_floorarea_pp):
    """Calculate future floor area per person depending
    on assumptions on final change and base year data

    Parameters
    ----------
    floorarea : dict
        Floor area base year for all regions
    reg_pop_by : dict
        Population of base year for all regions
    sim_param, : int
        Simulation parameters
    assump_final_diff_floorarea_pp : float
        Assumption of change in floor area up to end of simulation

    Returns
    -------
    data_floorarea_pp : dict
        Contains all values for floor area per person for every year

    Note
    ----
    - Linear change of floor area per person is assumed over time
    """
    data_floorarea_pp = {}

    for region, region_pop in reg_pop_by.items():
        floor_area_pp = {}

        if region_pop == 0:
            floorarea_pp_by = 0
        else:
            # Floor area per person of base year
            floorarea_pp_by = floorarea[region] / region_pop

        for curr_yr in sim_param['sim_period']:
            if curr_yr == sim_param['base_yr']:
                floor_area_pp[curr_yr] = floorarea_pp_by
            else:
                # Change up to current year (linear)
                lin_diff_factor = diffusion.linear_diff(
                    sim_param['base_yr'],
                    curr_yr,
                    0,
                    assump_final_diff_floorarea_pp,
                    sim_param['sim_period_yrs']
                    )

                # Floor area per person of simulation year
                floor_area_pp[curr_yr] = floorarea_pp_by + (floorarea_pp_by * lin_diff_factor)

        data_floorarea_pp[region] = floor_area_pp

    return data_floorarea_pp

def get_dwtype_distr(dwtype_distr_by, assump_dwtype_distr_ey, sim_param):
    """Calculates the annual distribution of dwelling types
    based on assumption of base and end year distribution

    Parameters
    ----------
    dwtype_distr_by : dict
        Distribution of dwelling types base year
    assump_dwtype_distr_ey : dict
        Distribution of dwelling types end year
    sim_param : list
        Simulation parameters

    Returns
    -------
    dwtype_distr : dict
        Contains all dwelling type distribution for every year
    Note
    -----
    - A linear change over time is assumed

    Example
    -------
    out = {year: {'dwtype': 0.3}}
    """
    dwtype_distr = {}

    for curr_yr in sim_param['sim_period']:
        nr_sim_yrs = curr_yr - sim_param['base_yr']

        if curr_yr == sim_param['base_yr']:
            y_distr = dwtype_distr_by
        else:
            y_distr = {}

            for dwtype in dwtype_distr_by:
                val_by = dwtype_distr_by[dwtype]
                val_ey = assump_dwtype_distr_ey[dwtype]
                diff_val = val_ey - val_by

                # Calculate linear difference up to sim_yr
                diff_y = diff_val / sim_param['sim_period_yrs']
                y_distr[dwtype] = val_by + (diff_y * nr_sim_yrs)

        dwtype_distr[curr_yr] = y_distr

    # Test if distribution is 100%
    for year in dwtype_distr:
        np.testing.assert_almost_equal(
            sum(dwtype_distr[year].values()),
            1.0,
            decimal=5,
            err_msg='The distribution of dwelling types went wrong', verbose=True
            )

    return dwtype_distr

def ss_build_stock(regions, data):
    """Create dwelling stock for service sector with service dwellings

    Iterate years and change floor area depending on assumption on
    linear change up to ey

    Parameters
    ----------
    data : dict
        Data

    Returns
    -------

    """
    dwelling_stock = {}

    # Iterate regions
    for region_name in regions:
        dwelling_stock[region_name] = {}

        # Iterate simulation year
        for sim_yr in data['sim_param']['sim_period']:

            # ------------------
            # Generate serivce dwellings
            # ------------------
            dw_stock = []

            # Iterate sectors
            for sector in data['ss_sectors']:

                # -------------------------
                #TODO: READ FROM Newcastle DATASET
                # -------------------------

                # -------------------------
                # -- Virstual service stock (so far very simple, e.g. not age considered)
                # -------------------------
                # Base year floor area
                floorarea_sector_by = data['ss_sector_floor_area_by'][region_name][sector]

                # Change in floor area up to end year
                if sector in data['assumptions']['ss_floorarea_change_ey_p']:
                    change_floorarea_p_ey = data['assumptions']['ss_floorarea_change_ey_p'][sector]
                else:
                    sys.exit("Error: The virtual ss building stock sector floor area assumption is not defined")

                # Floor area of sector in current year considering linear diffusion
                lin_diff_factor = diffusion.linear_diff(data['sim_param']['base_yr'], sim_yr, 1.0, change_floorarea_p_ey, data['sim_param']['sim_period_yrs'])

                floorarea_sector_cy = floorarea_sector_by + lin_diff_factor

                if floorarea_sector_cy == 0:
                    sys.exit("ERROR: FLOORAREA CANNOT BE ZERO")

                # create building object
                dw_stock.append(
                    Dwelling(
                        curr_yr=sim_yr,
                        region_name=region_name,
                        coordinates=data['reg_coordinates'][region_name],
                        floorarea=floorarea_sector_cy,
                        enduses=data['ss_all_enduses'],
                        driver_assumptions=data['assumptions']['scenario_drivers']['ss_submodule'],
                        sector_type=sector
                    )
                )

            # Add regional base year dwelling to dwelling stock
            dwelling_stock[region_name][sim_yr] = DwellingStock(
                region_name,
                dw_stock,
                data['ss_all_enduses']
                )

    return dwelling_stock

def rs_dwelling_stock(regions, data):
    """Creates a virtual building stock for every year and region

    Parameters
    ----------
    regions : dict
        Regions
    data : dict
        Data container

    Returns
    -------
    dwelling_stock : dict
        Building stock wei

    reg_dw_stock_by : Base year building stock
        reg_building_stock_yr : Building stock for every simulation year

    Notes
    -----
    - The assumption about internal temperature change is
      used as for each dwelling the hdd are calculated
      based on wheater data and assumption on t_base
    """
    base_yr = data['sim_param']['base_yr']

    dwelling_stock = {}

    # Get distribution of dwelling types of all simulation years
    dwtype_distr = get_dwtype_distr(
        data['assumptions']['assump_dwtype_distr_by'],
        data['assumptions']['assump_dwtype_distr_ey'],
        data['sim_param']
        )

    # Get floor area per person for every simulation year
    data_floorarea_pp = get_floorare_pp(
        data['reg_floorarea_resid'],
        data['population'][base_yr],
        data['sim_param'],
        data['assumptions']['assump_diff_floorarea_pp']
        )

    # Get fraction of total floorarea for every dwelling type
    floorarea_p = get_floorarea_dwtype_p(
        data['dwtype_lu'],
        data['assumptions']['assump_dwtype_floorarea'],
        dwtype_distr
        )

    for region in regions:

        floorarea_by = data['reg_floorarea_resid'][region]
        pop_by = data['population'][base_yr][region]

        if pop_by != 0:
            floorarea_pp_by = floorarea_by / pop_by # [m2 / person]
        else:
            floorarea_pp_by = 0

        dwelling_stock[region] = {}

        for curr_yr in data['sim_param']['sim_period']:

            # Calculate new necessary floor area  per person of current year
            floorarea_pp_cy = data_floorarea_pp[region][curr_yr]
            population_cy = data['population'][curr_yr][region]

            # Calculate new floor area
            tot_floorarea_cy = floorarea_pp_cy * population_cy
            new_floorarea_cy = tot_floorarea_cy - floorarea_by

            # Only calculate changing
            if curr_yr == base_yr:

                dw_stock_base = generate_dw_existing(
                    data=data,
                    region_name=region,
                    curr_yr=curr_yr,
                    dw_lu=data['dwtype_lu'],
                    floorarea_p=floorarea_p[base_yr],
                    floorarea_by=floorarea_by,
                    dwtype_age_distr_by=data['assumptions']['dwtype_age_distr'][base_yr],
                    floorarea_pp=floorarea_pp_by,
                    tot_floorarea_cy=floorarea_by,
                    pop_by=pop_by
                    )

                # Create regional base year building stock
                dwelling_stock[region][base_yr] = DwellingStock(
                    region,
                    dw_stock_base,
                    data['rs_all_enduses']
                    )
            else:
                """The number of people in the base year dwelling stock may change.
                If the floor area pp decreased with constant pop, the same number of
                people will be living in too large houses. It is not assumed
                that area is demolished.
                """
                floor_area_cy = pop_by * floorarea_pp_cy

                if floor_area_cy > floorarea_by:
                    demolished_area = 0
                else:
                    demolished_area = floorarea_by - floor_area_cy

                remaining_area = floorarea_by - demolished_area

                # In existing building stock fewer people are living, i.e. density changes
                pop_by = floorarea_by / floorarea_pp_cy 

                dw_stock_cy = generate_dw_existing(
                    data=data,
                    region_name=region,
                    curr_yr=curr_yr,
                    dw_lu=data['dwtype_lu'],
                    floorarea_p=floorarea_p[curr_yr],
                    floorarea_by=remaining_area,
                    dwtype_age_distr_by=data['assumptions']['dwtype_age_distr'][base_yr],
                    floorarea_pp=floorarea_pp_cy,
                    tot_floorarea_cy=remaining_area,
                    pop_by=pop_by
                    )

                # Append buildings of new floor area to 
                if new_floorarea_cy > 0:
                    #print("=================================")
                    #print("floorarea_pp_cy   " + str(tot_floorarea_cy))
                    #print("new_floorarea_cy: " + str(new_floorarea_cy))
                    #print("floorarea_pp_by   " + str(floorarea_pp_by))
                    #print("floorarea_pp_cy   " + str(floorarea_pp_cy))
                    dw_stock_cy = generate_dw_new(
                        data=data,
                        region_name=region,
                        curr_yr=curr_yr,
                        floorarea_p_by=floorarea_p[curr_yr],
                        floorarea_pp_cy=floorarea_pp_cy,
                        dw_stock_new_dw=dw_stock_cy,
                        new_floorarea_cy=new_floorarea_cy
                        )
                else:
                    # no new floor area is added
                    pass

                # Generate region and save it in dictionary (Add old and new buildings to stock)
                dwelling_stock[region][curr_yr] = DwellingStock(
                    region,
                    dw_stock_cy,
                    data['rs_all_enduses']
                    )

        # Add regional base year building stock
        #dwelling_stock[region][base_yr] = DwellingStock(region, dw_stock_base, data['rs_all_enduses']) # Add base year stock

    return dwelling_stock

def get_floorarea_dwtype_p(dw_lookup, dw_floorarea_by, dwtype_distr):
    """Calculates the percentage of the total floor area
    belonging to each dwelling type. Depending on average
    floor area per dwelling type and the dwelling type
    distribution, the percentages are calculated
    for ever simulation year

    Parameters
    ----------
    dw_lookup : dw_lookup
        Dwelling types
    dw_floorarea_by : dict
        floor area per type
    dwtype_distr : dict
        Distribution of dwelling type over the simulation period

    Returns
    -------
    dw_floorarea_p : dict
        Contains the percentage of the total floor
        area for each dwtype for every simulation year (must be 1.0 in tot)

    Notes
    -----
    This calculation is necessary as the share of dwelling types may differ depending the year
    """
    dw_floorarea_p = {}

    for current_yr in dwtype_distr:
        area_dw_type = {}

        # Calculate share of dwelling area based on absolute size and distribution
        for _, dwelling_name in dw_lookup.items():

            # Get distribution of dwellings of current year
            dwelling_type_p = dwtype_distr[current_yr][dwelling_name]

            # Get absolut size of dw_type
            area_dw = dwelling_type_p * dw_floorarea_by[dwelling_name]

            area_dw_type[dwelling_name] = area_dw

        # Convert absolute values into percentages
        tot_area = sum(area_dw_type.values())
        for dw_type, dw_type_area in area_dw_type.items():
            area_dw_type[dw_type] = (1 / tot_area) * dw_type_area

        dw_floorarea_p[current_yr] = area_dw_type

    return dw_floorarea_p

def generate_dw_existing(data, region_name, curr_yr, dw_lu, floorarea_p, floorarea_by, dwtype_age_distr_by, floorarea_pp, tot_floorarea_cy, pop_by):
    """Generates dwellings according to age, floor area and distribution assumption

    Parameters
    ----------
    data : dict
        Data container
    region_name : dict
        Region name
    curr_yr : int
        Base year
    dw_lu : dict
        Dwelling type look-up
    floorarea_p : dict
        Fraction of floor area per dwelling type
    floorarea_by : dict
        Floor area of base year
    dwtype_age_distr_by : dict
        Age distribution of dwelling
    floorarea_pp : dict
        Floor area per person
    tot_floorarea_cy : float
        Floor are in current year
    pop_by : dict
        Population in base year

    Return
    ------
    dw_stock_by : list
        Dwelling stocks in a list
    """
    dw_stock_by, control_pop, control_floorarea = [], 0, 0

    # Iterate dwelling types
    for dw_type, dw_type_name in dw_lu.items():
        
        # Calculate floor area per dwelling type
        dw_type_floorarea = floorarea_p[dw_type_name] * floorarea_by 

        # Distribute according to age
        for dwtype_age_id in dwtype_age_distr_by:
            age_class_p = dwtype_age_distr_by[dwtype_age_id] / 100 # Percent of dw of age class

            # Floor area of dwelling_class_age
            dw_type_age_class_floorarea = dw_type_floorarea * age_class_p # Distribute proportionally floor area

            control_floorarea += dw_type_age_class_floorarea

            # Pop
            if floorarea_pp != 0:
                pop_dwtype_age_class = dw_type_age_class_floorarea / floorarea_pp # Floor area is divided by base area value
            else:
                pop_dwtype_age_class = 0

            control_pop += pop_dwtype_age_class

            if dw_type_age_class_floorarea == 0:
                sys.exit("ERROR 2: FLOORAREA CANNOT BE ZERO")
        
            # create building object
            dw_stock_by.append(
                Dwelling(
                    curr_yr=curr_yr,
                    region_name=region_name,
                    coordinates=data['reg_coordinates'][region_name],
                    floorarea=dw_type_age_class_floorarea,
                    enduses=data['rs_all_enduses'],
                    driver_assumptions=data['assumptions']['scenario_drivers']['rs_submodule'],
                    population=pop_dwtype_age_class,
                    age=float(dwtype_age_id),
                    dwtype=dw_type
                    )
                )

            # TODO: IF Necessary calculate absolute number of buildings by dividng by the average floor size of a dwelling
            # Calculate number of dwellings

    #Testing
    np.testing.assert_array_almost_equal(tot_floorarea_cy, control_floorarea, decimal=3, err_msg="Error NR XXX  {} ---  {}".format(tot_floorarea_cy, control_floorarea))    # Test if floor area are the same
    np.testing.assert_array_almost_equal(pop_by, control_pop, decimal=3, err_msg="Error NR XXX")

    return dw_stock_by

def generate_dw_new(data, region_name, curr_yr, floorarea_p_by, floorarea_pp_cy, dw_stock_new_dw, new_floorarea_cy):
    """Generate dwelling objects for all new dwellings

    All new dwellings are appended to the existing
    building stock of the region

    Parameters
    ----------
    data : dict
        Data container
    region_name : str
        Region
    curr_yr : int
        Current year
    floorarea_p_by : dict
        Fraction of floorarea in base year
    floorarea_pp_cy : dict
        Floor area per person in current year
    dw_stock_new_dw : dict
        New dwellings
    new_floorarea_cy : dict
        New floorarea in current year

    Returns
    -------
    dw_stock_new_dw : list
        List with appended dwellings

    Notes
    -----
    The floor area id divided proprtionally depending on dwelling type
    Then the population is distributed
    builindg is creatd
    """
    control_pop, control_floorarea = 0, 0

    # Iterate dwelling types
    for dwelling_type, dw_type_name in data['dwtype_lu'].items():

        # Calculate new floor area per dewlling type
        dw_type_new_floorarea = floorarea_p_by[dw_type_name] * new_floorarea_cy

        control_floorarea += dw_type_new_floorarea

        # Calculate pop (Floor area is divided by floorarea_per_person)
        pop_dwtype_new_build_cy = dw_type_new_floorarea / floorarea_pp_cy             
        control_pop += pop_dwtype_new_build_cy

        if dw_type_new_floorarea == 0:
            sys.exit("ERROR: FLOORAREA CANNOT BE ZERO")

        # create building object
        dw_stock_new_dw.append(
            Dwelling(
                curr_yr=curr_yr,
                region_name=region_name,
                coordinates=data['reg_coordinates'][region_name],
                floorarea=dw_type_new_floorarea,
                enduses=data['rs_all_enduses'],
                driver_assumptions=data['assumptions']['scenario_drivers']['rs_submodule'],
                population=pop_dwtype_new_build_cy,
                age=curr_yr,
                dwtype=dwelling_type
                )
            )

    # Test if floor area are the same
    assert round(new_floorarea_cy, 3) == round(control_floorarea, 3)
    # Test if pop is the same
    assert round(new_floorarea_cy/floorarea_pp_cy, 3) == round(control_pop, 3)

    return dw_stock_new_dw
