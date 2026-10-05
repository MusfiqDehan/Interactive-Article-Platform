"use client";

import { ArrowDown, ArrowRight, BookOpen, Check, ChevronRight, CirclePlus, FileText, Globe2, Image as ImageIcon, Layers3, Menu, MessageSquareText, Moon, Play, Search, ShieldCheck, Sun, X } from "lucide-react";
import Link from "next/link";
import { useTheme } from "next-themes";
import { useEffect, useRef, useState, useSyncExternalStore } from "react";
import { StoryloomMark, StoryloomWordmark } from "@/components/brand/StoryloomMark";
import { PLATFORM } from "@/lib/brand";
import "./styles.css";

const subscribe = () => () => {};
const stages = [
  { title: ["Write", "লিখুন"], body: ["A blank page. Endless possibilities.", "একটি খালি পাতা। অসীম সম্ভাবনা।"], detail: ["Build your story block by block. Bring text, images, audio, and video together in one editor.", "একই এডিটরে টেক্সট, ছবি, অডিও ও ভিডিও দিয়ে আপনার গল্প সাজান।"], rows: ["The architecture of a better story", "Add a heading, image, or interactive block", "Your next great idea starts here"], status: "Draft", icon: FileText },
  { title: ["Enrich", "সমৃদ্ধ করুন"], body: ["Let curiosity lead the way.", "কৌতূহলকে পথ দেখাতে দিন।"], detail: ["Add context with annotations, turn images into discoveries, and give audio and video their own chapters.", "অ্যানোটেশন, ছবির হটস্পট এবং অডিও-ভিডিও চ্যাপ্টার দিয়ে গল্পকে সমৃদ্ধ করুন।"], rows: ["Text annotation added", "Image hotspot positioned", "Media chapter ready"], status: "Interactive", icon: CirclePlus },
  { title: ["Review", "পর্যালোচনা"], body: ["Good stories are a team effort.", "ভালো গল্প গড়ে ওঠে দলগত কাজে।"], detail: ["Move drafts through a dedicated review queue, with clear roles for authors, editors, and administrators.", "লেখক, সম্পাদক ও প্রশাসকের নির্দিষ্ট ভূমিকা সহ ড্রাফট পর্যালোচনা করুন।"], rows: ["Draft submitted by author", "Editorial review in progress", "Ready for a final check"], status: "In review", icon: ShieldCheck },
  { title: ["Publish", "প্রকাশ করুন"], body: ["From your desk to their world.", "আপনার ডেস্ক থেকে পাঠকের কাছে।"], detail: ["Prepare search previews, plan your publishing calendar, and manage distribution from the studio.", "সার্চ প্রিভিউ তৈরি করুন, প্রকাশনার ক্যালেন্ডার পরিকল্পনা করুন এবং স্টুডিও থেকে বিতরণ পরিচালনা করুন।"], rows: ["Search preview prepared", "Publication date selected", "Distribution settings ready"], status: "Ready to publish", icon: Globe2 },
];

