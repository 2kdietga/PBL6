from django.contrib import admin

from .models import VehicleType, Vehicle, Device, DriverVehicleAssignment


@admin.register(VehicleType)
class VehicleTypeAdmin(admin.ModelAdmin):
    list_display = ('name', 'category')
    list_filter = ('category',)
    search_fields = ('name',)
    readonly_fields = ('created_at', 'updated_at')


@admin.register(Vehicle)
class VehicleAdmin(admin.ModelAdmin):
    list_display = ('license_plate', 'vehicle_type', 'brand', 'status')
    list_filter = ('status', 'vehicle_type')
    search_fields = ('license_plate', 'brand', 'model')
    autocomplete_fields = ('vehicle_type',)
    readonly_fields = ('created_at', 'updated_at')
    list_select_related = ('vehicle_type',)


@admin.register(Device)
class DeviceAdmin(admin.ModelAdmin):
    list_display = ('device_code', 'name', 'vehicle', 'status', 'last_seen_at')
    list_filter = ('status',)
    search_fields = ('device_code', 'name', 'vehicle__license_plate')
    autocomplete_fields = ('vehicle',)
    readonly_fields = ('last_seen_at', 'created_at', 'updated_at')
    list_select_related = ('vehicle',)


@admin.register(DriverVehicleAssignment)
class DriverVehicleAssignmentAdmin(admin.ModelAdmin):
    list_display = ('id', 'driver', 'vehicle', 'start_at', 'end_at')
    search_fields = ('driver__full_name', 'vehicle__license_plate')
    autocomplete_fields = ('driver', 'vehicle')
    readonly_fields = ('created_at', 'updated_at')
    list_select_related = ('driver', 'vehicle')

    def get_readonly_fields(self, request, obj=None):
        fields = super().get_readonly_fields(request, obj)
        if obj and obj.driving_sessions.exists():
            return fields + ('driver', 'vehicle', 'start_at')
        return fields
