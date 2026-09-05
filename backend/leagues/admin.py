from django.contrib import admin

from .models import League, LeagueMembership


class LeagueMembershipInline(admin.TabularInline):
    model = LeagueMembership
    extra = 0


@admin.register(League)
class LeagueAdmin(admin.ModelAdmin):
    list_display = ("name", "code", "owner", "created_at")
    search_fields = ("name", "code")
    inlines = [LeagueMembershipInline]
