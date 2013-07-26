# coding=utf-8
import time
import json
from collections import OrderedDict
import urlparse
from aggregator import content
from bottle import Bottle

import feedparser
import opml


api = Bottle()

DEBUG = True


class AggregatorException(BaseException):
    pass


def get_feeds(store):
    result = []

    feeds = store.find(Feed)
    for feed in feeds:
        result.append(feed.as_dict())

    return result


def add_feed(store, url, title):
    if not url:
        raise AggregatorException('The url parameter is required')

    url = unicode(url)
    poll_time = time.localtime()
    poll = time.mktime(poll_time)

    if DEBUG:
        print('Adding feed: %s' % url)

    # find existing database feed for the provided url
    feed = store.find(Feed, url=url).one()

    if feed:
        raise AggregatorException('feed %d already exists for this url' % feed.id)

    data = feedparser.parse(url)

    if not data:
        raise AggregatorException('failed to load the feed')

    feed_link = data.feed.get('link')
    feed_favicon = __get_favicon(feed_link or '{0}://{1}'.format(*urlparse.urlparse(url)))

    feed = store.add(Feed(url, title or data.feed.title, feed_link, feed_favicon, data.get('etag'), data.get('modified'), poll))

    for entry_data in data.entries:
        store.add(Entry(feed, poll, *__as_entry_data(entry_data, poll_time)))

    return feed.as_dict()


def __get_favicon(feed_link):
    data = feedparser.parse(feed_link)
    if data:
        for link in data.feed.get('links', []):
            if link.rel == 'shortcut icon':
                return link.href
        for link in data.feed.get('links', []):
            if link.rel == 'icon':
                return link.href
    return '{0}://{1}/favicon.ico'.format(*urlparse.urlparse(feed_link))


def __as_entry_data(data, poll_time):
    return (
        data.get('id') or data.link,
        OrderedDict([
            ('title', data.title),
            ('link', data.get('link')),
            ('summary', __as_content(data.get('summary_detail'))),
            ('content', [__as_content(content_data) for content_data in data.get('content', [])]),
            ('published', data.get('published')),
            ('updated', data.get('updated'))
        ]),
        time.mktime(data.get('updated_parsed') or data.get('published_parsed') or poll_time)
    )


def __as_content(data):
    return OrderedDict([
        ('type', data.type),
        ('language', data.language),
        ('value', data.value),
    ]) if data else None


@api.get('/update/feeds')
def update_feeds():
    connection = content.open_connection()

    poll_time = time.localtime()
    poll = time.mktime(poll_time)

    for feed_id, feed_url, feed_etag, feed_modified in connection.execute('SELECT id, url, etag, modified FROM feed WHERE next_poll <= ?', [poll]):
        if DEBUG:
            print('Updating feed: %s' % feed_url)

        poll_time = time.localtime()
        poll = time.mktime(poll_time)

        data = feedparser.parse(feed_url, etag=feed_etag, modified=feed_modified)

        if not data:
            if DEBUG:
                print('ERROR: Failed to parse feed')

            connection.execute('UPDATE feed SET poll_status = ? WHERE id = ?', [feed_id, -1])

            continue # with next feed

        feed_link = data.feed.get('link')
        status = data.get('status', 0)

        for entry_data in data.entries:
            guid, data, updated = __as_entry_data(entry_data, poll_time)

            update_setters = ['data = ?']
            update_args = [json.dumps(data)]

            if updated != poll:
                update_setters.append('updated = ?')
                update_args.append(updated)

            update_args.append(feed_id)
            update_args.append(guid)
            update_query = ' '.join(['UPDATE entry SET', ', '.join(update_setters), 'WHERE feed_id = ? AND guid = ?'])
            if connection.execute(update_query, update_args).rowcount == 0:
                # entry doesn't exist
                connection.execute('INSERT INTO entry (feed_id, guid, poll, updated, data) VALUES (?, ?, ?, ?, ?)', [
                    feed_id,
                    guid,
                    poll,
                    updated,
                    update_args[0]
                ])

        day_entries = connection.execute('SELECT COUNT(1) FROM entry WHERE feed_id = ? AND updated >= ?', [feed_id, poll - 86400]).fetchone()[0]
        week_entries = connection.execute('SELECT COUNT(1) FROM entry WHERE feed_id = ? AND updated >= ?', [feed_id, poll - 604800]).fetchone()[0]

        poll_rate = 75600 / day_entries if day_entries else 259200 / week_entries if week_entries else 345600

        if poll_rate < 1800:
            # schedule new poll in 15 minutes
            feed_poll_type = u'every 15 minutes'
            feed_next_poll = poll + 900
        elif poll_rate < 3600:
            # schedule new poll in 30 minutes
            feed_poll_type = u'every 30 minutes'
            feed_next_poll = poll + 1800
        elif poll_rate < 10800:
            # schedule new poll in 1 hour
            feed_poll_type = u'every hour'
            feed_next_poll = poll + 3600
        elif poll_rate < 21600:
            # schedule new poll in 3 hours
            feed_poll_type = u'every 3 hours'
            feed_next_poll = poll + 10800
        elif poll_rate < 43200:
            # schedule new poll in 6 hours
            feed_poll_type = u'every 6 hours'
            feed_next_poll = poll + 21600
        elif poll_rate < 86400:
            # schedule new poll in 12 hours
            feed_poll_type = u'every 12 hours'
            feed_next_poll = poll + 43200
        elif poll_rate < 172800:
            # schedule new poll in 1 day
            feed_poll_type = u'every day'
            feed_next_poll = poll + 86400
        elif poll_rate < 259200:
            # schedule new poll in 2 day
            feed_poll_type = u'every 2 days'
            feed_next_poll = poll + 172800
        elif poll_rate < 345600:
            # schedule new poll in 3 day
            feed_poll_type = u'every 3 days'
            feed_next_poll = poll + 259200
        else:
            # schedule new poll in 4 days
            feed_poll_type = u'every 4 days'
            feed_next_poll = poll + 345600

        update_query = 'UPDATE feed SET poll_type = ?, next_poll = ?, link = ?, etag = ?, modified = ?, poll = ?, poll_status = ? WHERE id = ?'
        connection.execute(update_query, [feed_poll_type, feed_next_poll, feed_link, data.get('etag'), data.get('modified'), poll, status, feed_id])


