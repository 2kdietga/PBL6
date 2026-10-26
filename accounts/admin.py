from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin
from django.contrib.auth.forms import UserChangeForm, AdminUserCreationForm
from .models import User, DriverProfile, DriverLicense, FaceProfile


class UserCreationForm(AdminUserCreationForm):
    class Meta(AdminUserCreationForm.Meta):
        model = User
        fields = ('username', 'email', 'role')


class AccountChangeForm(UserChangeForm):
    class Meta(UserChangeForm.Meta):
        model = User
        fields = '__all__'


@admin.register(User)
class UserAdmin(DjangoUserAdmin):
    add_form = UserCreationForm
    form = AccountChangeForm
    fieldsets = DjangoUserAdmin.fieldsets + (('Vai trò ứng dụng', {'fields': ('role',)}),)
    add_fieldsets = DjangoUserAdmin.add_fieldsets + (('Thông tin', {'fields': ('email', 'role')}),)
    list_display = DjangoUserAdmin.list_display + ('role',)
    list_filter = DjangoUserAdmin.list_filter + ('role',)


@admin.register(DriverProfile)
class DriverProfileAdmin(admin.ModelAdmin):
    list_display = ('id', 'full_name', 'user', 'phone', 'approval_status')
    list_filter = ('approval_status',)
    search_fields = ('full_name', 'phone', 'user__username')
    autocomplete_fields = ('user',)
    readonly_fields = ('created_at', 'updated_at')
    list_select_related = ('user',)


@admin.register(DriverLicense)
class DriverLicenseAdmin(admin.ModelAdmin):
    list_display = ('license_number', 'driver', 'license_class', 'status', 'expiry_date')
    list_filter = ('status', 'license_class', 'license_standard')
    search_fields = ('license_number', 'driver__full_name')
    autocomplete_fields = ('driver',)
    readonly_fields = ('created_at', 'updated_at')
    list_select_related = ('driver',)


@admin.register(FaceProfile)
class FaceProfileAdmin(admin.ModelAdmin):
    list_display = ('id', 'driver', 'approval_status')
    list_filter = ('approval_status',)
    search_fields = ('driver__full_name',)
    autocomplete_fields = ('driver',)
    readonly_fields = ('created_at', 'updated_at')
    list_select_related = ('driver',)
