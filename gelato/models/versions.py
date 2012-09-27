from django.db import models
from gelato.translations.fields import PurifiedField
from gelato.models.base import ModelBase

class Version(ModelBase):
    addon = models.ForeignKey('addons.Addon', related_name='versions')
    license = models.ForeignKey('License', null=True)
    releasenotes = PurifiedField()
    approvalnotes = models.TextField(default='', null=True)
    version = models.CharField(max_length=255, default='0.1')
    version_int = models.BigIntegerField(null=True, editable=False)

    nomination = models.DateTimeField(null=True)
    reviewed = models.DateTimeField(null=True)

    has_info_request = models.BooleanField(default=False)
    has_editor_comment = models.BooleanField(default=False)

    class Meta(ModelBase.Meta):
        db_table = 'versions'
        ordering = ['-created', '-modified']
        app_label = 'versions'
