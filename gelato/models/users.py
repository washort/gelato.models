from base64 import decodestring
from datetime import datetime
import hashlib

from django.contrib.auth.models import User as DjangoUser
from django.core import validators, urlresolvers
from django import forms
from django.utils.encoding import smart_str, smart_unicode
from django.utils.functional import lazy
from django.db import models
from tower import ugettext as _
from gelato.models.base import ModelBase, OnChangeMixin
from gelato.translations.fields import PurifiedField
from gelato.constants.base import LOGIN_SOURCE_UNKNOWN, LOGIN_SOURCE_BROWSERIDS


def get_hexdigest(algorithm, salt, raw_password):
    if 'base64' in algorithm:
        # These are getpersonas passwords with base64 encoded salts.
        salt = decodestring(salt)
        algorithm = algorithm.replace('+base64', '')

    if algorithm.startswith('sha512+MD5'):
        # These are persona specific passwords when we imported
        # users from getpersonas.com. The password is md5 hashed
        # and then sha512'd.
        md5 = hashlib.new('md5', raw_password).hexdigest()
        return hashlib.new('sha512', smart_str(salt + md5)).hexdigest()

    return hashlib.new(algorithm, smart_str(salt + raw_password)).hexdigest()


class UserProfileBase(OnChangeMixin, ModelBase):
    username = models.CharField(max_length=255, default='', unique=True)
    display_name = models.CharField(max_length=255, default='', null=True,
                                    blank=True)

    password = models.CharField(max_length=255, default='')
    email = models.EmailField(unique=True, null=True)

    averagerating = models.CharField(max_length=255, blank=True, null=True)
    bio = PurifiedField(short=False)
    confirmationcode = models.CharField(max_length=255, default='',
                                        blank=True)
    deleted = models.BooleanField(default=False)
    display_collections = models.BooleanField(default=False)
    display_collections_fav = models.BooleanField(default=False)
    emailhidden = models.BooleanField(default=True)
    homepage = models.URLField(max_length=255, blank=True, default='',
                               verify_exists=False)
    location = models.CharField(max_length=255, blank=True, default='')
    notes = models.TextField(blank=True, null=True)
    notifycompat = models.BooleanField(default=True)
    notifyevents = models.BooleanField(default=True)
    occupation = models.CharField(max_length=255, default='', blank=True)
    # This is essentially a "has_picture" flag right now
    picture_type = models.CharField(max_length=75, default='', blank=True)
    resetcode = models.CharField(max_length=255, default='', blank=True)
    resetcode_expires = models.DateTimeField(default=datetime.now, null=True,
                                             blank=True)
    read_dev_agreement = models.DateTimeField(null=True, blank=True)

    last_login_ip = models.CharField(default='', max_length=45, editable=False)
    last_login_attempt = models.DateTimeField(null=True, editable=False)
    last_login_attempt_ip = models.CharField(default='', max_length=45,
                                             editable=False)
    failed_login_attempts = models.PositiveIntegerField(default=0,
                                                        editable=False)
    source = models.PositiveIntegerField(default=LOGIN_SOURCE_UNKNOWN,
                                         editable=False)
    user = models.ForeignKey(DjangoUser, null=True, editable=False, blank=True)

    class Meta:
        db_table = 'users'
        app_label = 'users'

    def __init__(self, *args, **kw):
        super(UserProfileBase, self).__init__(*args, **kw)
        if self.username:
            self.username = smart_unicode(self.username)

    def __unicode__(self):
        return u'%s: %s' % (self.id, self.display_name or self.username)

    def is_anonymous(self):
        return False

    def check_password(self, raw_password):
        # BrowserID does not store a password.
        if self.source in LOGIN_SOURCE_BROWSERIDS:
            return True
        if '$' not in self.password:
            valid = (get_hexdigest('md5', '', raw_password) == self.password)
            if valid:
                # Upgrade an old password.
                self.set_password(raw_password)
                self.save()
            return valid

        algo, salt, hsh = self.password.split('$')
        return hsh == get_hexdigest(algo, salt, raw_password)


class UserEmailField(forms.EmailField):

    def clean(self, value):
        if value in validators.EMPTY_VALUES:
            raise forms.ValidationError(self.error_messages['required'])
        try:
            return UserProfileBase.objects.get(email=value)
        except UserProfileBase.DoesNotExist:
            raise forms.ValidationError(_('No user with that email.'))

    def widget_attrs(self, widget):
        lazy_reverse = lazy(urlresolvers.reverse, str)
        return {'class': 'email-autocomplete',
                'data-src': lazy_reverse('users.ajax')}


class UserForeignKey(models.ForeignKey):
    """
    A replacement for  models.ForeignKey('users.UserProfile').

    This field uses UserEmailField to make form fields key off the user's email
    instead of the primary key id.  We also hook up autocomplete automatically.
    """

    def __init__(self, *args, **kw):
        super(UserForeignKey, self).__init__(UserProfileBase, *args, **kw)

    def value_from_object(self, obj):
        return getattr(obj, self.name).email

    def formfield(self, **kw):
        defaults = {'form_class': UserEmailField}
        defaults.update(kw)
        return models.Field.formfield(self, **defaults)


class AmoUserBackend(object):
    supports_anonymous_user = False
    supports_object_permissions = False

    def authenticate(self, username=None, password=None):
        try:
            profile = UserProfileBase.objects.get(email=username)
            if profile.check_password(password):
                if profile.user_id is None:
                    profile.create_django_user()
                return profile.user
        except UserProfileBase.DoesNotExist:
            return None

    def get_user(self, user_id):
        try:
            return DjangoUser.objects.get(pk=user_id)
        except DjangoUser.DoesNotExist:
            return None


