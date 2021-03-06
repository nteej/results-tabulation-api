from typing import Set
from sqlalchemy.ext.associationproxy import association_proxy
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.orm import relationship
from app import db
from auth import get_user_access_area_ids, get_user_name, has_role_based_access
from constants.AUTH_CONSTANTS import ACCESS_TYPE_LOCK, ACCESS_TYPE_UNLOCK
from constants.TALLY_SHEET_COLUMN_SOURCE import TALLY_SHEET_COLUMN_SOURCE_META
from exception import NotFoundException, ForbiddenException
from exception.messages import MESSAGE_CODE_TALLY_SHEET_SAME_USER_CANNOT_SAVE_AND_SUBMIT, \
    MESSAGE_CODE_TALLY_SHEET_NOT_AUTHORIZED_TO_UNLOCK, MESSAGE_CODE_TALLY_SHEET_NOT_AUTHORIZED_TO_LOCK, \
    MESSAGE_CODE_TALLY_SHEET_CANNOT_SUBMIT_AFTER_LOCK, MESSAGE_CODE_TALLY_SHEET_NOT_FOUND, \
    MESSAGE_CODE_TALLY_SHEET_CANNOT_LOCK_BEFORE_SUBMIT, \
    MESSAGE_CODE_TALLY_SHEET_CANNOT_BE_NOTIFIED_BEFORE_LOCK, \
    MESSAGE_CODE_TALLY_SHEET_CANNOT_BE_RELEASED_BEFORE_NOTIFYING, MESSAGE_CODE_TALLY_SHEET_ALREADY_RELEASED, \
    MESSAGE_CODE_TALLY_SHEET_ALREADY_NOTIFIED
from orm.entities import Submission, Election, Template, TallySheetVersionRow, Candidate, Party, Area, Meta
from orm.entities.Dashboard import StatusReport
from orm.entities.Election import ElectionCandidate, ElectionParty
from orm.entities.SubmissionVersion import TallySheetVersion
from orm.entities.Template import TemplateRow_DerivativeTemplateRow_Model, TemplateRowModel
from orm.enums import SubmissionTypeEnum, AreaTypeEnum
from sqlalchemy import and_, func, or_

from util import get_dict_key_value_or_none


