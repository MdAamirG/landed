# Landed

Landed gets signed delivery proof from the consignee's gate to the billing desk of a full-truckload transporter, so freight can be billed without waiting for paper.

## People and parties

**Client**:
The company that pays the transporter's freight.
_Avoid_: Customer, consignor

**Consignee**:
The party that receives the goods at the destination. Its name and phone are personal data.
_Avoid_: Customer, receiver

**Driver**:
The person who carries the delivery proof from the gate. A driver has no account and acts through a driver link.

**Own driver** and **hired driver**:
Whether the truck belongs to the transporter or is hired. Both use the same driver link.

**Billing executive**:
Office staff who review PODs, correct fields and export to Tally.
_Avoid_: Reviewer, accountant

**Operations head**:
Office staff who watch missing PODs and resend driver links, but can't approve or export.

**Branch**:
The transporter's office a trip belongs to.

## Paper and proof

**Trip**:
One full-truckload movement of goods for a client, identified by a trip code.
_Avoid_: Job, order, shipment

**Lorry receipt (LR)**:
The paper issued at dispatch for a trip.
_Avoid_: Bilty, consignment note

**Proof of delivery (POD)**:
The LR once it has been signed and stamped at delivery. A photo of it is the record in Landed.
_Avoid_: Receipt

**E-way bill**:
The government transport document every trip links to, by a 12-digit number.

**Remark**:
Anything written on the POD by the consignee, such as a shortage or damage note.

## Capture

**Delivery**:
The moment the POD photo is taken at the gate.

**Driver link**:
The SMS link that opens one trip for its driver.
_Avoid_: App link, login

**Attempt**:
One POD photo sent for a trip, with what the AI read from it.
_Avoid_: Upload, submission

**Retake**:
A further attempt asked for after an earlier one. A trip allows two, so three attempts at most.

**Late photo**:
A photo that arrives when the trip isn't waiting for one. It is kept and flagged, but not checked.

**Phone check**:
The blur and brightness check made on the phone before sending. Failing it costs no retake.

**AI check**:
The vision model reading an attempt's six fields. It suggests values and never decides on money.

**Voice prompt**:
A short spoken instruction on a driver screen, in the driver's language: Hindi, Marathi or English. It plays when the screen opens and again from the speaker button.

**Pending photo**:
A photo saved on the phone and not yet sent. It isn't a trip status.

**Basic phone**:
A low-cost Android phone with a camera and browser, which is how Landed reads the brief's "basic phones". Keypad phones aren't supported.

## Status

**Awaiting POD**:
No photo has arrived for the trip yet.

**Checking**:
A photo has arrived and the AI check isn't finished.

**Retake requested**:
The driver has been asked for a new photo.

**Needs review**:
A billing executive must decide before the trip can be billed.

**Verified**:
The POD is accepted and the trip can be billed, whether the AI passed it or a billing executive approved it.
_Avoid_: Approved, as a status

**Disputed**:
The client has challenged the POD, and the trip stays out of billing until resolved.

**Invoiced**:
A draft voucher has been exported to Tally. Landed never issues an invoice itself.
_Avoid_: Billed, sent

**Lost POD**:
A POD still missing 20 days after expected delivery.

## Billing

**Billing cycle**:
A client's billing period: the 1st to 15th, or the 16th to month end. A trip belongs to the cycle of its delivery.

**Voucher**:
The draft Sales entry created in Tally for one client, with a line per trip.
_Avoid_: Bill, invoice

**Export**:
A billing executive sending selected trips to Tally as vouchers.

**Reveal**:
Showing a masked name or phone to an office user, which is always logged.

## Demo

**Demo trip**:
One of five fixed trips a reviewer can try and reset. It is never part of the seeded history.
