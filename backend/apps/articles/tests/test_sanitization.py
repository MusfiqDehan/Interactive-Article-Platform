"""Regression tests for Editor.js block sanitization.

Two of these guard bugs that were confirmed to be corrupting live content:
multi-parameter URLs were HTML-escaped on every save, and rich markup inside
annotation modals was stripped to fused, unseparated text.
"""

import pytest
from rest_framework import serializers as drf_serializers

from apps.articles.serializers import (
    sanitize_block_text,
    sanitize_block_value,
    sanitize_url,
    validate_blocks,
)


def content(*blocks):
    return {"blocks": list(blocks)}


class TestUrlHandling:
    @pytest.mark.parametrize(
        "url",
        [
            "https://youtu.be/abc?a=1&t=5",
            "https://s3.example.com/f.png?X-Amz-Sig=x&Expires=1&Key=v",
            "https://example.com/path?a=1&b=2&c=3",
        ],
    )
    def test_multi_param_urls_survive_unchanged(self, url):
        # Previously nh3.clean turned every "&" into "&amp;", permanently
        # breaking the URL on the first save.
        assert sanitize_url(url) == url

    def test_url_survives_repeated_saves(self):
        url = "https://youtu.be/abc?a=1&t=5"
        for _ in range(3):
            url = sanitize_url(url)
        assert url == "https://youtu.be/abc?a=1&t=5"

    def test_url_keys_bypass_the_html_sanitizer(self):
        data = {"source": "https://youtu.be/abc?a=1&t=5", "caption": "hi"}
        assert sanitize_block_value(data)["source"] == "https://youtu.be/abc?a=1&t=5"

    def test_nested_file_url_is_preserved(self):
        data = {"file": {"url": "https://cdn.example.com/a.png?v=1&w=2"}}
        assert (
            sanitize_block_value(data)["file"]["url"]
            == "https://cdn.example.com/a.png?v=1&w=2"
        )

    def test_relative_urls_allowed(self):
        assert sanitize_url("/media/uploads/a.png") == "/media/uploads/a.png"

    @pytest.mark.parametrize(
        "url",
        [
            "javascript:alert(1)",
            "JavaScript:alert(1)",
            "data:text/html;base64,PHNjcmlwdD4=",
            "vbscript:msgbox(1)",
            "//evil.example.com/x.png",
        ],
    )
    def test_dangerous_schemes_are_dropped(self, url):
        assert sanitize_url(url) == ""

    def test_empty_and_non_string_pass_through(self):
        assert sanitize_url("") == ""
        assert sanitize_url(None) is None


class TestRichVersusInline:
    def test_block_text_stays_inline_only(self):
        out = sanitize_block_text("<h2>Head</h2><b>bold</b>", rich=False)
        assert "<h2>" not in out
        assert "<b>bold</b>" in out

    def test_annotation_body_keeps_rich_markup(self):
        # The bug: "<h2>Title</h2><ul><li>one</li></ul>" collapsed to "Titleone",
        # silently destroying both the structure and the word boundary.
        html = "<h2>Title</h2><ul><li>one</li><li>two</li></ul>"
        data = {"annotations": [{"id": "a", "modal_content": html}]}
        out = sanitize_block_value(data)["annotations"][0]["modal_content"]
        assert "<h2>Title</h2>" in out
        assert "<li>one</li>" in out

    def test_hotspot_body_keeps_rich_markup(self):
        data = {"hotspots": [{"id": "h", "modal_content": "<p>Para</p>"}]}
        assert "<p>Para</p>" in sanitize_block_value(data)["hotspots"][0]["modal_content"]

    def test_chapter_body_keeps_rich_markup(self):
        data = {"chapters": [{"id": "c", "modal_content": "<blockquote>q</blockquote>"}]}
        out = sanitize_block_value(data)["chapters"][0]["modal_content"]
        assert "<blockquote>q</blockquote>" in out

    def test_caption_keeps_rich_markup(self):
        assert "<p>" in sanitize_block_value({"caption": "<p>c</p>"})["caption"]

    def test_image_inside_annotation_survives(self):
        data = {"annotations": [{"modal_content": '<img src="/a.png" alt="x">'}]}
        out = sanitize_block_value(data)["annotations"][0]["modal_content"]
        assert "<img" in out and 'src="/a.png"' in out

    def test_table_cells_are_inline_only(self):
        # data["content"] is a table, not an annotation body, despite the name.
        data = {"content": [["<h2>x</h2>", "plain"]]}
        assert "<h2>" not in sanitize_block_value(data)["content"][0][0]