class TallySheetModel(db.Model):
    __tablename__ = 'tallySheet'

    tallySheetId = db.Column(db.Integer, db.ForeignKey(Submission.Model.__table__.c.submissionId), primary_key=True)
    templateId = db.Column(db.Integer, db.ForeignKey(Template.Model.__table__.c.templateId), nullable=False)
    statusReportId = db.Column(db.Integer, db.ForeignKey(StatusReport.Model.__table__.c.statusReportId), nullable=True)
    metaId = db.Column(db.Integer, db.ForeignKey(Meta.Model.__table__.c.metaId), nullable=True)

    submission = relationship("SubmissionModel", foreign_keys=[tallySheetId])
    statusReport = relationship(StatusReport.Model, foreign_keys=[statusReportId])
    template = relationship(Template.Model, foreign_keys=[templateId])
    meta = relationship(Meta.Model, foreign_keys=[metaId])

    electionId = association_proxy("submission", "electionId")
    election = association_proxy("submission", "election")
    areaId = association_proxy("submission", "areaId")
    area = association_proxy("submission", "area")
    latestVersionId = association_proxy("submission", "latestVersionId")
    latestStamp = association_proxy("submission", "latestStamp")
    lockedVersionId = association_proxy("submission", "lockedVersionId")
    lockedVersion = association_proxy("submission", "lockedVersion")
    notifiedVersionId = association_proxy("submission", "notifiedVersionId")
    notifiedVersion = association_proxy("submission", "notifiedVersion")
    releasedVersionId = association_proxy("submission", "releasedVersionId")
    releasedVersion = association_proxy("submission", "releasedVersion")
    lockedStamp = association_proxy("submission", "lockedStamp")
    submittedVersionId = association_proxy("submission", "submittedVersionId")
    submittedStamp = association_proxy("submission", "submittedStamp")
    locked = association_proxy("submission", "locked")
    submitted = association_proxy("submission", "submitted")
    notified = association_proxy("submission", "notified")
    released = association_proxy("submission", "released")
    submissionProofId = association_proxy("submission", "submissionProofId")
    submissionProof = association_proxy("submission", "submissionProof")
    versions = association_proxy("submission", "versions")
    metaDataList = association_proxy("meta", "metaDataList")

    children = relationship("TallySheetModel", secondary="tallySheet_tallySheet", lazy="subquery",
                            primaryjoin="TallySheetModel.tallySheetId==TallySheetTallySheetModel.parentTallySheetId",
                            secondaryjoin="TallySheetModel.tallySheetId==TallySheetTallySheetModel.childTallySheetId"
                            )
    parents = relationship("TallySheetModel", secondary="tallySheet_tallySheet", lazy="subquery",
                           primaryjoin="TallySheetModel.tallySheetId==TallySheetTallySheetModel.childTallySheetId",
                           secondaryjoin="TallySheetModel.tallySheetId==TallySheetTallySheetModel.parentTallySheetId"
                           )

    @hybrid_property
    def areaMapList(self):
        extended_election = self.submission.election.get_extended_election()
        area_map = extended_election.get_area_map_for_tally_sheet(tally_sheet=self)

        return area_map

    def add_parent(self, parentTallySheet):
        parentTallySheet.add_child(self.tallySheetId)

        return self

    def add_child(self, childTallySheet):
        existing_mapping = TallySheetTallySheetModel.query.filter(
            TallySheetTallySheetModel.parentTallySheetId == self.tallySheetId,
            TallySheetTallySheetModel.childTallySheetId == childTallySheet.tallySheetId
        ).one_or_none()

        if existing_mapping is None:
            tallySheetAssociation = TallySheetTallySheetModel(
                parentTallySheetId=self.tallySheetId,
                childTallySheetId=childTallySheet.tallySheetId
            )
            db.session.add(tallySheetAssociation)
            db.session.flush()

        return self

    @hybrid_property
    def tallySheetCode(self):
        return self.template.templateName

    def get_status_report_type(self):
        electoral_district_name = ""
        polling_division_name = ""
        status_report_type = ""

        election = self.submission.election
        submission_area = self.submission.area
        # if self.tallySheetCode == PRE_30_PD:
        #     if election.voteType is Postal:
        #         electoral_district_name = submission_area.areaName
        #         status_report_type = "PV"
        #     else:
        #         electoral_district_name = _get_electoral_district_name(submission_area)
        #         polling_division_name = submission_area.areaName
        #         status_report_type = "PD"
        # elif self.tallySheetCode == PRE_34_PD:
        #     if election.voteType is Postal:
        #         electoral_district_name = submission_area.areaName
        #         status_report_type = "PV [Revised]"
        #     else:
        #         electoral_district_name = _get_electoral_district_name(submission_area)
        #         polling_division_name = submission_area.areaName
        #         status_report_type = "PD [Revised]"
        # elif self.tallySheetCode == PRE_30_ED:
        #     electoral_district_name = submission_area.areaName
        #     status_report_type = "ED"
        # elif self.tallySheetCode == PRE_34_ED:
        #     electoral_district_name = submission_area.areaName
        #     status_report_type = "ED [Revised]"
        # else:
        # TODO
        status_report_type = self.tallySheetCode

        return electoral_district_name, polling_division_name, status_report_type

    def get_report_status(self):
        if self.template.has_data_entry():
            if self.locked:
                if self.released:
                    return "RELEASED"
                elif self.notified:
                    return "NOTIFIED"
                elif self.submissionProof.size() > 0:
                    return "CERTIFIED"
                else:
                    return "VERIFIED"
            elif self.submitted:
                return "SUBMITTED"
            elif self.latestVersionId is not None:
                return "ENTERED"
            else:
                return "NOT ENTERED"
        else:
            if self.locked:
                if self.released:
                    return "RELEASED"
                elif self.notified:
                    return "NOTIFIED"
                elif self.submissionProof.size() > 0:
                    return "CERTIFIED"
                else:
                    return "VERIFIED"
            else:
                return "PENDING"

    def update_status_report(self):
        election = self.submission.election.get_root_election()

        if self.statusReportId is None:
            electoral_district_name, polling_division_name, status_report_type = self.get_status_report_type()
            status_report = StatusReport.create(
                electionId=election.electionId,
                reportType=status_report_type,
                electoralDistrictName=electoral_district_name,
                pollingDivisionName=polling_division_name,
                status=self.get_report_status()
            )

            self.statusReportId = status_report.statusReportId
        else:
            self.statusReport.update_status(
                status=self.get_report_status()
            )

    def set_latest_version(self, tallySheetVersion: TallySheetVersion):
        if tallySheetVersion is None:
            self.submission.set_latest_version(submissionVersion=None)
        else:
            self.submission.set_latest_version(submissionVersion=tallySheetVersion.submissionVersion)

        self.update_status_report()

    def set_locked_version(self, tallySheetVersion: TallySheetVersion):
        if tallySheetVersion is None:
            if not has_role_based_access(self, ACCESS_TYPE_UNLOCK):
                raise ForbiddenException(
                    message="User not authorized to unlock the tally sheet.",
                    code=MESSAGE_CODE_TALLY_SHEET_NOT_AUTHORIZED_TO_UNLOCK
                )

            self.submission.set_locked_version(submissionVersion=None)
        else:
            if self.template.is_submit_allowed():
                if self.submittedVersionId is None:
                    raise ForbiddenException(
                        message="Data entry tally sheet cannot be locked before submitting",
                        code=MESSAGE_CODE_TALLY_SHEET_CANNOT_LOCK_BEFORE_SUBMIT
                    )
                elif self.submittedStamp.createdBy == get_user_name():
                    raise ForbiddenException(
                        message="Data entry tally sheet submitted user is not allowed to lock/unlock.",
                        code=MESSAGE_CODE_TALLY_SHEET_SAME_USER_CANNOT_SAVE_AND_SUBMIT
                    )

            if not has_role_based_access(self, ACCESS_TYPE_LOCK):
                raise ForbiddenException(
                    message="User is not authorized to lock the tally sheet.",
                    code=MESSAGE_CODE_TALLY_SHEET_NOT_AUTHORIZED_TO_LOCK
                )

            self.submission.set_locked_version(submissionVersion=tallySheetVersion.submissionVersion)

        self.update_status_report()

    def set_submitted_version(self, tallySheetVersion: TallySheetVersion):
        if self.locked:
            raise ForbiddenException(
                message="Tally sheet is already locked.",
                code=MESSAGE_CODE_TALLY_SHEET_CANNOT_SUBMIT_AFTER_LOCK
            )

        if tallySheetVersion is None:
            self.submission.set_submitted_version(submissionVersion=None)
        else:
            self.submission.set_submitted_version(submissionVersion=tallySheetVersion.submissionVersion)

        self.update_status_report()

    def set_notified_version(self):
        if self.lockedVersionId is None:
            raise ForbiddenException(
                message="Tally sheet cannot be notified before it's verified.",
                code=MESSAGE_CODE_TALLY_SHEET_CANNOT_BE_NOTIFIED_BEFORE_LOCK
            )
        elif self.notified is True:
            raise ForbiddenException(
                message="Tally sheet is already notified.",
                code=MESSAGE_CODE_TALLY_SHEET_ALREADY_NOTIFIED
            )
        else:
            self.submission.set_notified_version(submissionVersion=self.lockedVersion)

        self.update_status_report()

    def set_released_version(self):
        if self.notified is False:
            raise ForbiddenException(
                message="Tally sheet cannot be released before notifying",
                code=MESSAGE_CODE_TALLY_SHEET_CANNOT_BE_RELEASED_BEFORE_NOTIFYING
            )
        elif self.released is True:
            raise ForbiddenException(
                message="Tally sheet is already released.",
                code=MESSAGE_CODE_TALLY_SHEET_ALREADY_RELEASED
            )
        else:
            self.submission.set_released_version(submissionVersion=self.notifiedVersion)

        self.update_status_report()

    @hybrid_property
    def latestVersion(self):
        return TallySheetVersion.Model.query.filter(
            TallySheetVersion.Model.tallySheetVersionId == self.latestVersionId
        ).one_or_none()

    def __init__(self, template, electionId, areaId, metaId):
        submission = Submission.create(
            submissionType=SubmissionTypeEnum.TallySheet,
            electionId=electionId,
            areaId=areaId
        )

        super(TallySheetModel, self).__init__(
            tallySheetId=submission.submissionId,
            templateId=template.templateId,
            metaId=metaId
        )

        db.session.add(self)
        db.session.flush()

    def create_empty_version(self):
        tallySheetVersion = TallySheetVersion.Model(
            tallySheetId=self.tallySheetId
        )

        return tallySheetVersion

    def create_version(self, content=None):
        column_name_map = {
            "electionId": Election.Model.electionId,
            "areaId": Area.Model.areaId,
            "candidateId": Candidate.Model.candidateId,
            "partyId": Party.Model.partyId,
            "numValue": TallySheetVersionRow.Model.numValue,
            "strValue": TallySheetVersionRow.Model.strValue,
            "ballotBoxId": TallySheetVersionRow.Model.ballotBoxId
        }
        column_function_map = {
            "sum": func.sum,
            "count": func.count,
            "group_concat": func.group_concat
        }

        meta_data_map = {}
        for metaData in self.meta.metaDataList:
            meta_data_map[metaData.metaDataKey] = metaData.metaDataValue

        tally_sheet_version = self.create_empty_version()
        is_tally_sheet_version_complete = True

        for templateRow in self.template.rows:
            query_args = [
                TallySheetModel.tallySheetId
            ]
            group_by_args = []

            for templateRowColumn in templateRow.columns:
                column_name = templateRowColumn.templateRowColumnName
                column = column_name_map[column_name]

                if templateRowColumn.func is not None:
                    column_func = column_function_map[templateRowColumn.func]
                    column = column_func(column).label(column_name)

                query_args.append(column)

                if templateRowColumn.grouped:
                    group_by_args.append(column)

            content_rows = []

            if templateRow.isDerived is True:

                tally_sheet_version_row_join_condition = [
                    TallySheetVersionRow.Model.templateRowId == TemplateRowModel.templateRowId,
                    TallySheetVersionRow.Model.tallySheetVersionId == Submission.Model.lockedVersionId
                ]

                aggregated_results = db.session.query(
                    *query_args
                ).join(
                    Submission.Model,
                    Submission.Model.submissionId == TallySheetModel.tallySheetId
                )

                if Area.Model.areaId in query_args:
                    aggregated_results = aggregated_results.join(
                        Area.Model,
                        Area.Model.areaId == Submission.Model.areaId
                    )

                if Election.Model.electionId in query_args or Candidate.Model.candidateId in query_args or Party.Model.partyId in query_args:
                    aggregated_results = aggregated_results.join(
                        Election.Model,
                        Election.Model.electionId == Submission.Model.electionId
                    )

                if Candidate.Model.candidateId in query_args:
                    aggregated_results = aggregated_results.join(
                        ElectionCandidate.Model,
                        ElectionCandidate.Model.electionId == Election.Model.electionId
                    ).join(
                        Candidate.Model,
                        Candidate.Model.candidateId == ElectionCandidate.Model.candidateId
                    ).join(
                        Party.Model,
                        Party.Model.partyId == ElectionCandidate.Model.partyId
                    )
                    tally_sheet_version_row_join_condition += [
                        TallySheetVersionRow.Model.candidateId == Candidate.Model.candidateId,
                        TallySheetVersionRow.Model.partyId == Party.Model.partyId
                    ]
                elif Party.Model.partyId in query_args:
                    aggregated_results = aggregated_results.join(
                        ElectionParty.Model,
                        ElectionParty.Model.electionId == Election.Model.electionId
                    ).join(
                        Party.Model,
                        Party.Model.partyId == ElectionParty.Model.partyId
                    )
                    tally_sheet_version_row_join_condition.append(
                        TallySheetVersionRow.Model.partyId == Party.Model.partyId)

                aggregated_results = aggregated_results.join(
                    TallySheetTallySheetModel,
                    TallySheetTallySheetModel.childTallySheetId == TallySheetModel.tallySheetId
                ).join(
                    TemplateRowModel,
                    TemplateRowModel.templateId == TallySheetModel.templateId
                ).join(
                    TemplateRow_DerivativeTemplateRow_Model,
                    TemplateRow_DerivativeTemplateRow_Model.derivativeTemplateRowId == TemplateRowModel.templateRowId
                ).join(
                    TallySheetVersionRow.Model,
                    and_(
                        *tally_sheet_version_row_join_condition
                    ),
                    isouter=True
                ).filter(
                    TallySheetTallySheetModel.parentTallySheetId == self.tallySheetId,
                    TemplateRow_DerivativeTemplateRow_Model.templateRowId == templateRow.templateRowId
                ).group_by(
                    *group_by_args
                ).all()

                for aggregated_result in aggregated_results:
                    content_row = {}

                    for templateRowColumn in templateRow.columns:
                        column_name = templateRowColumn.templateRowColumnName
                        content_row[column_name] = getattr(aggregated_result, column_name)

                    content_rows.append(content_row)
            else:
                for content_row in content:
                    if content_row["templateRowId"] == templateRow.templateRowId:
                        for template_row_column in templateRow.columns:
                            if template_row_column.source == TALLY_SHEET_COLUMN_SOURCE_META:
                                template_row_column_name = template_row_column.templateRowColumnName
                                content_row[template_row_column_name] = meta_data_map[template_row_column_name]

                        content_rows.append(content_row)

                if templateRow.hasMany is False:
                    content_rows = [content_rows[0]]

            for content_row in content_rows:

                # Update the completed flag to False if there are null values in any row.
                if content_row["numValue"] is None:
                    is_tally_sheet_version_complete = False

                TallySheetVersionRow.create(
                    templateRow=templateRow,
                    tallySheetVersion=tally_sheet_version,
                    electionId=get_dict_key_value_or_none(content_row, "electionId"),
                    numValue=get_dict_key_value_or_none(content_row, "numValue"),
                    strValue=get_dict_key_value_or_none(content_row, "strValue"),
                    areaId=get_dict_key_value_or_none(content_row, "areaId"),
                    candidateId=get_dict_key_value_or_none(content_row, "candidateId"),
                    partyId=get_dict_key_value_or_none(content_row, "partyId"),
                    ballotBoxId=get_dict_key_value_or_none(content_row, "ballotBoxId")
                )

        if is_tally_sheet_version_complete:
            tally_sheet_version.set_complete()

        return tally_sheet_version

    def get_extended_tally_sheet_version(self, tallySheetVersionId):
        tally_sheet_version = TallySheetVersion.get_by_id(tallySheetId=self.tallySheetId,
                                                          tallySheetVersionId=tallySheetVersionId)
        extended_election = self.submission.election.get_extended_election()
        extended_tally_sheet_version_class = extended_election.get_extended_tally_sheet_version_class(
            self.template.templateName)
        extended_tally_sheet_version = extended_tally_sheet_version_class(tally_sheet_version)

        return extended_tally_sheet_version

    def html(self, tallySheetVersionId):
        extended_tally_sheet_version = self.get_extended_tally_sheet_version(tallySheetVersionId=tallySheetVersionId)
        return extended_tally_sheet_version.html()

    def html_letter(self, tallySheetVersionId):
        extended_tally_sheet_version = self.get_extended_tally_sheet_version(tallySheetVersionId=tallySheetVersionId)
        return extended_tally_sheet_version.html_letter()


