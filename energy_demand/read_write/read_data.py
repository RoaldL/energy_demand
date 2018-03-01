"""Reading raw data

This file holds all functions necessary to read in information
and data to run the energy demand model.
"""
import sys
import os
import csv
import logging
from collections import defaultdict
import numpy as np
from energy_demand.technologies import tech_related
from energy_demand.profiles import load_profile
from energy_demand.scripts import init_scripts

class TechnologyData(object):
    """Class to store technology related data

    Arguments
    ---------
    fueltype : str
        Fueltype of technology
    eff_by : str, default=1
        Efficiency of technology in base year
    eff_ey : str, default=1
        Efficiency of technology in future year
    year_eff_ey : int
        Future year when eff_ey is fully realised
    eff_achieved : float
        Factor of how much of the efficienc future
        efficiency is achieved
    diff_method : float
        Differentiation method
    market_entry : int,default=2015
        Year when technology comes on the market
    tech_list : list
        List where technology is part of
    tech_max_share : float
        Maximum theoretical fraction of how much
        this indivdual technology can contribute
        to total energy service of its enduse
    fueltypes : crit or bool,default=None
        Fueltype or criteria
    """
    def __init__(
            self,
            fueltype=None,
            eff_by=None,
            eff_ey=None,
            year_eff_ey=None,
            eff_achieved=None,
            diff_method=None,
            market_entry=2015,
            tech_list=None,
            tech_max_share=None,
            description=None,
            fueltypes=None
        ):
        self.fueltype_str = fueltype
        self.fueltype_int = tech_related.get_fueltype_int(fueltypes, fueltype)
        self.eff_by = eff_by
        self.eff_ey = eff_ey
        self.year_eff_ey = year_eff_ey
        self.eff_achieved = eff_achieved
        self.diff_method = diff_method
        self.market_entry = market_entry
        self.tech_list = tech_list
        self.tech_max_share = tech_max_share
        self.description = description

class CapacitySwitch(object):
    """Capacity switch class for storing
    switches

    Arguments
    ---------
    enduse : str
        Enduse of affected switch
    technology_install : str
        Installed technology
    switch_yr : int
        Year until capacity installation is fully realised
    installed_capacity : float
        Installed capacity in GWh
    """
    def __init__(
            self,
            enduse,
            technology_install,
            switch_yr,
            installed_capacity,
            sector
        ):

        self.enduse = enduse
        self.technology_install = technology_install
        self.switch_yr = switch_yr
        self.installed_capacity = installed_capacity

        if sector == '':
            self.sector = None # Not sector defined
        else:
            self.sector = sector

class FuelSwitch(object):
    """Fuel switch class for storing
    switches

    Arguments
    ---------
    enduse : str
        Enduse of affected switch
    enduse_fueltype_replace : str
        Fueltype which is beeing switched from
    technology_install : str
        Installed technology
    switch_yr : int
        Year until switch is fully realised
    fuel_share_switched_ey : float
        Switched fuel share
    """
    def __init__(
            self,
            enduse=None,
            enduse_fueltype_replace=None,
            technology_install=None,
            switch_yr=None,
            fuel_share_switched_ey=None,
            sector=None
        ):
        """Constructor
        """
        self.enduse = enduse
        self.sector = sector
        self.enduse_fueltype_replace = enduse_fueltype_replace
        self.technology_install = technology_install
        self.switch_yr = switch_yr
        self.fuel_share_switched_ey = fuel_share_switched_ey

class ServiceSwitch(object):
    """Service switch class for storing
    switches

    Arguments
    ---------
    enduse : str
        Enduse of affected switch
    sector : str
        Sector
    technology_install : str
        Installed technology
    service_share_ey : float
        Service share of installed technology in future year
    switch_yr : int
        Year until switch is fully realised
    """
    def __init__(
            self,
            enduse=None,
            sector=None,
            technology_install=None,
            service_share_ey=None,
            switch_yr=None
        ):
        self.enduse = enduse
        self.technology_install = technology_install
        self.service_share_ey = service_share_ey
        self.switch_yr = switch_yr

        if sector == '':
            self.sector = None # Not sector defined
        else:
            self.sector = sector

