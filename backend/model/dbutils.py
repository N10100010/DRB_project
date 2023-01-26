

from sqlalchemy import select
from sqlalchemy.orm import joinedload
from sqlalchemy_utils import database_exists, create_database

from contextlib import suppress
import datetime as dt

from common.helpers import Timedelta_Parser, parse_wr_intermediate_distance_key, get_

# from ..scraping_wr import utils_wr
from scraping_wr import api

from . import model

# logging stuff
import logging
logger = logging.getLogger(__name__)


def create_tables(engine):
    # create all tables (init) if they don't exist
    model.Base.metadata.create_all(engine, checkfirst=True)


def drop_all_tables(engine):
    model.Base.metadata.drop_all(engine, checkfirst=True)


def query_by_uuid_(session, Entity_Class, uuid):
    """Helper function.
    If an entity with given uuid exists:
        returns ORM object linked to db
    If not existing:
        returns None
    """
    # 1.4 / 2.0 https://docs.sqlalchemy.org/en/14/orm/queryguide.html
    # 2.0 https://docs.sqlalchemy.org/en/20/orm/queryguide/select.html#selecting-orm-entities
    statement = select(Entity_Class).where(Entity_Class.additional_id_ == uuid.lower())
    result_entity = session.scalars(statement).first()
    return result_entity


def wr_insert(session, Entity_Class, map_func, data, add_session=True, **kwargs):
    """Proxy function to fetch or create an entity.
    Usage: wr_insert(session, model.Country, wr_map_country, data_dict)"""
    if data == None:
        return None

    uuid = data.get('id','').lower()
    entity = query_by_uuid_(session, Entity_Class, uuid)
    create_entity = entity == None

    if create_entity:
        entity = Entity_Class()
        entity.additional_id_ = uuid

    entity = map_func(session, entity, data, **kwargs)

    if create_entity and add_session:
        session.add(entity)

    return entity


def wr_map_country(session, entity, data):
    entity.country_code = get_(data, 'CountryCode')
    entity.name = get_(data, 'DisplayName')

    entity.is_former_country__ = repr(get_(data, 'IsFormerCountry'))
    entity.is_noc__ = repr(get_(data, 'IsNOC'))
    return entity


def wr_map_boat_class(session, entity, data):
    entity.abbreviation = get_(data, 'DisplayName')
    # TODO: entity.name // full name not in API data
    return entity


def wr_map_gender(session, entity, data):
    entity.name = get_(data, 'DisplayName')
    return entity


def wr_map_athlete(session, entity, data):
    entity.name = get_(data, 'DisplayName')
    entity.first_name__ = get_(data, 'FirstName')
    entity.last_name__ = get_(data, 'LastName')
    with suppress(TypeError, ValueError):
        entity.birthdate = dt.datetime.fromisoformat(get_(data, 'BirthDate', '')).date()

    entity.height_cm__ = get_(data, 'HeightCm')
    entity.weight_kg__ = get_(data, 'WeightKg')
    return entity


def wr_insert_invalid_mark_result_code(session, data):
    """data example: {"code": "Did not start", "displayName": "DNS", "id": "4b554cb1-8468-4fa7-b75b-434ff1732d81"}"""
    Entity_Class = model.Invalid_Mark_Result_Code
    
    if data == None:
        return None

    # TODO: Force uppercase: Use validator or getter/setter
    #    - https://gist.github.com/luhn/4170996
    #    - https://stackoverflow.com/a/34322323
    #    - https://docs.sqlalchemy.org/en/14/orm/mapped_attributes.html

    abbreviation = get_(data, 'displayName', '').upper()
    if not abbreviation:
        return None

    entity = session.get(Entity_Class, {'id': abbreviation})
    create_entity = entity == None

    if create_entity:
        entity = Entity_Class()
        entity.id = abbreviation
        entity.name = get_(data, 'code')
        session.add(entity)
    
    return entity


