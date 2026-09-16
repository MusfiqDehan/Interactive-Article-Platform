"""Seed demo users, sites, and 8+8 articles (draft / public / hidden).

Idempotent: re-running updates the known demo rows rather than duplicating them.

    python manage.py seed_demo
"""

from __future__ import annotations

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.articles.models import Article
from apps.categories.models import Category
from apps.taxonomy.models import set_tags
from apps.tenancy.models import Site, SiteMembership, SiteSettings
from common.tenancy import use_site

User = get_user_model()

ADMIN_EMAIL = "admin@example.com"
ADMIN_PASSWORD = "Admin1234!"
OWNER_EMAIL = "owner@example.com"
OWNER_PASSWORD = "Owner1234!"

PLATFORM_SLUG = "default"
TENANT_SLUG = "meridian"

CATEGORIES = (
    ("Astronomy", "Moons, surveys, and the quiet geometry of the sky."),
    ("Technology", "Inference, compilers, and the machines that carry stories."),
    ("Geopolitics", "Choke points, treaties, and the latency of power."),
    ("System Design", "Blast radius, consensus, and capacity you can explain."),
)


def _blocks(*parts: tuple[str, object]) -> dict:
    blocks = []
    for kind, payload in parts:
        if kind == "h2":
            blocks.append({"type": "header", "data": {"text": payload, "level": 2}})
        elif kind == "h3":
            blocks.append({"type": "header", "data": {"text": payload, "level": 3}})
        elif kind == "p":
            blocks.append({"type": "paragraph", "data": {"text": payload}})
        elif kind == "quote":
            blocks.append({"type": "quote", "data": {"text": payload, "caption": ""}})
        elif kind == "list":
            blocks.append({"type": "list", "data": {"style": "unordered", "items": payload}})
    return {"time": 1, "version": "2.30.0", "blocks": blocks}


def _article(
    slug: str,
    title: str,
    category: str,
    tags: list[str],
    excerpt: str,
    visibility: str,
    featured: bool,
    content: dict,
) -> dict:
    return {
        "slug": slug,
        "title": title,
        "category": category,
        "tags": tags,
        "excerpt": excerpt,
        "visibility": visibility,
        "featured": featured,
        "content": content,
    }


