"""The XML on its own: no database. test_billing.py covers what goes into it."""

from datetime import date
from xml.etree import ElementTree as ET

from app.tally import FREIGHT_LEDGER, Voucher, VoucherLine, build_xml, rupees

LINE = VoucherLine("TRP-1", "48190", "123456789012", 3_850_000, None)
SHORT = VoucherLine("TRP-2", "48213", "210987654321", 4_120_050, "6 cartons short")


def voucher(*lines, ledger="Company B", number="LND-1") -> Voucher:
    return Voucher(number, date(2026, 11, 7), ledger, lines)


def parsed(*vouchers):
    return ET.fromstring(build_xml(list(vouchers))).findall(".//VOUCHER")


def entries(element):
    return element.findall("ALLLEDGERENTRIES.LIST")


def test_rupees_keeps_exact_paise():
    assert rupees(3_850_000) == "38500.00"
    assert rupees(4_120_050) == "41200.50"
    assert rupees(5) == "0.05"


def test_one_sales_voucher_each_with_its_own_party():
    first, second = parsed(voucher(LINE), voucher(SHORT, ledger="Company D", number="LND-2"))

    assert first.get("VCHTYPE") == "Sales"
    assert first.findtext("VOUCHERTYPENAME") == "Sales"
    assert first.findtext("PARTYLEDGERNAME") == "Company B"
    assert second.findtext("PARTYLEDGERNAME") == "Company D"
    assert (first.findtext("VOUCHERNUMBER"), second.findtext("VOUCHERNUMBER")) == ("LND-1", "LND-2")


def test_every_voucher_is_a_draft():
    assert parsed(voucher(LINE))[0].findtext("ISOPTIONAL") == "Yes"


def test_the_date_is_in_tallys_format():
    assert parsed(voucher(LINE))[0].findtext("DATE") == "20261107"


def test_each_trip_is_a_line_with_its_lr_and_eway_bill():
    _, first, second = entries(parsed(voucher(LINE, SHORT))[0])

    assert first.findtext("LEDGERNAME") == FREIGHT_LEDGER
    assert "TRP-1" in first.findtext("NARRATION")
    assert "48190" in first.findtext("NARRATION")
    assert "123456789012" in first.findtext("NARRATION")
    assert "48213" in second.findtext("NARRATION")
    assert "210987654321" in second.findtext("NARRATION")


def test_the_party_is_debited_and_each_line_credited():
    party, first, second = entries(parsed(voucher(LINE, SHORT))[0])

    assert party.findtext("LEDGERNAME") == "Company B"
    assert party.findtext("ISPARTYLEDGER") == "Yes"
    assert party.findtext("ISDEEMEDPOSITIVE") == "Yes"
    assert party.findtext("AMOUNT") == "-79700.50"
    assert first.findtext("ISDEEMEDPOSITIVE") == "No"
    assert first.findtext("AMOUNT") == "38500.00"
    assert second.findtext("AMOUNT") == "41200.50"


def test_the_amounts_on_a_voucher_balance():
    amounts = [float(row.findtext("AMOUNT")) for row in entries(parsed(voucher(LINE, SHORT))[0])]

    assert round(sum(amounts), 2) == 0


def test_a_remark_goes_in_the_voucher_narration():
    narration = parsed(voucher(LINE, SHORT))[0].findtext("NARRATION")

    assert "TRP-2" in narration
    assert "48213" in narration
    assert "6 cartons short" in narration
    assert "TRP-1" not in narration


def test_a_clean_voucher_has_no_narration():
    assert parsed(voucher(LINE))[0].find("NARRATION") is None


def test_special_characters_survive_the_round_trip():
    line = VoucherLine("TRP-3", "1", "123456789012", 100, 'Seal <broken> & "bent"')

    element = parsed(voucher(line, ledger="Shah & Sons"))[0]

    assert element.findtext("PARTYLEDGERNAME") == "Shah & Sons"
    assert 'Seal <broken> & "bent"' in element.findtext("NARRATION")


def test_a_control_character_cannot_break_the_file():
    line = VoucherLine("TRP-3", "1", "123456789012", 100, "short\x0bby 6")

    assert "short by 6" in parsed(voucher(line))[0].findtext("NARRATION")
