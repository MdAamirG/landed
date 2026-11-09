import { QRCodeSVG } from "qrcode.react";
import { Link } from "react-router";

import "./landing.css";

/**
 * The public page from Landing.html. The drawn product is replaced by screenshots of the real
 * screens, taken from the seeded demo data (docs/plan.md). Every figure on it comes from the brief.
 */

const SOURCE_URL = "https://github.com/MdAamirG/landed";

// A real export of TRP-66120 from the billing screen, cut to the voucher's main lines.
const TALLY_EXCERPT = `<VOUCHER VCHTYPE="Sales" ACTION="Create">
  <DATE>20261109</DATE>
  <VOUCHERNUMBER>LND-E5E149A7-1</VOUCHERNUMBER>
  <PARTYLEDGERNAME>Company B</PARTYLEDGERNAME>
  <ISOPTIONAL>Yes</ISOPTIONAL>
  <ALLLEDGERENTRIES.LIST>
    <LEDGERNAME>Freight Income</LEDGERNAME>
    <AMOUNT>38500.00</AMOUNT>
    <NARRATION>TRP-66120 LR 48190 e-way bill 341099217690</NARRATION>
  </ALLLEDGERENTRIES.LIST>
</VOUCHER>`;

function DemoQr({ size }: { size: number }) {
  return (
    <QRCodeSVG
      value={`${window.location.origin}/demo`}
      size={size}
      title="QR code that opens the driver demo"
      bgColor="transparent"
      fgColor="currentColor"
    />
  );
}

