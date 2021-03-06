"""Test cases for Zinnia's Entry"""
from __future__ import with_statement
import warnings
from datetime import datetime
from datetime import timedelta

from django.test import TestCase
from django.conf import settings
from django.contrib import comments
from django.contrib.auth.models import User
from django.contrib.sites.models import Site
from django.core.urlresolvers import reverse
from django.contrib.comments.models import CommentFlag

from zinnia import models
from zinnia.models import Entry
from zinnia.managers import PUBLISHED
from zinnia.managers import PINGBACK, TRACKBACK
from zinnia.models import get_base_model
from zinnia.models import EntryAbstractClass
from zinnia import models as models_settings
from zinnia import url_shortener as shortener_settings


class EntryTestCase(TestCase):

    def setUp(self):
        params = {'title': 'My entry',
                  'content': 'My content',
                  'slug': 'my-entry'}
        self.entry = Entry.objects.create(**params)

    def test_discussions(self):
        site = Site.objects.get_current()
        self.assertEquals(self.entry.discussions.count(), 0)
        self.assertEquals(self.entry.comments.count(), 0)
        self.assertEquals(self.entry.pingbacks.count(), 0)
        self.assertEquals(self.entry.trackbacks.count(), 0)

        comments.get_model().objects.create(comment='My Comment 1',
                                            content_object=self.entry,
                                            site=site)
        self.assertEquals(self.entry.discussions.count(), 1)
        self.assertEquals(self.entry.comments.count(), 1)
        self.assertEquals(self.entry.pingbacks.count(), 0)
        self.assertEquals(self.entry.trackbacks.count(), 0)

        comments.get_model().objects.create(comment='My Comment 2',
                                            content_object=self.entry,
                                            site=site, is_public=False)
        self.assertEquals(self.entry.discussions.count(), 1)
        self.assertEquals(self.entry.comments.count(), 1)
        self.assertEquals(self.entry.pingbacks.count(), 0)
        self.assertEquals(self.entry.trackbacks.count(), 0)

        author = User.objects.create_user(username='webmaster',
                                          email='webmaster@example.com')

        comment = comments.get_model().objects.create(
            comment='My Comment 3',
            content_object=self.entry,
            site=Site.objects.create(domain='http://toto.com',
                                     name='Toto.com'))
        comment.flags.create(user=author, flag=CommentFlag.MODERATOR_APPROVAL)
        self.assertEquals(self.entry.discussions.count(), 2)
        self.assertEquals(self.entry.comments.count(), 2)
        self.assertEquals(self.entry.pingbacks.count(), 0)
        self.assertEquals(self.entry.trackbacks.count(), 0)

        comment = comments.get_model().objects.create(
            comment='My Pingback 1', content_object=self.entry, site=site)
        comment.flags.create(user=author, flag=PINGBACK)
        self.assertEquals(self.entry.discussions.count(), 3)
        self.assertEquals(self.entry.comments.count(), 2)
        self.assertEquals(self.entry.pingbacks.count(), 1)
        self.assertEquals(self.entry.trackbacks.count(), 0)

        comment = comments.get_model().objects.create(
            comment='My Trackback 1', content_object=self.entry, site=site)
        comment.flags.create(user=author, flag=TRACKBACK)
        self.assertEquals(self.entry.discussions.count(), 4)
        self.assertEquals(self.entry.comments.count(), 2)
        self.assertEquals(self.entry.pingbacks.count(), 1)
        self.assertEquals(self.entry.trackbacks.count(), 1)

    def test_str(self):
        self.assertEquals(str(self.entry), 'My entry: draft')

    def test_word_count(self):
        self.assertEquals(self.entry.word_count, 2)

    def test_comments_are_open(self):
        original_auto_close = models.AUTO_CLOSE_COMMENTS_AFTER
        models.AUTO_CLOSE_COMMENTS_AFTER = None
        self.assertEquals(self.entry.comments_are_open, True)
        models.AUTO_CLOSE_COMMENTS_AFTER = 5
        self.entry.start_publication = datetime.now() - timedelta(days=7)
        self.entry.save()
        self.assertEquals(self.entry.comments_are_open, False)

        models.AUTO_CLOSE_COMMENTS_AFTER = original_auto_close

    def test_is_actual(self):
        self.assertTrue(self.entry.is_actual)
        self.entry.start_publication = datetime(2020, 3, 15)
        self.assertFalse(self.entry.is_actual)
        self.entry.start_publication = datetime.now()
        self.assertTrue(self.entry.is_actual)
        self.entry.end_publication = datetime(2000, 3, 15)
        self.assertFalse(self.entry.is_actual)

    def test_is_visible(self):
        self.assertFalse(self.entry.is_visible)
        self.entry.status = PUBLISHED
        self.assertTrue(self.entry.is_visible)
        self.entry.start_publication = datetime(2020, 3, 15)
        self.assertFalse(self.entry.is_visible)

    def test_short_url(self):
        original_shortener = shortener_settings.URL_SHORTENER_BACKEND
        shortener_settings.URL_SHORTENER_BACKEND = 'zinnia.url_shortener.'\
                                                   'backends.default'
        self.assertEquals(self.entry.short_url,
                          'http://example.com' +
                          reverse('zinnia_entry_shortlink',
                                  args=[self.entry.pk]))
        shortener_settings.URL_SHORTENER_BACKEND = original_shortener

    def test_previous_entry(self):
        site = Site.objects.get_current()
        self.assertFalse(self.entry.previous_entry)
        params = {'title': 'My second entry',
                  'content': 'My second content',
                  'slug': 'my-second-entry',
                  'creation_date': datetime(2000, 1, 1),
                  'status': PUBLISHED}
        self.second_entry = Entry.objects.create(**params)
        self.second_entry.sites.add(site)
        self.assertEquals(self.entry.previous_entry, self.second_entry)
        params = {'title': 'My third entry',
                  'content': 'My third content',
                  'slug': 'my-third-entry',
                  'creation_date': datetime(2001, 1, 1),
                  'status': PUBLISHED}
        self.third_entry = Entry.objects.create(**params)
        self.third_entry.sites.add(site)
        self.assertEquals(self.entry.previous_entry, self.third_entry)
        self.assertEquals(self.third_entry.previous_entry, self.second_entry)

    def test_next_entry(self):
        site = Site.objects.get_current()
        self.assertFalse(self.entry.next_entry)
        params = {'title': 'My second entry',
                  'content': 'My second content',
                  'slug': 'my-second-entry',
                  'creation_date': datetime(2100, 1, 1),
                  'status': PUBLISHED}
        self.second_entry = Entry.objects.create(**params)
        self.second_entry.sites.add(site)
        self.assertEquals(self.entry.next_entry, self.second_entry)
        params = {'title': 'My third entry',
                  'content': 'My third content',
                  'slug': 'my-third-entry',
                  'creation_date': datetime(2050, 1, 1),
                  'status': PUBLISHED}
        self.third_entry = Entry.objects.create(**params)
        self.third_entry.sites.add(site)
        self.assertEquals(self.entry.next_entry, self.third_entry)
        self.assertEquals(self.third_entry.next_entry, self.second_entry)

    def test_related_published(self):
        site = Site.objects.get_current()
        self.assertFalse(self.entry.related_published)
        params = {'title': 'My second entry',
                  'content': 'My second content',
                  'slug': 'my-second-entry',
                  'status': PUBLISHED}
        self.second_entry = Entry.objects.create(**params)
        self.second_entry.related.add(self.entry)
        self.assertEquals(len(self.entry.related_published), 0)

        self.second_entry.sites.add(site)
        self.assertEquals(len(self.entry.related_published), 1)
        self.assertEquals(len(self.second_entry.related_published), 0)

        self.entry.status = PUBLISHED
        self.entry.save()
        self.entry.sites.add(site)
        self.assertEquals(len(self.entry.related_published), 1)
        self.assertEquals(len(self.second_entry.related_published), 1)