PLATFORM_ARTICLES = [
    _article(
        "jupiters-quiet-geometry",
        "Jupiter’s quiet geometry",
        "Astronomy",
        ["moons", "orbits", "Juno"],
        "The Galilean moons are a clock you can read without looking up. Here is what their resonances still teach a newsroom that thinks in deadlines.",
        "public",
        True,
        _blocks(
            ("p", "Io, Europa, Ganymede and Callisto do not orbit Jupiter so much as they keep time for it. Their mean-motion resonances are old news in celestial mechanics and still underused as a metaphor for coupled systems: a change in one period is never local."),
            ("h2", "A resonance is a contract"),
            ("p", "The 1:2:4 lock between Io, Europa and Ganymede is a contract written in gravity. Energy moves. Heat appears in Io as volcanoes, in Europa as a suspected ocean. The interesting editorial question is not “is there water?” — it is how a system stores stress until a surface feature makes it visible."),
            ("quote", "A moon does not choose to be tidal. It is simply close enough, for long enough."),
            ("p", "Juno’s gravity harmonics keep tightening the map of the interior. For a CMS that ships bilingual long-form, the lesson is blunt: the public page is the surface; the resonances live in workflow, syndication, and the state machine that decides whether a story is draft, public, or hidden."),
        ),
    ),
    _article(
        "edge-inference-eats-the-data-center",
        "Why edge inference is eating the data center",
        "Technology",
        ["inference", "edge", "mlops"],
        "Training still loves a warehouse of GPUs. Serving a model next to the reader is a different economics, and newsrooms will feel it first.",
        "public",
        True,
        _blocks(
            ("p", "The last decade of machine learning was a pilgrimage to the data center. The next one is a dispersal. Once a model is trained, the scarce resource is not FLOPs in a desert — it is joules and milliseconds next to the person who asked the question."),
            ("h2", "The unit of cost moved"),
            ("p", "Batch training amortises well. Token-by-token serving does not. Edge inference — on a POP, a phone, a set-top — changes whose bill the latency appears on. Publishers already learned this with images: a 2MB hero shot is a policy, not an accident."),
            ("list", ["Quantise until quality is a product decision, not a research one.", "Cache embeddings the way you cache sitemaps.", "Keep the authoring GPU in the studio; keep the reader’s CPU on the page."]),
            ("p", "Storyloom’s public pages are server-rendered for crawlers and hydrated only where a hotspot or a chapter timeline needs interaction. That is the same shape as edge inference: do the expensive work once, close to truth; do the cheap work everywhere."),
        ),
    ),
    _article(
        "red-sea-choke-points",
        "The new choke points of the Red Sea",
        "Geopolitics",
        ["shipping", "Bab-el-Mandeb", "insurance"],
        "Hulls, premiums, and alternate capes: a map of a corridor that still carries more than it appears to on a globe.",
        "public",
        False,
        _blocks(
            ("p", "A strait is a political object disguised as geography. Bab-el-Mandeb is 26 kilometres at its narrowest and, on some weeks, the most expensive water in the world — not because of tides, but because of who is willing to underwrite a hull."),
            ("h2", "Insurance is the real blockade"),
            ("p", "When war-risk premiums spike, cargo does not wait for a communique. It reroutes around the Cape, adding ten days and a carbon ledger that no press release will mention. The map in a newsroom CMS should be able to say that without a plugin."),
            ("p", "For editors, the lesson is the same as for captains: a hidden article and a skipped transit look identical from the destination. Visibility is a derived state. Either the public can see the story, or they cannot."),
        ),
    ),
    _article(
        "blast-radius-not-uptime",
        "Design for blast radius, not uptime",
        "System Design",
        ["reliability", "tenancy", "isolation"],
        "Nine nines in a shared schema is a slogan. A tenant that cannot take down its neighbour is an architecture.",
        "public",
        False,
        _blocks(
            ("p", "Uptime is a lagging indicator. Blast radius is a design constraint. Storyloom’s tenancy model is a shared schema with three overlapping guards — a default manager, a final queryset, and a test that fails unscoped SQL — because one missed site_id is not an empty list. It is a leak."),
            ("h2", "Failure should be boring"),
            ("p", "A Celery worker that dies mid-publish must be safe to retry. Idempotency keys on deliveries, derived is_live, and a primary placement that mirrors the article exist so that “did it publish?” has one answer."),
            ("quote", "If two services can disagree about whether a story is public, readers will believe the wrong one."),
            ("p", "Hide is not delete. Archive is a state, a sitemap omission, and a placement that stopped being live. The studio exposes that choice as Draft, Public, or Hidden because those are the words a publisher already uses."),
        ),
    ),
    _article(
        "euclid-first-year-dark-map",
        "Mapping the dark: Euclid’s first year",
        "Astronomy",
        ["Euclid", "surveys", "dark matter"],
        "A survey telescope is a publishing system. The catalogue is the sitemap; the weak-lensing map is the story.",
        "public",
        False,
        _blocks(
            ("p", "Euclid does not take portraits. It takes a census. Weak lensing is a statistical claim about how mass — including the kind that does not shine — bends the light of galaxies too distant to interview."),
            ("h2", "Catalogues are sitemaps"),
            ("p", "A well-formed survey tells a crawler (or a cosmologist) what exists, when it changed, and which images to attach. That is also what /sitemap.xml is for. Shard it, keep lastmod honest, and do not list the drafts."),
            ("p", "The first-year releases are already dense enough that “pretty picture” is the wrong genre. The genre is infrastructure: how a civilisation indexes the sky so the next paper does not start from zero."),
        ),
    ),
    _article(
        "webgpu-notes-for-newsrooms",
        "Notes on WebGPU for newsrooms",
        "Technology",
        ["WebGPU", "graphics", "draft"],
        "A working brief on when a news graphic should leave the DOM. Not public yet — the examples still lie.",
        "draft",
        False,
        _blocks(
            ("p", "This is a draft on purpose. WebGPU is real, Safari is late in the way that matters, and a hotspot overlay that runs a compute shader is still a provocation rather than a default."),
            ("h2", "When the DOM is the wrong renderer"),
            ("p", "Annotation markers, chapter scrubbers, and ECG traces on a marketing page are CSS. A gravitational-lensing explainer is not. The moment a graphic has a simulation step, you have left document flow."),
            ("p", "Leave this hidden from the public index until the fallback path is boring. A canvas that is blank in Firefox is not a feature."),
        ),
    ),
    _article(
        "sanctions-architecture-2026",
        "Sanctions architecture after 2026",
        "Geopolitics",
        ["sanctions", "finance", "draft"],
        "Secondary sanctions, maritime AIS gaps, and the software that pretends a ship was never there. Still being reported.",
        "draft",
        False,
        _blocks(
            ("p", "Draft: the legal citations are not yet locked, and two of the AIS case studies are in review. Do not syndicate."),
            ("p", "What changed is not the existence of sanctions but the stack that enforces them: insurers, satellite vendors, and KYC vendors that treat a transponder gap as a product signal."),
            ("p", "A hidden or draft story is the correct state for a piece whose facts are still moving. Public is a promise."),
        ),
    ),
    _article(
        "capacity-planning-bilingual-cms",
        "Internal: capacity planning for a bilingual CMS",
        "System Design",
        ["capacity", "internal"],
        "Load numbers, Meilisearch memory, and why Bangla tokenisation is not a weekend task. Hidden from the public site.",
        "hidden",
        False,
        _blocks(
            ("p", "This brief is hidden. It was written for the platform desk, not for readers, and it stays out of the sitemap on purpose."),
            ("h2", "What we measured"),
            ("p", "ISR on article detail at one hour, list pages at five minutes, sitemap shards at fifteen. Meilisearch is a soft dependency: search failing must not take the site down."),
            ("p", "Unicode slugs are not optional. If slugify eats a headline, the article 404s in the language it was written in. That bug is worse than a slow query."),
        ),
    ),
]

