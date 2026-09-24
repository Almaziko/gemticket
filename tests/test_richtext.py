import pytest

from app.richtext import render_richtext


@pytest.mark.parametrize('url', [
    'https://example.com/a/b',
    'https://сделановмоскве.рф/catalog/ukraseniia/sergi-559/product/sergi-lisichka-81215',
    'http://пример.москва/path?x=1',
    'https://xn--80aafgcnbl4cvj9a.xn--p1ai/x',
    'сделановмоскве.рф/catalog',
])
def test_bare_urls_are_linkified(url):
    html = render_richtext(f'<p>Смотри {url} тут</p>')
    assert '<a href="' in html
    assert f'>{url}</a>' in html


def test_cyrillic_domain_link_opens_in_new_tab_safely():
    html = render_richtext('<p>https://сделановмоскве.рф/x</p>')
    assert 'target="_blank"' in html
    assert 'noopener' in html


def test_plain_words_with_dot_are_not_linkified():
    html = render_richtext('<p>Проверьте заявку.Потом напишите</p>')
    assert '<a ' not in html


def test_multiple_paragraphs_survive_cleaning_and_rendering_separately():
    """Регрессия: клиент правит редактор через Enter+Enter (или вставляет
    текст с пустой строкой между абзацами — редактор сам оборачивает это в
    отдельные <p>, см. richtext_editor.js) и ожидает два раздельных абзаца,
    а не один слипшийся кусок текста."""
    html = render_richtext('<p>Абзац один</p><p>Абзац два</p>')
    assert html.count('<p>') == 2
    assert '<p>Абзац один</p>' in html
    assert '<p>Абзац два</p>' in html


def test_line_break_within_paragraph_is_preserved():
    html = render_richtext('<p>Строка А<br>Строка Б</p>')
    assert '<br' in html
    assert 'Строка А' in html and 'Строка Б' in html


def test_two_paragraph_comment_renders_as_two_paragraphs(client_client, db):
    resp = client_client.post('/client/tickets/new', data={
        'title': 'Paragraphs check', 'description': '<p>d</p>', 'tracker_id': '1',
    }, follow_redirects=False)
    ticket_id = resp.headers['Location'].rstrip('/').split('/')[-1]

    client_client.post(f'/tickets/{ticket_id}/comment', data={
        'body': '<p>Комментарий раз</p><p>Комментарий два</p>',
    })
    html = client_client.get(f'/tickets/{ticket_id}').data.decode('utf-8')
    assert '<p>Комментарий раз</p>' in html
    assert '<p>Комментарий два</p>' in html


def test_link_in_ticket_description_is_clickable_on_detail_page(admin_client, client_client, db):
    """Смотрим от имени исполнителя: постановщик в начальном статусе видит
    описание в редакторе (оно редактируемое), а не в режиме чтения."""
    resp = client_client.post('/client/tickets/new', data={
        'title': 'Link check',
        'description': '<p>https://сделановмоскве.рф/catalog/x-81215</p>',
        'tracker_id': '1',
    }, follow_redirects=False)
    ticket_id = resp.headers['Location'].rstrip('/').split('/')[-1]

    html = admin_client.get(f'/tickets/{ticket_id}').data.decode('utf-8')
    assert 'href="https://сделановмоскве.рф/catalog/x-81215"' in html
