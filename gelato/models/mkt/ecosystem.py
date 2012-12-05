from django.db import models

from gelato.models.base import ModelBase


class MdnCache(ModelBase):

    name = models.CharField(max_length=255)
    title = models.CharField(max_length=255, default='', blank=True)
    toc = models.TextField(blank=True)
    content = models.TextField(blank=True)
    permalink = models.CharField(max_length=255, default='', blank=True)
    locale = models.CharField(max_length=10, default='en', blank=False)

    class Meta:
        app_label = 'ecosystem'
        db_table = 'mdn_cache'
        unique_together = ('name', 'locale')

    def __unicode__(self):
        return self.title
