import re

from django import forms
from django.conf import settings
from django.db import models
from django.db.models.fields import related
from django.forms import fields
from django.forms.widgets import Input
from django.utils import translation as translation_utils
from django.utils.translation.trans_real import to_language
from django.core import exceptions

from tower import ugettext as _


from gelato.translations.models import (Translation, PurifiedTranslation,
                                        LinkifiedTranslation)



def get_string(x):
    locale = translation_utils.get_language()
    try:
        return (Translation.objects.filter(id=x, locale=locale)
                .filter(localized_string__isnull=False)
                .values_list('localized_string', flat=True)[0])
    except IndexError:
        return u''


class TranslationTextInput(forms.widgets.TextInput):
    """A simple textfield replacement for collecting translated names."""

    def _format_value(self, value):
        if isinstance(value, long):
            return get_string(value)
        return value


class TranslationTextarea(forms.widgets.Textarea):

    def render(self, name, value, attrs=None):
        if isinstance(value, long):
            value = get_string(value)
        return super(TranslationTextarea, self).render(name, value, attrs)


class TransMulti(forms.widgets.MultiWidget):
    """
    Builds the inputs for a translatable field.

    The backend dumps all the available translations into a set of widgets
    wrapped in div.trans and javascript handles the rest of the UI.
    """
    choices = None  # Django expects widgets to have a choices attribute.

    def __init__(self, attrs=None):
        # We set up the widgets in render since every Translation needs a
        # different number of widgets.
        super(TransMulti, self).__init__(widgets=[], attrs=attrs)

    def render(self, name, value, attrs=None):
        self.name = name
        value = self.decompress(value)
        if value:
            self.widgets = [self.widget() for ignored in value]
        else:
            # Give an empty widget in the current locale.
            self.widgets = [self.widget()]
            value = [Translation(locale=translation_utils.get_language())]
        return super(TransMulti, self).render(name, value, attrs)

    def decompress(self, value):
        if not value:
            return []
        elif isinstance(value, (long, int)):
            # We got a foreign key to the translation table.
            qs = Translation.objects.filter(id=value)
            return list(qs.filter(localized_string__isnull=False))
        elif isinstance(value, dict):
            # We're getting a datadict, there was a validation error.
            return [Translation(locale=k, localized_string=v)
                    for k, v in value.items()]

    def value_from_datadict(self, data, files, name):
        # All the translations for this field are called {name}_{locale}, so
        # pull out everything that starts with name.
        rv = {}
        prefix = '%s_' % name
        locale = lambda s: s[len(prefix):]
        delete_locale = lambda s: s[len(prefix):-len('_delete')]
        # Look for the name without a locale suffix.
        if name in data:
            rv[translation_utils.get_language()] = data[name]
        # Now look for {name}_{locale}.
        for key in data:
            if key.startswith(prefix):
                if key.endswith('_delete'):
                    rv[delete_locale(key)] = None
                else:
                    rv[locale(key)] = data[key]
        return rv

    def format_output(self, widgets):
        s = super(TransMulti, self).format_output(widgets)
        init = self.widget().render(self.name + '_',
                                    Translation(locale='init'),
                                    {'class': 'trans-init'})
        return '<div id="trans-%s" class="trans" data-name="%s">%s%s</div>' % (
            self.name, self.name, s, init)


class _TransWidget(object):
    """
    Widget mixin that adds a Translation locale to the lang attribute and the
    input name.
    """

    def render(self, name, value, attrs=None):
        from .fields import switch
        attrs = self.build_attrs(attrs)
        lang = to_language(value.locale)
        attrs.update(lang=lang)
        # Use rsplit to drop django's name_idx numbering.  (name_0 => name)
        name = '%s_%s' % (name.rsplit('_', 1)[0], lang)
        # Make sure we don't get a Linkified/Purified Translation. We don't
        # want people editing a bleached value.
        if value.__class__ != Translation:
            value = switch(value, Translation)
        return super(_TransWidget, self).render(name, value, attrs)


# TransInput and TransTextarea are MultiWidgets that know how to set up our
# special translation attributes.
class TransInput(TransMulti):
    widget = type('_TextInput', (_TransWidget, forms.widgets.TextInput), {})


class TransTextarea(TransMulti):
    widget = type('_Textarea', (_TransWidget, forms.widgets.Textarea), {})

class EmailWidget(Input):
    """HTML5 email type."""
    input_type = 'email'

    def __init__(self, *args, **kwargs):
        self.placeholder = kwargs.pop('placeholder', None)
        return super(EmailWidget, self).__init__(*args, **kwargs)

    def render(self, name, value, attrs=None):
        attrs = attrs or {}
        if self.placeholder:
            attrs['placeholder'] = self.placeholder
        return super(EmailWidget, self).render(name, value, attrs)


class ColorWidget(Input):
    """HTML5 color type."""
    input_type = 'color'

    def __init__(self, *args, **kwargs):
        self.placeholder = kwargs.pop('placeholder', None)
        return super(ColorWidget, self).__init__(*args, **kwargs)

    def render(self, name, value, attrs=None):
        attrs = attrs or {}
        if self.placeholder:
            attrs['placeholder'] = self.placeholder
        return super(ColorWidget, self).render(name, value, attrs)


