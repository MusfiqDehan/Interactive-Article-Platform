import Link from "next/link";

/**
 * Real 404.
 *
 * Reached via `notFound()` in the server fetch layer, so the response carries
 * an actual 404 status. The previous behaviour rendered a "not found" message
 * inside a 200 response -- a soft 404, which search engines will happily index.
 */
export default function NotFound() {
  return (
    <div className="mx-auto flex min-h-[60vh] max-w-2xl flex-col items-center justify-center px-4 text-center">
      <p className="font-display text-6xl font-bold text-primary-600 dark:text-primary-400">
        404
      </p>
      <h1 className="mt-4 font-display text-2xl font-bold text-slate-900 dark:text-slate-100">
        We couldn&apos;t find that page
      </h1>
      <p className="mt-3 text-slate-600 dark:text-slate-400">
        The page may have been moved or removed.
      </p>
      <div className="mt-8 flex gap-3">
        <Link href="/" className="btn-primary">
          Go home
        </Link>
        <Link href="/articles" className="btn-secondary">
          Browse articles
        </Link>
      </div>
    </div>
  );
}
