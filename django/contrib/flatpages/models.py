from django.core import validators
from django.db import models
from django.contrib.sites.models import Site
from django.utils.translation import ugettext_lazy as _

class FlatPage(models.Model):
    url = models.CharField(_('URL'), max_length=100, validator_list=[validators.isAlphaNumericURL], db_index=True,
        help_text=_("Example: '/about/contact/'. Make sure to have leading and trailing slashes."))
    title = models.CharField(_('title'), max_length=200)
    content = models.TextField(_('content'))
    enable_comments = models.BooleanField(_('enable comments'))
    template_name = models.CharField(_('template name'), max_length=70, blank=True,
        help_text=_("Example: 'flatpages/contact_page.html'. If this isn't provided, the system will use 'flatpages/default.html'."))
    registration_required = models.BooleanField(_('registration required'), help_text=_("If this is checked, only logged-in users will be able to view the page."))
    sites = models.ManyToManyField(Site)

    class Meta:
        db_table = 'django_flatpage'
        verbose_name = _('flat page')
        verbose_name_plural = _('flat pages')
        ordering = ('url',)

    def __unicode__(self):
        return u"%s -- %s" % (self.url, self.title)

    def get_absolute_url(self):
        return self.url

# Register the admin options for these models.
# TODO: Maybe this should live in a separate module admin.py, but how would we
# ensure that module was loaded?

from django.contrib import admin

class FlatPageAdmin(admin.ModelAdmin):
    fieldsets = (
        (None, {'fields': ('url', 'title', 'content', 'sites')}),
        ('Advanced options', {'classes': ('collapse',), 'fields': ('enable_comments', 'registration_required', 'template_name')}),
    )
    list_filter = ('sites',)
    search_fields = ('url', 'title')

admin.site.register(FlatPage, FlatPageAdmin)
