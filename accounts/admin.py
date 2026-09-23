from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin
from django.contrib.auth.forms import UserChangeForm, AdminUserCreationForm
from .models import User


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