class TestXssIsStillBlocked:
    @pytest.mark.parametrize(
        "payload",
        [
            "<script>alert(1)</script>",
            "<img src=x onerror=alert(1)>",
            "<svg/onload=alert(1)>",
            '<a href="javascript:alert(1)">x</a>',
            "<iframe src='https://evil.com'></iframe>",
            "<style>body{background:url(javascript:alert(1))}</style>",
            "<object data='x'></object>",
        ],
    )
    def test_inline_context(self, payload):
        out = sanitize_block_text(payload, rich=False)
        assert "<script" not in out.lower()
        assert "onerror" not in out.lower()
        assert "onload" not in out.lower()
        assert "javascript:" not in out.lower()
        assert "<iframe" not in out.lower()

    @pytest.mark.parametrize(
        "payload",
        [
            "<script>alert(1)</script>",
            "<img src=x onerror=alert(1)>",
            "<svg/onload=alert(1)>",
            "<iframe src='https://evil.com'></iframe>",
        ],
    )
    def test_rich_context_is_not_a_loophole(self, payload):
        # The rich allowlist permits <img>, so it must still strip handlers.
        out = sanitize_block_text(payload, rich=True)
        assert "<script" not in out.lower()
        assert "onerror" not in out.lower()
        assert "onload" not in out.lower()
        assert "<iframe" not in out.lower()

    def test_dangerous_url_in_annotation_media_is_dropped(self):
        data = {"annotations": [{"image_url": "javascript:alert(1)"}]}
        assert sanitize_block_value(data)["annotations"][0]["image_url"] == ""


class TestValidateBlocks:
    def test_unknown_block_type_rejected(self):
        with pytest.raises(drf_serializers.ValidationError):
            validate_blocks(content({"type": "malicious", "data": {}}))

    def test_known_block_type_accepted(self):
        out = validate_blocks(content({"type": "paragraph", "data": {"text": "hi"}}))
        assert out["blocks"][0]["data"]["text"] == "hi"

    def test_block_id_is_backfilled(self):
        out = validate_blocks(content({"type": "paragraph", "data": {"text": "hi"}}))
        assert out["blocks"][0]["id"]

    def test_existing_block_id_is_preserved(self):
        out = validate_blocks(
            content({"id": "keepme", "type": "paragraph", "data": {"text": "hi"}})
        )
        assert out["blocks"][0]["id"] == "keepme"

    def test_block_ids_are_stable_across_a_save_round_trip(self):
        # If ids churn between saves, block-anchored review comments orphan and
        # revision diffs become meaningless.
        first = validate_blocks(
            content(
                {"type": "paragraph", "data": {"text": "a"}},
                {"type": "header", "data": {"text": "b", "level": 2}},
            )
        )
        second = validate_blocks({"blocks": first["blocks"]})
        assert [b["id"] for b in first["blocks"]] == [b["id"] for b in second["blocks"]]

    def test_malformed_blocks_are_dropped(self):
        out = validate_blocks({"blocks": ["nope", None, {"data": {}}, 7]})
        assert out["blocks"] == []

    def test_non_dict_content_rejected(self):
        with pytest.raises(drf_serializers.ValidationError):
            validate_blocks("not a dict")

    def test_annotation_content_survives_full_validation(self):
        # End-to-end: the rich body and the multi-param URL both make it through
        # the real entry point, not just the helper.
        out = validate_blocks(
            content(
                {
                    "type": "interactive_text",
                    "data": {
                        "text": "body",
                        "annotations": [
                            {
                                "id": "a1",
                                "type": "youtube",
                                "modal_content": "<h3>T</h3><p>Body</p>",
                                "youtube_source": "https://youtu.be/x?a=1&t=5",
                            }
                        ],
                    },
                }
            )
        )
        ann = out["blocks"][0]["data"]["annotations"][0]
        assert "<h3>T</h3>" in ann["modal_content"]
        assert ann["youtube_source"] == "https://youtu.be/x?a=1&t=5"