Model = TallySheetModel


class TallySheetTallySheetModel(db.Model):
    __tablename__ = 'tallySheet_tallySheet'
    parentTallySheetId = db.Column(db.Integer, db.ForeignKey("tallySheet.tallySheetId"), primary_key=True)
    childTallySheetId = db.Column(db.Integer, db.ForeignKey("tallySheet.tallySheetId"), primary_key=True)


def _get_electoral_district_name(polling_division):
    electoral_district_name = ""
    electoral_district = polling_division.get_associated_areas(
        areaType=AreaTypeEnum.ElectoralDistrict,
        electionId=polling_division.electionId
    )
    if len(electoral_district) > 0:
        electoral_district_name = electoral_district[0].areaName

    return electoral_district_name


def get_by_id(tallySheetId, tallySheetCode=None):
    # Filter by authorized areas
    user_access_area_ids: Set[int] = get_user_access_area_ids()

    query_args = [TallySheetModel]
    query_filters = [
        TallySheetModel.tallySheetId == tallySheetId,
        Submission.Model.areaId.in_(user_access_area_ids),
        Template.Model.templateId == Model.templateId,
        Submission.Model.submissionId == Model.tallySheetId
    ]
    query_group_by = [Model.tallySheetId]

    if tallySheetCode is not None:
        query_filters.append(Template.Model.templateName == tallySheetCode)

    return db.session.query(*query_args).filter(*query_filters).group_by(*query_group_by).one_or_none()


