import connexion
from app import db
from auth import ADMIN_ROLE, authorize
from constants.AUTH_CONSTANTS import ALL_ROLES
from exception import NotFoundException
from exception.messages import MESSAGE_CODE_ELECTION_NOT_FOUND
from orm.entities.Election.election_helper import get_root_token
from orm.entities import Election
from schemas import ElectionSchema as Schema
from util import RequestBody, get_paginated_query


@authorize(required_roles=ALL_ROLES)
def get_all():
    result = Election.get_all()

    result = get_paginated_query(result).all()

    return Schema(many=True).dump(result).data


@authorize(required_roles=ALL_ROLES)
def get_by_id(electionId):
    result = Election.get_by_id(electionId=electionId)
    if result is None:
        raise NotFoundException(
            message="Election not found (electionId=%d)" % electionId,
            code=MESSAGE_CODE_ELECTION_NOT_FOUND
        )

    return Schema().dump(result).data


@authorize(required_roles=[ADMIN_ROLE])
def create(body):
    request_body = RequestBody(body)
    election_name = request_body.get("electionName")
    election_template_name = request_body.get("electionTemplateName")

    files = connexion.request.files
    polling_stations_dataset = files.get("pollingStationsDataset")
    postal_counting_centres_dataset = files.get("postalCountingCentresDataset")
    party_candidates_dataset = files.get("partyCandidatesDataset")
    invalid_vote_categories_dataset = files.get("invalidVoteCategoriesDataset")

    election = Election.create(electionTemplateName=election_template_name, electionName=election_name, isListed=True,
                               party_candidate_dataset_file=party_candidates_dataset,
                               polling_station_dataset_file=polling_stations_dataset,
                               postal_counting_centers_dataset_file=postal_counting_centres_dataset,
                               invalid_vote_categories_dataset_file=invalid_vote_categories_dataset)

    db.session.commit()

    return Schema().dump(election).data


@authorize(required_roles=[ADMIN_ROLE])
def getRootToken(electionId):
    return get_root_token(electionId=electionId)
