import collections
import caching.base
from django.conf import settings
from django.core import urlresolvers
from django.db import models
from django.utils.translation import trans_real as translation
from jinja2.filters import do_dictsort

from tower import ugettext_lazy as _
from gelato.constants import base
from gelato.translations.fields import (LinkifiedField, TranslatedField,
                                        PurifiedField)
from gelato.models.fields import DecimalCharField
from gelato.models.base import OnChangeMixin, ModelBase
from gelato.models.versions import VersionBase
from gelato.models.users import UserProfileBase, UserForeignKey
from gelato.models.utils import sorted_groupby



class AddonBase(OnChangeMixin, ModelBase):
    STATUS_CHOICES = base.STATUS_CHOICES.items()
    LOCALES = [(translation.to_locale(k).replace('_', '-'), v) for k, v in
               do_dictsort(settings.LANGUAGES)]

    guid = models.CharField(max_length=255, unique=True, null=True)
    slug = models.CharField(max_length=30, unique=True, null=True)
    # This column is only used for webapps, so they can have a slug namespace
    # separate from addons and personas.
    app_slug = models.CharField(max_length=30, unique=True, null=True)
    name = TranslatedField()
    default_locale = models.CharField(max_length=10,
                                      default=settings.LANGUAGE_CODE,
                                      db_column='defaultlocale')

    type = models.PositiveIntegerField(db_column='addontype_id')
    status = models.PositiveIntegerField(
        choices=STATUS_CHOICES, db_index=True, default=0)
    highest_status = models.PositiveIntegerField(
        choices=STATUS_CHOICES, default=0,
        help_text="An upper limit for what an author can change.",
        db_column='higheststatus')
    icon_type = models.CharField(max_length=25, blank=True,
                                 db_column='icontype')
    homepage = TranslatedField()
    support_email = TranslatedField(db_column='supportemail')
    support_url = TranslatedField(db_column='supporturl')
    description = PurifiedField(short=False)

    summary = LinkifiedField()
    developer_comments = PurifiedField(db_column='developercomments')
    eula = PurifiedField()
    privacy_policy = PurifiedField(db_column='privacypolicy')
    the_reason = PurifiedField()
    the_future = PurifiedField()

    average_rating = models.FloatField(max_length=255, default=0, null=True,
                                       db_column='averagerating')
    bayesian_rating = models.FloatField(default=0, db_index=True,
                                        db_column='bayesianrating')
    total_reviews = models.PositiveIntegerField(default=0,
                                                db_column='totalreviews')
    weekly_downloads = models.PositiveIntegerField(
            default=0, db_column='weeklydownloads', db_index=True)
    total_downloads = models.PositiveIntegerField(
            default=0, db_column='totaldownloads')
    hotness = models.FloatField(default=0, db_index=True)

    average_daily_downloads = models.PositiveIntegerField(default=0)
    average_daily_users = models.PositiveIntegerField(default=0)
    share_count = models.PositiveIntegerField(default=0, db_index=True,
                                              db_column='sharecount')
    last_updated = models.DateTimeField(db_index=True, null=True,
        help_text='Last time this add-on had a file/version update')
    ts_slowness = models.FloatField(db_index=True, null=True,
        help_text='How much slower this add-on makes browser ts tests. '
                  'Read as {addon.ts_slowness}% slower.')

    disabled_by_user = models.BooleanField(default=False, db_index=True,
                                           db_column='inactive')
    trusted = models.BooleanField(default=False)
    view_source = models.BooleanField(default=True, db_column='viewsource')
    public_stats = models.BooleanField(default=False, db_column='publicstats')
    prerelease = models.BooleanField(default=False)
    admin_review = models.BooleanField(default=False, db_column='adminreview')
    admin_review_type = models.PositiveIntegerField(
                                    choices=base.ADMIN_REVIEW_TYPES.items(),
                                    default=base.ADMIN_REVIEW_FULL)
    site_specific = models.BooleanField(default=False,
                                        db_column='sitespecific')
    external_software = models.BooleanField(default=False,
                                            db_column='externalsoftware')
    dev_agreement = models.BooleanField(default=False,
                            help_text="Has the dev agreement been signed?")
    auto_repackage = models.BooleanField(default=True,
        help_text='Automatically upgrade jetpack add-on to a new sdk version?')
    outstanding = models.BooleanField(default=False)

    nomination_message = models.TextField(null=True,
                                          db_column='nominationmessage')
    target_locale = models.CharField(
        max_length=255, db_index=True, blank=True, null=True,
        help_text="For dictionaries and language packs")
    locale_disambiguation = models.CharField(
        max_length=255, blank=True, null=True,
        help_text="For dictionaries and language packs")

    wants_contributions = models.BooleanField(default=False)
    paypal_id = models.CharField(max_length=255, blank=True)
    charity = models.ForeignKey('Charity', null=True)
    # TODO(jbalogh): remove nullify_invalid once remora dies.
    suggested_amount = DecimalCharField(
        max_digits=8, decimal_places=2, nullify_invalid=True, blank=True,
        null=True, help_text=_(u'Users have the option of contributing more '
                               'or less than this amount.'))

    total_contributions = DecimalCharField(max_digits=8, decimal_places=2,
                                           nullify_invalid=True, blank=True,
                                           null=True)

    annoying = models.PositiveIntegerField(
        choices=base.CONTRIB_CHOICES, default=0,
        help_text=_(u"Users will always be asked in the Add-ons"
                     " Manager (Firefox 4 and above)"))
    enable_thankyou = models.BooleanField(default=False,
        help_text="Should the thankyou note be sent to contributors?")
    thankyou_note = TranslatedField()

    get_satisfaction_company = models.CharField(max_length=255, blank=True,
                                                null=True)
    get_satisfaction_product = models.CharField(max_length=255, blank=True,
                                                null=True)

    authors = models.ManyToManyField(UserProfileBase, through='AddonUser',
                                     related_name='addons')
    categories = models.ManyToManyField('Category', through='AddonCategoryBase')
    dependencies = models.ManyToManyField('self', symmetrical=False,
                                          through='AddonDependency',
                                          related_name='addons')
    premium_type = models.PositiveIntegerField(
                                    choices=base.ADDON_PREMIUM_TYPES.items(),
                                    default=base.ADDON_FREE)
    manifest_url = models.URLField(max_length=255, blank=True, null=True,
                                   verify_exists=False)
    app_domain = models.CharField(max_length=255, blank=True, null=True,
                                  db_index=True)

    _current_version = models.ForeignKey(VersionBase, related_name='___ignore',
            db_column='current_version', null=True, on_delete=models.SET_NULL)
    # This is for Firefox only.
    _backup_version = models.ForeignKey(VersionBase, related_name='___backup',
            db_column='backup_version', null=True, on_delete=models.SET_NULL)
    _latest_version = None
    make_public = models.DateTimeField(null=True)
    mozilla_contact = models.EmailField()

    # Whether the app is packaged or not (aka hosted).
    is_packaged = models.BooleanField(default=False, db_index=True)

    # This gets overwritten in the transformer.
    share_counts = collections.defaultdict(int)

    class Meta:
        db_table = 'addons'
        app_label = 'addons'

    @staticmethod
    def __new__(cls, *args, **kw):
        # # Return a Webapp instead of an Addon if the `type` column says this is
        # # really a webapp.
        # try:
        #     type_idx = AddonBase._meta._type_idx
        # except AttributeError:
        #     type_idx = (idx for idx, f in enumerate(AddonBase._meta.fields)
        #                 if f.attname == 'type').next()
        #     AddonBase._meta._type_idx = type_idx
        # if ((len(args) == len(AddonBase._meta.fields)
        #      and args[type_idx] == base.ADDON_WEBAPP)
        #     or kw and kw.get('type') == base.ADDON_WEBAPP):
        #     from gelato.models.webapp import Webapp
        #     cls = Webapp
        return super(AddonBase, cls).__new__(cls, *args, **kw)

    def __unicode__(self):
        return u'%s: %s' % (self.id, self.name)

    def __init__(self, *args, **kw):
        super(AddonBase, self).__init__(*args, **kw)
        self._first_category = {}


    @property
    def premium(self):
        """
        Returns the premium object which will be gotten by the transformer,
        if its not there, try and get it. Will return None if there's nothing
        there.
        """
        if not hasattr(self, '_premium'):
            try:
                self._premium = self.addonpremium
            except AddonPremium.DoesNotExist:
                self._premium = None
        return self._premium