def read_in_results(path_runs, seasons, model_yeardays_daytype):
    """Read and post calculate results from txt files
    and store into container

    Arguments
    ---------
    path_runs : str
        Paths
    seasons : dict
        seasons
    model_yeardays_daytype : dict
        Daytype of modelled yeardays

    """
    logging.info("... Reading in results")

    results_container = {}

    # -------------
    # Fuels
    # -------------
    results_container['results_enduse_every_year'] = read_enduse_specific_results(
        path_runs)

    results_container['results_every_year'] = read_results_yh(path_runs)

    results_container['tot_peak_enduses_fueltype'] = read_max_results(
        os.path.join(path_runs, "result_tot_peak_enduses_fueltype"))

    # -------------
    # Load factors
    # -------------
    results_container['load_factors_y'] = read_lf_y(
        os.path.join(path_runs, "result_reg_load_factor_y"))
    results_container['load_factors_yd'] = read_lf_y(
        os.path.join(path_runs, "result_reg_load_factor_yd"))

    results_container['load_factor_seasons'] = {}
    results_container['load_factor_seasons']['winter'] = read_lf_y(
        os.path.join(path_runs, "result_reg_load_factor_winter"))
    results_container['load_factor_seasons']['spring'] = read_lf_y(
        os.path.join(path_runs, "result_reg_load_factor_spring"))
    results_container['load_factor_seasons']['summer'] = read_lf_y(
        os.path.join(path_runs, "result_reg_load_factor_summer"))
    results_container['load_factor_seasons']['autumn'] = read_lf_y(
        os.path.join(path_runs, "result_reg_load_factor_autumn"))

    # -------------
    # Post-calculations
    # -------------
    # Calculate average per season and fueltype for every fueltype
    results_container['av_season_daytype_cy'], results_container['season_daytype_cy'] = calc_av_per_season_fueltype(
        results_container['results_every_year'],
        seasons,
        model_yeardays_daytype)

    logging.info("... Reading in results finished")
    return results_container

def calc_av_per_season_fueltype(results_every_year, seasons, model_yeardays_daytype):
    """Calculate average demand per season and fueltype for every fueltype

    Arguments
    ---------
    results_every_year : dict
        Results for every year
    seasons : dict
        Seasons
    model_yeardays_daytype : list
        Daytype of modelled days

    Returns
    -------
    av_season_daytype_cy : 
        Average demand per season and daytype
    season_daytype_cy : 
        Demand per season and daytpe
    """
    av_season_daytype_cy = defaultdict(dict)
    season_daytype_cy = defaultdict(dict)

    for year, fueltypes_data in results_every_year.items():

        for fueltype, reg_fuels in enumerate(fueltypes_data):

            # Summarise across regions
            tot_all_reg_fueltype = np.sum(reg_fuels, axis=0)

            tot_all_reg_fueltype_reshape = tot_all_reg_fueltype.reshape((365, 24))

            calc_av, calc_lp = load_profile.calc_av_lp(
                tot_all_reg_fueltype_reshape,
                seasons,
                model_yeardays_daytype)

            av_season_daytype_cy[year][fueltype] = calc_av
            season_daytype_cy[year][fueltype] = calc_lp

    return dict(av_season_daytype_cy), dict(season_daytype_cy)

def read_results_yh(path_to_folder):
    """Read results

    Arguments
    ---------
    fueltypes_nr : int
        Number of fueltypes
    reg_nrs : int
        Number of regions
    path_to_folder : str
        Path to folder

    Returns
    -------
    results = dict
        Results
    """
    results = {}

    path_to_folder = os.path.join(path_to_folder, 'result_tot_yh')

    all_txt_files_in_folder = os.listdir(path_to_folder)

    # Iterate files in folder
    for file_path in all_txt_files_in_folder:
        try:
            path_file_to_read = os.path.join(path_to_folder, file_path)
            file_path_split = file_path.split("__")
            year = int(file_path_split[1])

            results[year] = np.load(path_file_to_read)

        except IndexError:
            pass #path is a folder and not a file

    return results

