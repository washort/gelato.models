import collections

from django.conf import settings
from django.db import models
from django.utils.translation import trans_real as translation
from jinja2.filters import do_dictsort

from tower import ugettext_lazy as _
from gelato.translations.fields import (LinkifiedField, TranslatedField,
                                        PurifiedField)
from gelato.models.fields import DecimalCharField
from gelato.models.base import OnChangeMixin, ModelBase
from gelato.models.versions import Version

from gelato.constants import base


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

    authors = models.ManyToManyField('users.UserProfile', through='AddonUser',
                                     related_name='addons')
    categories = models.ManyToManyField('Category', through='AddonCategory')
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

    _current_version = models.ForeignKey(Version, related_name='___ignore',
            db_column='current_version', null=True, on_delete=models.SET_NULL)
    # This is for Firefox only.
    _backup_version = models.ForeignKey(Version, related_name='___backup',
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
        # Return a Webapp instead of an Addon if the `type` column says this is
        # really a webapp.
        try:
            type_idx = Addon._meta._type_idx
        except AttributeError:
            type_idx = (idx for idx, f in enumerate(Addon._meta.fields)
                        if f.attname == 'type').next()
            Addon._meta._type_idx = type_idx
        if ((len(args) == len(Addon._meta.fields)
             and args[type_idx] == base.ADDON_WEBAPP)
            or kw and kw.get('type') == base.ADDON_WEBAPP):
            from gelato.models.webapp import Webapp
            cls = Webapp
        return super(Addon, cls).__new__(cls, *args, **kw)

    def __unicode__(self):
        return u'%s: %s' % (self.id, self.name)

    def __init__(self, *args, **kw):
        super(Addon, self).__init__(*args, **kw)
        self._first_category = {}

    def save(self, **kw):
        self.clean_slug()
        super(Addon, self).save(**kw)
