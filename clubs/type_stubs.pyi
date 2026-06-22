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

# PublishedActivity model stub
class PublishedActivity(Model):
    id: int
    club: Club
    source_submission: Any
    activity_name: str
    activity_type: str
    activity_description: str
    activity_date: Any
    activity_time_start: Any
    activity_time_end: Any
    activity_location: str
    expected_participants: int
    budget: Any
    contact_person: str
    contact_phone: str
    is_public: bool
    published_at: Any
    def __init__(self): ...

# Officer model stub
class Officer(Model):
    id: int
    user_profile: UserProfile
    club: Club
    position: str
    is_current: bool
    def __init__(self): ...
