"""Copy local media to object storage and rewrite every reference to it.

Rewriting ``MediaFile.file`` is the easy half. The hard half is that uploaded
URLs are also embedded throughout ``Article.content`` -- in image blocks, in
annotation ``image_url``/``audio_url``/``video_url`` fields, and inside hotspot
and chapter payloads. Missing those leaves articles pointing at a filesystem
that is about to go away.

Defaults to a dry run; ``--apply`` performs the writes.

    python manage.py migrate_media_to_s3                # preview
    python manage.py migrate_media_to_s3 --apply        # execute
    python manage.py migrate_media_to_s3 --apply --skip-existing
"""

from __future__ import annotations

import json

from django.conf import settings
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.articles.models import Article
from apps.media_library.models import MediaFile


class Command(BaseCommand):
    help = "Copy local media files to the configured storage backend and rewrite references."

    def add_arguments(self, parser):
        parser.add_argument(
            "--apply",
            action="store_true",
            help="Perform the migration. Without this flag the command only reports.",
        )
        parser.add_argument(
            "--skip-existing",
            action="store_true",
            help="Skip files already present in the destination storage.",
        )
        parser.add_argument(
            "--batch-size", type=int, default=100, help="Articles rewritten per transaction."
        )

    def handle(self, *args, **options):
        apply_changes = options["apply"]
        if apply_changes and not getattr(settings, "USE_S3", False):
            raise CommandError(
                "USE_S3 is false, so the default storage is still the local "
                "filesystem and this migration would be a no-op. Set USE_S3=true "
                "with credentials before running with --apply."
            )

        if not apply_changes:
            self.stdout.write(
                self.style.WARNING("DRY RUN -- no changes will be written. Pass --apply to execute.")
            )

        url_map = self._migrate_files(apply_changes, options["skip_existing"])
        self._rewrite_articles(url_map, apply_changes, options["batch_size"])

        self.stdout.write(self.style.SUCCESS("Done."))

    # -- files ------------------------------------------------------------

    def _migrate_files(self, apply_changes: bool, skip_existing: bool) -> dict[str, str]:
        """Copy each MediaFile into the new storage; return old URL -> new URL."""
        url_map: dict[str, str] = {}
        copied = skipped = failed = 0

        for media in MediaFile.objects.iterator(chunk_size=100):
            if not media.file:
                continue
            name = media.file.name
            try:
                old_url = media.file.url
            except Exception:  # storage cannot resolve it; nothing to rewrite
                old_url = ""

            if skip_existing and default_storage.exists(name):
                skipped += 1
                continue

            if not apply_changes:
                url_map[old_url] = f"<new url for {name}>"
                copied += 1
                continue

            try:
                with media.file.open("rb") as handle:
                    payload = handle.read()
                saved_name = default_storage.save(name, ContentFile(payload))
                media.file.name = saved_name
                media.save(update_fields=["file"])
                if old_url:
                    url_map[old_url] = media.file.url
                copied += 1
            except Exception as exc:
                failed += 1
                self.stderr.write(self.style.ERROR(f"  failed {name}: {exc}"))

        self.stdout.write(
            f"Files: {copied} copied, {skipped} skipped, {failed} failed."
        )
        return url_map

    # -- article content --------------------------------------------------

    def _rewrite_articles(
        self, url_map: dict[str, str], apply_changes: bool, batch_size: int
    ) -> None:
        """Replace old media URLs everywhere inside Article.content."""
        if not url_map:
            self.stdout.write("No URL replacements to apply to article content.")
            return

        changed = 0
        batch: list[Article] = []

        for article in Article.objects.only("id", "content").iterator(chunk_size=batch_size):
            # Serialise, substitute, re-parse. This reaches every nested field --
            # image blocks, annotation media, hotspots, chapters -- without
            # needing to enumerate the block schema, which keeps working as new
            # block types are added.
            raw = json.dumps(article.content or {}, ensure_ascii=False)
            replaced = raw
            for old_url, new_url in url_map.items():
                if old_url and old_url in replaced:
                    replaced = replaced.replace(old_url, new_url)

            if replaced == raw:
                continue

            changed += 1
            if not apply_changes:
                continue

            article.content = json.loads(replaced)
            batch.append(article)
            if len(batch) >= batch_size:
                self._flush(batch)
                batch = []

        if apply_changes and batch:
            self._flush(batch)

        verb = "would be" if not apply_changes else "were"
        self.stdout.write(f"Articles: {changed} {verb} rewritten.")

    def _flush(self, batch: list[Article]) -> None:
        with transaction.atomic():
            # bulk_update bypasses save(), so plain_text/word_count/content_hash
            # are not recomputed -- correct here, since only URLs changed and the
            # prose is identical. content_hash is refreshed below to stay honest.
            for article in batch:
                article.content_hash = Article(
                    content=article.content
                )._compute_content_hash()
            Article.objects.bulk_update(batch, ["content", "content_hash"])