class Charity(ModelBase):
    name = models.CharField(max_length=255)
    url = models.URLField(verify_exists=False)
    paypal = models.CharField(max_length=255)

    class Meta:
        db_table = 'charities'
        app_label = 'addons'

class Category(ModelBase):
    name = TranslatedField()
    slug = models.SlugField(max_length=50, help_text='Used in Category URLs.')
    type = models.PositiveIntegerField(db_column='addontype_id',
                                       choices=do_dictsort(base.ADDON_TYPE))
    application = models.ForeignKey('applications.Application', null=True,
                                    blank=True)
    count = models.IntegerField('Addon count', default=0)
    weight = models.IntegerField(default=0,
        help_text='Category weight used in sort ordering')
    misc = models.BooleanField(default=False)

    addons = models.ManyToManyField(AddonBase, through='AddonCategoryBase')

    class Meta:
        db_table = 'categories'
        verbose_name_plural = 'Categories'
        app_label = 'addons'

    def __unicode__(self):
        return unicode(self.name)

    def flush_urls(self):
        urls = ['*%s' % self.get_url_path(), ]
        return urls

    def get_url_path(self):
        try:
            type = base.ADDON_SLUGS[self.type]
        except KeyError:
            type = base.ADDON_SLUGS[base.ADDON_EXTENSION]
        if settings.MARKETPLACE and self.type == base.ADDON_PERSONA:
            #TODO: (davor) this is a temp stub. Return category URL when done.
            return urlresolvers.reverse('themes.browse', args=[self.slug])
        return urlresolvers.reverse('browse.%s' % type, args=[self.slug])

    @staticmethod
    def transformer(addons):
        qs = (Category.uncached.filter(addons__in=addons)
              .extra(select={'addon_id': 'addons_categories.addon_id'}))
        cats = dict((addon_id, list(cs))
                    for addon_id, cs in sorted_groupby(qs, 'addon_id'))
        for addon in addons:
            addon.all_categories = cats.get(addon.id, [])

