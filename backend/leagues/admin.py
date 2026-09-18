from django.contrib import admin

from .models import League, LeagueMembership


class LeagueMembershipInline(admin.TabularInline):
    model = LeagueMembership
    extra = 0


@admin.register(League)
class LeagueAdmin(admin.ModelAdmin):
    list_display = ("name", "public_id", "code", "is_public", "max_members", "owner", "created_at")
    list_filter = ("is_public",)
    search_fields = ("name", "code", "public_id", "owner__username", "owner__email")
    inlines = [LeagueMembershipInline]
