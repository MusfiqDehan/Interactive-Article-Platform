"use client";

import Link from "next/link";
import { useState, type InputHTMLAttributes, type ReactNode } from "react";
import {
  ArrowRight,
  AlertCircle,
  Eye,
  EyeOff,
  LoaderCircle,
  MessageSquareText,
  Image as ImageIcon,
  Layers3,
} from "lucide-react";
import { StoryloomMark } from "@/components/brand/StoryloomMark";

export function AuthPanel({
  mode,
  error,
  children,
}: {
  mode: "login" | "register";
  error: string;
  children: ReactNode;
}) {
  const login = mode === "login";
  return (
    <div className="sl-auth-grid">
      <aside className="sl-auth-story">
        <span className="sl-eyebrow">A NEW DIMENSION TO EVERY STORY</span>
        <h2>
          Words bring us in.
          <br />
          <em>
            Discovery keeps
            <br />
            us here.
          </em>
        </h2>
        <p>
          A space for curious readers and thoughtful writers. Explore stories
          that invite you to look a little closer.
        </p>
        <div className="sl-story-illustration" aria-hidden="true">
          <div className="sl-paper sl-paper-back" />
          <div className="sl-paper">
            <span>THE ART OF LOOKING CLOSER</span>
            <h3>
              Every story has
              <br />
              another layer.
            </h3>
            <div className="sl-paper-lines" />
            <div className="sl-paper-note">
              <MessageSquareText size={18} />
              <span>
                A little more context.
                <br />
                <strong>A whole new perspective.</strong>
              </span>
            </div>
          </div>
          <span className="sl-floating-mark">
            <StoryloomMark size={58} title="" />
          </span>
        </div>
        <div className="sl-auth-features">
          <span>
            <Layers3 size={15} />
            Rich stories
          </span>
          <span>
            <MessageSquareText size={15} />
            Annotations
          </span>
          <span>
            <ImageIcon size={15} />
            Image hotspots
          </span>
        </div>
      </aside>
      <section className="sl-auth-form">
        <span className="sl-eyebrow">
          {login ? "YOUR NEXT CHAPTER" : "MAKE ROOM FOR DISCOVERY"}
        </span>
        <h1>{login ? "Welcome back." : "Your story starts here."}</h1>
        <p>
          {login
            ? "Sign in to pick up where your curiosity left off."
            : "Create an account and become part of the story."}
        </p>
        {error && (
          <div className="sl-form-error" role="alert">
            <AlertCircle size={18} />
            <span>{error}</span>
          </div>
        )}
        {children}
        <p className="sl-auth-switch">
          {login ? "New to Storyloom?" : "Already have an account?"}{" "}
          <Link href={login ? "/register" : "/login"}>
            {login ? "Create an account" : "Sign in"}
            <ArrowRight size={14} />
          </Link>
        </p>
        <Link href="/articles" className="sl-auth-browse">
          Just looking around? Explore the articles ↗
        </Link>
      </section>
    </div>
  );
}

export function AuthField({
  label,
  hint,
  type = "text",
  ...props
}: InputHTMLAttributes<HTMLInputElement> & { label: string; hint?: string }) {
  const [visible, setVisible] = useState(false);
  const password = type === "password";
  return (
    <div className="sl-field">
      <label htmlFor={props.id}>
        {label}
        {!props.required && <span>optional</span>}
      </label>
      <div className="sl-input-wrap">
        <input
          {...props}
          type={password && visible ? "text" : type}
          className={`sl-input ${password ? "sl-input-password" : ""}`}
          aria-describedby={hint ? `${props.id}-hint` : undefined}
        />
        {password && (
          <button
            type="button"
            className="sl-password-toggle"
            aria-label={`${visible ? "Hide" : "Show"} ${label.toLowerCase()}`}
            aria-pressed={visible}
            onClick={() => setVisible(!visible)}
          >
            {visible ? <EyeOff size={17} /> : <Eye size={17} />}
          </button>
        )}
      </div>
      {hint && <small id={`${props.id}-hint`}>{hint}</small>}
    </div>
  );
}

export function AuthSubmit({
  loading,
  children,
  pending,
}: {
  loading: boolean;
  children: ReactNode;
  pending: string;
}) {
  return (
    <button
      className="sl-button sl-auth-submit"
      type="submit"
      disabled={loading}
      aria-busy={loading}
    >
      {loading ? (
        <>
          <LoaderCircle size={17} className="sl-spinner" />
          {pending}
        </>
      ) : (
        <>
          {children}
          <ArrowRight size={17} />
        </>
      )}
    </button>
  );
}