class TranslatedField(models.ForeignKey):
    """
    A foreign key to the translations table.

    If require_locale=False, the fallback join will not use a locale.  Instead,
    we will look for 1) a translation in the current locale and 2) fallback
    with any translation matching the foreign key.
    """
    to = Translation

    def __init__(self, **kwargs):
        # to_field: The field on the related object that the relation is to.
        # Django wants to default to translations.autoid, but we need id.
        options = dict(null=True, to_field='id', unique=True, blank=True)
        kwargs.update(options)
        self.short = kwargs.pop('short', True)
        self.require_locale = kwargs.pop('require_locale', True)
        super(TranslatedField, self).__init__(self.to, **kwargs)

    @property
    def db_column(self):
        # Django wants to call the db_column ('%s_id' % self.name), but our
        # translations foreign keys aren't set up that way.
        return self._db_column if hasattr(self, '_db_column') else self.name

    @db_column.setter
    def db_column(self, value):
        # Django sets db_column=None to initialize it.  I don't think anyone
        # would set the db_column otherwise.
        if value is not None:
            self._db_column = value

    def contribute_to_class(self, cls, name):
        """Add this Translation to ``cls._meta.translated_fields``."""
        super(TranslatedField, self).contribute_to_class(cls, name)

        # Add self to the list of translated fields.
        if hasattr(cls._meta, 'translated_fields'):
            cls._meta.translated_fields.append(self)
        else:
            cls._meta.translated_fields = [self]

        # Set up a unique related name.  The + means it's hidden.
        self.rel.related_name = '%s_%s_set+' % (cls.__name__, name)

        # Replace the normal descriptor with our custom descriptor.
        setattr(cls, self.name, TranslationDescriptor(self))

    def formfield(self, **kw):
        widget = TransInput if self.short else TransTextarea
        defaults = {'form_class': TransField, 'widget': widget}
        defaults.update(kw)
        return super(TranslatedField, self).formfield(**defaults)

    def validate(self, value, model_instance):
        # Skip ForeignKey.validate since that expects only one Translation when
        # doing .get(id=id)
        return models.Field.validate(self, value, model_instance)


class PurifiedField(TranslatedField):
    to = PurifiedTranslation


class LinkifiedField(TranslatedField):
    to = LinkifiedTranslation


def switch(obj, new_model):
    """Switch between Translation and Purified/Linkified Translations."""
    fields = [(f.name, getattr(obj, f.name)) for f in new_model._meta.fields]
    return new_model(**dict(fields))


def save_on_signal(obj, trans):
    """Connect signals so the translation gets saved during obj.save()."""
    signal = models.signals.pre_save

    def cb(sender, instance, **kw):
        if instance is obj:
            is_new = trans.autoid is None
            trans.save(force_insert=is_new, force_update=not is_new)
            signal.disconnect(cb)
    signal.connect(cb, sender=obj.__class__, weak=False)


class TranslationDescriptor(related.ReverseSingleRelatedObjectDescriptor):
    """
    Descriptor that handles creating and updating Translations given strings.
    """

    def __init__(self, field):
        super(TranslationDescriptor, self).__init__(field)
        self.model = field.rel.to

    def __get__(self, instance, instance_type=None):
        if instance is None:
            return self

        # If Django doesn't find find the value in the cache (which would only
        # happen if the field was set or accessed already), it does a db query
        # to follow the foreign key.  We expect translations to be set by
        # queryset transforms, so doing a query is the wrong thing here.
        try:
            return getattr(instance, self.field.get_cache_name())
        except AttributeError:
            return None

    def __set__(self, instance, value):
        lang = translation_utils.get_language()
        if isinstance(value, basestring):
            value = self.translation_from_string(instance, lang, value)
        elif hasattr(value, 'items'):
            value = self.translation_from_dict(instance, lang, value)

        # Don't let this be set to None, because Django will then blank out the
        # foreign key for this object.  That's incorrect for translations.
        if value is not None:
            # We always get these back from the database as Translations, but
            # we may want them to be a more specific Purified/Linkified child
            # class.
            if not isinstance(value, self.model):
                value = switch(value, self.model)
            super(TranslationDescriptor, self).__set__(instance, value)
        elif getattr(instance, self.field.attname, None) is None:
            super(TranslationDescriptor, self).__set__(instance, None)


    def translation_from_string(self, instance, lang, string):
        """Create, save, and return a Translation from a string."""
        try:
            trans = getattr(instance, self.field.name)
            trans_id = getattr(instance, self.field.attname)
            if trans is None and trans_id is not None:
                # This locale doesn't have a translation set, but there are
                # translations in another locale, so we have an id already.
                translation = self.model.new(string, lang, id=trans_id)
            elif to_language(trans.locale) == lang.lower():
                # Replace the translation in the current language.
                trans.localized_string = string
                translation = trans
            else:
                # We already have a translation in a different language.
                translation = self.model.new(string, lang, id=trans.id)
        except AttributeError:
            # Create a brand new translation.
            translation = self.model.new(string, lang)
        save_on_signal(instance, translation)
        return translation

    def translation_from_dict(self, instance, lang, dict_):
        """
        Create Translations from a {'locale': 'string'} mapping.

        If one of the locales matches lang, that Translation will be returned.
        """
        rv = None
        for locale, string in dict_.items():
            if locale.lower() not in settings.LANGUAGES:
                continue
            # The Translation is created and saved in here.
            trans = self.translation_from_string(instance, locale, string)

            # Set the Translation on the object because translation_from_string
            # doesn't expect Translations to be created but not attached.
            self.__set__(instance, trans)

            # If we're setting the current locale, set it to the object so
            # callers see the expected effect.
            if to_language(locale) == lang:
                rv = trans
        return rv


