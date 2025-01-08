from typing import Any, Optional, List
from pydantic.v1 import Field
from typing_extensions import TypedDict
import pydantic
import dspy

from app.api.schemas import PipelineResponse

class PersonName(pydantic.BaseModel):
    """Structured format for a person's name"""
    prefix: Optional[str] = Field(None, description="Title/prefix like Dr., Mr., Ms.")
    given_name: Optional[str] = Field(None, description="First name")
    middle_name: Optional[str] = Field(None, description="Middle name")
    family_name: Optional[str] = Field(None, description="Last name")
    suffix: Optional[str] = Field(None, description="Suffix like Jr., Ph.D.")

class WorkInformation(pydantic.BaseModel):
    """Structured format for work-related information"""
    job_title: Optional[str] = Field(None, description="Professional title")
    department: Optional[str] = Field(None, description="Department within organization")
    organization: Optional[str] = Field(None, description="Company or organization name")

class PostalAddress(pydantic.BaseModel):
    """Structured format for a postal address"""
    street: Optional[str] = Field(None, description="Street name and number")
    sub_locality: Optional[str] = Field(None, description="Neighborhood or district")
    city: Optional[str] = Field(None, description="City name")
    sub_administrative_area: Optional[str] = Field(None, description="County or region")
    state: Optional[str] = Field(None, description="State or province")
    postal_code: Optional[str] = Field(None, description="ZIP or postal code")
    country: Optional[str] = Field(None, description="Country name")
    iso_country_code: Optional[str] = Field(None, description="ISO country code")

class ContactInformation(pydantic.BaseModel):
    """Structured format for contact information"""
    phone_numbers: List[str] = Field(default_factory=list, description="List of phone numbers")
    email_addresses: List[str] = Field(default_factory=list, description="List of email addresses")
    postal_addresses: List[PostalAddress] = Field(default_factory=list, description="List of postal addresses")
    url_addresses: List[str] = Field(default_factory=list, description="List of websites/URLs")
    social_profiles: List[str] = Field(default_factory=list, description="List of social media profiles")

class BusinessCardResponse(pydantic.BaseModel):
    """Structured response for business card data"""
    name: PersonName
    work: WorkInformation
    contact: ContactInformation
    notes: Optional[str] = Field(None, description="Additional notes or information")

# Update PipelineResponse for business cards
class BusinessCardPipelineResponse(PipelineResponse):
    """Specialized response model for business card pipeline"""
    content: BusinessCardResponse


class BusinessCardExtractor(dspy.Signature):
    """Extract business card information from an image."""

    image: dspy.Image = dspy.InputField()
    
    # Name Information
    name_prefix: Optional[str] = dspy.OutputField()
    given_name: Optional[str] = dspy.OutputField()
    middle_name: Optional[str] = dspy.OutputField()
    family_name: Optional[str] = dspy.OutputField()
    name_suffix: Optional[str] = dspy.OutputField()
    
    # Work Information
    job_title: Optional[str] = dspy.OutputField()
    department_name: Optional[str] = dspy.OutputField()
    organization_name: Optional[str] = dspy.OutputField()
    
    # Contact Information
    phone_numbers: List[str] = dspy.OutputField()
    email_addresses: List[str] = dspy.OutputField()
    postal_addresses: List[PostalAddress] = dspy.OutputField()
    url_addresses: List[str] = dspy.OutputField()
    social_profiles: List[str] = dspy.OutputField()
    notes: Optional[str] = dspy.OutputField()

    @classmethod
    def process_output(cls, result: Any) -> BusinessCardResponse:
        """Process raw output into validated BusinessCardResponse"""
        return BusinessCardResponse(
            name=PersonName(
                prefix=result.name_prefix,
                given_name=result.given_name,
                middle_name=result.middle_name,
                family_name=result.family_name,
                suffix=result.name_suffix
            ),
            work=WorkInformation(
                job_title=result.job_title,
                department=result.department_name,
                organization=result.organization_name
            ),
            contact=ContactInformation(
                phone_numbers=result.phone_numbers,
                email_addresses=result.email_addresses,
                postal_addresses=[PostalAddress(**addr) for addr in result.postal_addresses],
                url_addresses=result.url_addresses,
                social_profiles=result.social_profiles
            ),
            notes=result.notes
        )