export type MockSms = { sentTo: string; token: string };

/** Only DEMO_MODE returns a token, so only a reviewer ever sees this. A real SMS needs no toast. */
export default function MockSmsToast({ sms, onClose }: { sms: MockSms; onClose: () => void }) {
  return (
    <div className="toast stock" role="status">
      <p>Mock SMS sent to {sms.sentTo}</p>
      {/* A new tab, so the office screen stays where it was while the reviewer plays the driver. */}
      <a className="btn btn--ink btn--sm" href={`/d/${sms.token}`} target="_blank" rel="noopener">
        Open link
      </a>
      <button className="btn btn--card btn--sm" type="button" onClick={onClose}>
        Close
      </button>
    </div>
  );
}