class EntryHtmlContentTestCase(TestCase):

    def setUp(self):
        params = {'title': 'My entry',
                  'content': 'My content',
                  'slug': 'my-entry'}
        self.entry = Entry(**params)
        self.original_debug = settings.DEBUG
        self.original_rendering = models_settings.MARKUP_LANGUAGE
        settings.DEBUG = False

    def tearDown(self):
        settings.DEBUG = self.original_debug
        models_settings.MARKUP_LANGUAGE = self.original_rendering

    def test_html_content_default(self):
        models_settings.MARKUP_LANGUAGE = None
        self.assertEquals(self.entry.html_content, '<p>My content</p>')

        self.entry.content = 'Hello world !\n' \
                             ' this is my content'
        self.assertEquals(self.entry.html_content,
                          '<p>Hello world !<br /> this is my content</p>')

    def test_html_content_textitle(self):
        models_settings.MARKUP_LANGUAGE = 'textile'
        self.entry.content = 'Hello world !\n\n' \
                             'this is my content :\n\n' \
                             '* Item 1\n* Item 2'
        html_content = self.entry.html_content
        try:
            self.assertEquals(html_content,
                              '\t<p>Hello world !</p>\n\n\t' \
                              '<p>this is my content :</p>\n\n\t' \
                              '<ul>\n\t\t<li>Item 1</li>\n\t\t' \
                              '<li>Item 2</li>\n\t</ul>')
        except AssertionError:
            self.assertEquals(html_content, self.entry.content)

    def test_html_content_markdown(self):
        models_settings.MARKUP_LANGUAGE = 'markdown'
        self.entry.content = 'Hello world !\n\n' \
                             'this is my content :\n\n' \
                             '* Item 1\n* Item 2'
        html_content = self.entry.html_content
        try:
            self.assertEquals(html_content,
                              '<p>Hello world !</p>\n' \
                              '<p>this is my content :</p>'\
                              '\n<ul>\n<li>Item 1</li>\n' \
                              '<li>Item 2</li>\n</ul>')
        except AssertionError:
            self.assertEquals(html_content, self.entry.content)

    def test_html_content_restructuredtext(self):
        models_settings.MARKUP_LANGUAGE = 'restructuredtext'
        self.entry.content = 'Hello world !\n\n' \
                             'this is my content :\n\n' \
                             '* Item 1\n* Item 2'
        html_content = self.entry.html_content
        try:
            self.assertEquals(html_content,
                              '<p>Hello world !</p>\n' \
                              '<p>this is my content :</p>'\
                              '\n<ul class="simple">\n<li>Item 1</li>\n' \
                              '<li>Item 2</li>\n</ul>\n')
        except AssertionError:
            self.assertEquals(html_content, self.entry.content)


class EntryGetBaseModelTestCase(TestCase):

    def setUp(self):
        self.original_entry_base_model = models_settings.ENTRY_BASE_MODEL

    def tearDown(self):
        models_settings.ENTRY_BASE_MODEL = self.original_entry_base_model

    def test_get_base_model(self):
        models_settings.ENTRY_BASE_MODEL = ''
        self.assertEquals(get_base_model(), EntryAbstractClass)

        models_settings.ENTRY_BASE_MODEL = 'mymodule.myclass'
        try:
            with warnings.catch_warnings(record=True) as w:
                self.assertEquals(get_base_model(), EntryAbstractClass)
                self.assertTrue(issubclass(w[-1].category, RuntimeWarning))
        except AttributeError:
            # Fail under Python2.5, because of'warnings.catch_warnings'
            pass

        models_settings.ENTRY_BASE_MODEL = 'zinnia.models.EntryAbstractClass'
        self.assertEquals(get_base_model(), EntryAbstractClass)
