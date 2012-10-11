from django.db import models

from gelato.constants.applications import APPS_ALL
from gelato.models.base import ModelBase


class Application(ModelBase):

    guid = models.CharField(max_length=255, default='')
    supported = models.BooleanField(default=1)
    # We never reference these translated fields, so stop loading them.
    # name = TranslatedField()
    # shortname = TranslatedField()

    class Meta:
        db_table = 'applications'
        app_label = 'applications'

    def __unicode__(self):
        return unicode(APPS_ALL[self.id].pretty)


class AppVersion(ModelBase):

    application = models.ForeignKey(Application)
    version = models.CharField(max_length=255, default='')
    version_int = models.BigIntegerField(editable=False)

    class Meta:
        db_table = 'appversions'
        ordering = ['-version_int']
        app_label = 'applications'

    def save(self, *args, **kw):
        from gelato.models.versions import version_int
        if not self.version_int:
            self.version_int = version_int(self.version)
        return super(AppVersion, self).save(*args, **kw)

    def __init__(self, *args, **kwargs):
        from gelato.models.versions import version_dict
        super(AppVersion, self).__init__(*args, **kwargs)
        # Add all the major, minor, ..., version attributes to the object.
        self.__dict__.update(version_dict(self.version or ''))

    def __unicode__(self):
        return self.version

    def flush_urls(self):
        return ['*/pages/appversions/*']
