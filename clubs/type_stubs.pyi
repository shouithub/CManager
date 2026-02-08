# Type stubs for Django models to help Pylance
from typing import Optional, Any
from django.db import models
from django.contrib.auth.models import User

# Django Model base class - add id attribute
class Model(models.Model):
    id: int
    pk: int

# Club model stub
class Club(Model):
    id: int
    name: str
    status: str
    members_count: int
    founded_date: Optional[str]
    description: str
    president: Optional[User]
    def __init__(self): ...

# UserProfile model stub
class UserProfile(Model):
    id: int
    user: User
    role: str
    real_name: str
    student_id: str
    phone: str
    status: str
    department: Optional[str]
    staff_level: Optional[str]
    def __init__(self): ...

# ClubRegistrationRequest model stub
class ClubRegistrationRequest(Model):
    id: int
    club_name: str
    reviews: Any  # Related manager
    status: str
    resubmission_attempt: int
    establishment_application: Any
    constitution_draft: Any
    three_year_plan: Any
    leaders_resumes: Any
    one_month_activity_plan: Any
    advisor_certificates: Any
    requested_by: User
    submitted_at: Any
    reviewed_at: Optional[Any]
    reviewer_comment: str
    reviewer: Optional[User]
    is_read: bool
    def __init__(self): ...

# ClubRegistration model stub
class ClubRegistration(Model):
    id: int
    club: Club
    reviews: Any  # Related manager
    status: str
    registration_form: Any
    basic_info_form: Any
    membership_fee_form: Any
    leader_change_application: Any
    meeting_minutes: Any
    name_change_application: Any
    advisor_change_application: Any
    business_advisor_change_application: Any
    new_media_application: Any
    submitted_at: Any
    reviewed_at: Optional[Any]
    def __init__(self): ...

# ReviewSubmission model stub
class ReviewSubmission(Model):
    id: int
    club: Club
    reviews: Any  # Related manager
    status: str
    submitted_at: Any
    submission_year: int
    def __init__(self): ...

# PresidentTransition model stub
class PresidentTransition(Model):
    id: int
    club: Club
    status: str
    submitted_at: Any
    def __init__(self): ...

# ActivityApplication model stub
class ActivityApplication(Model):
    id: int
    club: Club
    status: str
    staff_approved: Optional[bool]
    staff_reviewer: Optional[User]
    staff_comment: str
    staff_reviewed_at: Optional[Any]
    reviewer: Optional[User]
    reviewed_at: Optional[Any]
    reviewer_comment: str
    submitted_at: Any
    def __init__(self): ...

# Officer model stub
class Officer(Model):
    id: int
    user_profile: UserProfile
    club: Club
    position: str
    is_current: bool
    def __init__(self): ...