def read_max_results(path):
    """Read max results

    Arguments
    ---------
    path : str
        Path to folder
    """
    results = {}
    all_txt_files_in_folder = os.listdir(path)

    # Iterate files
    for file_path in all_txt_files_in_folder:
        path_file_to_read = os.path.join(path, file_path)
        file_path_split = file_path.split("__")
        year = int(file_path_split[1])

        # Add year if not already exists
        results[year] = np.load(path_file_to_read)

    return results

def read_enduse_specific_results(path_to_folder):
    """Read enduse specific results

    Arguments
    ---------
    path_to_folder : str
        Folder path
    """
    results = defaultdict(dict)

    path_results = os.path.join(
        path_to_folder,
        "enduse_specific_results")

    all_txt_files_in_folder = os.listdir(path_results)

    for file_path in all_txt_files_in_folder:
        path_file_to_read = os.path.join(path_results, file_path)
        file_path_split = file_path.split("__")

        enduse = file_path_split[1]
        year = int(file_path_split[2])

        results[year][enduse] = np.load(path_file_to_read)

    return dict(results)

def load_script_data(data):
    """Load data generated by scripts
    #SCRAP REMOVE
    Arguments
    ---------
    data : dict
        Data container
    """
    init_cont, fuel_disagg = init_scripts.scenario_initalisation(
        data['paths']['path_main'],
        data)

    for key, value in init_cont.items():
        data['assumptions'][key] = value

    for key, value in fuel_disagg.items():
        data[key] = value

    return data

def read_fuel_ss(path_to_csv, fueltypes_nr):
    """This function reads in base_data_CSV all fuel types

    Arguments
    ----------
    path_to_csv : str
        Path to csv file
    fueltypes_nr : str
        Nr of fueltypes

    Returns
    -------
    fuels : dict
        Fuels per enduse
    sectors : list
        Service sectors
    enduses : list
        Service enduses
    """
    rows_list = []
    fuels = {}

    with open(path_to_csv, 'r') as csvfile:
        rows = csv.reader(csvfile, delimiter=',')
        _headings = next(rows) # Skip row
        _secondline = next(rows) # Skip row

        # All sectors
        sectors = set([])
        for sector in _secondline[1:]: #skip fuel ID:
            sectors.add(sector)

        # All enduses
        enduses = set([])
        for enduse in _headings[1:]: #skip fuel ID:
            enduses.add(enduse)

        # Initialise dict
        for enduse in enduses:
            fuels[enduse] = {}
            for sector in sectors:
                fuels[enduse][sector] = np.zeros((fueltypes_nr), dtype=float)

        for row in rows:
            rows_list.append(row)

        for cnt_fueltype, row in enumerate(rows_list):
            for cnt, entry in enumerate(row[1:], 1):
                enduse = _headings[cnt]
                sector = _secondline[cnt]
                fuels[enduse][sector][cnt_fueltype] += float(entry)

    return fuels, list(sectors), list(enduses)

def read_load_shapes_tech(path_to_csv):
    """This function reads in csv technology shapes

    Arguments
    ----------
    path_to_csv : str
        Path to csv file
    """
    load_shapes_dh = {}

    with open(path_to_csv, 'r') as csvfile:
        rows = csv.reader(csvfile, delimiter=',')
        _headings = next(rows) # Skip first row

        for row in rows:
            dh_shape = np.zeros((24), dtype=float)
            for cnt, row_entry in enumerate(row[1:], 1):
                dh_shape[int(_headings[cnt])] = float(row_entry)

            load_shapes_dh[str(row[0])] = dh_shape

    return load_shapes_dh