def __as_unicode(data):
    return unicode(data) if data else None


@api.get('/update/favicons')
def update_favicons():
    connection = content.open_connection()
    with content.transaction(connection) as cursor:
        for feed_id, feed_url, feed_link in cursor.execute('SELECT id, url, link FROM feed'):
            if DEBUG:
                print('Updating favicon for: %s' % feed_url)

            favicon = __get_favicon(feed_link or '{0}://{1}'.format(*urlparse.urlparse(feed_url)))

            if DEBUG:
                print('Detected favicon: %s' % favicon)

            connection.execute('UPDATE feed SET favicon = ? WHERE id = ?', [favicon, feed_id])


def delete_feed(store, feed_id):
    store.find(Entry, Entry.feed_id == feed_id).remove()
    store.find(Feed, Feed.id == feed_id).remove()
    store.commit()


def import_opml(store, opml_source):
    result = []

    def import_outline(outline):
        try:
            if outline.type == 'rss':
                result.append(add_feed(store, outline.xmlUrl, outline.title))
                store.commit()
                # TODO: handle commit exceptions
        except AttributeError:
            if len(outline):
                for o in outline:
                    import_outline(o)

    outlines = opml.parse(opml_source)

    import_outline(outlines)

    return result


def get_entries(store, feed_id=None, with_tags=None, without_tags=None, order='<', limit=50, offset=0):
    result = []

    selection = []
    selectionArgs = []

    if feed_id:
        selection.append('f.id = ?')
        selectionArgs.append(feed_id)

    if with_tags:
        selection.append('e.reader_tags & ? = ?')
        selectionArgs.append(__as_signed_long(with_tags))
        selectionArgs.append(__as_signed_long(with_tags))

    if without_tags:
        selection.append('e.reader_tags & ? = 0')
        selectionArgs.append(__as_signed_long(without_tags))

    query = 'SELECT e.id, e.updated, e.data, e.reader_tags | e.server_tags, f.id, f.link, f.favicon FROM entry e LEFT JOIN feed f ON e.feed_id = f.id'

    if selection:
        query = ' WHERE '.join((query, ' AND '.join(selection)))

    query = ' ORDER BY '.join((query, 'e.updated DESC' if order == '>' else 'e.updated'))

    if limit > 0:
        query = ' '.join((query, 'LIMIT %d OFFSET %d' % (limit, offset)))

    print query

    for entry_id, entry_timestamp, entry_data, entry_tags, feed_id, feed_link, feed_favicon in store.execute(query, selectionArgs):
        entry_values = json.loads(unicode(entry_data))
        entry_values['id'] = entry_id
        entry_values['timestamp'] = entry_timestamp
        entry_values['tags'] = entry_tags
        entry_values['feed_link'] = feed_link
        entry_values['feed_favicon'] = feed_favicon

        result.append(entry_values)

    return result


def __as_signed_long(value):
    # convert to signed 64bit signed
    value &= 0xFFFFFFFFFFFFFFFF
    if value > 0x7FFFFFFFFFFFFFFF:
        value -= 0x10000000000000000
    return value


def tag_entry(store, entry_id, tag):
    tag = __as_signed_long(tag)
    store.execute('UPDATE entry SET reader_tags = reader_tags | ? WHERE id = ?', (tag, entry_id))
    store.commit()


def untag_entry(store, entry_id, tag):
    mask = __as_signed_long(~tag)
    store.execute('UPDATE entry SET reader_tags = reader_tags & ? WHERE id = ?', (mask, entry_id))
    store.commit()