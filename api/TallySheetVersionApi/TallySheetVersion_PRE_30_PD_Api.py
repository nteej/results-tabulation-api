from app import db
from orm.entities import Candidate, Area, Submission, SubmissionVersion
from orm.entities.Election import ElectionCandidate
from orm.entities.SubmissionVersion.ReportVersion.util import get_PRE41_candidate_and_area_wise_aggregated_result
from orm.entities.TallySheetVersionRow import TallySheetVersionRow_PRE_41
from orm.enums import AreaTypeEnum
from util import RequestBody
from schemas import TallySheetVersionPRE41Schema, TallySheetVersionSchema, TallySheetVersion_PRE_30_PD_Schema
from orm.entities.Submission import TallySheet
from orm.entities.SubmissionVersion.TallySheetVersion import TallySheetVersionPRE41, TallySheetVersion_PRE_30_PD
from exception import NotFoundException
from sqlalchemy import func


def create(tallySheetId):
    tallySheetVersion = TallySheetVersion_PRE_30_PD.create(
        tallySheetId=tallySheetId
    )

    countingCentres = tallySheetVersion.submission.area.get_associated_areas(AreaTypeEnum.CountingCentre)

    query = db.session.query(
        TallySheetVersionRow_PRE_41.Model.candidateId,
        Submission.Model.areaId,
        func.sum(TallySheetVersionRow_PRE_41.Model.count).label("count"),
    ).join(
        SubmissionVersion.Model,
        SubmissionVersion.Model.submissionVersionId == TallySheetVersionRow_PRE_41.Model.tallySheetVersionId
    ).join(
        Submission.Model,
        Submission.Model.submissionId == SubmissionVersion.Model.submissionId
    ).filter(
        TallySheetVersionRow_PRE_41.Model.tallySheetVersionId == Submission.Model.latestVersionId,
        Submission.Model.areaId.in_([area.areaId for area in countingCentres])
    ).group_by(
        TallySheetVersionRow_PRE_41.Model.candidateId,
        Submission.Model.areaId
    ).order_by(
        TallySheetVersionRow_PRE_41.Model.candidateId,
        Submission.Model.areaId
    ).all()

    print("################ query ", query)

    for row in query:
        print("################ row ", row)
        tallySheetVersion.add_row(
            candidateId=row.candidateId,
            countingCentreId=row.areaId,
            count=row.count
        )

    db.session.commit()

    return TallySheetVersion_PRE_30_PD_Schema().dump(tallySheetVersion).data