TENANT_ARTICLES = [
    _article(
        "meridian-constellation-becomes-a-border",
        "When a constellation becomes a border",
        "Astronomy",
        ["sovereignty", "satellites", "LEO"],
        "Low Earth orbit is filling up with flags. Meridian looks at who draws lines in a place that has no ground.",
        "public",
        True,
        _blocks(
            ("p", "A constellation used to mean a story we told about stars. It now means a corporation’s shell of spacecraft, refreshed like a CDN, claiming coverage of Earth as if coverage were a synonym for belonging."),
            ("h2", "Orbit is not terra nullius, but it behaves like a market"),
            ("p", "Slots, frequencies, and debris are the real cadastre. The night sky is the UI. When two systems occupy the same band of sky, the conflict is not poetic — it is a coordination failure with a liability regime that has not caught up."),
            ("p", "Meridian will keep reporting the launches. We will also report the conjunctions: the near-misses that never make a homepage unless someone treats them as news."),
        ),
    ),
    _article(
        "meridian-compiler-as-diplomacy",
        "The compiler as a diplomatic instrument",
        "Technology",
        ["compilers", "export-control", "toolchains"],
        "Export controls on toolchains are quieter than chip bans and, some weeks, more effective.",
        "public",
        True,
        _blocks(
            ("p", "A compiler is a political object. It decides which instructions a machine is allowed to become. When a toolchain is listed, forked, or geofenced, the press tends to write about chips. The more durable story is about the software that makes chips speak."),
            ("h2", "Instruction sets are treaties with extra steps"),
            ("p", "LLVM backends, CUDA compatibility layers, and the quiet deprecation of a target are how industrial policy arrives in a git log. Engineers experience this as broken builds. Diplomats experience it as leverage."),
            ("p", "This newsroom compiles against that fact. We name the flags."),
        ),
    ),
    _article(
        "meridian-arctic-fiber",
        "Pipeline politics and the Arctic fiber",
        "Geopolitics",
        ["cables", "Arctic", "infrastructure"],
        "A new northern route is not just latency. It is a bet on ice, landing stations, and whose court hears a cut.",
        "public",
        False,
        _blocks(
            ("p", "Subsea cables prefer boring water. The Arctic is not boring. It is shorter, colder, and suddenly interesting to anyone who has watched the Red Sea become a premium."),
            ("h2", "Landing stations are capitals"),
            ("p", "The politics of a cable are concentrated where it comes ashore: permits, power, and the building that a backhoe can find. A map of latency is a map of those rooms."),
            ("p", "Meridian’s desk will follow the repair ships as closely as the press releases. A hidden cut and a hidden article have the same user experience: nothing loads, and nobody is sure why."),
        ),
    ),
    _article(
        "meridian-consensus-planetary-scale",
        "Consensus at planetary scale",
        "System Design",
        ["consensus", "time", "distributed-systems"],
        "What Paxos looks like when the message delay is a satellite hop and the clock is a cesium fountain.",
        "public",
        False,
        _blocks(
            ("p", "Distributed systems textbooks assume a data center. Planetary systems assume a light-time. The difference is not philosophical — it is whether your timeout is a bug or a law of physics."),
            ("h2", "Time is the hardest API"),
            ("p", "Cesium fountains, GNSS, and leap seconds are not trivia. They are the shared memory of civilisation. A newsroom that timestamps datePublished incorrectly is, in miniature, the same failure as a ledger that cannot agree on order."),
            ("quote", "If two replicas disagree about now, they will disagree about the story."),
            ("p", "We design Meridian’s publishing pipeline as if the reader might be on the far side of a delay-tolerant link. That sounds romantic. It is mostly just honest caching."),
        ),
    ),
    _article(
        "meridian-failed-space-treaties",
        "A brief history of failed space treaties",
        "Astronomy",
        ["law", "outer-space", "history"],
        "The Outer Space Treaty still holds. Almost everything drafted after it does not. Here is the paper trail.",
        "public",
        False,
        _blocks(
            ("p", "1967 was a good year for sentences that begin with “States Parties.” It was a worse year for enforcement. The Outer Space Treaty banned national appropriation and said almost nothing about the companies that would, decades later, file mining claims in a press release."),
            ("h2", "Moon Agreements and other empty chairs"),
            ("p", "The Moon Agreement is the classic empty chair: ambitious, sparsely ratified, cited mainly as a warning. Subsequent attempts to write traffic rules for mega-constellations keep stalling on the same question: who is the sheriff when the beat is orbital?"),
            ("p", "Meridian’s position is journalistic, not legal: we will keep a running appendix of the drafts that did not become law, because failed treaties are still data."),
        ),
    ),
    _article(
        "meridian-oncall-distributed-newsroom",
        "On-call culture in a distributed newsroom",
        "Technology",
        ["oncall", "culture", "draft"],
        "A draft handbook for nights when the site is up and the story is not. Not ready for the front.",
        "draft",
        False,
        _blocks(
            ("p", "Draft handbook. The rotation table is still wrong for Dhaka time, and the escalation path mixes Telegram with the studio in a way legal has not blessed."),
            ("p", "A distributed newsroom fails in the gaps between time zones. Autosave is not a substitute for a named editor of last resort."),
            ("p", "This stays a draft until the runbook has been used in anger once."),
        ),
    ),
    _article(
        "meridian-tsmc-latency-of-power",
        "Taiwan, TSMC, and the latency of power",
        "Geopolitics",
        ["semiconductors", "Taiwan", "draft"],
        "Still reporting: foundry geography as strategy, and why “friend-shoring” is a latency number.",
        "draft",
        False,
        _blocks(
            ("p", "Draft. Two on-the-record interviews are pending and one number from a ministry deck cannot yet be sourced."),
            ("p", "The lead, if it survives: chips are not a metaphor for power. They are a lead time. A node that takes three years to stand up is a diplomatic fact."),
            ("p", "Do not make public until the map of announced fabs matches the map of tools that can actually run there."),
        ),
    ),
    _article(
        "meridian-style-guide-unfinished-briefs",
        "Style guide: hiding unfinished briefs",
        "System Design",
        ["style", "internal"],
        "How Meridian uses Hidden. Internal, and intentionally off the public site.",
        "hidden",
        False,
        _blocks(
            ("p", "Hidden, not deleted. A brief that is wrong on the internet should come down without pretending it was never written."),
            ("h2", "The three states we actually use"),
            ("list", ["Draft — still ours. Not in the sitemap, not in search, not on /home.", "Public — a promise to the reader and to crawlers.", "Hidden — was public or would confuse; archived; omitted from the index."]),
            ("p", "If you need a piece gone from Google but kept for the desk, Hide it. If you need it gone from the database, that is a different conversation and not this guide."),
        ),
    ),
]


