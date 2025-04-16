"""
This is for keeping a local copy of the EDMs from the Commons API.
This can then be queried far faster as a pair of parquet files.
"""

from __future__ import annotations

import datetime
from pathlib import Path
from typing import Optional, Union

import httpx
import pandas as pd
from mysoc_validator import Popolo
from mysoc_validator.models.consts import IdentifierScheme
from pydantic import BaseModel, Field, RootModel
from pydantic.alias_generators import to_snake
from tqdm import tqdm

from pyscraper.regmem.funcs import memberdata_path, parldata_path

COMMONS_START_DATE = datetime.date(2015, 1, 1)


edm_path = parldata_path / "scrapedjson" / "edm"
edm_json = edm_path / "commons.json"


class Member(BaseModel):
    MnisId: int
    PimsId: Optional[int] = None
    Name: str
    ListAs: str
    Constituency: Optional[str] = None
    Status: str
    Party: Optional[str] = None
    PartyId: Optional[int] = None
    PartyColour: Optional[str] = None
    PhotoUrl: str


class Sponsor(BaseModel):
    Id: int
    MemberId: int
    Member: Member
    SponsoringOrder: Optional[int] = None
    CreatedWhen: datetime.datetime
    IsWithdrawn: bool
    WithdrawnDate: Optional[datetime.datetime]


class Proposal(BaseModel):
    Id: int
    Status: int
    StatusDate: str
    MemberId: int
    Sponsors: list[Sponsor] = Field(default_factory=list)
    PrimarySponsor: Member
    Title: str
    MotionText: str
    AmendmentToMotionId: Union[None, int] = None
    UIN: int
    AmendmentSuffix: Union[None, str] = None
    DateTabled: str
    PrayingAgainstNegativeStatutoryInstrumentId: Union[None, int] = None
    StatutoryInstrumentNumber: Union[None, int] = None
    StatutoryInstrumentYear: Union[None, int] = None
    StatutoryInstrumentTitle: Union[None, str] = None
    UINWithAmendmentSuffix: str
    SponsorsCount: int

    @classmethod
    def from_api(cls, division_id: int) -> Proposal:
        url = f"https://oralquestionsandmotions-api.parliament.uk/EarlyDayMotion/{division_id}"
        response = httpx.get(url, timeout=30)
        response.raise_for_status()
        return cls.model_validate(response.json()["Response"])


class ProposalSearchList(RootModel):
    root: list[Proposal]

    @classmethod
    def expand_from_partial(cls, partial: ProposalSearchList) -> ProposalSearchList:
        expanded_items = [
            Proposal.from_api(item.Id)
            for item in tqdm(partial.root, desc="Expanding EDMs")
        ]
        return cls(root=expanded_items)

    def __iter__(self):
        return iter(self.root)

    @classmethod
    def from_date(
        cls,
        *,
        start_date: datetime.date,
        end_date: datetime.date,
        expand: bool = True,
        quiet: bool = False,
    ) -> ProposalSearchList:
        items = []
        skip = 0
        take = 100

        bar = tqdm(desc="Downloading EDM lists", unit="EDM", total=1000, disable=quiet)

        while True:
            params = {
                "parameters.tabledStartDate": start_date.isoformat(),
                "parameters.tabledEndDate": end_date.isoformat(),
                "parameters.skip": skip,
                "parameters.take": take,
            }

            url = (
                "https://oralquestionsandmotions-api.parliament.uk/EarlyDayMotions/list"
            )
            response = httpx.get(url, params=params)
            response.raise_for_status()
            data = response.json()
            items.extend(data["Response"])
            total_expected = data["PagingInfo"]["Total"]
            bar.total = total_expected
            bar.update(take)
            if len(items) >= total_expected:
                break
            skip += take

        bar.close()
        partial = ProposalSearchList.model_validate(items)
        if not expand:
            return partial
        return cls.expand_from_partial(partial)

    @classmethod
    def from_path(cls, filename: Path) -> ProposalSearchList:
        with filename.open("r") as f:
            data = f.read()
            return cls.model_validate_json(data)

    def to_path(self, filename: Path):
        with filename.open("w") as f:
            data = self.model_dump_json(indent=2)
            f.write(data)

    def to_proposal_parquet(self):
        """
        Moves  EDM 'motions' into a flat parquet file
        """

        # all fields except for the following:
        # MemberId, Sponsors, PrimarySponsor

        items = [
            x.model_dump(exclude={"MemberId", "Sponsors", "PrimarySponsor"})
            for x in self.root
        ]
        df = pd.DataFrame(items)
        df = df.rename(columns=to_snake)
        df["chamber"] = "house-of-commons"
        if edm_path.exists() is False:
            edm_path.mkdir(parents=True, exist_ok=True)
        filename = edm_path / "proposals.parquet"
        df.to_parquet(filename, index=False)

    def to_signature_parquet(self):
        """
        Moves sponsors into a flat parquet file.
        Where we can, adapts MNIS IDs to Twfy IDs.
        """

        items = []

        popolo = Popolo.from_path(memberdata_path / "people.json")

        for proposal in self.root:
            for sponsor in proposal.Sponsors:
                sponsor_data = sponsor.model_dump(exclude={"Member"})
                sponsor_data["ProposalId"] = proposal.Id
                sponsor_data["IsPrimary"] = proposal.MemberId == sponsor.MemberId

                try:
                    popolo_person = popolo.persons.from_identifier(
                        str(sponsor.MemberId), scheme=IdentifierScheme.MNIS
                    )
                    int_twfy_id = int(popolo_person.reduced_id())
                except ValueError:
                    int_twfy_id = None
                sponsor_data["TwfyID"] = int_twfy_id

                items.append(sponsor_data)

        df = pd.DataFrame(items)
        df = df.rename(columns=to_snake)
        df["chamber"] = "house-of-commons"

        if edm_path.exists() is False:
            edm_path.mkdir(parents=True, exist_ok=True)

        filename = edm_path / "signatures.parquet"
        df.to_parquet(filename, index=False)


def fetch_and_update(quiet: bool = False):
    if edm_json.exists():
        existing = ProposalSearchList.from_path(edm_json)
    else:
        initial_populate()
        existing = ProposalSearchList(root=[])

    today = datetime.date.today()
    three_months_ago = today - datetime.timedelta(days=90)

    new_items = ProposalSearchList.from_date(
        start_date=three_months_ago, end_date=today, quiet=quiet
    )
    new_ids = {item.Id for item in new_items}

    existing.root = [x for x in existing.root if x.Id not in new_ids]
    existing.root.extend(new_items.root)
    existing.root = sorted(existing.root, key=lambda x: x.Id)
    existing.to_path(edm_json)
    existing.to_proposal_parquet()
    existing.to_signature_parquet()


def initial_populate():
    """
    Fetch all items from the start date to today for an initial pass.
    """
    if not edm_json.exists():
        edm_json.parent.mkdir(parents=True, exist_ok=True)
    now = datetime.datetime.now()
    items = ProposalSearchList.from_date(
        start_date=COMMONS_START_DATE, end_date=now.date()
    )
    items.to_path(edm_json)
    items.to_proposal_parquet()
    items.to_signature_parquet()


def to_parquet():
    """
    Convert the json to parquet.
    """
    items = ProposalSearchList.from_path(edm_json)
    items.to_proposal_parquet()
    items.to_signature_parquet()
