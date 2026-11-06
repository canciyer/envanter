from envanter.bot import render_report
from envanter.models import Recognition, ScanReport


def test_html_escaping_and_premium_emoji():
    item = Recognition(
        item_id="test",
        name="<b>& bad",
        kind="set",
        rarity="mythic",
        emoji_id="1234567890123456789",
        score=1,
        observed_frames=2,
    )
    report = ScanReport(70, 8, (item,), 1)
    markup = render_report(report, custom_emoji=True)
    assert "&lt;b&gt;&amp; bad" in markup
    assert '<tg-emoji emoji-id="1234567890123456789">' in markup
    assert "Təsdiqlənmiş Mythic" in markup


def test_empty_catalog_warning():
    report = ScanReport(65, 5, (), 0)
    text = render_report(report)
    assert "kataloqu boşdur" in text
    assert "bütün Mythic" in text


def test_empty_catalog_does_not_claim_zero_mythics():
    report = ScanReport(65, 5, (), 0)
    output = render_report(report)
    assert "qiymətləndirilməyib" in output
    assert "Təsdiqlənmiş Mythic" not in output


def test_nonempty_catalog_zero_is_scoped():
    report = ScanReport(65, 5, (), 1)
    output = render_report(report)
    assert "Təsdiqlənmiş Mythic (kataloq üzrə)" in output
    assert "bütün Mythic" in output