class AddonCategoryBase(caching.base.CachingMixin, models.Model):
    addon = models.ForeignKey(AddonBase)
    category = models.ForeignKey('Category')
    feature = models.BooleanField(default=False)
    feature_locales = models.CharField(max_length=255, default='', null=True)

    objects = caching.base.CachingManager()

    class Meta:
        db_table = 'addons_categories'
        unique_together = ('addon', 'category')
        app_label = 'addons'

    def flush_urls(self):
        urls = ['*/addon/%d/' % self.addon_id,
                '*%s' % self.category.get_url_path(), ]
        return urls

class AddonUser(caching.base.CachingMixin, models.Model):
    addon = models.ForeignKey(AddonBase)
    user = UserForeignKey()
    role = models.SmallIntegerField(default=base.AUTHOR_ROLE_OWNER,
                                    choices=base.AUTHOR_CHOICES)
    listed = models.BooleanField(_(u'Listed'), default=True)
    position = models.IntegerField(default=0)

    objects = caching.base.CachingManager()

    def __init__(self, *args, **kwargs):
        super(AddonUser, self).__init__(*args, **kwargs)
        self._original_role = self.role
        self._original_user_id = self.user_id

    class Meta:
        db_table = 'addons_users'
        app_label = 'addons'

    def flush_urls(self):
        return self.addon.flush_urls() + self.user.flush_urls()


class AddonDependency(models.Model):
    addon = models.ForeignKey(AddonBase,
                              related_name='addons_dependencies')
    dependent_addon = models.ForeignKey(AddonBase,
                                        related_name='dependent_on')

    class Meta:
        db_table = 'addons_dependencies'
        unique_together = ('addon', 'dependent_addon')
        app_label = 'addons'

