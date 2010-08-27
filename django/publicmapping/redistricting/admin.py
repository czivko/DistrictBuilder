"""
Configure the appearance of the redistricting admin interface.

The classes in redistricting.admin assist the Django framework's 
administrative interface in presenting the models. The classes contained
within change the default behavior of the administrative to make maintenance
of models easier.

This file is part of The Public Mapping Project
http://sourceforge.net/projects/publicmapping/

License:
    Copyright 2010 Micah Altman, Michael McDonald

    Licensed under the Apache License, Version 2.0 (the "License");
    you may not use this file except in compliance with the License.
    You may obtain a copy of the License at

        http://www.apache.org/licenses/LICENSE-2.0

    Unless required by applicable law or agreed to in writing, software
    distributed under the License is distributed on an "AS IS" BASIS,
    WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
    See the License for the specific language governing permissions and
    limitations under the License.

Author: 
    David Zwarg, Andrew Jennings
"""

from publicmapping.redistricting.models import *
from django.contrib.gis import admin

class CharacteristicAdmin(admin.ModelAdmin):
    """
    Administrative settings for Characteristics of a Geounit.

    A Geounit's characteristic is a measurement of the Geounit, such as
    'total population', or 'percent with a high school diploma'.
    """

    # When displayed as a list, show these fields in columns.
    list_display = ('subject','geounit','number',)
    
    # Don't try to lookup the relationships to geounits, just list their
    # IDs
    raw_id_fields = ('geounit',)

class CharacteristicInline(admin.TabularInline):
    """
    Administrative setting for inline displays of Characteristics.

    Characteristics are displayed inline when viewing Geounits. This class
    defines the model that should be used in the inline display.
    """

    # The model that this inline class is displaying.
    model = Characteristic

class GeounitAdmin(admin.OSMGeoAdmin):
    """
    Administrative setting for Geounits.

    Geounits are the units of geography in the redistricting app. Each 
    Geounit can have zero or more Characteristics, with one Characteristic
    per Subject.

    This class controls the display of an OpenStreetMap slippy map for the
    geometry fields in the Geounit model.
    """

    # Display the Characteristics of this Geounit inline.
    inlines = [CharacteristicInline]

    # When displayed as a list, show the name and geolevel
    list_display = ('name','geolevel',)

    # In admin view, show the name, geolevel, and geom fields.
    fields = ('name','geolevel','geom',)

    # Order geounits by name by default.
    ordering = ('name',)

class DistrictInline(admin.TabularInline):
    """
    Administrative setting for inline displays of Districts.

    Districts are displayed inline when viewing plans. This class
    defines the model that should be used in the inline display, as well
    as the fields of that model that are editable inline.
    """

    # The fields that are editable inline.
    fields = ('district_id','name','version',)

    # The model that this inline class is displaying.
    model = District

class DistrictAdmin(admin.OSMGeoAdmin):
    """
    Administrative setting for Districts.

    Districts are composite sets of geometry that are built out of Geounits.
    Each district aggregates the Characteristics of the Geounits that are
    contained within in, and stores those results in ComputedCharacteristic
    models.

    This class controls the display of an OpenStreetMap slippy map for the
    geometry fields in the District model.
    """

    # In admin view, show the district_id, name, plan, version, and geom
    # fields.
    fields = ('district_id','name','plan','version','geom',)

    # When displayed as a list, show the name, plan, and version.
    list_display = ('name','plan','version',)

    # Enable filtering by plan and version in the admin list view.
    list_filter = ('plan','version',)

    # Order Districts by name by default.
    ordering = ('name',)

class PlanAdmin(admin.ModelAdmin):
    """
    Administrative setting for Plans.

    Plans are collections of Districts. Admin views of plans display all
    the districts that are in the plan.
    """

    # Display the Districts of this Plan inline.
    inlines = [DistrictInline]

    # When displayed as a list, show the name, is_template, is_shared,
    # owner, created, edited flags.
    list_display = ('name','is_template','is_shared','owner','created','edited',)

    # Enable filtering by the template and shared flags.
    list_filter = ('is_template','is_shared',)

    # Order Plans by name by default.
    ordering = ('name',)

class SubjectAdmin(admin.ModelAdmin):
    """
    Administrative setting for Subjects.

    Subjects are the names of attributes of Geounits. Each Geounit has one
    Characteristic per Subject.
    """

    # When displayed as a list, show the display name, the short display,
    # and a flag indicating if it should be displayed (in the app).
    list_display = ('display', 'short_display', 'is_displayed',)

    # Enable filtering by the displayed flag
    list_filter = ('is_displayed',)

# Register these classes with the admin interface.
admin.site.register(Geounit, GeounitAdmin)
admin.site.register(ComputedCharacteristic) 
admin.site.register(Characteristic, CharacteristicAdmin)
admin.site.register(Subject, SubjectAdmin)
admin.site.register(Geolevel)
admin.site.register(Plan, PlanAdmin)
admin.site.register(District, DistrictAdmin)
admin.site.register(Target)
