import Link from "next/link";
import { StoryloomWordmark } from "@/components/brand/StoryloomMark";
import { PLATFORM } from "@/lib/brand";

export default function Footer() {
  return (
    <footer className="sl-footer">
      <div className="sl-container sl-footer-row">
        <div>
          <Link href="/" className="sl-brand">
            <StoryloomWordmark markSize={32} />
          </Link>
          <p>{PLATFORM.tagline}</p>
        </div>
        <nav aria-label="Footer navigation">
          <Link href="/home">Journal</Link>
          <Link href="/articles">Articles</Link>
          <Link href="/categories">Categories</Link>
          <Link href="/register">Join Storyloom ↗</Link>
        </nav>
        <small>
          © {new Date().getFullYear()} {PLATFORM.name}
        </small>
      </div>
    </footer>
  );
}