def wr_map_race_boat(session, entity, data):
    entity.country = wr_insert(session, model.Country, wr_map_country, get_(data, 'country'))
    
    # Current Strategy: Delete all associations and create new ones according to given data.
    entity.athletes.clear()
    for raceBoatAthlete in get_(data, 'raceBoatAthletes', []):
        athlete_data = get_(raceBoatAthlete, 'person', {})
        if athlete_data:
            association = model.Association_Race_Boat_Athlete(boat_position=get_(raceBoatAthlete,'boatPosition'))
            association.athlete = wr_insert(session, model.Athlete, wr_map_athlete, athlete_data)
            session.add(association)
            
            entity.athletes.append(association)

    entity.name = get_(data, 'DisplayName') # e.g. "GER2" for the second German boat
    
    with suppress(TypeError, ValueError):
        entity.result_time_ms = Timedelta_Parser.to_millis( get_(data, 'ResultTime') )
    
    entity.invalid_mark_result_code = wr_insert_invalid_mark_result_code(session, get_(data, 'invalidMarkResultCode'))

    entity.lane = get_(data, 'Lane')
    entity.rank = get_(data, 'Rank')
    
    entity.remark__ = repr( get_(data, 'Remark') )
    entity.world_cup_points__ = get_(data, 'WorldCupPoints')
    entity.club_name__ = get_( get_(data, 'boat', {}), 'clubName' )

    # Intermediate times
    # (Beware: Contains duplicates for same distance raceID:931fd903-1d44-4ace-8665-bf1230dc0227 -> boat:2d5a3f94-37ba-480d-9d72-eada6a4c30f9 (DEN))
    entity.intermediates.clear()
    seen_set = set()
    for interm_data in get_(data, 'raceBoatIntermediates', []):
        intermediate = model.Intermediate_Time()

        # filter out duplicates // Future TODO/NOTE: Check if current strategy is appropriate
        distance_key = get_(get_(interm_data, 'distance'), 'DisplayName', '')
        if distance_key in seen_set:
            pass
            continue

        with suppress(TypeError, ValueError):
            intermediate.distance_meter = parse_wr_intermediate_distance_key(distance_key)
            intermediate.data_source_ = model.Enum_Data_Source.world_rowing_api.value
            intermediate.rank = get_(interm_data, 'Rank')
            intermediate.result_time_ms = Timedelta_Parser.to_millis( get_(interm_data, 'ResultTime') )

            intermediate.difference__ = repr( get_(interm_data, 'Difference') )
            intermediate.start_position__ = repr( get_(interm_data, 'StartPosition') )

            session.add(intermediate)
            entity.intermediates.append(intermediate)

            seen_set.add(distance_key)
    return entity


def wr_map_race(session, entity: model.Race, data):
    entity.name = get_(data, 'DisplayName')
    with suppress(TypeError, ValueError):
        entity.date = dt.datetime.fromisoformat(get_(data, 'Date', ''))

    # phase details
    phase_type = get_( get_(data, 'racePhase', {}), 'DisplayName' )
    rsc_code = get_(data, 'RscCode')

    phase_details = api.extract_race_phase_details(race_phase=phase_type, rsc_code=rsc_code, display_name=entity.name)

    entity.phase_type = phase_type.lower()
    entity.phase_subtype = get_(phase_details, 'subtype')
    entity.phase_number  = get_(phase_details, 'number')

    entity.progression = get_(data, 'Progression')
    entity.rsc_code = rsc_code

    entity.pdf_url_results = get_(api.select_pdf_(get_(data, 'pdfUrls', []), 'results'), 'url')
    entity.pdf_url_race_data = get_(api.select_pdf_(get_(data, 'pdfUrls', []), 'race data'), 'url')

    entity.race_status__ = str( get_( get_(data, 'raceStatus', {} ), 'DisplayName' ) ).strip().lower()
    entity.race_nr__ = str( get_(data, 'RaceNr') )
    entity.rescheduled__ = repr( get_(data, 'Rescheduled') )
    entity.rescheduled_from__ = repr( get_(data, 'RescheduledFrom') )

    # Race Boats
    race_boats = map(
        lambda d : wr_insert(session, model.Race_Boat, wr_map_race_boat, d),
        get_(data, 'raceBoats', [])
    )
    entity.race_boats.extend(race_boats)
    return entity


def wr_map_event(session, entity, data):
    entity.name = get_(data, 'DisplayName')
    entity.boat_class = wr_insert(session, model.Boat_Class, wr_map_boat_class, get_(data, 'boatClass'))
    entity.gender = wr_insert(session, model.Gender, wr_map_gender, get_(data, 'gender'))
    entity.rsc_code__ = get_(data, 'RscCode')

    # Races
    races = map(
        lambda d : wr_insert(session, model.Race, wr_map_race, d),
        get_(data, 'races', [])
    )
    entity.races.extend(races)
    return entity


