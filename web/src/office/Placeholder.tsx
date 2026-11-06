/** Holds a destination's place in the top bar until its ticket builds the real screen. */
export default function Placeholder({ title }: { title: string }) {
  return (
    <>
      <div className="head">
        <h1>{title}</h1>
      </div>
      <p className="muted">This screen isn't built yet.</p>
    </>
  );
}
