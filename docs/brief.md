# Take-home brief

Copied from the assignment. Only brief 1 applies.

## Assignment rules

```text
Brief
Your task
A client has sent us the brief you pick below. Build the product, end to end, with a great UI and UX.
	
You submit	One ZIP file with two files: your Technical Design Document (TDD) and a deployment.md
Time	7 days from when this step opens
Work	Alone
Build a small part really well instead of the whole scope badly. The "CORE BUILD" paragraph in your problem statement says which slice must work end to end.
Use AI, and use it well
AI tools are highly recommended. Use them to draft faster, test ideas, find gaps and polish your work, so that what you hand in is a more finished, specific outcome for this client and not a generic one. The judgement, the numbers and the final choices must still be yours. You will explain them in the interview.
What to do
Pick one problem statement from the ones shown to you. Then build it.
Must have
* The main flows in the brief work, on realistic sample data you create. No dead buttons
* Frontend, backend, a database and sign-in. Use roles if the brief has more than one kind of user
* The AI or automation part actually works, including what happens when it is wrong or unsure
* A polished UI: a consistent design, a layout that works on a phone, and loading, empty and error states
* Tests for the most important logic, and basic security: no secrets in the repository, validated inputs, access control
How to submit
Put these two files in one .zip (up to 25 MB) and upload it.
1. Technical Design Document (PDF or Word)
* The GitHub URL of your project, at the top. Also add the link to the live app if you deployed it
* The architecture and why you chose it
* The data model, the main flows and how the AI part works
* UI and design decisions: the key screens and why they look the way they do
* What you cut, and what you would do next
2. deployment.md
* How to run it locally, step by step
* How it is deployed, and the environment variables it needs (names only, never the values)
* Demo login details for the reviewer
Rules
* Use only the information in the problem statement. Label every assumption in your TDD
* Keep the commit history. We read it
* Do not put secrets or real personal data in the repository
* Keep the repository public until we have finished reviewing
* You can resubmit until the deadline; we review your latest version
What great looks like
* A product a client could try today
* Clean, readable code with a clear structure
* A UI that feels designed, not default
* Honest notes about the limits
* Extra depth, well-judged features beyond the core and careful edge cases count in your favour
Common mistakes
* A beautiful front end with nothing behind it
* Everything built, nothing working
* No sample data, so the app looks empty
* The AI part faked, or not handling mistakes
* A TDD with no GitHub URL
How you'll be scored
Area	Weight
Quality of work	50%
Problem solving	30%
Communication	20%
```

## Brief 1: road transport fleet POD capture and billing

```text
1.Road transport fleet's proof-of-delivery capture and billing app CLIENT
Company A, Chhatrapati Sambhajinagar, Maharashtra. Full-truckload transporter for cement, steel and packaged goods firms. 140 own trucks plus about 200 hired ones, 210 staff, revenue ₹75–90 crore a year.
TODAY
Drivers bring the signed lorry receipt (LR) or proof of delivery (POD) back after the trip, often 10–20 days later. Photos sent on WhatsApp get lost. Billing in Tally waits for the POD, as clients reject invoices without one.
THE PROBLEM
Assumptions: 2,200 trips a month at ₹32,000 average freight, ₹84.48 crore a year. POD-to-invoice takes 18 days; cutting it to 4 days brings billing 14 days forward: ₹84.48 crore × 14 / 365 = ₹3.24 crore of working capital, costing ₹38.9 lakh a year at 12% interest. 1.5% of PODs (396 trips a year) are lost or disputed, losing half the freight: 396 × ₹16,000 = ₹63.36 lakh. Total ₹1.02 crore a year.
USERS
Drivers (basic phones, low literacy), billing executives, and the operations head. The Managing Director signs the deal.
THE ASK
I can't bill until a piece of paper comes back from 800 km away. I want the driver to take a photo at the consignee's gate and be done. The system should check the photo while the driver is still there.
MUST HAVE
* Driver app with one big button to photograph the POD, stamped with GPS and time
* SMS upload link for hired drivers who won't install an app
* AI POD check of LR number, consignee stamp, quantity, shortage or damage remarks, date and signature, asking for a retake if needed
* Billing queue of verified trips by client and cycle, with Tally export and POD images attached to invoices
* Dashboard of trips without POD and POD-to-invoice days by branch, plus a client link to view PODs
* Daily trip import with LR and e-way bill numbers
CORE BUILD
Software Engineering candidates must ship this slice end to end, in about 6 to 8 screens: driver POD capture, AI check with retake prompt, review queue, billing queue with export, and missing-POD dashboard. Roles: driver and billing executive. AI: POD photo check. Hard part: offline capture with compressed upload. Mock payments, messages and outside systems, and seed from the sample data. The rest of MUST HAVE is optional depth.
OUT OF SCOPE
* Live GPS tracking
* Trip planning
* Fuel and driver expense accounting
AI OR AUTOMATION
A vision AI model checks each POD photo and extracts fields. When it is wrong: the image stays the source of truth; any POD with a shortage or damage remark, or low confidence, goes to a billing executive, who can correct fields; invoices are never sent automatically. Retakes are capped at two.
CONSTRAINTS
Each trip links to its e-way bill. Drivers need icons and Hindi or Marathi voice prompts, not typing. Highways have dead zones, so capture works offline and images are compressed under 300 KB. Consignee names and phones are personal data under the DPDP Act 2023.
DESIGN
The client values good, minimal design: clean layouts, white space, a restrained palette and clear type, with nothing on screen that lacks a purpose. Design counts as much as features. Many drivers do not read well: one big button, icons, a clear colour for success or retake, and no forms.
BUDGET AND TIME
₹7.5 lakh, 6 weeks. Success: 80% of PODs in the system within 24 hours of delivery; POD-to-invoice from 18 days to 4; lost or disputed PODs from 1.5% to 0.5%.
SAMPLE DATA
Trip ID	Client	Vehicle	To	Freight ₹	POD Status	Remarks
TRP-66120	Company B (cement)	MH20 EL 4521	Nagpur	38500	Verified	None
TRP-66134	Company C (steel)	MH20 GT 7718	Pune	26000	Retake requested	Stamp not visible
TRP-66141	Company D (packaged foods)	MH17 BY 3092 (hired)	Indore	41200	Needs review	Short by 6 cartons
```