def wr_map_competition_category(session, entity, data):
    entity.name = get_(data, 'DisplayName')
    return entity


def wr_map_venue(session, entity, data):
    entity.country = wr_insert(session, model.Country, wr_map_country, get_(data, 'country'))
    entity.city = get_(data, 'RegionCity')
    entity.site = get_(data, 'Site')
    entity.is_world_rowing_venue = get_(data, 'IsWorldRowingVenue')
    return entity


def wr_map_competition_prescrape(session, entity, data):
    STATE_RESULT_STATE = model.Enum_Maintenance_Level.world_rowing_api_prescraped.value

    state = entity.scraper_maintenance_level
    update_entity = state == None or state < STATE_RESULT_STATE
    if not update_entity:
        return entity

    entity.scraper_maintenance_level = STATE_RESULT_STATE
    entity.scraper_data_provider = model.Enum_Data_Provider.world_rowing.value

    entity.name = get_(data, 'DisplayName')
    with suppress(TypeError, ValueError):
        entity.year = int(get_(data, 'Year'))
    return entity


def __wr_map_competition(session, entity: model.Competition, data):
    # Competition_Category
    competition_category = wr_insert(
        session,
        model.Competition_Category,
        wr_map_competition_category,
        get_(get_(data, 'competitionType'), 'competitionCategory')
    )

    # Venue
    venue = wr_insert(session, model.Venue, wr_map_venue, get_(data, 'venue'))

    entity.competition_category = competition_category
    entity.venue = venue
    entity.name = get_(data, 'DisplayName')
    with suppress(TypeError, ValueError):
        entity.year = int(get_(data, 'Year'))
    with suppress(TypeError, ValueError):
        entity.start_date = dt.datetime.fromisoformat(get_(data, 'StartDate', ''))
    with suppress(TypeError, ValueError):
        entity.end_date = dt.datetime.fromisoformat(get_(data, 'EndDate', ''))

    entity.competition_code__ = get_(data, 'CompetitionCode')
    entity.is_fisa__ = get_(data, 'IsFisa')

    # Events
    # Insert 1:m https://stackoverflow.com/q/16433338
    events = map(
        lambda d : wr_insert(session, model.Event, wr_map_event, d),
        get_(data, 'events', [])
    )
    entity.events.extend(events)
    return entity


def wr_map_competition_scrape(session, entity: model.Competition, data: dict):
    # Check maintenance state
    STATE_RESULT_STATE = model.Enum_Maintenance_Level.world_rowing_api_scraped.value
    STATE_UPPER_LIMIT  = STATE_RESULT_STATE

    state = entity.scraper_maintenance_level
    update_entity = state == None or state <= STATE_UPPER_LIMIT
    if not update_entity:
        return entity

    entity.scraper_maintenance_level = STATE_RESULT_STATE
    entity.scraper_data_provider = model.Enum_Data_Provider.world_rowing.value
    entity.scraper_last_scrape = dt.datetime.today()

    entity = __wr_map_competition(session, entity, data)
    return entity


if __name__ == '__main__':
    # Command line interface (CLI)
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("-c", "--create", help="Create tables if not yet existing", action="store_true")
    parser.add_argument("-d", "--drop", help="Drop all tables described by the schema defined in model.py", action="store_true")
    parser.add_argument("-i", "--insert", help="Import JSON data for a rowing competition")
    args = parser.parse_args()
    print(args)

    # ----------------------------------

    import json
    from .model import engine, Scoped_Session

    if not database_exists(engine.url): 
        print("----- Create Database 'rowing' -----")
        create_database(engine.url)

    logging.basicConfig(level=logging.DEBUG)

    if args.drop:
        logger.info("----- Drop All Tables -----")
        drop_all_tables(engine)

    if args.create:
        logger.info("----- Create Tables -----")
        create_tables(engine)

    if args.insert:
        logger.info(f"Load JSON file: {args.insert}")
        with Scoped_Session() as session:
            with open(args.insert, mode="r", encoding="utf-8") as fp:
                competition_data = json.load(fp)
            competition = wr_insert(session, model.Competition, wr_map_competition_scrape, competition_data)
            session.commit()
    