def _upsert_user(*, email, username, password, role, first_name, last_name, superuser=False):
    user, _ = User.objects.get_or_create(
        email=email,
        defaults={
            "username": username,
            "role": role,
            "first_name": first_name,
            "last_name": last_name,
            "is_staff": superuser,
            "is_superuser": superuser,
        },
    )
    user.username = username
    user.role = role
    user.first_name = first_name
    user.last_name = last_name
    user.is_staff = superuser
    user.is_superuser = superuser
    user.is_active = True
    user.set_password(password)
    user.save()
    return user


def _upsert_site(*, slug, name, kind, primary_domain, base_url, locale, is_default, title, description, og_image):
    site = Site.objects.filter(slug=slug).first()
    if site is None:
        site = Site(
            slug=slug,
            name=name,
            kind=kind,
            primary_domain=primary_domain,
            base_url=base_url,
            locale=locale,
            is_default=is_default,
            is_active=True,
        )
        site.save()
    else:
        site.name = name
        site.kind = kind
        site.base_url = base_url.rstrip("/")
        site.locale = locale
        site.is_active = True
        site.save()

    settings, _ = SiteSettings.objects.get_or_create(site=site)
    settings.site_title = title
    settings.title_template = "%s | " + title
    settings.default_meta_description = description
    settings.default_og_image = og_image
    settings.allow_ai_crawlers = True
    settings.organization_jsonld = {
        "@type": "Organization",
        "name": title,
        "url": site.base_url,
        "logo": og_image,
    }
    settings.save()
    return site


