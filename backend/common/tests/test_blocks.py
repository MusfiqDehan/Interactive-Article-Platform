"""Tests for common.blocks -- the shared Editor.js text/annotation extractor."""

import json

from common.blocks import (
    blocks_to_plaintext,
    count_words,
    extract_annotations,
    html_to_text,
)


def doc(*blocks):
    return {"blocks": list(blocks)}


def block(btype, data, block_id="b1"):
    return {"id": block_id, "type": btype, "data": data}


class TestHtmlToText:
    def test_tags_become_word_boundaries(self):
        # The bug this guards: naive tag-stripping fuses adjacent blocks into
        # one token ("TitleBody"), corrupting word counts and keyword density.
        assert html_to_text("<h2>Title</h2><p>Body</p>") == "Title Body"

    def test_list_items_do_not_fuse(self):
        assert html_to_text("<ul><li>one</li><li>two</li></ul>") == "one two"

    def test_entities_are_decoded(self):
        assert html_to_text("Tom &amp; Jerry &quot;quoted&quot;") == 'Tom & Jerry "quoted"'

    def test_whitespace_is_normalised(self):
        assert html_to_text("  a  \n\n  b  ") == "a b"

    def test_non_string_is_empty(self):
        assert html_to_text(None) == ""
        assert html_to_text(42) == ""


class TestIterAndPlaintext:
    def test_paragraph_and_header(self):
        content = doc(
            block("header", {"text": "The Heading", "level": 2}, "h"),
            block("paragraph", {"text": "Some <b>bold</b> prose."}, "p"),
        )
        assert blocks_to_plaintext(content) == "The Heading\nSome bold prose."

    def test_list_both_item_shapes(self):
        assert "alpha" in blocks_to_plaintext(doc(block("list", {"items": ["alpha", "beta"]})))
        assert "gamma" in blocks_to_plaintext(
            doc(block("list", {"items": [{"content": "gamma"}]}))
        )

    def test_table_cells(self):
        content = doc(block("table", {"content": [["r1c1", "r1c2"], ["r2c1"]]}))
        text = blocks_to_plaintext(content)
        assert "r1c1" in text and "r2c1" in text

    def test_warning_title_and_message(self):
        content = doc(block("warning", {"title": "Careful", "message": "Mind the gap"}))
        text = blocks_to_plaintext(content)
        assert "Careful" in text and "Mind the gap" in text

    def test_code_block(self):
        assert "print(1)" in blocks_to_plaintext(doc(block("code", {"code": "print(1)"})))

    def test_urls_are_never_counted_as_prose(self):
        # A URL is an address, not text. Counting it inflates reading time and
        # pollutes the search index.
        content = doc(
            block(
                "interactive_youtube",
                {
                    "source": "https://youtu.be/abc?a=1&t=5",
                    "caption": "Watch this",
                    "chapters": [],
                },
            )
        )
        text = blocks_to_plaintext(content)
        assert "Watch this" in text
        assert "youtu.be" not in text

    def test_image_url_excluded_caption_included(self):
        content = doc(
            block("image", {"file": {"url": "https://cdn/x.png"}, "caption": "A photo"})
        )
        text = blocks_to_plaintext(content)
        assert "A photo" in text
        assert "cdn" not in text

    def test_malformed_blocks_are_skipped(self):
        content = {"blocks": ["not-a-dict", None, {"type": "paragraph"}, 42]}
        assert blocks_to_plaintext(content) == ""

    def test_non_dict_content_is_empty(self):
        assert blocks_to_plaintext(None) == ""
        assert blocks_to_plaintext([]) == ""
        assert blocks_to_plaintext({"blocks": "nope"}) == ""