def service_switch(path_to_csv, technologies):
    """This function reads in service assumptions from csv file,
    tests whether the maximum defined switch is larger than
    possible for a technology,

    Arguments
    ----------
    path_to_csv : str
        Path to csv file
    technologies : list
        All technologies

    Returns
    -------
    enduse_tech_ey_p : dict
        Technologies per enduse for endyear in p
    service_switches : dict
        Service switches

    Notes
    -----
    The base year service shares are generated from technology stock definition

    Info
    -----
    The following attributes need to be defined for a service switch.

        Attribute                   Description
        ==========                  =========================
        enduse                      [str]   Enduse affected by switch
        tech                        [str]   Technology
        switch_yr                   [int]   Year until switch is fully realised
        service_share_ey            [str]   Service share of 'tech' in 'switch_yr'
        sector                      [str]   Optional sector specific info where switch applies
    """
    service_switches = []

    with open(path_to_csv, 'r') as csvfile:
        rows = csv.reader(csvfile, delimiter=',')
        _headings = next(rows) # Skip first row

        for row in rows:
            try:
                # Check if setor is defined
                try:
                    sector = str(row[4])
                except IndexError:
                    sector = ''

                service_switches.append(
                    ServiceSwitch(
                        enduse=str(row[0]),
                        technology_install=str(row[1]),
                        service_share_ey=float(row[2]),
                        switch_yr=float(row[3]),
                        sector=sector))

            except (KeyError, ValueError):
                sys.exit("Check if provided data is complete (no empty csv entries)")

    # Test if more service is provided as input than possible to maximum switch
    for entry in service_switches:
        if entry.service_share_ey > technologies[entry.technology_install].tech_max_share:
            sys.exit(
                "Input error: more service provided for tech '{}' in enduse '{}' than max possible".format(
                    entry['enduse'], entry['technology_install']))

    return service_switches

def read_fuel_switches(path_to_csv, enduses, fueltypes):
    """This function reads in from CSV file defined fuel
    switch assumptions

    Arguments
    ----------
    path_to_csv : str
        Path to csv file
    enduses : dict
        Endues per submodel
    fueltypes : dict
        Look-ups

    Returns
    -------
    dict_with_switches : dict
        All assumptions about fuel switches provided as input


    Info
    -----
    The following attributes need to be defined for a fuel switch.

        Attribute                   Description
        ==========                  =========================
        enduse                      [str]   Enduse affected by switch
        enduse_fueltype_replace     [str]   Fueltype to be switched from
        technology_install          [str]   Technology which is installed
        switch_yr                   [int]   Year until switch is fully realised
        fuel_share_switched_ey      [float] Share of fuel which is switched until switch_yr
        sector                      [str]   Optional sector specific info where switch applies
                                            If field is empty the switch is across all sectors
    """
    fuel_switches = []

    with open(path_to_csv, 'r') as csvfile:
        rows = csv.reader(csvfile, delimiter=',')
        _headings = next(rows)

        for row in rows:
            try:
                
                try:
                    sector = str(row[5])
                except IndexError:
                    sector = ''

                fuel_switches.append(
                    FuelSwitch(
                        enduse=str(row[0]),
                        enduse_fueltype_replace=fueltypes[str(row[1])],
                        technology_install=str(row[2]),
                        switch_yr=float(row[3]),
                        fuel_share_switched_ey=float(row[4]),
                        sector=sector))
            except (KeyError, ValueError):
                sys.exit("Check if provided data is complete (no emptly csv entries)")

    # Testing wheter the provided inputs make sense
    for obj in fuel_switches:
        if obj.fuel_share_switched_ey == 0:
            sys.exit(
                "Input error: The share of switched fuel must be > 0. Delete {} from input".format(
                    obj.technology_install))

    # --------
    # Testing
    # --------
    # Test if more than 100% per fueltype is switched
    for obj in fuel_switches:
        enduse = obj.enduse
        fueltype = obj.enduse_fueltype_replace
        tot_share_fueltype_switched = 0
        for obj_iter in fuel_switches:
            if enduse == obj_iter.enduse and fueltype == obj_iter.enduse_fueltype_replace:
                tot_share_fueltype_switched += obj_iter.fuel_share_switched_ey
        if tot_share_fueltype_switched > 1.0:
            sys.exit(
                "Input error: The fuel switches are > 1.0 for enduse {} and fueltype {}".format(
                    enduse, fueltype))

    # Test whether defined enduse exist
    for obj in fuel_switches:
        if obj.enduse in enduses['ss_enduses'] or obj.enduse in enduses['rs_enduses'] or obj.enduse in enduses['is_enduses']:
            pass
        else:
            sys.exit(
                "Input Error: The defined enduse '{}' to switch fuel from is not defined...".format(
                    obj.enduse))

    return fuel_switches

