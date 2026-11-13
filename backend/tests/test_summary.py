"""Tests of the text of the summary form: how the items of a section are
written as paragraphs and read back (app/services/summary.py)."""

import pytest

from app.schemas import InsightItem
from app.services.summary import items_to_text, text_to_items

# Made-up feedback
ITEMS = [
    InsightItem(
        title="Shared session plans",
        explanation="The players should see the plan before training.",
    ),
    InsightItem(title="Offline mode", explanation=""),
]


def test_items_to_text_writes_one_paragraph_per_item():
    items = [
        *ITEMS,
        # A line break inside the AI text must not split the item
        InsightItem(title="Slow\nupload", explanation="Takes long.\n\nOn Wi-Fi too."),
    ]

    assert items_to_text(items) == (
        "Shared session plans\n"
        "The players should see the plan before training.\n"
        "\n"
        "Offline mode\n"
        "\n"
        "Slow upload\n"
        "Takes long. On Wi-Fi too."
    )


def test_text_to_items_ignores_extra_empty_lines_and_spaces():
    # Windows line endings, empty lines at the start and the end, several
    # empty lines (one of them with spaces) between the items, and an
    # explanation in two lines
    text = (
        "\r\n\r\n"
        "  Shared session plans  \r\n"
        "The players should see   the plan\r\n"
        "  before training.\r\n"
        "\r\n"
        "   \r\n"
        "\r\n"
        "Offline mode\r\n"
        "\r\n"
    )

    assert text_to_items(text) == ITEMS


@pytest.mark.parametrize("text", ["", "   ", "\n\n  \n"])
def test_an_empty_field_gives_no_items(text):
    assert text_to_items(text) == []


def test_items_survive_the_way_to_text_and_back():
    assert text_to_items(items_to_text(ITEMS)) == ITEMS
