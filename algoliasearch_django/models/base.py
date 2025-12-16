import logging
from typing import Callable, Iterable, Optional

from algoliasearch.http.exceptions import AlgoliaException
from algoliasearch.search.models.operation_index_params import OperationIndexParams
from algoliasearch.search.models.operation_type import OperationType
from algoliasearch.search.models.search_params_object import SearchParamsObject

from ..settings import DEBUG


logger = logging.getLogger(__name__)


def sanitize(hit):
    """Remove _highlightResult from hit to prevent issues when saving rules."""
    if "_highlightResult" in hit:
        hit.pop("_highlightResult")
    return hit


class AlgoliaIndexError(Exception):
    """Something went wrong with an Algolia Index."""


class BaseAlgoliaIndex:

    # Use to specify the fields that should be included in the index.
    fields = ()

    # Use to specify the geo-fields that should be used for location search.
    # The attribute should be a callable that returns a tuple.
    geo_field = None

    # Use to specify the field that should be used for filtering by tag.
    tags = None

    # Use to specify the index to target on Algolia.
    index_name: Optional[str] = None

    # Use to specify the settings of the index.
    settings = None

    # Used to specify if the instance should be indexed.
    # The attribute should be either:
    # - a callable that returns a boolean.
    # - a BooleanField
    # - a boolean property or attribute
    should_index = None

    get_queryset: Optional[Callable[[], Iterable]] = None

    def __init__(self, client, settings):
        self.__client = client
        self._named_fields = {}
        self._translate_fields = {}

        if self.settings is None:  # Only set settings if the actual index class does not define some
            self.settings = {}

        if isinstance(self.fields, str):
            self.fields = (self.fields,)
        elif isinstance(self.fields, (list, tuple, set)):
            self.fields = tuple(self.fields)
        else:
            raise AlgoliaIndexError('Fields must be a str, list, tuple or set')

    def _init_index(self, client, settings):
        tmp_index_name = '{index_name}_tmp'.format(index_name=self.index_name)

        if 'INDEX_PREFIX' in settings:
            self.index_name = settings['INDEX_PREFIX'] + '_' + self.index_name
            tmp_index_name = '{index_prefix}_{tmp_index_name}'.format(
                tmp_index_name=tmp_index_name,
                index_prefix=settings['INDEX_PREFIX']
            )
        if 'INDEX_SUFFIX' in settings:
            self.index_name += '_' + settings['INDEX_SUFFIX']
            tmp_index_name = '{tmp_index_name}_{index_suffix}'.format(
                tmp_index_name=tmp_index_name,
                index_suffix=settings['INDEX_SUFFIX']
            )

        self.tmp_index_name = tmp_index_name

    @staticmethod
    def _validate_geolocation(geolocation):
        """
        Make sure we have the proper geolocation format.
        """
        if set(geolocation) != {'lat', 'lng'}:
            raise AlgoliaIndexError(
                'Invalid geolocation format, requires "lat" and "lng" keys only got {}'.format(
                    geolocation
                )
            )

    def get_raw_record(self, instance, update_fields=None):
        """
        Gets the raw record.

        If `update_fields` is set, the raw record will be build with only
        the objectID and the given fields. Also, `_geoloc` and `_tags` will
        not be included.
        """
        tmp = {'objectID': self.objectID(instance)}

        if update_fields:
            if isinstance(update_fields, str):
                update_fields = (update_fields,)

            for elt in update_fields:
                key = self._translate_fields.get(elt, None)
                if key:
                    tmp[key] = self._named_fields[key](instance)
        else:
            for key, value in self._named_fields.items():
                tmp[key] = value(instance)

            if self.geo_field:
                loc = self.geo_field(instance)

                if isinstance(loc, tuple):
                    tmp['_geoloc'] = {'lat': loc[0], 'lng': loc[1]}
                elif isinstance(loc, dict):
                    self._validate_geolocation(loc)
                    tmp['_geoloc'] = loc
                elif isinstance(loc, list):
                    [self._validate_geolocation(geo) for geo in loc]
                    tmp['_geoloc'] = loc

            if self.tags:
                if callable(self.tags):
                    tmp['_tags'] = self.tags(instance)
                if not isinstance(tmp['_tags'], list):
                    tmp['_tags'] = list(tmp['_tags'])

        return tmp

    def _has_should_index(self):
        """Return True if this AlgoliaIndex has a should_index method or attribute"""
        return self.should_index is not None

    def _should_index(self, instance):
        """Return True if the object should be indexed (including when self.should_index is not set)."""
        if self._has_should_index():
            return self._should_really_index(instance)
        else:
            return True

    def _should_really_index(self, instance):
        raise NotImplementedError

    def save_record(self, instance, update_fields=None, **kwargs):
        """Saves the record.

        If `update_fields` is set, this method will use partial_update_object()
        and will update only the given fields (never `_geoloc` and `_tags`).

        For more information about partial_update_object:
        https://github.com/algolia/algoliasearch-client-python#update-an-existing-object-in-the-index
        """
        if not self._should_index(instance):
            # Should not index, but since we don't now the state of the
            # instance, we need to send a DELETE request to ensure that if
            # the instance was previously indexed, it will be removed.
            self.delete_record(instance)
            return

        try:
            if update_fields:
                obj = self.get_raw_record(instance, update_fields=update_fields)
                self.__client.partial_update_objects(
                    self.index_name, [obj], create_if_not_exists=True
                )
            else:
                obj = self.get_raw_record(instance)
                self.__client.save_objects(self.index_name, [obj])
            logger.info('SAVE %s FROM %s', obj['objectID'], instance._meta.label)
        except AlgoliaException as e:
            if DEBUG:
                raise e
            else:
                logger.warning('%s FROM %s NOT SAVED: %s', obj['objectID'],
                               instance._meta.label, e)

    def delete_record(self, instance):
        """Deletes the record."""
        objectID = self.objectID(instance)
        try:
            self.__client.delete_objects(self.index_name, [objectID])
            logger.info('DELETE %s FROM %s', objectID, instance._meta.label)
        except AlgoliaException as e:
            if DEBUG:
                raise e
            else:
                logger.warning('%s FROM %s NOT DELETED: %s', objectID,
                               instance._meta.label, e)

    def update_records(self, qs, batch_size=1000, **kwargs):
        """
        Updates multiple records.

        This method is optimized for speed. It takes a QuerySet and the same
        arguments as QuerySet.update(). Optionnaly, you can specify the size
        of the batch send to Algolia with batch_size (default to 1000).

        >>> from algoliasearch_django import update_records
        >>> qs = MyModel.objects.filter(myField=False)
        >>> update_records(MyModel, qs, myField=True)
        >>> qs.update(myField=True)
        """
        tmp = {}
        for key, value in kwargs.items():
            name = self._translate_fields.get(key, None)
            if name:
                tmp[name] = value

        batch = []
        objectsIDs = qs.only(self.custom_objectID).values_list(
            self.custom_objectID, flat=True)
        for elt in objectsIDs:
            tmp['objectID'] = elt
            batch.append(dict(tmp))

            if len(batch) >= batch_size:
                self.__client.partial_update_objects(self.index_name, batch)
                batch = []

        if len(batch) > 0:
            self.__client.partial_update_objects(self.index_name, batch)

    def raw_search(self, query='', params=None):
        """Performs a search query and returns the parsed JSON."""
        if params is None:
            params = {}

        try:
            search_params = SearchParamsObject(query=query, **params)
            return self.__client.search_single_index(self.index_name, search_params).to_dict()
        except AlgoliaException as e:
            if DEBUG:
                raise e
            else:
                logger.warning('ERROR DURING SEARCH ON %s: %s', self.index_name, e)

    def get_settings(self) -> Optional[dict]:
        """Returns the settings of the index."""
        try:
            logger.info('GET SETTINGS ON %s', self.index_name)
            return self.__client.get_settings(self.index_name).to_dict()
        except AlgoliaException as e:
            if DEBUG:
                raise e
            else:
                logger.warning('ERROR DURING GET_SETTINGS ON %s: %s',
                               self.index_name, e)

    def set_settings(self):
        """Applies the settings to the index."""
        if not self.settings:
            return

        try:
            _resp = self.__client.set_settings(self.index_name, self.settings)
            self.__client.wait_for_task(self.index_name, _resp.task_id)
            logger.info('APPLY SETTINGS ON %s', self.index_name)
        except AlgoliaException as e:
            if DEBUG:
                raise e
            else:
                logger.warning('SETTINGS NOT APPLIED ON %s: %s',
                               self.index_name, e)

    def clear_objects(self):
        """Clears the index."""
        try:
            _resp = self.__client.clear_objects(self.index_name)
            self.__client.wait_for_task(self.index_name, _resp.task_id)
            logger.info('CLEAR INDEX %s', self.index_name)
        except AlgoliaException as e:
            if DEBUG:
                raise e
            else:
                logger.warning('%s NOT CLEARED: %s', self.index_name, e)

    def wait_task(self, task_id):
        try:
            self.__client.wait_for_task(self.index_name, task_id)
            logger.info('WAIT TASK %s', self.index_name)
        except AlgoliaException as e:
            if DEBUG:
                raise e
            else:
                logger.warning('%s NOT WAIT: %s', self.index_name, e)

    def reindex_all(self, batch_size=1000):
        """
        Reindex all the records.

        By default, this method use Model.objects.all() but you can implement
        a method `get_queryset` in your subclass. This can be used to optimize
        the performance (for example with select_related or prefetch_related).
        """
        should_keep_synonyms = False
        should_keep_rules = False
        try:
            if not self.settings:
                self.settings = self.get_settings()
                logger.debug('Got settings for index %s: %s', self.index_name, self.settings)
            else:
                logger.debug("index %s already has settings: %s", self.index_name, self.settings)
        except AlgoliaException as e:
            if any("Index does not exist" in arg for arg in e.args):
                pass  # Expected, let's clear and recreate from scratch
            else:
                raise e  # Unexpected error while getting settings
        try:
            if self.settings:
                replicas = self.settings.get('replicas', None)
                slaves = self.settings.get('slaves', None)

                should_keep_replicas = replicas is not None
                should_keep_slaves = slaves is not None

                if should_keep_replicas:
                    self.settings['replicas'] = []
                    logger.debug("REMOVE REPLICAS FROM SETTINGS")
                if should_keep_slaves:
                    self.settings['slaves'] = []
                    logger.debug("REMOVE SLAVES FROM SETTINGS")

                _resp = self.__client.set_settings(self.tmp_index_name, self.settings.copy())
                self.__client.wait_for_task(self.tmp_index_name, _resp.task_id)
                logger.debug('APPLY SETTINGS ON %s_tmp', self.index_name)

            rules = []
            synonyms = []
            self.__client.browse_rules(
                self.index_name,
                lambda _resp: rules.extend([sanitize(_hit.to_dict()) for _hit in _resp.hits]),
            )
            self.__client.browse_synonyms(
                self.index_name,
                lambda _resp: synonyms.extend([sanitize(_hit.to_dict()) for _hit in _resp.hits]),
            )
            if len(rules):
                logger.debug('Got rules for index %s: %s', self.index_name, rules)
                should_keep_rules = True
            if len(synonyms):
                logger.debug('Got synonyms for index %s: %s', self.index_name, synonyms)
                should_keep_synonyms = True

            _resp = self.__client.clear_objects(self.tmp_index_name)
            self.__client.wait_for_task(self.tmp_index_name, _resp.task_id)
            logger.debug('CLEAR INDEX %s_tmp', self.index_name)

            counts = 0
            batch = []

            for instance in self.get_queryset():
                if not self._should_index(instance):
                    continue  # should not index

                batch.append(self.get_raw_record(instance))
                if len(batch) >= batch_size:
                    self.__client.save_objects(self.tmp_index_name, batch)
                    logger.info('SAVE %d OBJECTS TO %s_tmp', len(batch),
                                self.index_name)
                    batch = []
                counts += 1
            if len(batch) > 0:
                self.__client.save_objects(self.tmp_index_name, batch)
                logger.info('SAVE %d OBJECTS TO %s_tmp', len(batch),
                            self.index_name)

            _resp = self.__client.operation_index(
                self.tmp_index_name,
                OperationIndexParams(
                    operation=OperationType.MOVE, destination=self.index_name
                ),
            )
            self.__client.wait_for_task(self.tmp_index_name, _resp.task_id)
            logger.info('MOVE INDEX %s_tmp TO %s', self.index_name,
                        self.index_name)

            if self.settings:
                if should_keep_replicas:
                    self.settings['replicas'] = replicas
                    logger.debug("RESTORE REPLICAS")
                if should_keep_slaves:
                    self.settings['slaves'] = slaves
                    logger.debug("RESTORE SLAVES")
                if should_keep_replicas or should_keep_slaves:
                    _resp = self.__client.set_settings(self.index_name, self.settings)
                    self.__client.wait_for_task(self.index_name, _resp.task_id)
                if should_keep_rules:
                    _resp = self.__client.save_rules(self.index_name, rules, True)
                    self.__client.wait_for_task(self.index_name, _resp.task_id)
                    logger.info("Saved rules for index %s", self.index_name)
                if should_keep_synonyms:
                    _resp = self.__client.save_synonyms(self.index_name, synonyms, True)
                    self.__client.wait_for_task(self.index_name, _resp.task_id)
                    logger.info("Saved synonyms for index %s", self.index_name)
            return counts
        except AlgoliaException as e:
            if DEBUG:
                raise e
            else:
                logger.warning('ERROR DURING REINDEXING %s: %s', self.index_name,
                               e)
