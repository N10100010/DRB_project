import numpy as np

from .api import get_competition_ids, get_by_competition_id, get_by_competition_id_
from .utils_wr import load_json
import requests

import logging

logger = logging.getLogger(__name__)

from . import api
########################################################################################################################
# NOTE:
# This main.py is just for rapid testing
########################################################################################################################
import json
from sys import exit as sysexit


def grab_competition_example(competition_id, out_path='dump.json'):
    comp_data = get_by_competition_id_(comp_ids=[str(competition_id)], parse_pdf=False)
    with open(out_path, "w", encoding='ascii') as fp:
        json.dump(comp_data, fp)


if __name__ == '__main__':
    import argparse

    DEFAULT_COMPETITION = '718b3256-e778-4003-88e9-832c4aad0cc2'

    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(help='Available sub-commands', dest='command')
    parser_cgrab = subparsers.add_parser('grabc', help='Grab a competition and save as JSON')
    parser_cgrab.add_argument("-i", "--uuid", help="Scrape competition and save as JSON", default=DEFAULT_COMPETITION)
    parser_cgrab.add_argument("-o", "--out", help="Specify path for output", default="dump.json")

    args = parser.parse_args()
    print(args)

    if args.command == 'grabc':
        grab_competition_example(args.uuid, args.out)
        sysexit()

    ### KEEP FOR TESTING

    #_ids_all = []
    #for y in np.arange(2000, 2024):
    #    _ids_all.extend(get_competition_ids(y))

    #ret = api.get_by_competition_id(_ids_all, ['races', 'pdf'])

    #api.save(ret, './races_2000_2024_pdfs.json')

    ret = api.load('./races_2000_2024_pdfs.json')

    import collections
    d = dict()

    tup_set__rsc_disname = set()
    tup_set__rsc_disname_short = set()
    # [race for race in ret['races'] if 'RND' in race["RscCode"]]
    test = set()
    extracted = set()
    race_disname = set()
    for race in ret['races']:
        boat_class, rsc = api.process_rsc_code(race['RscCode'])
        tup_set__rsc_disname.add((api.extract_race_phase_from_rsc(rsc), api.process_race_display_name(race['DisplayName']), race['DisplayName']))
        tup_set__rsc_disname_short.add((rsc, api.process_race_display_name(race['DisplayName'])))
        #if len(race['pdfUrls']['results']) != 0:
        #    d[(rsc, api.process_race_display_name(race['DisplayName']))] = race['pdfUrls']
        race['rsc_race_phase'] = api.extract_race_phase_from_rsc(rsc)
        test.add(rsc)
        extracted.add(api.extract_race_phase_from_rsc(rsc))
        race_disname.add(race['DisplayName'])

    #d = collections.OrderedDict(sorted(d.items()))
    extracted = sorted(extracted)
    tup_set = sorted(tup_set__rsc_disname)
    tup_set_short = sorted(tup_set__rsc_disname_short)


    # tuple_set__rsc_racePhase = set()
    # for race in ret['races']:
    #     boat_class, phase = api.process_rsc_code(race['RscCode'])
    #     rpdn = ' '.join(race['DisplayName'].split(' ')[-3:-1])
    #     rp = race['racePhase']['DisplayName']
    #
    #     tuple_set__rsc_racePhase.add((rp, phase))
    #
    # tuple_set__rsc_racePhase = sorted(tuple_set__rsc_racePhase)

    print()
    #
    # # extract race phases
    # race_phases = set()
    # race_statuses = set()
    # race_genders = set()  # races have gender? --> ofcourse they have gender ids. the races are separated by gender
    # for race in ret['races']:
    #     race_status = race['raceStatus']
    #     race_phase = race['racePhase']
    #     race_phases.add((race_phase['DisplayName'], race_phase['id']))
    #     race_statuses.add((race_status['DisplayName'], race_status['id']))
    #     race_genders.add(race['genderId'])
    #


    #ret = api.get_by_competition_id('718b3256-e778-4003-88e9-832c4aad0cc2', 'everything')
    #ret = api.load('./one_comp_id.json')


    print()  # breakpoint me