def _ensure_categories(site):
    by_name = {}
    for order, (name, description) in enumerate(CATEGORIES):
        category, _ = Category.unscoped.get_or_create(
            site=site,
            name=name,
            defaults={"description": description, "order": order, "is_active": True},
        )
        if category.description != description or category.order != order:
            category.description = description
            category.order = order
            category.is_active = True
            category.save()
        by_name[name] = category
    return by_name


def _apply_visibility(article, visibility):
    now = timezone.now()
    if visibility == "public":
        article.status = "published"
        article.published_at = article.published_at or now
        article.last_published_at = now
        article.unpublished_at = None
    elif visibility == "hidden":
        article.status = "archived"
        article.published_at = article.published_at or now
        article.unpublished_at = now
    else:
        article.status = "draft"
        article.unpublished_at = None


def _upsert_articles(site, author, specs, cover):
    categories = _ensure_categories(site)
    created = updated = 0
    with use_site(site):
        for spec in specs:
            category = categories[spec["category"]]
            article = Article.unscoped.filter(site=site, slug=spec["slug"]).first()
            if article is None:
                article = Article(site=site, slug=spec["slug"], author=author)
                created += 1
            else:
                updated += 1
            article.title = spec["title"]
            article.author = author
            article.category = category
            article.excerpt = spec["excerpt"]
            article.content = spec["content"]
            article.featured_image = cover
            article.is_featured = spec["featured"]
            article.locale = site.locale
            _apply_visibility(article, spec["visibility"])
            article.save()
            set_tags(article, spec["tags"], site=site)
    return created, updated