class _TransField(object):

    def __init__(self, *args, **kwargs):
        self.default_locale = settings.LANGUAGE_CODE
        for k in ('queryset', 'to_field_name'):
            if k in kwargs:
                del kwargs[k]
        self.widget = kwargs.pop('widget', TransInput)
        super(_TransField, self).__init__(*args, **kwargs)

    def clean(self, value):
        errors = LocaleList()

        value = dict((k, v.strip() if v else v) for (k, v) in value.items())

        # Raise an exception if the default locale is required and not present
        if self.default_locale.lower() not in value:
            value[self.default_locale.lower()] = None

        # Now, loop through them and validate them separately.
        for locale, val in value.items():
            try:
                # Only the default locale can be required; all non-default
                # fields are automatically optional.
                if self.default_locale.lower() == locale:
                    super(_TransField, self).validate(val)
                super(_TransField, self).run_validators(val)
            except forms.ValidationError, e:
                errors.extend(e.messages, locale)

        if errors:
            raise LocaleValidationError(errors)

        return value


class LocaleValidationError(forms.ValidationError):

    def __init__(self, messages, code=None, params=None):
        self.messages = messages


class TransField(_TransField, forms.CharField):
    """
    A CharField subclass that can deal with multiple locales.

    Most validators are run over the data for each locale.  The required
    validator is only run on the default_locale, which is hooked up to the
    instance with TranslationFormMixin.
    """

    @staticmethod
    def adapt(cls, opts={}):
        """Get a new TransField that subclasses cls instead of CharField."""
        return type('Trans%s' % cls.__name__, (_TransField, cls), opts)


# Subclass list so that isinstance(list) in Django works.
class LocaleList(dict):
    """
    List-like objects that maps list elements to a locale.

    >>> LocaleList([1, 2], 'en')
    [1, 2]
    ['en', 'en']

    This is useful for validation error lists where we want to associate an
    error with a locale.
    """

    def __init__(self, seq=None, locale=None):
        self.seq, self.locales = [], []
        if seq:
            assert seq and locale
            self.extend(seq, locale)

    def __iter__(self):
        return iter(self.zip())

    def extend(self, seq, locale):
        self.seq.extend(seq)
        self.locales.extend([locale] * len(seq))

    def __nonzero__(self):
        return bool(self.seq)

    def __contains__(self, item):
        return item in self.seq

    def zip(self):
        return zip(self.locales, self.seq)


class DecimalCharField(models.DecimalField):
    """Like the standard django DecimalField but stored in a varchar

    In order to gracefully read crappy data, use nullify_invalid=True.
    This will set the field's value to None rather than raising an exception
    whenever a non-null, non-decimal string is read from a queryset.

    However, use this option with caution as it also prevents exceptions
    from being raised during model property assignment. This could allow you
    to "successfuly" save a ton of data when all that is really written
    is NULL. It might be best to combine this with the null=False option.
    """

    description = 'Decimal number stored as a varchar'
    __metaclass__ = models.SubfieldBase

    def __init__(self, verbose_name=None, name=None, max_digits=None,
            decimal_places=None, nullify_invalid=False, **kwargs):
        self.nullify_invalid = nullify_invalid
        kwargs['max_length'] = max_digits + 1
        super(DecimalCharField, self).__init__(verbose_name, name,
            max_digits=max_digits, decimal_places=decimal_places, **kwargs)

    def get_internal_type(self):
        return "CharField"

    def to_python(self, value):
        try:
            return super(DecimalCharField, self).to_python(value)
        except exceptions.ValidationError:
            if self.nullify_invalid:
                return None
            else:
                raise

    def get_db_prep_save(self, value, connection, prepared=False):
        if prepared:
            return value
        else:
            return self.get_prep_value(value)

    def get_prep_value(self, value):
        if value is None:
            return value
        return self.format_number(value)


class ColorField(fields.CharField):

    widget = ColorWidget

    def __init__(self, max_length=7, min_length=None, *args, **kwargs):
        super(ColorField, self).__init__(max_length, min_length, *args,
                                         **kwargs)

    def clean(self, value):
        super(ColorField, self).clean(value)
        if value and not re.match('^\#([0-9a-fA-F]{6})$', value):
            raise exceptions.ValidationError(
                _(u'This must be a valid hex color code, such as #000000.'))
        return value
