"""Tests for the gafaelfawr.session package."""

from __future__ import annotations

import pytest

from gafaelfawr.exceptions import InvalidTokenError
from gafaelfawr.models.token import Token


def test_token() -> None:
    token = Token()
    assert str(token).startswith("gt-")


def test_token_from_str() -> None:
    bad_tokens = [
        "",
        ".",
        "MLF5MB3Peg79wEC0BY8U8Q",
        "MLF5MB3Peg79wEC0BY8U8Q.",
        "gt-",
        "gt-.",
        "gt-MLF5MB3Peg79wEC0BY8U8Q",
        "gt-MLF5MB3Peg79wEC0BY8U8Q.",
        "gt-.ChbkqEyp3EIJ2e_1Sqff3w",
        "gt-NOT.VALID",
        "gt-MLF5MB3Peg79wEC0BY8U8Q.ChbkqEyp3EIJ2e_1Sqff3w.!!!!",
        "gtMLF5MB3Peg79wEC0BY8U8Q.ChbkqEyp3EIJ2e_1Sqff3w",
    ]
    for token_str in bad_tokens:
        with pytest.raises(InvalidTokenError):
            Token.from_str(token_str)

    token_str = "gt-MLF5MB3Peg79wEC0BY8U8Q.ChbkqEyp3EIJ2e_1Sqff3w"
    token = Token.from_str(token_str)
    assert token.key == "MLF5MB3Peg79wEC0BY8U8Q"
    assert token.secret == "ChbkqEyp3EIJ2e_1Sqff3w"
    assert str(token) == token_str