class Command(BaseCommand):
    help = "Seed demo admin/owner users, Storyloom + Meridian sites, and 8 articles each."

    def handle(self, *args, **options):
        admin = _upsert_user(
            email=ADMIN_EMAIL,
            username="admin",
            password=ADMIN_PASSWORD,
            role="admin",
            first_name="Amina",
            last_name="Rahman",
            superuser=True,
        )
        owner = _upsert_user(
            email=OWNER_EMAIL,
            username="owner",
            password=OWNER_PASSWORD,
            role="author",
            first_name="Nabil",
            last_name="Chowdhury",
            superuser=False,
        )

        default = Site.objects.filter(is_default=True).first() or Site.objects.filter(slug=PLATFORM_SLUG).first()
        platform_domain = (default.primary_domain if default else "localhost")
        platform_base = (default.base_url if default else "http://localhost:3003")

        platform = _upsert_site(
            slug=default.slug if default else PLATFORM_SLUG,
            name="Storyloom",
            kind="owned",
            primary_domain=platform_domain,
            base_url=platform_base,
            locale="en",
            is_default=True,
            title="Storyloom",
            description=(
                "Storyloom is a bilingual publishing platform. Write in English or "
                "Bangla, enrich with interactive blocks, and review and publish together in one editorial studio."
            ),
            og_image=f"{platform_base.rstrip('/')}/og/storyloom.png",
        )

        tenant = _upsert_site(
            slug=TENANT_SLUG,
            name="Meridian",
            kind="owned",
            primary_domain="meridian.localhost",
            base_url=platform_base,
            locale="en",
            is_default=False,
            title="Meridian",
            description=(
                "Meridian publishes long-form reporting and analysis at the intersection "
                "of astronomy, technology, geopolitics, and system design."
            ),
            og_image=f"{platform_base.rstrip('/')}/og/tenant.jpg",
        )

        SiteMembership.objects.get_or_create(
            site=platform, user=admin, defaults={"role": "owner"}
        )
        SiteMembership.objects.update_or_create(
            site=tenant, user=owner, defaults={"role": "owner"}
        )
        SiteMembership.objects.get_or_create(
            site=tenant, user=admin, defaults={"role": "owner"}
        )
        # Tenant owner stays off the platform desk.
        SiteMembership.objects.filter(site=platform, user=owner).delete()

        p_new, p_upd = _upsert_articles(
            platform, admin, PLATFORM_ARTICLES, f"{platform.base_url}/og/storyloom.png"
        )
        t_new, t_upd = _upsert_articles(
            tenant, owner, TENANT_ARTICLES, f"{tenant.base_url}/og/tenant.jpg"
        )

        self.stdout.write(self.style.SUCCESS(
            f"Seeded Storyloom ({p_new} new / {p_upd} updated) and "
            f"Meridian ({t_new} new / {t_upd} updated)."
        ))
        self.stdout.write(f"  Platform admin  {ADMIN_EMAIL} / {ADMIN_PASSWORD}")
        self.stdout.write(f"  Tenant owner    {OWNER_EMAIL} / {OWNER_PASSWORD}")
        self.stdout.write("  Visibility: 5 public, 2 draft, 1 hidden per site.")
        self.stdout.write("  Studio: Draft / Public / Hidden on every article.")
