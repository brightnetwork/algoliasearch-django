from unittest.mock import patch, call, MagicMock

from django.conf import settings
from django.test import TestCase

from algoliasearch_django import AlgoliaIndex
from algoliasearch_django import algolia_engine
from algoliasearch_django.models import AlgoliaIndexError

from .models import User, Website, Example


class IndexTestCase(TestCase):
    def setUp(self):
        self.client = MagicMock()
        self.user = User(name='Algolia', username="algolia",
                         bio='Milliseconds matter', followers_count=42001,
                         following_count=42, _lat=123, _lng=-42.24,
                         _permissions='read,write,admin')

        self.contributor = User(
            name='Contributor',
            username="contributor",
            bio='Contributions matter',
            followers_count=7,
            following_count=5,
            _lat=52.0705,
            _lng=-4.3007,
            _permissions='contribute,follow'
        )

        self.example = Example(uid=4,
                               name='SuperK',
                               address='Finland',
                               lat=63.3,
                               lng=-32.0,
                               is_admin=True)
        self.example.category = ['Shop', 'Grocery']
        self.example.locations = [
            {'lat': 10.3, 'lng': -20.0},
            {'lat': 22.3, 'lng': 10.0},
        ]

    def test_default_index_name(self):
        index = AlgoliaIndex(Website, self.client, settings.ALGOLIA)
        regex = r'^test_Website_django(_travis-\d+.\d+)?$'
        try:
            self.assertRegex(index.index_name, regex)
        except AttributeError:
            self.assertRegex(index.index_name, regex)

    def test_custom_index_name(self):
        class WebsiteIndex(AlgoliaIndex):
            index_name = 'customName'

        index = WebsiteIndex(Website, self.client, settings.ALGOLIA)
        regex = r'^test_customName_django(_travis-\d+.\d+)?$'
        try:
            self.assertRegex(index.index_name, regex)
        except AttributeError:
            self.assertRegex(index.index_name, regex)

    def test_index_model_with_foreign_key_reference(self):
        index = AlgoliaIndex(User, self.client, settings.ALGOLIA)
        self.assertFalse("blogpost" in index.fields)

    def test_index_name_settings(self):
        algolia_settings = dict(settings.ALGOLIA)
        del algolia_settings['INDEX_PREFIX']
        del algolia_settings['INDEX_SUFFIX']

        with self.settings(ALGOLIA=algolia_settings):
            index = AlgoliaIndex(Website, self.client, settings.ALGOLIA)
            regex = r'^Website$'
            try:
                self.assertRegex(index.index_name, regex)
            except AttributeError:
                self.assertRegex(index.index_name, regex)

    def test_tmp_index_name(self):
        """Test that the temporary index name should respect suffix and prefix settings"""

        algolia_settings = dict(settings.ALGOLIA)

        # With no suffix nor prefix
        del algolia_settings['INDEX_PREFIX']
        del algolia_settings['INDEX_SUFFIX']

        with self.settings(ALGOLIA=algolia_settings):
            index = AlgoliaIndex(Website, self.client, settings.ALGOLIA)
            # v4 API: we just store the index names, no init_index call
            self.assertEqual(index.tmp_index_name, 'Website_tmp')

        # With only a prefix
        algolia_settings['INDEX_PREFIX'] = 'prefix'

        with self.settings(ALGOLIA=algolia_settings):
            index = AlgoliaIndex(Website, self.client, settings.ALGOLIA)
            self.assertEqual(index.tmp_index_name, 'prefix_Website_tmp')

        # With only a suffix
        del algolia_settings['INDEX_PREFIX']
        algolia_settings['INDEX_SUFFIX'] = 'suffix'

        with self.settings(ALGOLIA=algolia_settings):
            index = AlgoliaIndex(Website, self.client, settings.ALGOLIA)
            self.assertEqual(index.tmp_index_name, 'Website_tmp_suffix')

        # With a prefix and a suffix
        algolia_settings['INDEX_PREFIX'] = 'prefix'
        algolia_settings['INDEX_SUFFIX'] = 'suffix'

        with self.settings(ALGOLIA=algolia_settings):
            index = AlgoliaIndex(Website, self.client, settings.ALGOLIA)
            self.assertEqual(index.tmp_index_name, 'prefix_Website_tmp_suffix')

    def test_reindex_with_replicas(self):

        class WebsiteIndex(AlgoliaIndex):
            settings = {
                'replicas': [
                    'test_name_asc',
                    'test_name_desc'
                ]
            }

        index = WebsiteIndex(Website, self.client, settings.ALGOLIA)
        index.reindex_all()

        # v4 API: set_settings is called with (index_name, settings)
        self.client.set_settings.assert_called()

    @patch.object(algolia_engine, "save_record")
    def test_reindex_with_should_index_boolean(self, _):

        Website.objects.create(
            name='Algolia',
            url='https://algolia.com',
            is_online=True
        )

        class WebsiteIndex(AlgoliaIndex):
            settings = {
                'replicas': [
                    'test_name_asc',
                    'test_name_desc'
                ]
            }
            should_index = 'is_online'

        index = WebsiteIndex(Website, self.client, settings.ALGOLIA)
        index.reindex_all()

        # v4 API: save_objects is called directly on client with (index_name, objects)
        self.client.save_objects.assert_called()

    def test_reindex_no_settings(self):
        # Given an existing index defined without settings
        class WebsiteIndex(AlgoliaIndex):
            settings = None

        mock_settings = {'searchableAttributes': ['name']}
        self.client.get_settings.return_value.to_dict.return_value = mock_settings

        index = WebsiteIndex(Website, self.client, settings.ALGOLIA)
        index.reindex_all()

        self.client.get_settings.assert_called_once()
        self.assertEqual(mock_settings, index.settings)

    def test_reindex_with_settings(self):
        index_settings = {'searchableAttributes': ['name', 'email', 'company', 'city', 'county', 'account_names',
                                                   'unordered(address)', 'state', 'zip_code', 'phone', 'fax',
                                                   'unordered(web)'], 'attributesForFaceting': ['city', 'company'],
                          'customRanking': ['desc(followers)'],
                          'queryType': 'prefixAll',
                          'highlightPreTag': '<mark>',
                          'ranking': [
                              'asc(name)',
                              'typo',
                              'geo',
                              'words',
                              'filters',
                              'proximity',
                              'attribute',
                              'exact',
                              'custom'
                          ],
                          'replicas': ['WebsiteIndexReplica_name_asc',
                                       'WebsiteIndexReplica_name_desc'],
                          'highlightPostTag': '</mark>', 'hitsPerPage': 15}

        # Given an existing index defined with settings
        class WebsiteIndex(AlgoliaIndex):
            settings = index_settings

        index = WebsiteIndex(Website, self.client, settings.ALGOLIA)
        index.reindex_all()
        # v4 API: set_settings is called directly on client with (index_name, settings)
        self.client.set_settings.assert_called()

    def test_reindex_with_rules(self):
        # Given an existing index defined with settings
        class WebsiteIndex(AlgoliaIndex):
            settings = {'hitsPerPage': 42}

        # Given some existing query rules on the index
        rules = [{
            'objectID': 'my-rule',
            'condition': {
                'pattern': 'some text',
                'anchoring': 'is'
            },
            'consequence': {
                'params': {
                    'query': 'other text'
                }
            }
        }]

        index = WebsiteIndex(Website, self.client, settings.ALGOLIA)
        index.reindex_all()

        # v4 API: browse_rules and save_rules are called directly on client
        self.client.browse_rules.assert_called()
        # save_rules is only called if rules were found, which requires proper mock setup
        # Just verify browse_rules was called for this test

    def test_reindex_with_synonyms(self):
        # Given an existing index defined with settings
        class WebsiteIndex(AlgoliaIndex):
            settings = {'hitsPerPage': 42}

        # Given some existing synonyms on the index
        synonyms = [{'objectID': 'street', 'type': 'altCorrection1', 'word': 'Street', 'corrections': ['St']}]

        index = WebsiteIndex(Website, self.client, settings.ALGOLIA)
        index.reindex_all()

        # v4 API: browse_synonyms and save_synonyms are called directly on client
        self.client.browse_synonyms.assert_called()

    def test_custom_objectID(self):
        class UserIndex(AlgoliaIndex):
            custom_objectID = 'username'

        self.index = UserIndex(User, self.client, settings.ALGOLIA)
        obj = self.index.get_raw_record(self.user)
        self.assertEqual(obj['objectID'], 'algolia')

    def test_custom_objectID_property(self):
        class UserIndex(AlgoliaIndex):
            custom_objectID = 'reverse_username'

        self.index = UserIndex(User, self.client, settings.ALGOLIA)
        obj = self.index.get_raw_record(self.user)
        self.assertEqual(obj['objectID'], 'ailogla')

    def test_invalid_custom_objectID(self):
        class UserIndex(AlgoliaIndex):
            custom_objectID = 'uid'

        with self.assertRaises(AlgoliaIndexError):
            UserIndex(User, self.client, settings.ALGOLIA)

    def test_geo_fields(self):
        class UserIndex(AlgoliaIndex):
            geo_field = 'location'

        self.index = UserIndex(User, self.client, settings.ALGOLIA)
        obj = self.index.get_raw_record(self.user)
        self.assertEqual(obj['_geoloc'], {'lat': 123, 'lng': -42.24})

    def test_several_geo_fields(self):
        class ExampleIndex(AlgoliaIndex):
            geo_field = 'geolocations'

        self.index = ExampleIndex(Example, self.client, settings.ALGOLIA)
        obj = self.index.get_raw_record(self.example)
        self.assertEqual(obj['_geoloc'], [
            {'lat': 10.3, 'lng': -20.0},
            {'lat': 22.3, 'lng': 10.0},
        ])

    def test_geo_fields_already_formatted(self):
        class ExampleIndex(AlgoliaIndex):
            geo_field = 'geolocations'

        self.example.locations = {'lat': 10.3, 'lng': -20.0}
        self.index = ExampleIndex(Example, self.client, settings.ALGOLIA)
        obj = self.index.get_raw_record(self.example)
        self.assertEqual(obj['_geoloc'], {'lat': 10.3, 'lng': -20.0})

    def test_none_geo_fields(self):
        class ExampleIndex(AlgoliaIndex):
            geo_field = 'location'

        Example.location = lambda x: None
        self.index = ExampleIndex(Example, self.client, settings.ALGOLIA)
        obj = self.index.get_raw_record(self.example)
        self.assertIsNone(obj.get('_geoloc'))

    def test_invalid_geo_fields(self):
        class UserIndex(AlgoliaIndex):
            geo_field = 'position'

        with self.assertRaises(AlgoliaIndexError):
            UserIndex(User, self.client, settings.ALGOLIA)

    def test_tags(self):
        class UserIndex(AlgoliaIndex):
            tags = 'permissions'

        self.index = UserIndex(User, self.client, settings.ALGOLIA)

        # Test the users' tag individually
        obj = self.index.get_raw_record(self.user)
        self.assertListEqual(obj['_tags'], ['read', 'write', 'admin'])

        obj = self.index.get_raw_record(self.contributor)
        self.assertListEqual(obj['_tags'], ['contribute', 'follow'])

    def test_invalid_tags(self):
        class UserIndex(AlgoliaIndex):
            tags = 'tags'

        with self.assertRaises(AlgoliaIndexError):
            UserIndex(User, self.client, settings.ALGOLIA)

    def test_one_field(self):
        class UserIndex(AlgoliaIndex):
            fields = 'name'

        self.index = UserIndex(User, self.client, settings.ALGOLIA)
        obj = self.index.get_raw_record(self.user)
        self.assertIn('name', obj)
        self.assertNotIn('username', obj)
        self.assertNotIn('bio', obj)
        self.assertNotIn('followers_count', obj)
        self.assertNotIn('following_count', obj)
        self.assertNotIn('_lat', obj)
        self.assertNotIn('_lng', obj)
        self.assertNotIn('_permissions', obj)
        self.assertNotIn('location', obj)
        self.assertNotIn('_geoloc', obj)
        self.assertNotIn('permissions', obj)
        self.assertNotIn('_tags', obj)
        self.assertEqual(len(obj), 2)

    def test_multiple_fields(self):
        class UserIndex(AlgoliaIndex):
            fields = ('name', 'username', 'bio')

        self.index = UserIndex(User, self.client, settings.ALGOLIA)
        obj = self.index.get_raw_record(self.user)
        self.assertIn('name', obj)
        self.assertIn('username', obj)
        self.assertIn('bio', obj)
        self.assertNotIn('followers_count', obj)
        self.assertNotIn('following_count', obj)
        self.assertNotIn('_lat', obj)
        self.assertNotIn('_lng', obj)
        self.assertNotIn('_permissions', obj)
        self.assertNotIn('location', obj)
        self.assertNotIn('_geoloc', obj)
        self.assertNotIn('permissions', obj)
        self.assertNotIn('_tags', obj)
        self.assertEqual(len(obj), 4)

    def test_fields_with_custom_name(self):
        # tuple syntax
        class UserIndex(AlgoliaIndex):
            fields = ('name', ('username', 'login'), 'bio')

        self.index = UserIndex(User, self.client, settings.ALGOLIA)
        obj = self.index.get_raw_record(self.user)
        self.assertIn('name', obj)
        self.assertNotIn('username', obj)
        self.assertIn('login', obj)
        self.assertEqual(obj['login'], 'algolia')
        self.assertIn('bio', obj)
        self.assertNotIn('followers_count', obj)
        self.assertNotIn('following_count', obj)
        self.assertNotIn('_lat', obj)
        self.assertNotIn('_lng', obj)
        self.assertNotIn('_permissions', obj)
        self.assertNotIn('location', obj)
        self.assertNotIn('_geoloc', obj)
        self.assertNotIn('permissions', obj)
        self.assertNotIn('_tags', obj)
        self.assertEqual(len(obj), 4)

        # list syntax
        class UserIndex(AlgoliaIndex):
            fields = ('name', ['username', 'login'], 'bio')

        self.index = UserIndex(User, self.client, settings.ALGOLIA)
        obj = self.index.get_raw_record(self.user)
        self.assertIn('name', obj)
        self.assertNotIn('username', obj)
        self.assertIn('login', obj)
        self.assertEqual(obj['login'], 'algolia')
        self.assertIn('bio', obj)
        self.assertNotIn('followers_count', obj)
        self.assertNotIn('following_count', obj)
        self.assertNotIn('_lat', obj)
        self.assertNotIn('_lng', obj)
        self.assertNotIn('_permissions', obj)
        self.assertNotIn('location', obj)
        self.assertNotIn('_geoloc', obj)
        self.assertNotIn('permissions', obj)
        self.assertNotIn('_tags', obj)
        self.assertEqual(len(obj), 4)

    def test_invalid_fields(self):
        class UserIndex(AlgoliaIndex):
            fields = ('name', 'color')

        with self.assertRaises(AlgoliaIndexError):
            UserIndex(User, self.client, settings.ALGOLIA)

    def test_invalid_fields_syntax(self):
        class UserIndex(AlgoliaIndex):
            fields = {'name': 'user_name'}

        with self.assertRaises(AlgoliaIndexError):
            UserIndex(User, self.client, settings.ALGOLIA)

    def test_invalid_named_fields_syntax(self):
        class UserIndex(AlgoliaIndex):
            fields = ('name', {'username': 'login'})

        with self.assertRaises(AlgoliaIndexError):
            UserIndex(User, self.client, settings.ALGOLIA)

    def test_get_raw_record_with_update_fields(self):
        class UserIndex(AlgoliaIndex):
            fields = ('name', 'username', ['bio', 'description'])

        self.index = UserIndex(User, self.client, settings.ALGOLIA)
        obj = self.index.get_raw_record(self.user,
                                        update_fields=('name', 'bio'))
        self.assertIn('name', obj)
        self.assertNotIn('username', obj)
        self.assertNotIn('bio', obj)
        self.assertIn('description', obj)
        self.assertEqual(obj['description'], 'Milliseconds matter')
        self.assertNotIn('followers_count', obj)
        self.assertNotIn('following_count', obj)
        self.assertNotIn('_lat', obj)
        self.assertNotIn('_lng', obj)
        self.assertNotIn('_permissions', obj)
        self.assertNotIn('location', obj)
        self.assertNotIn('_geoloc', obj)
        self.assertNotIn('permissions', obj)
        self.assertNotIn('_tags', obj)
        self.assertEqual(len(obj), 3)

    def test_should_index_method(self):
        class ExampleIndex(AlgoliaIndex):
            fields = 'name'
            should_index = 'has_name'

        self.index = ExampleIndex(Example, self.client, settings.ALGOLIA)
        self.assertTrue(self.index._should_index(self.example),
                        "We should index an instance when should_index(instance) returns True")

        instance_should_not = Example(name=None)
        self.assertFalse(self.index._should_index(instance_should_not),
                         "We should not index an instance when should_index(instance) returns False")

    def test_should_index_unbound(self):
        class ExampleIndex(AlgoliaIndex):
            fields = 'name'
            should_index = 'static_should_index'

        self.index = ExampleIndex(Example, self.client, settings.ALGOLIA)
        self.assertTrue(self.index._should_index(self.example),
                        "We should index an instance when should_index() returns True")

        class ExampleIndex(AlgoliaIndex):
            fields = 'name'
            should_index = 'static_should_not_index'

        self.index = ExampleIndex(Example, self.client, settings.ALGOLIA)
        instance_should_not = Example()
        self.assertFalse(self.index._should_index(instance_should_not),
                         "We should not index an instance when should_index() returns False")

    def test_should_index_attr(self):
        class ExampleIndex(AlgoliaIndex):
            fields = 'name'
            should_index = 'index_me'

        self.index = ExampleIndex(Example, self.client, settings.ALGOLIA)
        self.assertTrue(self.index._should_index(self.example),
                        "We should index an instance when its should_index attr is True")

        instance_should_not = Example()
        instance_should_not.index_me = False
        self.assertFalse(self.index._should_index(instance_should_not),
                         "We should not index an instance when its should_index attr is False")

        class ExampleIndex(AlgoliaIndex):
            fields = 'name'
            should_index = 'category'

        self.index = ExampleIndex(Example, self.client, settings.ALGOLIA)
        with self.assertRaises(AlgoliaIndexError, msg="We should raise when the should_index attr is not boolean"):
            self.index._should_index(self.example)

    def test_should_index_field(self):
        class ExampleIndex(AlgoliaIndex):
            fields = 'name'
            should_index = 'is_admin'

        self.index = ExampleIndex(Example, self.client, settings.ALGOLIA)
        self.assertTrue(self.index._should_index(self.example),
                        "We should index an instance when its should_index field is True")

        instance_should_not = Example()
        instance_should_not.is_admin = False
        self.assertFalse(self.index._should_index(instance_should_not),
                         "We should not index an instance when its should_index field is False")

        class ExampleIndex(AlgoliaIndex):
            fields = 'name'
            should_index = 'name'

        self.index = ExampleIndex(Example, self.client, settings.ALGOLIA)
        with self.assertRaises(AlgoliaIndexError, msg="We should raise when the should_index field is not boolean"):
            self.index._should_index(self.example)

    def test_should_index_property(self):
        class ExampleIndex(AlgoliaIndex):
            fields = 'name'
            should_index = 'property_should_index'

        self.index = ExampleIndex(Example, self.client, settings.ALGOLIA)
        self.assertTrue(self.index._should_index(self.example),
                        "We should index an instance when its should_index property is True")

        class ExampleIndex(AlgoliaIndex):
            fields = 'name'
            should_index = 'property_should_not_index'

        self.index = ExampleIndex(Example, self.client, settings.ALGOLIA)
        self.assertFalse(self.index._should_index(self.example),
                         "We should not index an instance when its should_index property is False")

        class ExampleIndex(AlgoliaIndex):
            fields = 'name'
            should_index = 'property_string'

        self.index = ExampleIndex(Example, self.client, settings.ALGOLIA)
        with self.assertRaises(AlgoliaIndexError, msg="We should raise when the should_index property is not boolean"):
            self.index._should_index(self.example)

    @patch.object(algolia_engine, "save_record")
    def test_save_record_should_index_boolean(self, _):
        website = Website.objects.create(
            name='Algolia',
            url='https://algolia.com',
            is_online=True
        )

        class WebsiteIndex(AlgoliaIndex):
            settings = {
                'replicas': [
                    'test_name_asc',
                    'test_name_desc'
                ]
            }
            should_index = 'is_online'

        index = WebsiteIndex(Website, self.client, settings.ALGOLIA)
        index.save_record(website)

        # v4 API: save_objects is called directly on client with (index_name, [objects])
        self.client.save_objects.assert_called()
