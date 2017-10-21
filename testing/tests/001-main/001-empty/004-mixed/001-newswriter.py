import re

def unread_news_count(document):
    pageheader = document.find("table", attrs={ "class": "pageheader" })
    for link in pageheader.find("ul").findAll("a"):
        m = re.match("News \((\d+)\)", link.string)
        if m:
            return int(m.group(1))
    return 0

NEWSTEXT = "I'm as mad as hell, and I'm not going to take this anymore."

with frontend.signin("alice"):
    dashboard = frontend.page("dashboard", expect={ "document_title": testing.expect.document_title("Dashboard") })
    initial_unread = unread_news_count(dashboard)

with frontend.signin("howard"):
    response = frontend.operation(
        "addnewsitem",
        data={ "text": "I'm as mad as hell" })
    newsitem_id = response["item_id"]

    frontend.operation(
        "editnewsitem",
        data={ "item_id": newsitem_id,
               "text": NEWSTEXT })

with frontend.signin("alice"):
    dashboard = frontend.page("dashboard", expect={ "document_title": testing.expect.document_title("Dashboard") })
    testing.expect.check(initial_unread + 1, unread_news_count(dashboard))

    newsitem = frontend.page("news", params={ "item": newsitem_id })
    newstext = newsitem.find("td", attrs={ "class": "text" })
    testing.expect.check(NEWSTEXT, testing.expect.extract_text(newstext).strip())

    dashboard = frontend.page("dashboard", expect={ "document_title": testing.expect.document_title("Dashboard") })
    testing.expect.check(initial_unread, unread_news_count(dashboard))

    frontend.operation(
        "addnewsitem",
        data={ "text": "Quid quid latine dictum sit, altum viditur." },
        expect={ "status": "failure",
                 "code": "notallowed" })

    frontend.operation(
        "editnewsitem",
        data={ "item_id": newsitem_id,
               "text": "It's all hat, no cattle." },
        expect={ "status": "failure",
                 "code": "notallowed" })

with frontend.signin("bob"):
    # Howard's news item should still be unread by bob.
    dashboard = frontend.page("dashboard", expect={ "document_title": testing.expect.document_title("Dashboard") })
    testing.expect.check(initial_unread + 1, unread_news_count(dashboard))

# Anonymous users should not be able to add or edit news items.
frontend.operation(
    "addnewsitem",
    data={ "text": "If you have a lifetime warranty on something, it is also a hammer." },
    expect={ "status": "failure",
             "code": "mustlogin" })

frontend.operation(
    "editnewsitem",
    data={ "item_id": newsitem_id,
           "text": "The only completely consistent people are dead." },
    expect={ "status": "failure",
             "code": "mustlogin" })