export default function Landing() {
  return (
    <div className="landing">
      <nav className="landing__pill stock" aria-label="Main">
        <a href="#top" className="landing__word">
          Landed
        </a>
        <a href="#how" className="landing__navlink">
          How it works
        </a>
        <a href="#unsure" className="landing__navlink">
          When the AI is unsure
        </a>
        <a href="#tally" className="landing__navlink">
          Tally
        </a>
        <a href="#try" className="btn btn--ink">
          Try the demo
        </a>
      </nav>

      <header id="top" className="desk landing__header">
        <div className="landing__wrap landing__hero">
          <div>
            <h1>Bill the POD from the gate.</h1>
            <p className="landing__lead">
              Drivers photograph the signed receipt. Landed checks it before they drive away.
            </p>
            <div className="landing__acts">
              <a href="#try" className="btn btn--ink">
                Try the demo
              </a>
              <a href="#how" className="landing__quiet-link">
                See one delivery
              </a>
            </div>
            <p className="muted landing__small">Sample data for a 340-truck fleet. No sign-up.</p>
          </div>

          <div className="landing__shots">
            <img
              className="landing__shot landing__shot--desk stock"
              src="/landing/billing.jpg"
              width={1440}
              height={900}
              alt="The billing screen: verified trips grouped by client for the 1 to 15 November cycle, ready to export to Tally."
            />
            <img
              className="landing__shot landing__shot--phone stock"
              src="/landing/driver-home.jpg"
              width={660}
              height={1106}
              alt="The driver's phone: trip TRP-66159 to Nashik and one large button reading फोटो लें, Take POD photo."
            />
            <Link to="/demo" className="landing__card landing__card--qr stock">
              <DemoQr size={72} />
              <span>
                <span className="landing__card-title">Try the driver app</span>
                <span className="muted landing__small-text">Scan with your phone</span>
              </span>
            </Link>
          </div>
        </div>
      </header>

      <section id="how" className="landing__sec">
        <div className="landing__wrap">
          <h2>One delivery, start to finish.</h2>
          <div className="landing__pin">
            <figure className="landing__vis">
              <div className="landing__phones">
                <img
                  className="stock"
                  src="/landing/driver-home.jpg"
                  width={660}
                  height={1106}
                  alt="The driver's trip screen with the photo button."
                  loading="lazy"
                />
                <img
                  className="stock"
                  src="/landing/driver-retake.jpg"
                  width={700}
                  height={556}
                  alt="The retake screen: फिर से फोटो लें, the stamp is not visible, with Stamp crossed out and the other five checks ticked. Retake 1 of 2."
                  loading="lazy"
                />
              </div>
              <figcaption>
                The driver screen at the gate, and the retake it asks for when the stamp is
                missing.
              </figcaption>
            </figure>
            <div>
              <div className="landing__panel">
                <h3>At the gate</h3>
                <p>
                  One big button. Hindi and Marathi voice prompts. No forms, and it works with no
                  signal.
                </p>
              </div>
              <div className="landing__panel">
                <h3>Checked while the driver waits</h3>
                <p>
                  LR number, stamp, quantity, remarks, date and signature. A bad photo gets a retake,
                  twice at most.
                </p>
              </div>
              <div className="landing__panel landing__panel--last">
                <h3>Billed the same week</h3>
                <p>Verified trips line up by client and cycle, ready for Tally.</p>
              </div>
            </div>
          </div>
        </div>
      </section>

      <section id="unsure" className="landing__sec landing__sec--follow">
        <div className="landing__wrap">
          <h2>When the AI is unsure, a person decides.</h2>
          <figure className="landing__figure">
            <img
              className="landing__shot stock"
              src="/landing/review.jpg"
              width={1440}
              height={900}
              alt="The review desk: the photo of lorry receipt 48213 beside what the AI read, 394 of 400 cartons received and the remark short by 6 cartons, flagged for a person."
              loading="lazy"
            />
            <figcaption>
              A shortage or damage remark, or an unsure read, always goes to review. The photo stays
              the record, and no invoice is ever sent on its own.
            </figcaption>
          </figure>
        </div>
      </section>

      <section id="tally" className="landing__sec landing__sec--follow">
        <div className="landing__wrap landing__split landing__split--tally">
          <div>
            <h2>Into Tally, with the photo attached.</h2>
            <p className="landing__body">
              Export makes draft vouchers. Your team still decides when an invoice goes out.
            </p>
          </div>
          <figure className="landing__figure-flat">
            <div className="stock landing__code-card">
              <pre className="landing__code">{TALLY_EXCERPT}</pre>
              <div className="landing__file">
                <span className="fig">LND-E5E149A7-1/TRP-66120.jpg</span>
                <span className="fig muted">174 KB</span>
              </div>
            </div>
            <figcaption>
              Part of a real export of one verified trip, and its photo in the POD ZIP.
            </figcaption>
          </figure>
        </div>
      </section>

      <section className="landing__board landing__sec">
        <div className="landing__wrap landing__split landing__split--board">
          <div>
            <p className="landing__big-fig">₹1.02 crore</p>
            <p className="landing__board-note">
              a year, spent waiting for paper, by your own estimate.
            </p>
          </div>
          <div>
            <table className="landing__ledger">
              <tbody>
                <tr>
                  <td>Billing 14 days late on ₹84.48 crore of freight, at 12%</td>
                  <td className="fig">₹38.9 lakh</td>
                </tr>
                <tr>
                  <td>396 PODs lost or disputed a year, half the freight gone each time</td>
                  <td className="fig">₹63.36 lakh</td>
                </tr>
              </tbody>
            </table>
            <p className="landing__board-source">
              From your brief: 2,200 trips a month at ₹32,000 average freight.
            </p>
          </div>
        </div>
      </section>

      <section id="try" className="landing__sec">
        <div className="landing__wrap landing__split landing__split--try">
          <div>
            <h2>Try it on your phone.</h2>
            <p className="landing__body">
              Scan to open the driver app, or open the billing desk here.
            </p>
            <div className="landing__acts">
              <Link to="/sign-in" className="btn btn--ink">
                Open the billing desk
              </Link>
              <Link to="/demo" className="landing__quiet-link">
                Open the driver demo
              </Link>
            </div>
          </div>
          <Link to="/demo" className="stock landing__qr" aria-label="Open the driver demo">
            <DemoQr size={148} />
          </Link>
        </div>
      </section>

      <footer className="landing__footer">
        <div className="landing__wrap">
          <p>
            <strong>Landed</strong> is a take-home build for Company A, a full-truckload transporter
            in Chhatrapati Sambhajinagar. It runs on sample data with no real personal data.{" "}
            <a href={SOURCE_URL}>Source on GitHub</a>. Built by Mohamed Aamir, 2026.
          </p>
        </div>
      </footer>
    </div>
  );
}
