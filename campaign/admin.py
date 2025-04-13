from django.contrib import admin
from .models import User, Campaign, Region, Place, ThematicArea, Activity, ImplementationStatus
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

class UserAdmin(BaseUserAdmin):
    fieldsets = BaseUserAdmin.fieldsets + (
        (None, {'fields': ('role', 'region', 'phone_number')}),
    )

admin.site.register(User, UserAdmin)
admin.site.register(Campaign)
admin.site.register(Region)
admin.site.register(Place)
admin.site.register(ThematicArea)
admin.site.register(Activity)
admin.site.register(ImplementationStatus)
