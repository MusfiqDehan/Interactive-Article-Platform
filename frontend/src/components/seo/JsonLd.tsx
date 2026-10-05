/**
 * Emit JSON-LD.
 *
 * `<` is escaped to `<` so a string inside the payload can never close the
 * script tag early -- the standard XSS vector for inline JSON.
 */
export function JsonLd({ data }: { data: object | object[] }) {
  const payload = Array.isArray(data) ? data : [data];
  if (payload.length === 0) return null;

  return (
    <>
      {payload.map((entry, index) => (
        <script
          key={index}
          type="application/ld+json"
          dangerouslySetInnerHTML={{
            __html: JSON.stringify(entry).replace(/</g, "\\u003c"),
          }}
        />
      ))}
    </>
  );
}
