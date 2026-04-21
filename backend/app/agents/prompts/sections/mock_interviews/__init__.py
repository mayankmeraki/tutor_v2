"""Company-specific mock interview prompt sections."""


def get_mock_prompt(company: str) -> str:
    """Return the company-specific mock interview prompt section."""
    company = (company or "generic").lower()
    if company == "google":
        from .google import MOCK_GOOGLE
        return MOCK_GOOGLE
    elif company == "meta":
        from .meta import MOCK_META
        return MOCK_META
    elif company == "amazon":
        from .amazon import MOCK_AMAZON
        return MOCK_AMAZON
    elif company == "microsoft":
        from .microsoft import MOCK_MICROSOFT
        return MOCK_MICROSOFT
    else:
        from .generic import MOCK_GENERIC
        return MOCK_GENERIC
