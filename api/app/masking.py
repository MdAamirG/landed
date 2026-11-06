"""Masks personal data for API responses. The DPDP Act 2023 covers consignee and driver contacts,
so these are what every response shows. The one logged reveal route is the only way past them.
"""


def mask_name(name: str) -> str:
    """Initials only: "Sample Consignee Nagpur" becomes "S. C. N."."""
    return " ".join(f"{part[0]}." for part in name.split())


def mask_phone(phone: str) -> str:
    """Enough to recognise a number, not enough to call it: "+91 90••• ••021"."""
    digits = "".join(character for character in phone if character.isdigit())
    return f"+91 {digits[:2]}••• ••{digits[-3:]}"
