"""Typed extensions used by supplemental committee Popolo models."""

from mysoc_validator.models.popolo import (
    MembershipExtra,
    OrganizationExtra,
)


class CommitteeOrganizationExtra(OrganizationExtra):
    """Non-standard category tags attached to a committee organization."""

    tags: list[str]


class MinisterialMembershipExtra(MembershipExtra):
    """NI source metadata retained on a ministerial membership."""

    tags: list[str]
    department_id: int
    department: str