export default function LandingPage() {
  const [bn, setBn] = useState(false);
  const [intro, setIntro] = useState(false);
  const [chapters, setChapters] = useState<{ id: string; title: string; titleBn: string; t: number }[]>([]);
  const [activeChapter, setActiveChapter] = useState(0);
  const videoRef = useRef<HTMLVideoElement>(null);
  const [menu, setMenu] = useState(false);
  const [mode, setMode] = useState(0);
  const [detail, setDetail] = useState(false);
  const [chapter, setChapter] = useState(0);
  const [stage, setStage] = useState(0);
  const { resolvedTheme, setTheme } = useTheme();
  const mounted = useSyncExternalStore(subscribe, () => true, () => false);
  const t = (en: string, bangla: string) => bn ? bangla : en;
  useEffect(() => {
    const previous = document.documentElement.lang;
    document.documentElement.lang = bn ? "bn" : "en";
    return () => { document.documentElement.lang = previous; };
  }, [bn]);
  useEffect(() => {
    if (!intro) return;
    let cancel = false;
    fetch("/marketing/chapters.json")
      .then((response) => response.json())
      .then((data) => { if (!cancel) setChapters(data); })
      .catch(() => {});
    const onKey = (event: KeyboardEvent) => { if (event.key === "Escape") setIntro(false); };
    document.addEventListener("keydown", onKey);
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    const video = videoRef.current;
    video?.play().catch(() => {});
    return () => {
      cancel = true;
      document.removeEventListener("keydown", onKey);
      document.body.style.overflow = previousOverflow;
      video?.pause();
    };
  }, [intro]);
  const active = stages[stage];
  const features = [
    { icon: Layers3, title: t("Your story, in every format", "সব ফরম্যাটে আপনার গল্প"), body: t("Compose with flexible blocks for text, images, audio, and video. Make room for the whole story.", "টেক্সট, ছবি, অডিও এবং ভিডিওর ব্লক দিয়ে সম্পূর্ণ গল্পটি সাজান।"), label: t("BLOCK-BASED EDITOR", "ব্লক এডিটর"), className: "formats" },
    { icon: Globe2, title: t("Two languages. No compromise.", "দুই ভাষা। সমান গুরুত্ব।"), body: t("Publish in English and Bangla, with native typography and Unicode-friendly article links.", "নিজস্ব টাইপোগ্রাফি ও ইউনিকোড লিংক সহ ইংরেজি ও বাংলায় প্রকাশ করুন।"), label: t("ENGLISH + বাংলা", "বাংলা + ENGLISH"), className: "languages" },
    { icon: Search, title: t("Made to be discovered", "পাঠক খুঁজে পাবেন সহজেই"), body: t("Searchable stories, SEO previews, social cards, and sitemaps help your work find its readers.", "সার্চ, SEO প্রিভিউ, সোশ্যাল কার্ড এবং সাইটম্যাপ দিয়ে পাঠকের কাছে পৌঁছান।"), label: t("SEARCH & SEO", "সার্চ ও SEO"), className: "discovery" },
  ];
  return (
    <div className="sp-landing" lang={bn ? "bn" : "en"}>
      <a className="sp-skip" href="#main">{t("Skip to content", "মূল বিষয়বস্তুতে যান")}</a>
      <header className="sp-header">
        <div className="sp-container sp-nav">
          <Link href="/" className="sp-brand" aria-label="Storyloom home"><StoryloomWordmark markSize={38} /></Link>
          <nav className="sp-desktop-nav" aria-label={t("Main navigation", "প্রধান নেভিগেশন")}>
            <a href="#experience">{t("The experience", "অভিজ্ঞতা")}</a><a href="#features">{t("Features", "ফিচার")}</a><a href="#studio">{t("The studio", "স্টুডিও")}</a><Link href="/articles">{t("Explore articles", "আর্টিকেল দেখুন")} ↗</Link>
          </nav>
          <div className="sp-nav-actions">
            <button className="sp-locale" onClick={() => setBn(!bn)} aria-label={t("Switch to Bangla", "Switch to English")}>{bn ? "EN" : "বাং"}</button>
            <button className="sp-icon-button" aria-label={t("Toggle color theme", "থিম পরিবর্তন করুন")} onClick={() => setTheme(resolvedTheme === "dark" ? "light" : "dark")}>{mounted && resolvedTheme === "dark" ? <Sun size={17} /> : <Moon size={17} />}</button>
            <Link className="sp-signin" href="/login">{t("Sign in", "সাইন ইন")}</Link>
            <Link className="sp-button sp-button-small" href="/register">{t("Get started", "শুরু করুন")}<ArrowRight size={15} /></Link>
            <button className="sp-menu-button sp-icon-button" aria-label={t("Toggle navigation", "নেভিগেশন খুলুন")} aria-expanded={menu} aria-controls="sp-mobile-nav" onClick={() => setMenu(!menu)}>{menu ? <X /> : <Menu />}</button>
          </div>
        </div>
        {menu && <nav id="sp-mobile-nav" className="sp-mobile-nav" aria-label="Mobile navigation">{[["#experience", t("The experience", "অভিজ্ঞতা")], ["#features", t("Features", "ফিচার")], ["#studio", t("The studio", "স্টুডিও")], ["/articles", t("Explore articles", "আর্টিকেল দেখুন")], ["/login", t("Sign in", "সাইন ইন")]].map(([href, label]) => <Link key={href} href={href} onClick={() => setMenu(false)}>{label}<ArrowRight size={16} /></Link>)}</nav>}
      </header>
      <main id="main">
        <section className="sp-container sp-hero" id="experience">
          <div className="sp-hero-copy">
            <span className="sp-eyebrow"><span className="sp-small-square" />{t("A NEW CHAPTER IN PUBLISHING", "প্রকাশনার নতুন অধ্যায়")}</span>
            <h1>{t("Stories worth", "পড়ার মতো গল্প।")}{!bn && <><br />reading.</>}<br /><span>{t("And exploring.", "অন্বেষণের আনন্দ।")}</span></h1>
            <p>{t("Go beyond the written word. Create interactive articles that invite readers to discover more — with a publishing studio built for your entire team.", "লেখার বাইরেও গল্প বলুন। ইন্টারেক্টিভ আর্টিকেল দিয়ে পাঠককে আরও আবিষ্কারের সুযোগ দিন — পুরো দলের জন্য তৈরি একটি প্রকাশনা স্টুডিওতে।")}</p>
            <div className="sp-hero-actions"><Link href="/register" className="sp-button">{t("Start your story", "আপনার গল্প শুরু করুন")}<ArrowRight size={17} /></Link><a className="sp-text-link" href="/marketing/storyloom-intro.mp4" onClick={(event) => { event.preventDefault(); setActiveChapter(0); setIntro(true); }}><Play size={15} />{t("Watch the intro", "ভূমিকা দেখুন")}</a><a className="sp-text-link" href="#studio">{t("Explore the studio", "স্টুডিও দেখুন")}<ArrowDown size={16} /></a></div>
            <div className="sp-hero-note"><span><Check size={14} />{t("Built for writers", "লেখকদের জন্য")}</span><span><Check size={14} />{t("Designed for curiosity", "কৌতূহলের জন্য")}</span></div>
          </div>
          <div className="sp-demo-wrap">
            <div className="sp-demo-topline"><span><span className="sp-small-square" />{t("THE READER EXPERIENCE", "পাঠকের অভিজ্ঞতা")}</span><span>{t("Interactive demo", "ইন্টারেক্টিভ ডেমো")}</span></div>
            <div className="sp-demo">
              <div className="sp-demo-masthead"><span>MERIDIAN<span> / {t("Field notes", "ফিল্ড নোট")}</span></span><BookOpen size={17} /></div>
              <div className="sp-landscape" role="img" aria-label={t("Illustrated mountain landscape with a setting sun", "সূর্যাস্তে পাহাড়ের চিত্র")}><div className="sp-sun" /><div className="sp-mountain sp-mountain-back" /><div className="sp-mountain sp-mountain-front" /><div className="sp-landscape-caption">27°59′ N &nbsp; 86°55′ E</div></div>
              {mode === 1 && <button className="sp-hotspot" aria-expanded={detail} aria-controls="sp-demo-detail" onClick={() => setDetail(!detail)} aria-label={t("Explore the mountain hotspot", "পাহাড়ের হটস্পট দেখুন")}><CirclePlus size={25} /></button>}
              <div className="sp-demo-article"><span className="sp-article-category">{t("NATURE & PERSPECTIVE", "প্রকৃতি ও দৃষ্টিভঙ্গি")} <span>· {t("6 MIN READ", "৬ মিনিট")}</span></span><h2>{t("A little closer to the extraordinary.", "অসাধারণের আরও একটু কাছে।")}</h2><p>{t("Some landscapes ask us to slow down. To look closer. To discover the ", "কিছু দৃশ্য আমাদের থামতে বলে। কাছে দেখতে বলে। আবিষ্কার করতে বলে ")}{mode === 0 ? <button className="sp-annotation" aria-expanded={detail} aria-controls="sp-demo-detail" onClick={() => setDetail(!detail)}>{t("stories beneath the surface", "দৃশ্যের আড়ালের গল্প")}<MessageSquareText size={12} /></button> : t("stories beneath the surface", "দৃশ্যের আড়ালের গল্প")}{t(".", "।")}</p>
              {mode === 2 && <div className="sp-chapters" aria-label="Sample media chapters">{["The journey", "A new perspective", "Looking closer"].map((label, i) => <button key={label} aria-pressed={chapter === i} onClick={() => { setChapter(i); setDetail(true); }}><Play size={12} />0{i * 2}:00 <span>{t(label, ["যাত্রা", "নতুন দৃষ্টিভঙ্গি", "আরও কাছে"][i])}</span></button>)}</div>}
              {detail && <div id="sp-demo-detail" className="sp-demo-detail" role="status"><div><strong>{mode === 0 ? t("A layer of context", "প্রাসঙ্গিক তথ্য") : mode === 1 ? t("A different point of view", "একটি ভিন্ন দৃষ্টিভঙ্গি") : t(["01 / The journey", "02 / A new perspective", "03 / Looking closer"][chapter], ["০১ / যাত্রা", "০২ / নতুন দৃষ্টিভঙ্গি", "০৩ / আরও কাছে"][chapter])}</strong><button aria-label={t("Close detail", "বন্ধ করুন")} onClick={() => setDetail(false)}><X size={14} /></button></div><p>{mode === 0 ? t("Annotations bring definitions, sources, and extra detail into the story without taking readers away from the page.", "অ্যানোটেশন পাঠককে একই পাতায় সংজ্ঞা, উৎস ও বাড়তি তথ্য দেয়।") : mode === 1 ? t("An image can hold more than one story. Hotspots connect a specific place in a picture to additional context.", "ছবির নির্দিষ্ট স্থানে হটস্পট দিয়ে বাড়তি তথ্য দেখানো যায়।") : t(["Introduce your readers to the setting with a chapter at the start of your media.", "Let readers jump to another perspective using timed chapter markers.", "Attach supporting context to the moments that matter."][chapter], ["মিডিয়ার শুরুতে একটি চ্যাপ্টার দিয়ে পাঠককে পরিচয় করান।", "নির্দিষ্ট সময়ের চ্যাপ্টার দিয়ে নতুন অংশে পৌঁছান।", "গুরুত্বপূর্ণ মুহূর্তে প্রাসঙ্গিক তথ্য যোগ করুন।"][chapter])}</p></div>}
              </div>
              <div className="sp-demo-hint"><span>↳</span>{t(mode === 0 ? "Try it — click the highlighted text" : mode === 1 ? "Try it — click the + on the image" : "Try it — select a sample chapter", mode === 0 ? "হাইলাইট করা লেখায় ক্লিক করুন" : mode === 1 ? "ছবির + চিহ্নে ক্লিক করুন" : "একটি চ্যাপ্টার বেছে নিন")}</div>
            </div>
            <div className="sp-demo-controls" aria-label={t("Choose a demo", "ডেমো বেছে নিন")}>{[MessageSquareText, ImageIcon, Play].map((Icon, i) => <button key={i} aria-pressed={mode === i} onClick={() => { setMode(i); setDetail(false); }}><Icon size={15} />{[t("Annotations", "অ্যানোটেশন"), t("Hotspots", "হটস্পট"), t("Chapters", "চ্যাপ্টার")][i]}</button>)}</div>
            <span className="sp-margin-note">{t("More than a page. An experience.", "শুধু একটি পাতা নয়। একটি অভিজ্ঞতা।")}</span>
          </div>
        </section>
        <div className="sp-capabilities"><div className="sp-container"><span>{t("FROM FIRST DRAFT TO FINAL DISCOVERY", "প্রথম ড্রাফট থেকে পাঠকের কাছে")}</span>{[[FileText, t("Create", "তৈরি করুন")], [MessageSquareText, t("Make it interactive", "ইন্টারেক্টিভ করুন")], [ShieldCheck, t("Collaborate", "সহযোগিতা করুন")], [Globe2, t("Publish", "প্রকাশ করুন")]].map(([Icon, label], i) => { const ItemIcon = Icon as typeof FileText; return <div key={i}><ItemIcon size={18} />{label as string}</div>; })}</div></div>
        <section className="sp-container sp-features" id="features"><div className="sp-section-heading"><div><span className="sp-eyebrow">{t("BUILT AROUND YOUR STORY", "আপনার গল্পের জন্য")}</span><h2>{t("Everything you need.", "যা কিছু প্রয়োজন।")}<br /><span>{t("Room to do more.", "আরও কিছু করার সুযোগ।")}</span></h2></div><p>{t("From a simple idea to a rich reading experience. The tools belong together, so your team can focus on the story.", "সহজ ভাবনা থেকে সমৃদ্ধ পাঠের অভিজ্ঞতা। সব সরঞ্জাম একসঙ্গে, যেন আপনার দল গল্পে মন দিতে পারে।")}</p></div><div className="sp-feature-grid">{features.map(({ icon: Icon, title, body, label, className }, i) => <article key={className} className={`sp-feature ${className}`}><span className="sp-feature-label"><Icon size={15} />{label}</span><div className="sp-feature-art" aria-hidden="true">{i === 0 ? <div className="sp-blocks"><span><FileText />{t("Your headline goes here", "আপনার শিরোনাম")}</span><span><ImageIcon /><i /><i /><i /></span><span><MessageSquareText />{t("A little more context", "আরও কিছু তথ্য")}<CirclePlus size={15} /></span></div> : i === 1 ? <div className="sp-language-art"><span>Aa</span><span>অ আ</span><small>{t("Different scripts. Same story.", "ভিন্ন লিপি। একই গল্প।")}</small></div> : <div className="sp-search-art"><span><Search size={14} />{t("Find your next discovery", "নতুন কিছু খুঁজুন")}</span><small>meridian / stories</small><strong>{t("Stories that take you further", "আরও দূরে নিয়ে যায় যে গল্প")}</strong><i /><i /></div>}</div><h3>{title}</h3><p>{body}</p></article>)}</div></section>
        <section className="sp-studio-section" id="studio"><div className="sp-container"><div className="sp-section-heading"><div><span className="sp-eyebrow">{t("MEET YOUR EDITORIAL STUDIO", "আপনার এডিটোরিয়াল স্টুডিও")}</span><h2>{t("Big ideas. A clear path.", "বড় ভাবনা। স্পষ্ট পথ।")}</h2></div><Link className="sp-text-link" href="/studio">{t("Open the studio", "স্টুডিও খুলুন")}<ArrowRight size={17} /></Link></div><div className="sp-workflow"><div className="sp-workflow-options">{stages.map((s, i) => <button key={i} aria-pressed={stage === i} aria-controls="sp-workflow-preview" onClick={() => setStage(i)}><span>0{i + 1}</span><div><strong>{s.title[bn ? 1 : 0]}</strong>{stage === i && <p>{s.detail[bn ? 1 : 0]}</p>}</div><ChevronRight size={18} /></button>)}</div><div id="sp-workflow-preview" className="sp-studio-preview" aria-live="polite"><div className="sp-studio-bar"><span><StoryloomMark size={20} title="" /> {PLATFORM.name} / studio</span><span>{t("WORKFLOW PREVIEW", "ওয়ার্কফ্লো প্রিভিউ")}</span></div><div className="sp-studio-content"><span className="sp-status"><active.icon size={13} />{bn ? active.title[1] : active.status}</span><h3>{active.body[bn ? 1 : 0]}</h3><div className="sp-studio-rows">{active.rows.map((row, i) => <div key={row}><span>{stage === 0 ? <FileText size={16} /> : <Check size={16} />}</span>{bn ? [["আরও ভালো গল্পের গঠন", "শিরোনাম, ছবি বা ইন্টারেক্টিভ ব্লক যোগ করুন", "পরবর্তী ভাবনা এখানেই শুরু"], ["অ্যানোটেশন যোগ করা হয়েছে", "ছবির হটস্পট নির্ধারিত", "মিডিয়া চ্যাপ্টার প্রস্তুত"], ["লেখক ড্রাফট জমা দিয়েছেন", "সম্পাদকের পর্যালোচনা চলছে", "চূড়ান্ত পরীক্ষার জন্য প্রস্তুত"], ["সার্চ প্রিভিউ প্রস্তুত", "প্রকাশের তারিখ নির্বাচিত", "বিতরণ সেটিংস প্রস্তুত"]][stage][i] : row}</div>)}</div><div className="sp-studio-bottom"><span>{t("One connected workspace", "একটি সমন্বিত কর্মক্ষেত্র")}</span><span>0{stage + 1} / 04</span></div></div></div></div></div></section>
        <section className="sp-container sp-final"><span className="sp-eyebrow">{t("MAKE SOMETHING WORTH EXPLORING", "আবিষ্কার করার মতো কিছু তৈরি করুন")}</span><h2>{t("Your next story", "আপনার পরের গল্প")}<br />{t("deserves more.", "আরও কিছু দাবি করে।")}<span>↗</span></h2><div><p>{t("Give your ideas a home. Give your readers a reason to stay.", "আপনার ভাবনাকে জায়গা দিন। পাঠককে আরও জানার সুযোগ দিন।")}</p><Link href="/register" className="sp-button">{t("Start creating with Storyloom", "Storyloom দিয়ে শুরু করুন")}<ArrowRight size={17} /></Link><Link href="/home" className="sp-text-link">{t("Visit the Meridian journal", "Meridian জার্নাল দেখুন")} ↗</Link></div></section>
      </main>
      <footer className="sp-container sp-footer"><Link href="/" className="sp-brand"><StoryloomWordmark markSize={34} /></Link><span>{t("A new dimension to every story.", "প্রতিটি গল্পে নতুন মাত্রা।")}</span><div><Link href="/articles">{t("Articles", "আর্টিকেল")}</Link><Link href="/categories">{t("Categories", "বিভাগ")}</Link><Link href="/login">{t("Sign in", "সাইন ইন")}</Link></div><small>© {new Date().getFullYear()} {PLATFORM.name}</small></footer>
      {intro && <div className="sp-intro" role="dialog" aria-modal="true" aria-labelledby="sp-intro-title">
        <button className="sp-intro-backdrop" type="button" aria-label={t("Close intro", "ভূমিকা বন্ধ করুন")} onClick={() => setIntro(false)} />
        <div className="sp-intro-panel">
          <div className="sp-intro-bar">
            <span id="sp-intro-title"><span className="sp-small-square" />{t("Product intro", "পণ্যের ভূমিকা")}</span>
            <button type="button" autoFocus aria-label={t("Close intro", "ভূমিকা বন্ধ করুন")} onClick={() => setIntro(false)}><X size={18} /></button>
          </div>
          <video
            ref={videoRef}
            className="sp-intro-video"
            src="/marketing/storyloom-intro.mp4"
            poster="/marketing/storyloom-intro-poster.jpg"
            controls
            playsInline
            preload="metadata"
            onTimeUpdate={() => {
              const time = videoRef.current?.currentTime ?? 0;
              let index = 0;
              chapters.forEach((chapter, i) => { if (time + 0.05 >= chapter.t) index = i; });
              setActiveChapter((current) => current === index ? current : index);
            }}
          />
          <div className="sp-intro-chapters" role="tablist" aria-label={t("Intro chapters", "ভূমিকার অধ্যায়")}>
            {chapters.map((chapter, index) => <button key={chapter.id} type="button" role="tab" aria-selected={activeChapter === index} onClick={() => { const video = videoRef.current; if (!video) return; video.currentTime = chapter.t; setActiveChapter(index); video.play().catch(() => {}); }}>{bn ? chapter.titleBn : chapter.title}</button>)}
          </div>
        </div>
      </div>}
    </div>
  );
}
