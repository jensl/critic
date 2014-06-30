with_class = testing.expect.with_class
extract_text = testing.expect.extract_text

frontend.page(
    "news",
    expect={ "document_title": testing.expect.document_title(u"News"),
             "content_title": testing.expect.paleyellow_title(0, u"News"),
             "pageheader_links": testing.expect.pageheader_links("anonymous"),
             "script_user": testing.expect.script_no_user() })

# Load all news items to make sure they are syntactically correct.
#
# There may not be any, and we can't easily test that the right set of news
# items are listed, since this depends on whether we upgraded and from what.
# But this testing is still somewhat meaningful.

document = frontend.page("news", params={ "display": "all" })
items = document.findAll(attrs=with_class("item"))

for item in items:
    item_id = item["critic-item-id"]
    item_title = extract_text(item.find(attrs=with_class("title")))

    frontend.page(
        "news",
        params={ "item": item_id },
        expect={ "document_title": testing.expect.document_title(item_title),
                 "content_title": testing.expect.paleyellow_title(0, item_title),
                 "pageheader_links": testing.expect.pageheader_links("anonymous"),
                 "script_user": testing.expect.script_no_user() })