def read_technologies(path_to_csv, fueltypes):
    """Read in technology definition csv file. Append
    for every technology type a 'dummy_tech'.

    Arguments
    ----------
    path_to_csv : str
        Path to csv file

    Returns
    -------
    dict_technologies : dict
        All technologies and their assumptions provided as input
    dict_tech_lists : dict
        List with technologies. The technology type
        is defined in the technology input file. A dummy_tech
        is added for every list in order to allow that a generic
        technology type can be added for every enduse

    Info
    -----
    The following attributes need to be defined for implementing
    a technology.

        Attribute                   Description
        ==========                  =========================
        technology                  [str]   Name of technology
        fueltype                    [str]   Fueltype of technology
        eff_by                      [float] Efficiency in base year
        eff_ey                      [float] Efficiency in future end year
        year_eff_ey	                [int]   Future year where efficiency is fully reached
        eff_achieved                [float] Factor of how much of the efficiency
                                            is achieved (overwritten by scenario input)
                                            This is set to 1.0 as default for initial
                                            technology class generation
        diff_method	market_entry    [int]   Year of market entry of technology
        tech_list                   [str]   Definition of to which group
                                            of technologies a technology belongs
        tech_max_share              [float] Maximum share of technology related
                                            energy service which can be reached in theory
        description                 [str]   Optional technology description
    """
    dict_technologies = {}
    dict_tech_lists = {}

    with open(path_to_csv, 'r') as csvfile:
        rows = csv.reader(csvfile, delimiter=',')
        _headings = next(rows) # Skip heading

        for row in rows:
            technology = row[0]
            try:
                dict_technologies[technology] = TechnologyData(
                    fueltype=str(row[1]),
                    eff_by=float(row[2]),
                    eff_ey=float(row[3]),
                    year_eff_ey=float(row[4]),
                    eff_achieved=1.0, # Set to one as default
                    diff_method=str(row[5]),
                    market_entry=float(row[6]),
                    tech_list=str.strip(row[7]),
                    tech_max_share=float(str.strip(row[8])),
                    description=str(row[9]),
                    fueltypes=fueltypes)
                try:
                    dict_tech_lists[str.strip(row[7])].append(technology)
                except KeyError:
                    dict_tech_lists[str.strip(row[7])] = [technology]

            except Exception as e:

                logging.error(
                    "Error technology table (e.g. empty field): %s %s", e, row)
    
                sys.exit()

    # Add dummy_technology to all tech_lists
    for tech_list in dict_tech_lists.values():
        tech_list.append('dummy_tech')

    return dict_technologies, dict_tech_lists

