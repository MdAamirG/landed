"""Turns vouchers into Tally's import XML. Pure: no database and no HTTP, so tests parse the output.

Landed never connects to Tally. A person imports this file, and ISOPTIONAL makes each voucher an
optional one: Tally holds it as a draft, outside the books, until someone accepts it. That is what
keeps "the AI never sends an invoice" true at the last step.
"""

import re
from dataclasses import dataclass
from datetime import date
from xml.etree import ElementTree as ET

# Assumption: the brief names no sales ledger, so every trip credits this one.
FREIGHT_LEDGER = "Freight Income"

# XML 1.0 can't carry these, even escaped. A handwritten remark is the only way one could arrive.
FORBIDDEN_IN_XML = re.compile("[\x00-\x08\x0b\x0c\x0e-\x1f￾￿]")


@dataclass(frozen=True)
class VoucherLine:
    trip_code: str
    lr_number: str
    eway_bill_no: str
    freight_paise: int
    remark: str | None  # A shortage bills full freight, so this is a note, not a deduction.


@dataclass(frozen=True)
class Voucher:
    number: str
    voucher_date: date
    party_ledger: str
    lines: tuple[VoucherLine, ...]

    @property
    def total_paise(self) -> int:
        return sum(line.freight_paise for line in self.lines)


def rupees(paise: int) -> str:
    """Integer arithmetic, because a float could turn 3850000 paise into 38499.99."""
    return f"{paise // 100}.{paise % 100:02d}"


def add_text(parent: ET.Element, tag: str, text: str) -> None:
    ET.SubElement(parent, tag).text = FORBIDDEN_IN_XML.sub(" ", text)


def add_ledger_entry(
    voucher: ET.Element, ledger: str, debit: bool, paise: int, narration: str | None = None
) -> ET.Element:
    """Tally's sign rule: a debit is a negative amount with ISDEEMEDPOSITIVE set to Yes."""
    entry = ET.SubElement(voucher, "ALLLEDGERENTRIES.LIST")
    add_text(entry, "LEDGERNAME", ledger)
    add_text(entry, "ISDEEMEDPOSITIVE", "Yes" if debit else "No")
    add_text(entry, "AMOUNT", f"-{rupees(paise)}" if debit else rupees(paise))
    if narration:
        add_text(entry, "NARRATION", narration)
    return entry


def add_voucher(messages: ET.Element, voucher: Voucher) -> None:
    message = ET.SubElement(messages, "TALLYMESSAGE")
    element = ET.SubElement(message, "VOUCHER", {"VCHTYPE": "Sales", "ACTION": "Create"})
    add_text(element, "DATE", voucher.voucher_date.strftime("%Y%m%d"))
    add_text(element, "VOUCHERTYPENAME", "Sales")
    add_text(element, "VOUCHERNUMBER", voucher.number)
    add_text(element, "PARTYLEDGERNAME", voucher.party_ledger)
    add_text(element, "PERSISTEDVIEW", "Accounting Voucher View")
    add_text(element, "ISOPTIONAL", "Yes")

    remarks = [
        f"{line.trip_code} LR {line.lr_number}: {line.remark}"
        for line in voucher.lines
        if line.remark
    ]
    if remarks:
        add_text(element, "NARRATION", "; ".join(remarks))

    party = add_ledger_entry(element, voucher.party_ledger, debit=True, paise=voucher.total_paise)
    add_text(party, "ISPARTYLEDGER", "Yes")
    for line in voucher.lines:
        add_ledger_entry(
            element,
            FREIGHT_LEDGER,
            debit=False,
            paise=line.freight_paise,
            narration=f"{line.trip_code} LR {line.lr_number} e-way bill {line.eway_bill_no}",
        )


def build_xml(vouchers: list[Voucher]) -> str:
    envelope = ET.Element("ENVELOPE")
    add_text(ET.SubElement(envelope, "HEADER"), "TALLYREQUEST", "Import Data")
    import_data = ET.SubElement(ET.SubElement(envelope, "BODY"), "IMPORTDATA")
    description = ET.SubElement(import_data, "REQUESTDESC")
    add_text(description, "REPORTNAME", "Vouchers")
    messages = ET.SubElement(import_data, "REQUESTDATA")
    for voucher in vouchers:
        add_voucher(messages, voucher)

    ET.indent(envelope)
    return '<?xml version="1.0" encoding="UTF-8"?>\n' + ET.tostring(envelope, encoding="unicode")