def get_all(electionId=None, areaId=None, tallySheetCode=None, voteType=None):
    # Filter by authorized areas
    user_access_area_ids: Set[int] = get_user_access_area_ids()

    query_args = [Model]
    query_filters = [
        Submission.Model.areaId.in_(user_access_area_ids),
        Template.Model.templateId == Model.templateId,
        Submission.Model.submissionId == Model.tallySheetId,
        Election.Model.electionId == Submission.Model.electionId
    ]
    query_group_by = [Model.tallySheetId]

    if areaId is not None:
        query_filters.append(Submission.Model.areaId == areaId)

    if electionId is not None:
        election = Election.get_by_id(electionId=electionId)
        query_filters.append(Election.Model.electionId.in_(election.get_this_and_below_election_ids()))

    if tallySheetCode is not None:
        query_filters.append(Template.Model.templateName == tallySheetCode)

    if voteType is not None:
        query_filters.append(Election.Model.voteType == voteType)

    return db.session.query(*query_args).filter(*query_filters).group_by(*query_group_by)


def create(template, electionId, areaId, metaId):
    result = Model(
        template=template,
        electionId=electionId,
        areaId=areaId,
        metaId=metaId
    )

    return result


def create_empty_version(tallySheetId):
    tallySheet = get_by_id(tallySheetId=tallySheetId)
    if tallySheet is None:
        raise NotFoundException(
            message="Tally sheet not found. (tallySheetId=%d)" % tallySheetId,
            code=MESSAGE_CODE_TALLY_SHEET_NOT_FOUND
        )

    tallySheetVersion = tallySheet.create_empty_version()

    return tallySheet, tallySheetVersion


def create_version(tallySheetId, content=None):
    print("\n\n\n\n\n\n####### create_version #####")
    tallySheet = get_by_id(tallySheetId=tallySheetId)
    if tallySheet is None:
        raise NotFoundException(
            message="Tally sheet not found. (tallySheetId=%d)" % (tallySheetId),
            code=MESSAGE_CODE_TALLY_SHEET_NOT_FOUND
        )

    tallySheetVersion = tallySheet.create_version(content=content)

    return tallySheet, tallySheetVersion


def create_latest_version(tallySheetId, content=None):
    tallySheet, tallySheetVersion = create_version(tallySheetId, content=content)
    tallySheet.set_latest_version(tallySheetVersion=tallySheetVersion)

    return tallySheet, tallySheetVersion