def read_fuel_rs(path_to_csv):
    """This function reads in base_data_CSV all fuel types

    (first row is fueltype, subkey), header is appliances

    Arguments
    ----------
    path_to_csv : str
        Path to csv file
    _dt : str
        Defines dtype of array to be read in (takes float)

    Returns
    -------
    fuels : dict
        Residential fuels
    enduses : list
        Residential end uses

    Notes
    -----
    the first row is the fuel_ID
    The header is the sub_key
    """
    try:
        rows_list = []
        fuels = {}

        with open(path_to_csv, 'r') as csvfile:
            rows = csv.reader(csvfile, delimiter=',')
            _headings = next(rows) # Skip first row

            for row in rows:
                rows_list.append(row)

            for i in _headings[1:]: # skip first
                fuels[i] = np.zeros((len(rows_list)), dtype=float)

            for cnt_fueltype, row in enumerate(rows_list):
                cnt = 1 #skip first
                for fuel in row[1:]:
                    end_use = _headings[cnt]
                    fuels[end_use][cnt_fueltype] = float(fuel)
                    cnt += 1
    except (KeyError, ValueError):
        sys.exit(
            "Check if empty cells in the csv files for enduse '{}".format(
                end_use))

    # Create list with all rs enduses
    enduses = fuels.keys()

    return fuels, list(enduses)

def read_fuel_is(path_to_csv, fueltypes_nr, fueltypes):
    """This function reads in base_data_CSV all fuel types

    Arguments
    ----------
    path_to_csv : str
        Path to csv file
    fueltypes_nr : int
        Number of fueltypes
    fueltypes : dict
        Fueltypes

    Returns
    -------
    fuels : dict
        Industry fuels
    sectors : list
        Industral sectors
    enduses : list
        Industrial enduses

    Info
    ----
    Source: User Guide Energy Consumption in the UK
            https://www.gov.uk/government/uploads/system/uploads/attach
            ment_data/file/573271/ECUK_user_guide_November_2016_final.pdf

    High temperature processes
    =============================
    High temperature processing dominates energy consumption in the iron and steel,
    non-ferrous metal, bricks, cement, glass and potteries industries. This includes
        - coke ovens
        - blast furnaces and other furnaces
        - kilns and
        - glass tanks.

    Low temperature processes
    =============================
    Low temperature processes are the largest end use of energy for the food, drink
    and tobacco industry. This includes:
        - process heating and distillation in the chemicals sector;
        - baking and separation processes in food and drink;
        - pressing and drying processes, in paper manufacture;
        - and washing, scouring, dyeing and drying in the textiles industry.

    Drying/separation
    =============================
    Drying and separation is important in paper-making while motor processes are used
    more in the manufacture of chemicals and chemical products than in any other
    individual industry.

    Motors
    =============================
    This includes pumping, fans and machinery drives.

    Compressed air
    =============================
    Compressed air processes are mainly used in the publishing, printing and
    reproduction of recorded media sub-sector.

    Lighting
    =============================
    Lighting (along with space heating) is one of the main end uses in engineering
    (mechanical and electrical engineering and vehicles industries).

    Refrigeration
    =============================
    Refrigeration processes are mainly used in the chemicals and food and drink
    industries.

    Space heating
    =============================
    Space heating (along with lighting) is one of the main end uses in engineering
    (mechanical and electrical engineering and vehicles industries).

    Other
    =============================
    """
    rows_list = []
    fuels = {}

    with open(path_to_csv, 'r') as csvfile:
        rows = csv.reader(csvfile, delimiter=',')
        _headings = next(rows)
        _secondline = next(rows)

        # All sectors
        enduses = set([])
        for enduse in _headings[1:]:
            if enduse is not '':
                enduses.add(enduse)

        # All enduses
        sectors = set([])
        for row in rows:
            rows_list.append(row)
            sectors.add(row[0])

        # Initialise dict
        for enduse in enduses:
            fuels[enduse] = {}
            for sector in sectors:

                fuels[str(enduse)][str(sector)] = np.zeros(
                    (fueltypes_nr), dtype=float)

        for row in rows_list:
            sector = row[0]
            for position, entry in enumerate(row[1:], 1): # Start with position 1

                if entry != '':
                    enduse = str(_headings[position])
                    fueltype = _secondline[position]
                    fueltype_int = tech_related.get_fueltype_int(fueltypes, fueltype)
                    fuels[enduse][sector][fueltype_int] += float(row[position])

    return fuels, list(sectors), list(enduses)

