from __future__ import annotations

import pytest

from notebooklm_auto.input_parser import (
    UrlEntry,
    parse_csv,
    parse_file,
    parse_txt,
    parse_urls,
    validate_youtube_url,
)


@pytest.mark.parametrize(
    "url",
    [
        "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
        "https://youtube.com/watch?v=dQw4w9WgXcQ",
        "http://www.youtube.com/watch?v=abc_DEF-123",
        "https://youtu.be/dQw4w9WgXcQ",
        "https://www.youtube.com/shorts/abc123",
        "https://www.youtube.com/live/abc123?si=xyz",
        "  https://youtu.be/dQw4w9WgXcQ  ",
    ],
)
def test_validate_youtube_url_accepts_valid(url):
    assert validate_youtube_url(url)


@pytest.mark.parametrize(
    "url",
    [
        "",
        "not a url",
        "https://vimeo.com/123456",
        "https://www.youtube.com/",
        "https://www.youtube.com/channel/UC123",
        "ftp://youtu.be/abc",
        "https://evil.com/?u=https://youtu.be/abc",
    ],
)
def test_validate_youtube_url_rejects_invalid(url):
    assert not validate_youtube_url(url)


def test_parse_txt_skips_comments_blanks_and_invalid(tmp_path, capsys):
    path = tmp_path / "urls.txt"
    path.write_text(
        "# コメント\n"
        "\n"
        "https://youtu.be/aaa\n"
        "  https://www.youtube.com/watch?v=bbb  \n"
        "https://example.com/video\n",
        encoding="utf-8",
    )

    entries = parse_txt(path)

    assert entries == [
        UrlEntry(url="https://youtu.be/aaa", title=""),
        UrlEntry(url="https://www.youtube.com/watch?v=bbb", title=""),
    ]
    assert "https://example.com/video" in capsys.readouterr().out


def test_parse_txt_empty_file(tmp_path):
    path = tmp_path / "empty.txt"
    path.write_text("", encoding="utf-8")
    assert parse_txt(path) == []


def test_parse_csv_with_url_and_title_columns(tmp_path):
    path = tmp_path / "list.csv"
    path.write_text(
        "Session Title,YouTube URL\n"
        "Keynote, https://youtu.be/aaa \n"
        ",https://youtu.be/bbb\n"
        "Broken,https://example.com/x\n"
        "Empty,\n",
        encoding="utf-8",
    )

    entries = parse_csv(path)

    assert entries == [
        UrlEntry(url="https://youtu.be/aaa", title="Keynote"),
        UrlEntry(url="https://youtu.be/bbb", title=""),
    ]


@pytest.mark.parametrize("url_col", ["url", "URL", "youtube_url", "Link", " url "])
def test_parse_csv_url_column_aliases(tmp_path, url_col):
    path = tmp_path / "list.csv"
    path.write_text(f"{url_col}\nhttps://youtu.be/aaa\n", encoding="utf-8")
    assert parse_csv(path) == [UrlEntry(url="https://youtu.be/aaa", title="")]


@pytest.mark.parametrize("title_col", ["title", "session_title", "name", "Session Title"])
def test_parse_csv_title_column_aliases(tmp_path, title_col):
    path = tmp_path / "list.csv"
    path.write_text(f"url,{title_col}\nhttps://youtu.be/aaa,My Talk\n", encoding="utf-8")
    assert parse_csv(path) == [UrlEntry(url="https://youtu.be/aaa", title="My Talk")]


def test_parse_csv_without_url_column_raises(tmp_path):
    path = tmp_path / "list.csv"
    path.write_text("foo,bar\n1,2\n", encoding="utf-8")
    with pytest.raises(ValueError, match="URL列が見つかりません"):
        parse_csv(path)


def test_parse_file_dispatches_by_extension(tmp_path):
    csv_path = tmp_path / "list.CSV"
    csv_path.write_text("url,title\nhttps://youtu.be/aaa,T\n", encoding="utf-8")
    txt_path = tmp_path / "list.txt"
    txt_path.write_text("https://youtu.be/bbb\n", encoding="utf-8")

    assert parse_file(csv_path) == [UrlEntry("https://youtu.be/aaa", "T")]
    assert parse_file(str(txt_path)) == [UrlEntry("https://youtu.be/bbb", "")]


def test_parse_file_missing_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        parse_file(tmp_path / "nope.txt")


def test_parse_urls_filters_invalid(capsys):
    entries = parse_urls([" https://youtu.be/aaa ", "bad", "https://www.youtube.com/shorts/ccc"])
    assert entries == [
        UrlEntry("https://youtu.be/aaa", ""),
        UrlEntry("https://www.youtube.com/shorts/ccc", ""),
    ]
    assert "bad" in capsys.readouterr().out


def test_sample_input_file_has_no_urls():
    from pathlib import Path

    sample = Path(__file__).parent.parent / "input" / "urls.txt"
    assert parse_file(sample) == []
