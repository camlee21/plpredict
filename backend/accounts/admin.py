from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin

from .models import User


@admin.register(User)
class UserAdmin(DjangoUserAdmin):
    list_display = ("username", "email", "is_active", "is_staff", "signed_in_with_google", "date_joined")
    list_filter = ("is_active", "is_staff", "is_superuser")
    search_fields = ("username", "email", "first_name", "last_name")
    ordering = ("-date_joined",)
    actions = ["deactivate_users", "activate_users"]

    fieldsets = DjangoUserAdmin.fieldsets + (
        ("Google sign-in", {"fields": ("google_sub",)}),
    )
    readonly_fields = ("google_sub",)

    @admin.display(boolean=True, description="Via Google")
    def signed_in_with_google(self, obj):
        return bool(obj.google_sub)

    @admin.action(description="Deactivate selected users (revokes login access)")
    def deactivate_users(self, request, queryset):
        updated = queryset.exclude(pk=request.user.pk).update(is_active=False)
        self.message_user(request, f"Deactivated {updated} user(s).")

    @admin.action(description="Re-activate selected users")
    def activate_users(self, request, queryset):
        updated = queryset.update(is_active=True)
        self.message_user(request, f"Activated {updated} user(s).")