class TestAnnotationText:
    def test_sibling_annotation_array_is_counted(self):
        content = doc(
            block(
                "interactive_text",
                {
                    "text": '<span data-annotation-id="a1">term</span> in context',
                    "annotations": [
                        {
                            "id": "a1",
                            "type": "text",
                            "modal_title": "Definition",
                            "modal_content": "<p>An explanation here</p>",
                        }
                    ],
                },
            )
        )
        text = blocks_to_plaintext(content)
        assert "An explanation here" in text
        assert "Definition" in text

    def test_annotations_can_be_excluded(self):
        content = doc(
            block(
                "interactive_text",
                {
                    "text": "body",
                    "annotations": [{"id": "a1", "modal_content": "hidden detail"}],
                },
            )
        )
        assert "hidden detail" not in blocks_to_plaintext(
            content, include_annotations=False
        )

    def test_inline_annotation_attribute_is_counted(self):
        payload = json.dumps(
            {"id": "x1", "type": "text", "modal_title": "T", "modal_content": "inline body"}
        ).replace('"', "&quot;")
        content = doc(
            block("paragraph", {"text": f'<span data-annotation-id="x1" data-annotation="{payload}">w</span>'})
        )
        assert "inline body" in blocks_to_plaintext(content)

    def test_word_count_includes_annotations(self):
        # The regression the plan calls out: interactive articles were reported
        # at a fraction of their true length because annotations were ignored.
        content = doc(
            block(
                "interactive_text",
                {
                    "text": "one two three",
                    "annotations": [
                        {"id": "a", "modal_title": "", "modal_content": "four five six seven"}
                    ],
                },
            )
        )
        assert count_words(content, include_annotations=False) == 3
        assert count_words(content) == 7


class TestExtractAnnotations:
    def test_sibling_array_with_label_from_span(self):
        content = doc(
            block(
                "interactive_text",
                {
                    "text": '<span data-annotation-id="a1">photosynthesis</span> matters',
                    "annotations": [
                        {
                            "id": "a1",
                            "type": "text",
                            "modal_title": "Definition",
                            "modal_content": "<p>Plants make food</p>",
                        }
                    ],
                },
                "blk",
            )
        )
        (ann,) = extract_annotations(content)
        assert ann["id"] == "a1"
        assert ann["block_id"] == "blk"
        assert ann["kind"] == "text"
        assert ann["label"] == "photosynthesis"
        assert ann["title"] == "Definition"
        assert ann["plain"] == "Plants make food"
        assert ann["media"] is None

    def test_image_annotation_exposes_media(self):
        content = doc(
            block(
                "interactive_text",
                {
                    "text": "",
                    "annotations": [
                        {
                            "id": "i1",
                            "type": "image",
                            "modal_title": "Diagram",
                            "image_url": "https://cdn/d.png",
                            "image_caption": "A diagram",
                        }
                    ],
                },
            )
        )
        (ann,) = extract_annotations(content)
        assert ann["media"] == {
            "url": "https://cdn/d.png",
            "type": "image",
            "alt": "A diagram",
        }

    def test_hotspots(self):
        content = doc(
            block(
                "interactive_image",
                {
                    "url": "https://cdn/i.png",
                    "hotspots": [
                        {"id": "h1", "modal_title": "Engine", "modal_content": "<p>V8</p>"}
                    ],
                },
            )
        )
        (ann,) = extract_annotations(content)
        assert ann["kind"] == "hotspot"
        assert ann["title"] == "Engine"
        assert ann["plain"] == "V8"

    def test_chapters_keep_their_timestamp(self):
        content = doc(
            block(
                "interactive_audio",
                {
                    "url": "https://cdn/a.mp3",
                    "chapters": [
                        {
                            "id": "c1",
                            "time": 42.5,
                            "label": "Intro",
                            "modal_title": "Opening",
                            "modal_content": "notes",
                        }
                    ],
                },
            )
        )
        (ann,) = extract_annotations(content)
        assert ann["kind"] == "chapter"
        assert ann["time"] == 42.5
        assert ann["label"] == "Intro"

    def test_duplicate_ids_are_collapsed(self):
        # The same annotation can appear both in the sibling array and inline;
        # it must surface once, not twice.
        payload = json.dumps({"id": "a1", "type": "text", "modal_content": "body"}).replace(
            '"', "&quot;"
        )
        content = doc(
            block(
                "interactive_text",
                {
                    "text": f'<span data-annotation-id="a1" data-annotation="{payload}">w</span>',
                    "annotations": [{"id": "a1", "type": "text", "modal_content": "body"}],
                },
            )
        )
        assert len(extract_annotations(content)) == 1

    def test_malformed_annotation_json_does_not_raise(self):
        content = doc(
            block("paragraph", {"text": '<span data-annotation="{not json">w</span>'})
        )
        assert extract_annotations(content) == []

    def test_reading_order_is_preserved(self):
        content = {
            "blocks": [
                block("interactive_text", {"text": "", "annotations": [{"id": "1"}]}, "b1"),
                block("interactive_image", {"hotspots": [{"id": "2"}]}, "b2"),
                block("interactive_audio", {"chapters": [{"id": "3"}]}, "b3"),
            ]
        }
        assert [a["id"] for a in extract_annotations(content)] == ["1", "2", "3"]