def read_lf_y(result_path):
    """Read load factors from .npy file

    Arguments
    ----------
    result_path : str
        Path

    Returns
    -------
    results : dict
        Annual results
    """
    results = {}

    all_txt_files_in_folder = os.listdir(result_path)

    for file_path in all_txt_files_in_folder:
        path_file_to_read = os.path.join(result_path, file_path)
        file_path_split = file_path.split("__")
        year = int(file_path_split[1])

        results[year] = np.load(path_file_to_read)

    return results

def read_scenaric_population_data(result_path):
    """Read population data

    Arguments
    ---------
    result_path : str
        Path

    Returns
    -------
    results : dict
        Population, {year: np.array(fueltype, regions)}

    """
    results = {}

    all_txt_files_in_folder = os.listdir(
        result_path)

    # Iterate files
    for file_path in all_txt_files_in_folder:
        path_file_to_read = os.path.join(result_path, file_path)
        file_path_split = file_path.split("__")
        year = int(file_path_split[1])

        # Add year if not already exists
        results[year] = np.load(path_file_to_read)

    return results

def read_capacity_switch(path_to_csv):
    """This function reads in service assumptions
    from csv file

    Arguments
    ----------
    path_to_csv : str
        Path to csv file

    Returns
    -------
    service_switches : dict
        Service switches which implement the defined capacity installation

    Info
    -----
    The following attributes need to be defined for a capacity switch.

        Attribute                   Description
        ==========                  =========================
        enduse                      [str]   Enduse affected by switch
        tech                        [str]   Technology installed
        switch_yr                   [int]   Year until switch is fully realised
        installed_capacity          [float] Installed total capacity in GWh
        sector                      [str]   Optional sector specific info where switch applies
                                            If field is empty the switch is across all sectors

    """
    service_switches = []

    with open(path_to_csv, 'r') as csvfile:
        rows = csv.reader(csvfile, delimiter=',')
        _headings = next(rows)

        for row in rows:
            try:
                
                # Check if setor is defined
                try:
                    sector = str(row[4])
                except IndexError:
                    sector = ''

                service_switches.append(
                    CapacitySwitch(
                        enduse=str(row[0].strip()),
                        technology_install=str(row[1].strip()),
                        switch_yr=float(row[2].strip()),
                        installed_capacity=float(row[3].strip()),
                        sector=sector))

            except (KeyError, ValueError):
                sys.exit(
                    "Error in loading capacity switch: Check if no emptly csv entries (except for optional sector field)")

    return service_switches

def read_floor_area_virtual_stock(path_to_csv):
    """Read in floor area from csv file for every LAD
    to generate virtual building stock.

    Arguments
    ---------
    path_floor_area : str
        Path to csv file

    Returns
    -------
    res_floorarea : dict
        Residential floor area per region
    non_res_floorarea : dict
        Non residential floor area per region
    """
    res_floorarea, non_res_floorarea = {}, {}

    with open(path_to_csv, 'r') as csvfile:
        rows = csv.reader(csvfile, delimiter=',')
        _headings = next(rows)

        for row in rows:
            geo_name = str.strip(row[get_position(_headings, 'lad')])
            res_floorarea[geo_name] = float(row[get_position(_headings, 'res_footprint_area')])
            non_res_floorarea[geo_name] = float(row[get_position(_headings, 'nonres_footprint_area')])

    return res_floorarea, non_res_floorarea

def get_position(headings, name):
    """Read position in list

    Arguments
    ---------
    headings : list
        List with names
    name : str
        Name of entry to find

    Returns
    -------
    position : int
        Position in list
    """
    for position, value in enumerate(headings):
        if str(value) == str(name):
            return position

def read_np_array_from_txt(path_file_to_read):
    """Read np array from textfile

    Arguments
    ---------
    path_file_to_read : str
        File to path with stored array

    Return
    ------
    txt_array : array
        Array containing read text
    """
    txt_array = np.loadtxt(path_file_to_read, delimiter=',')
    return txt_array
